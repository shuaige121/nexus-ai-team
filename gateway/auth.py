"""Authentication middleware — bearer-token + optional JWT."""

from __future__ import annotations

import hmac
import logging
from typing import TYPE_CHECKING

from fastapi import Request, WebSocket
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.responses import Response

from gateway.config import settings

logger = logging.getLogger("gateway.auth")

# Paths that don't require auth
PUBLIC_PATHS: set[str] = {"/health", "/docs", "/openapi.json", "/redoc"}


def _is_public(path: str) -> bool:
    return path in PUBLIC_PATHS


def _verify_token(token: str) -> bool:
    """Timing-safe comparison of bearer token against API_SECRET."""
    if not settings.api_secret:
        # No secret configured → auth disabled (dev mode)
        return True
    return hmac.compare_digest(token.encode(), settings.api_secret.encode())


def extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


class AuthMiddleware(BaseHTTPMiddleware):
    """Reject requests without a valid bearer token (when API_SECRET is set)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if _is_public(request.url.path):
            return await call_next(request)

        token = extract_token(request.headers.get("authorization"))
        if not _verify_token(token or ""):
            logger.warning("Auth failed from %s on %s", request.client.host, request.url.path)
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        return await call_next(request)


async def verify_ws_token(websocket: WebSocket) -> bool:
    """Verify token for WebSocket connections (called during handshake)."""
    token = websocket.query_params.get("token") or extract_token(
        websocket.headers.get("authorization")
    )
    return _verify_token(token or "")
