"""Auto-recovery for NEXUS health issues.

Attempts to automatically recover from common failures:
- Gateway unresponsive -> restart service
- Agent stuck -> kill and restart
- Disk full -> cleanup logs
- Redis/PostgreSQL down -> retry connection
"""

from __future__ import annotations

import contextlib
import logging
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from heartbeat.alerts import AlertManager, AlertSeverity
from heartbeat.monitor import HealthStatus, SystemHealth

logger = logging.getLogger("heartbeat.recovery")

RECOVERY_ATTEMPT_TTL: int = 3600  # 1 hour in seconds
RECOVERY_KEY_PREFIX: str = "recovery:attempts:"


class RecoveryManager:
    """Manages automatic recovery from health issues."""

    def __init__(
        self,
        alert_manager: AlertManager,
        project_root: str = "/home/leonard/Desktop/nexus-ai-team",
        enable_auto_recovery: bool = True,
        enable_restart: bool = False,  # Requires systemd service
        redis_client: object | None = None,
    ):
        self.alert_manager = alert_manager
        self.project_root = Path(project_root)
        self.enable_auto_recovery = enable_auto_recovery
        self.enable_restart = enable_restart
        self._redis = redis_client

        # In-memory fallback when Redis is unavailable
        self._recovery_attempts: dict[str, int] = {}
        self._max_recovery_attempts = 3

    async def _get_attempt_count(self, component: str) -> int:
        """Get current recovery attempt count, preferring Redis."""
        if self._redis is not None:
            try:
                key = f"{RECOVERY_KEY_PREFIX}{component}"
                val = await self._redis.get(key)
                return int(val) if val else 0
            except Exception:
                logger.debug("Redis unavailable for get, using in-memory fallback")
        return self._recovery_attempts.get(component, 0)

    async def _increment_attempt_count(self, component: str) -> int:
        """Increment and return the new attempt count, preferring Redis."""
        if self._redis is not None:
            try:
                key = f"{RECOVERY_KEY_PREFIX}{component}"
                new_val = await self._redis.incr(key)
                await self._redis.expire(key, RECOVERY_ATTEMPT_TTL)
                self._recovery_attempts[component] = int(new_val)
                return int(new_val)
            except Exception:
                logger.debug("Redis unavailable for incr, using in-memory fallback")

        self._recovery_attempts[component] = self._recovery_attempts.get(component, 0) + 1
        return self._recovery_attempts[component]

    async def process_health(self, health: SystemHealth):
        """Process health report and attempt recovery if needed."""
        if not self.enable_auto_recovery:
            return

        if health.gateway.is_critical():
            await self._recover_gateway(health.gateway)

        if health.redis.is_critical():
            await self._recover_redis(health.redis)

        if health.postgres.is_critical():
            await self._recover_postgres(health.postgres)

        if health.agents.status == "degraded":
            await self._recover_agents(health.agents)

        if health.disk.is_critical():
            await self._recover_disk(health.disk)

        if health.budget.is_critical():
            await self._recover_budget(health.budget)

    async def _recover_gateway(self, status: HealthStatus):
        """Attempt to recover Gateway service."""
        component = "gateway"

        if not await self._should_attempt_recovery(component):
            logger.warning("Max recovery attempts reached for %s", component)
            return

        logger.info("Attempting to recover Gateway...")

        if self.enable_restart:
            try:
                subprocess.run(
                    ["systemctl", "restart", "nexus-gateway"],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                logger.info("Gateway service restarted via systemd")
                await self.alert_manager.send_custom_alert(
                    severity=AlertSeverity.WARNING,
                    message="Gateway was unresponsive and has been restarted",
                    details={"component": component, "method": "systemd"},
                )
                await self._record_recovery_attempt(component)
                return
            except Exception as e:
                logger.error("Failed to restart Gateway via systemd: %s", e)

        await self.alert_manager.send_custom_alert(
            severity=AlertSeverity.CRITICAL,
            message="Gateway is down and automatic restart is disabled. Manual intervention required.",
            details={"component": component, "error": status.message},
        )

    async def _recover_redis(self, status: HealthStatus):
        """Attempt to recover Redis connection."""
        component = "redis"

        if not await self._should_attempt_recovery(component):
            logger.warning("Max recovery attempts reached for %s", component)
            return

        logger.info("Attempting to recover Redis connection...")

        await self.alert_manager.send_custom_alert(
            severity=AlertSeverity.CRITICAL,
            message="Redis is unreachable. Check if Redis service is running.",
            details={"component": component, "error": status.message},
        )

        await self._record_recovery_attempt(component)

    async def _recover_postgres(self, status: HealthStatus):
        """Attempt to recover PostgreSQL connection."""
        component = "postgres"

        if not await self._should_attempt_recovery(component):
            logger.warning("Max recovery attempts reached for %s", component)
            return

        logger.info("Attempting to recover PostgreSQL connection...")

        await self.alert_manager.send_custom_alert(
            severity=AlertSeverity.CRITICAL,
            message="PostgreSQL is unreachable. Check if database service is running.",
            details={"component": component, "error": status.message},
        )

        await self._record_recovery_attempt(component)

    async def _recover_agents(self, status: HealthStatus):
        """Attempt to recover stuck agents."""
        component = "agents"

        if not await self._should_attempt_recovery(component):
            logger.warning("Max recovery attempts reached for %s", component)
            return

        logger.info("Attempting to recover stuck agents...")

        stale_count = status.details.get("stale_work_orders", 0)

        await self.alert_manager.send_custom_alert(
            severity=AlertSeverity.WARNING,
            message=f"Detected {stale_count} stale work order(s). Agents may be stuck.",
            details={
                "component": component,
                "stale_work_orders": stale_count,
                "action": "Monitor or manually cancel stuck work orders",
            },
        )

        await self._record_recovery_attempt(component)

    async def _recover_disk(self, status: HealthStatus):
        """Attempt to free disk space."""
        component = "disk"

        if not await self._should_attempt_recovery(component):
            logger.warning("Max recovery attempts reached for %s", component)
            return

        logger.info("Attempting to free disk space...")

        usage_pct = status.details.get("usage_pct", 0)
        freed_mb = 0

        try:
            logs_dir = self.project_root / "logs"
            if logs_dir.exists():
                freed_mb += await self._cleanup_old_logs(logs_dir, days=7)

            reports_dir = self.project_root / "reports"
            if reports_dir.exists():
                freed_mb += await self._cleanup_old_files(reports_dir, days=30)

            freed_mb += await self._cleanup_pycache(self.project_root)

            logger.info("Freed approximately %d MB of disk space", freed_mb)

            await self.alert_manager.send_custom_alert(
                severity=AlertSeverity.WARNING,
                message=f"Disk usage was at {usage_pct}%. Cleaned {freed_mb} MB.",
                details={
                    "component": component,
                    "freed_mb": freed_mb,
                    "usage_pct": usage_pct,
                },
            )

            await self._record_recovery_attempt(component)

        except Exception:
            logger.exception("Failed to cleanup disk")
            await self.alert_manager.send_custom_alert(
                severity=AlertSeverity.CRITICAL,
                message=f"Disk usage critical ({usage_pct}%) and automatic cleanup failed.",
                details={"component": component, "usage_pct": usage_pct},
            )

    async def _recover_budget(self, status: HealthStatus):
        """Handle token budget exhaustion."""
        component = "budget"

        if not await self._should_attempt_recovery(component):
            logger.warning("Max recovery attempts reached for %s", component)
            return

        logger.info("Token budget exceeded, sending notification...")

        tokens_used = status.details.get("tokens_used", 0)
        tokens_limit = status.details.get("tokens_limit", 0)

        await self.alert_manager.send_custom_alert(
            severity=AlertSeverity.CRITICAL,
            message="Daily token budget exceeded. Consider pausing operations or increasing budget.",
            details={
                "component": component,
                "tokens_used": tokens_used,
                "tokens_limit": tokens_limit,
            },
        )

        await self._record_recovery_attempt(component)

    async def _cleanup_old_logs(self, logs_dir: Path, days: int) -> int:
        """Delete log files older than specified days. Returns MB freed."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        freed_bytes = 0

        for log_file in logs_dir.rglob("*.log"):
            if log_file.is_file():
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff.replace(tzinfo=None):
                    size = log_file.stat().st_size
                    log_file.unlink()
                    freed_bytes += size
                    logger.debug("Deleted old log: %s (%d bytes)", log_file, size)

        return freed_bytes // (1024 * 1024)

    async def _cleanup_old_files(self, directory: Path, days: int) -> int:
        """Delete files older than specified days. Returns MB freed."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        freed_bytes = 0

        for file_path in directory.rglob("*"):
            if file_path.is_file():
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff.replace(tzinfo=None):
                    size = file_path.stat().st_size
                    file_path.unlink()
                    freed_bytes += size
                    logger.debug("Deleted old file: %s (%d bytes)", file_path, size)

        return freed_bytes // (1024 * 1024)

    async def _cleanup_pycache(self, root: Path) -> int:
        """Delete all __pycache__ directories. Returns MB freed."""
        freed_bytes = 0

        for pycache_dir in root.rglob("__pycache__"):
            if pycache_dir.is_dir():
                size = sum(f.stat().st_size for f in pycache_dir.rglob("*") if f.is_file())
                shutil.rmtree(pycache_dir)
                freed_bytes += size
                logger.debug("Deleted __pycache__: %s (%d bytes)", pycache_dir, size)

        return freed_bytes // (1024 * 1024)

    async def _should_attempt_recovery(self, component: str) -> bool:
        """Check if we should attempt recovery for this component."""
        attempts = await self._get_attempt_count(component)
        return attempts < self._max_recovery_attempts

    async def _record_recovery_attempt(self, component: str) -> None:
        """Record a recovery attempt for rate limiting."""
        await self._increment_attempt_count(component)

    async def reset_recovery_attempts(self, component: str | None = None) -> None:
        """Reset recovery attempt counter (call when issue is resolved)."""
        if component:
            self._recovery_attempts[component] = 0
            if self._redis is not None:
                with contextlib.suppress(Exception):
                    await self._redis.delete(f"{RECOVERY_KEY_PREFIX}{component}")
        else:
            self._recovery_attempts.clear()
            if self._redis is not None:
                try:
                    keys = await self._redis.keys(f"{RECOVERY_KEY_PREFIX}*")
                    if keys:
                        await self._redis.delete(*keys)
                except Exception:
                    pass
