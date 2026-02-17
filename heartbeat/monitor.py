"""Health monitoring for NEXUS components.

Periodically checks:
- Gateway HTTP/WebSocket responsiveness
- Agent last activity times
- Redis/PostgreSQL connectivity
- GPU status (Ollama)
- Token budget usage
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import aiohttp
import psutil
import redis.asyncio as aioredis
from psycopg import AsyncConnection

logger = logging.getLogger("heartbeat.monitor")


@dataclass
class HealthStatus:
    """Health check result for a component."""

    component: str
    status: str  # "healthy" | "degraded" | "critical" | "unknown"
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: float = field(default_factory=time.time)

    def is_healthy(self) -> bool:
        return self.status == "healthy"

    def is_critical(self) -> bool:
        return self.status == "critical"

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "checked_at": self.checked_at,
        }


@dataclass
class SystemHealth:
    """Overall system health report."""

    timestamp: float
    gateway: HealthStatus
    redis: HealthStatus
    postgres: HealthStatus
    agents: HealthStatus
    gpu: HealthStatus
    budget: HealthStatus
    disk: HealthStatus

    def is_healthy(self) -> bool:
        """Returns True if all components are healthy."""
        return all(
            status.is_healthy()
            for status in [
                self.gateway,
                self.redis,
                self.postgres,
                self.agents,
                self.gpu,
                self.budget,
                self.disk,
            ]
        )

    def has_critical_issues(self) -> bool:
        """Returns True if any component is critical."""
        return any(
            status.is_critical()
            for status in [
                self.gateway,
                self.redis,
                self.postgres,
                self.agents,
                self.gpu,
                self.budget,
                self.disk,
            ]
        )

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "overall_status": "healthy" if self.is_healthy() else "unhealthy",
            "has_critical": self.has_critical_issues(),
            "components": {
                "gateway": self.gateway.to_dict(),
                "redis": self.redis.to_dict(),
                "postgres": self.postgres.to_dict(),
                "agents": self.agents.to_dict(),
                "gpu": self.gpu.to_dict(),
                "budget": self.budget.to_dict(),
                "disk": self.disk.to_dict(),
            },
        }


class HealthMonitor:
    """Monitors NEXUS system health periodically."""

    def __init__(
        self,
        gateway_url: str = "http://localhost:8000",
        redis_url: str = "redis://localhost:6379/0",
        postgres_url: str = "",
        ollama_url: str = "http://localhost:11434",
        check_interval: int = 30,  # seconds
        agent_timeout: int = 300,  # seconds (5 minutes)
        token_budget_limit: int = 1_000_000,  # tokens per day
    ):
        self.gateway_url = gateway_url
        self.redis_url = redis_url
        self.postgres_url = postgres_url
        self.ollama_url = ollama_url
        self.check_interval = check_interval
        self.agent_timeout = agent_timeout
        self.token_budget_limit = token_budget_limit

        self._running = False
        self._task: asyncio.Task | None = None
        self._last_health: SystemHealth | None = None

    async def start(self):
        """Start the health monitoring loop."""
        if self._running:
            logger.warning("Health monitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Health monitor started (interval=%ds)", self.check_interval)

    async def stop(self):
        """Stop the health monitoring loop."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                health = await self.check_health()
                self._last_health = health

                if not health.is_healthy():
                    logger.warning("System health degraded: %s", health.to_dict())
                else:
                    logger.debug("System health: OK")

            except Exception:
                logger.exception("Error during health check")

            await asyncio.sleep(self.check_interval)

    async def check_health(self) -> SystemHealth:
        """Perform all health checks and return system health."""
        logger.debug("Starting health checks")

        # Run all checks concurrently
        gateway_task = asyncio.create_task(self._check_gateway())
        redis_task = asyncio.create_task(self._check_redis())
        postgres_task = asyncio.create_task(self._check_postgres())
        agents_task = asyncio.create_task(self._check_agents())
        gpu_task = asyncio.create_task(self._check_gpu())
        budget_task = asyncio.create_task(self._check_budget())
        disk_task = asyncio.create_task(self._check_disk())

        results = await asyncio.gather(
            gateway_task,
            redis_task,
            postgres_task,
            agents_task,
            gpu_task,
            budget_task,
            disk_task,
            return_exceptions=True,
        )

        # Handle any exceptions
        gateway_status, redis_status, postgres_status, agents_status, gpu_status, budget_status, disk_status = [
            r
            if isinstance(r, HealthStatus)
            else HealthStatus(
                component="unknown",
                status="critical",
                message=f"Check failed: {r}",
            )
            for r in results
        ]

        return SystemHealth(
            timestamp=time.time(),
            gateway=gateway_status,
            redis=redis_status,
            postgres=postgres_status,
            agents=agents_status,
            gpu=gpu_status,
            budget=budget_status,
            disk=disk_status,
        )

    async def _check_gateway(self) -> HealthStatus:
        """Check if Gateway is responsive."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.gateway_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return HealthStatus(
                            component="gateway",
                            status="healthy",
                            message="Gateway responding",
                            details=data,
                        )
                    else:
                        return HealthStatus(
                            component="gateway",
                            status="degraded",
                            message=f"Gateway returned status {resp.status}",
                        )
        except asyncio.TimeoutError:
            return HealthStatus(
                component="gateway",
                status="critical",
                message="Gateway timeout",
            )
        except Exception as e:
            return HealthStatus(
                component="gateway",
                status="critical",
                message=f"Gateway unreachable: {e}",
            )

    async def _check_redis(self) -> HealthStatus:
        """Check Redis connectivity."""
        try:
            redis = await aioredis.from_url(self.redis_url, decode_responses=True)
            await redis.ping()
            info = await redis.info("memory")
            used_memory_mb = info.get("used_memory", 0) / 1024 / 1024
            await redis.close()

            return HealthStatus(
                component="redis",
                status="healthy",
                message="Redis connected",
                details={"used_memory_mb": round(used_memory_mb, 2)},
            )
        except Exception as e:
            return HealthStatus(
                component="redis",
                status="critical",
                message=f"Redis connection failed: {e}",
            )

    async def _check_postgres(self) -> HealthStatus:
        """Check PostgreSQL connectivity."""
        if not self.postgres_url:
            return HealthStatus(
                component="postgres",
                status="unknown",
                message="PostgreSQL URL not configured",
            )

        try:
            conn = await AsyncConnection.connect(self.postgres_url, autocommit=True)
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM work_orders")
                result = await cur.fetchone()
                work_order_count = result[0] if result else 0

            await conn.close()

            return HealthStatus(
                component="postgres",
                status="healthy",
                message="PostgreSQL connected",
                details={"work_orders": work_order_count},
            )
        except Exception as e:
            return HealthStatus(
                component="postgres",
                status="critical",
                message=f"PostgreSQL connection failed: {e}",
            )

    async def _check_agents(self) -> HealthStatus:
        """Check agent activity via work order timestamps."""
        if not self.postgres_url:
            return HealthStatus(
                component="agents",
                status="unknown",
                message="Cannot check agents without database",
            )

        try:
            conn = await AsyncConnection.connect(self.postgres_url, autocommit=True)
            async with conn.cursor() as cur:
                # Check for stale in-progress work orders
                await cur.execute(
                    """
                    SELECT COUNT(*) FROM work_orders
                    WHERE status = 'in_progress'
                    AND updated_at < NOW() - INTERVAL '%s seconds'
                    """,
                    (self.agent_timeout,),
                )
                result = await cur.fetchone()
                stale_count = result[0] if result else 0

            await conn.close()

            if stale_count > 0:
                return HealthStatus(
                    component="agents",
                    status="degraded",
                    message=f"{stale_count} agent(s) may be stuck",
                    details={"stale_work_orders": stale_count},
                )
            else:
                return HealthStatus(
                    component="agents",
                    status="healthy",
                    message="Agents active",
                )
        except Exception as e:
            return HealthStatus(
                component="agents",
                status="critical",
                message=f"Agent check failed: {e}",
            )

    async def _check_gpu(self) -> HealthStatus:
        """Check GPU/Ollama availability."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.ollama_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        model_count = len(data.get("models", []))
                        return HealthStatus(
                            component="gpu",
                            status="healthy",
                            message=f"Ollama available ({model_count} models)",
                            details={"model_count": model_count},
                        )
                    else:
                        return HealthStatus(
                            component="gpu",
                            status="degraded",
                            message="Ollama responded with error",
                        )
        except Exception:
            # GPU/Ollama is optional, not critical
            return HealthStatus(
                component="gpu",
                status="unknown",
                message="Ollama not available (optional)",
            )

    async def _check_budget(self) -> HealthStatus:
        """Check token budget usage."""
        if not self.postgres_url:
            return HealthStatus(
                component="budget",
                status="unknown",
                message="Cannot check budget without database",
            )

        try:
            conn = await AsyncConnection.connect(self.postgres_url, autocommit=True)
            async with conn.cursor() as cur:
                # Get today's token usage
                await cur.execute(
                    """
                    SELECT COALESCE(SUM(prompt_tokens + completion_tokens), 0)
                    FROM agent_metrics
                    WHERE created_at >= CURRENT_DATE
                    """
                )
                result = await cur.fetchone()
                tokens_used = result[0] if result else 0

            await conn.close()

            usage_pct = (tokens_used / self.token_budget_limit) * 100

            if usage_pct >= 100:
                status = "critical"
                message = "Token budget exceeded"
            elif usage_pct >= 80:
                status = "degraded"
                message = "Token budget nearly exhausted"
            else:
                status = "healthy"
                message = "Token budget OK"

            return HealthStatus(
                component="budget",
                status=status,
                message=message,
                details={
                    "tokens_used": tokens_used,
                    "tokens_limit": self.token_budget_limit,
                    "usage_pct": round(usage_pct, 1),
                },
            )
        except Exception as e:
            return HealthStatus(
                component="budget",
                status="critical",
                message=f"Budget check failed: {e}",
            )

    async def _check_disk(self) -> HealthStatus:
        """Check disk usage."""
        try:
            disk_usage = psutil.disk_usage("/")
            usage_pct = disk_usage.percent

            if usage_pct >= 95:
                status = "critical"
                message = "Disk nearly full"
            elif usage_pct >= 85:
                status = "degraded"
                message = "Disk usage high"
            else:
                status = "healthy"
                message = "Disk usage OK"

            return HealthStatus(
                component="disk",
                status=status,
                message=message,
                details={
                    "used_gb": round(disk_usage.used / (1024**3), 2),
                    "total_gb": round(disk_usage.total / (1024**3), 2),
                    "usage_pct": usage_pct,
                },
            )
        except Exception as e:
            return HealthStatus(
                component="disk",
                status="critical",
                message=f"Disk check failed: {e}",
            )

    def get_last_health(self) -> SystemHealth | None:
        """Get the last health check result."""
        return self._last_health
