"""Standalone heartbeat service runner.

Can be run as:
1. Python script: python -m heartbeat.service
2. Systemd service: systemctl start nexus-heartbeat
3. Cron job: */5 * * * * cd /path/to/nexus && python -m heartbeat.service --once
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from heartbeat.alerts import AlertManager
from heartbeat.monitor import HealthMonitor
from heartbeat.recovery import RecoveryManager

logger = logging.getLogger("heartbeat.service")


async def run_heartbeat_loop(
    monitor: HealthMonitor,
    alert_manager: AlertManager,
    recovery_manager: RecoveryManager,
):
    """Run the heartbeat monitoring loop."""
    logger.info("Starting heartbeat service...")

    # Start monitor
    await monitor.start()

    try:
        # Main loop: process health checks and trigger alerts/recovery
        while True:
            await asyncio.sleep(monitor.check_interval)

            health = monitor.get_last_health()
            if health:
                # Process alerts
                await alert_manager.process_health(health)

                # Attempt recovery
                await recovery_manager.process_health(health)

                # Reset recovery attempts if system is healthy
                if health.is_healthy():
                    recovery_manager.reset_recovery_attempts()

    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
    finally:
        await monitor.stop()


async def run_once(
    monitor: HealthMonitor,
    alert_manager: AlertManager,
    recovery_manager: RecoveryManager,
):
    """Run a single health check (for cron jobs)."""
    logger.info("Running single health check...")

    health = await monitor.check_health()

    # Process alerts
    await alert_manager.process_health(health)

    # Attempt recovery
    await recovery_manager.process_health(health)

    # Print summary
    print(f"Overall status: {'healthy' if health.is_healthy() else 'unhealthy'}")
    for component_name in ["gateway", "redis", "postgres", "agents", "gpu", "budget", "disk"]:
        status = getattr(health, component_name)
        print(f"  {component_name}: {status.status} - {status.message}")


def main():
    parser = argparse.ArgumentParser(description="NEXUS Heartbeat Service")
    parser.add_argument("--once", action="store_true", help="Run once and exit (for cron)")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument("--check-interval", type=int, default=30, help="Health check interval in seconds")
    parser.add_argument("--gateway-url", default="http://localhost:8000", help="Gateway URL")
    parser.add_argument("--redis-url", default="redis://localhost:6379/0", help="Redis URL")
    parser.add_argument("--postgres-url", default="", help="PostgreSQL URL")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama URL")
    parser.add_argument("--telegram-token", default="", help="Telegram bot token")
    parser.add_argument("--telegram-chat-id", default="", help="Telegram chat ID")
    parser.add_argument("--enable-telegram", action="store_true", help="Enable Telegram alerts")
    parser.add_argument("--enable-recovery", action="store_true", default=True, help="Enable auto-recovery")
    parser.add_argument("--enable-restart", action="store_true", help="Enable service restart (requires systemd)")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )

    # Load from environment if not provided
    import os

    postgres_url = args.postgres_url or os.getenv("DATABASE_URL", "")
    telegram_token = args.telegram_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = args.telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID", "")

    # Initialize components
    monitor = HealthMonitor(
        gateway_url=args.gateway_url,
        redis_url=args.redis_url,
        postgres_url=postgres_url,
        ollama_url=args.ollama_url,
        check_interval=args.check_interval,
    )

    alert_manager = AlertManager(
        telegram_bot_token=telegram_token,
        telegram_chat_id=telegram_chat_id,
        enable_telegram=args.enable_telegram,
    )

    recovery_manager = RecoveryManager(
        alert_manager=alert_manager,
        project_root=str(project_root),
        enable_auto_recovery=args.enable_recovery,
        enable_restart=args.enable_restart,
    )

    # Run
    if args.once:
        asyncio.run(run_once(monitor, alert_manager, recovery_manager))
    else:
        asyncio.run(run_heartbeat_loop(monitor, alert_manager, recovery_manager))


if __name__ == "__main__":
    main()
