"""Redis-backed sliding-window rate limiter with in-memory fallback."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING

import redis.asyncio as aioredis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import Request
    from starlette.responses import Response

from gateway.config import settings

logger = logging.getLogger(__name__)


class _InMemorySlidingWindow:
    """Fallback per-client sliding window counter (no Redis)."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]
        if len(self._hits[key]) >= self.max_requests:
            return False
        self._hits[key].append(now)
        return True

    def cleanup(self) -> None:
        now = time.monotonic()
        cutoff = now - self.window
        empty_keys = []
        for key, hits in self._hits.items():
            self._hits[key] = [t for t in hits if t > cutoff]
            if not self._hits[key]:
                empty_keys.append(key)
        for key in empty_keys:
            del self._hits[key]


class RedisSlidingWindow:
    """Redis sorted-set sliding window rate limiter."""

    KEY_PREFIX = "ratelimit:"

    def __init__(
        self, redis_client: aioredis.Redis, max_requests: int, window_seconds: int
    ) -> None:
        self._redis = redis_client
        self.max_requests = max_requests
        self.window = window_seconds
        self._fallback = _InMemorySlidingWindow(max_requests, window_seconds)
        self._using_fallback = False

    async def is_allowed(self, key: str) -> bool:
        try:
            return await self._check_redis(key)
        except (aioredis.RedisError, ConnectionError, OSError) as exc:
            if not self._using_fallback:
                logger.warning("Redis unavailable for rate limiting, falling back to in-memory: %s", exc)
                self._using_fallback = True
            return self._fallback.is_allowed(key)

    async def _check_redis(self, key: str) -> bool:
        redis_key = f"{self.KEY_PREFIX}{key}"
        now = time.time()
        cutoff = now - self.window

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(redis_key, "-inf", cutoff)
        pipe.zadd(redis_key, {str(now): now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, self.window + 1)
        results = await pipe.execute()

        count: int = results[2]
        if count > self.max_requests:
            await self._redis.zrem(redis_key, str(now))
            return False

        if self._using_fallback:
            logger.info("Redis connection restored for rate limiting")
            self._using_fallback = False
        return True

    async def cleanup(self) -> None:
        """Remove expired entries from all rate limit keys."""
        try:
            now = time.time()
            cutoff = now - self.window
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor, match=f"{self.KEY_PREFIX}*", count=100
                )
                for key in keys:
                    await self._redis.zremrangebyscore(key, "-inf", cutoff)
                if cursor == 0:
                    break
        except (aioredis.RedisError, ConnectionError, OSError) as exc:
            logger.warning("Redis cleanup failed: %s", exc)
        self._fallback.cleanup()


def _build_rate_limiter() -> RedisSlidingWindow:
    """Build the rate limiter with a Redis connection from settings."""
    redis_client = aioredis.from_url(
        settings.redis_url, decode_responses=True
    )
    return RedisSlidingWindow(
        redis_client=redis_client,
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )


_window = _build_rate_limiter()


class RateLimiterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        if not await _window.is_allowed(client_ip):
            return JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": str(settings.rate_limit_window_seconds)},
            )
        return await call_next(request)
