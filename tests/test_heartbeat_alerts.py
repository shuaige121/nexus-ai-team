#!/usr/bin/env python3
"""UAT Test 2: test alert triggering and automatic recovery logic"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from heartbeat.alerts import AlertManager
from heartbeat.monitor import HealthMonitor
from heartbeat.recovery import RecoveryManager


async def test_alert_and_recovery():
    """Test alert triggering and auto-recovery."""
    print("=" * 60)
    print("UAT Test 2: Alert and Recovery Test")
    print("=" * 60)

    alert_manager = AlertManager(
        telegram_bot_token="",
        telegram_chat_id="",
        enable_telegram=False,
    )

    recovery_manager = RecoveryManager(
        alert_manager=alert_manager,
        project_root=str(Path(__file__).resolve().parent.parent),
        enable_auto_recovery=True,
        enable_restart=False,
    )

    # Scenario 1: Gateway offline
    print("\n" + "=" * 60)
    print("Scenario 1: Gateway offline")
    print("=" * 60)

    monitor_offline = HealthMonitor(
        gateway_url="http://localhost:9999",
        redis_url="redis://localhost:6379/0",
        postgres_url="",
    )

    health_offline = await monitor_offline.check_health()
    print(f"\nGateway status: {health_offline.gateway.status}")
    print(f"Gateway message: {health_offline.gateway.message}")
    print(f"Has critical issues: {'yes' if health_offline.has_critical_issues() else 'no'}")

    print("\nProcessing alerts...")
    await alert_manager.process_health(health_offline)

    print("Processing recovery...")
    await recovery_manager.process_health(health_offline)

    # Scenario 2: Redis offline
    print("\n" + "=" * 60)
    print("Scenario 2: Redis offline")
    print("=" * 60)

    monitor_redis_offline = HealthMonitor(
        gateway_url="http://localhost:8000",
        redis_url="redis://localhost:9999/0",
        postgres_url="",
    )

    health_redis_offline = await monitor_redis_offline.check_health()
    print(f"\nRedis status: {health_redis_offline.redis.status}")
    print(f"Redis message: {health_redis_offline.redis.message}")

    await alert_manager.process_health(health_redis_offline)
    await recovery_manager.process_health(health_redis_offline)

    # Scenario 3: Recovery attempt limiting
    print("\n" + "=" * 60)
    print("Scenario 3: Recovery attempt limiting (prevent infinite restart)")
    print("=" * 60)

    print(f"\nCurrent gateway recovery attempts: {recovery_manager._recovery_attempts.get('gateway', 0)}")
    print(f"Max recovery attempts: {recovery_manager._max_recovery_attempts}")

    test_component = "test_service"
    for i in range(5):
        if await recovery_manager._should_attempt_recovery(test_component):
            await recovery_manager._record_recovery_attempt(test_component)
            attempts = recovery_manager._recovery_attempts.get(test_component, 0)
            print(f"Attempt {i+1}: recorded, count={attempts}")
        else:
            print(f"Attempt {i+1}: BLOCKED (max {recovery_manager._max_recovery_attempts} reached)")
            break

    # Verify results
    print("\n" + "=" * 60)
    print("Verification:")
    print("=" * 60)

    issues = []

    if health_offline.gateway.status != "critical":
        issues.append(f"Gateway offline detection failed: {health_offline.gateway.status}")

    if health_redis_offline.redis.status != "critical":
        issues.append(f"Redis offline detection failed: {health_redis_offline.redis.status}")

    test_attempts = recovery_manager._recovery_attempts.get('test_service', 0)
    if test_attempts != recovery_manager._max_recovery_attempts:
        issues.append(f"Recovery limit failed: expected {recovery_manager._max_recovery_attempts}, got {test_attempts}")

    if not health_offline.has_critical_issues():
        issues.append("Failed to identify critical issues")

    if issues:
        print("FAILED:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("ALL CHECKS PASSED")
        return True


if __name__ == "__main__":
    success = asyncio.run(test_alert_and_recovery())
    sys.exit(0 if success else 1)
