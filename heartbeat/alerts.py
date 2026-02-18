"""Alert notifications for NEXUS health issues.

Sends notifications via:
- Telegram (for critical issues → Board/User)
- Logging (for all issues)
- WebSocket (for connected clients)
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any

import aiohttp

from heartbeat.monitor import HealthStatus, SystemHealth

logger = logging.getLogger("heartbeat.alerts")


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertManager:
    """Manages health alert notifications."""

    def __init__(
        self,
        telegram_bot_token: str = "",
        telegram_chat_id: str = "",
        enable_telegram: bool = False,
    ):
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.enable_telegram = enable_telegram

        # Track last alert time to avoid spam
        self._last_alert: dict[str, float] = {}
        self._alert_cooldown = 300  # 5 minutes

    async def process_health(self, health: SystemHealth):
        """Process health report and send alerts as needed."""
        if health.has_critical_issues():
            await self._send_critical_alert(health)
        elif not health.is_healthy():
            await self._send_warning_alert(health)

    async def _send_critical_alert(self, health: SystemHealth):
        """Send critical alert for severe issues."""
        critical_components = []
        for component_name in ["gateway", "redis", "postgres", "agents", "gpu", "budget", "disk"]:
            status: HealthStatus = getattr(health, component_name)
            if status.is_critical():
                critical_components.append(status)

        if not critical_components:
            return

        # Log critical issues
        for comp in critical_components:
            logger.critical(
                "CRITICAL: %s — %s (details: %s)",
                comp.component,
                comp.message,
                comp.details,
            )

        # Send Telegram notification
        if self.enable_telegram and self.telegram_bot_token and self.telegram_chat_id:
            await self._send_telegram_alert(
                severity=AlertSeverity.CRITICAL,
                components=critical_components,
            )

    async def _send_warning_alert(self, health: SystemHealth):
        """Send warning alert for degraded components."""
        degraded_components = []
        for component_name in ["gateway", "redis", "postgres", "agents", "gpu", "budget", "disk"]:
            status: HealthStatus = getattr(health, component_name)
            if status.status == "degraded":
                degraded_components.append(status)

        if not degraded_components:
            return

        # Log warnings
        for comp in degraded_components:
            logger.warning(
                "WARNING: %s — %s (details: %s)",
                comp.component,
                comp.message,
                comp.details,
            )

        # Send Telegram notification (rate-limited)
        if self._should_send_alert("warning") and self.enable_telegram and self.telegram_bot_token and self.telegram_chat_id:
            await self._send_telegram_alert(
                    severity=AlertSeverity.WARNING,
                    components=degraded_components,
                )

    async def _send_telegram_alert(
        self,
        severity: AlertSeverity,
        components: list[HealthStatus],
    ):
        """Send alert via Telegram Bot API."""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.debug("Telegram not configured, skipping alert")
            return

        # Rate limit to avoid spam
        if not self._should_send_alert(f"telegram_{severity.value}"):
            logger.debug("Alert rate limited, skipping Telegram notification")
            return

        # Format message
        emoji = "🚨" if severity == AlertSeverity.CRITICAL else "⚠️"
        message_lines = [
            f"{emoji} *NEXUS Health Alert*",
            f"Severity: {severity.value.upper()}",
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        for comp in components:
            message_lines.append(f"• *{comp.component}*: {comp.message}")
            if comp.details:
                for key, value in comp.details.items():
                    message_lines.append(f"  - {key}: {value}")

        message = "\n".join(message_lines)

        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
                payload = {
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                }
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        logger.info("Telegram alert sent successfully")
                    else:
                        logger.error("Failed to send Telegram alert: status=%d", resp.status)
        except Exception:
            logger.exception("Error sending Telegram alert")

    def _should_send_alert(self, alert_type: str) -> bool:
        """Check if enough time has passed since last alert of this type."""
        import time

        now = time.time()
        last_time = self._last_alert.get(alert_type, 0)

        if now - last_time >= self._alert_cooldown:
            self._last_alert[alert_type] = now
            return True
        return False

    async def send_custom_alert(
        self,
        severity: AlertSeverity,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        """Send a custom alert (e.g., from recovery manager)."""
        details = details or {}

        # Log
        if severity == AlertSeverity.CRITICAL:
            logger.critical("CUSTOM ALERT: %s (details: %s)", message, details)
        elif severity == AlertSeverity.WARNING:
            logger.warning("CUSTOM ALERT: %s (details: %s)", message, details)
        else:
            logger.info("CUSTOM ALERT: %s (details: %s)", message, details)

        # Send Telegram notification
        if self.enable_telegram and self.telegram_bot_token and self.telegram_chat_id and self._should_send_alert(f"custom_{severity.value}"):
                emoji_map = {
                    AlertSeverity.INFO: "ℹ️",
                    AlertSeverity.WARNING: "⚠️",
                    AlertSeverity.CRITICAL: "🚨",
                }
                emoji = emoji_map[severity]

                message_lines = [
                    f"{emoji} *NEXUS Alert*",
                    f"Severity: {severity.value.upper()}",
                    f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "",
                    message,
                ]

                if details:
                    message_lines.append("")
                    for key, value in details.items():
                        message_lines.append(f"• {key}: {value}")

                telegram_message = "\n".join(message_lines)

                try:
                    async with aiohttp.ClientSession() as session:
                        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
                        payload = {
                            "chat_id": self.telegram_chat_id,
                            "text": telegram_message,
                            "parse_mode": "Markdown",
                        }
                        async with session.post(
                            url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
                        ) as resp:
                            if resp.status == 200:
                                logger.info("Custom alert sent via Telegram")
                            else:
                                logger.error("Failed to send custom alert: status=%d", resp.status)
                except Exception:
                    logger.exception("Error sending custom alert via Telegram")
