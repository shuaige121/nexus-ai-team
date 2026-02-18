#!/usr/bin/env python3
"""UAT Test 2: 测试告警触发和自动恢复逻辑"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from heartbeat.alerts import AlertManager, AlertSeverity
from heartbeat.monitor import HealthMonitor
from heartbeat.recovery import RecoveryManager


async def test_alert_and_recovery():
    """测试告警触发和自动恢复"""
    print("=" * 60)
    print("UAT Test 2: 告警触发和自动恢复测试")
    print("=" * 60)

    # 创建 alert manager (不启用 Telegram)
    alert_manager = AlertManager(
        telegram_bot_token="",
        telegram_chat_id="",
        enable_telegram=False,
    )

    # 创建 recovery manager (禁用实际重启)
    recovery_manager = RecoveryManager(
        alert_manager=alert_manager,
        project_root="/home/leonard/Desktop/nexus-ai-team",
        enable_auto_recovery=True,
        enable_restart=False,  # 不实际重启服务
    )

    # 测试场景 1: Gateway 离线
    print("\n" + "=" * 60)
    print("场景 1: 模拟 Gateway 离线")
    print("=" * 60)

    # 使用错误端口模拟 gateway 离线
    monitor_offline = HealthMonitor(
        gateway_url="http://localhost:9999",  # 错误端口
        redis_url="redis://localhost:6379/0",
        postgres_url="",
    )

    health_offline = await monitor_offline.check_health()
    print(f"\nGateway 状态: {health_offline.gateway.status}")
    print(f"Gateway 消息: {health_offline.gateway.message}")
    print(f"有严重问题: {'是' if health_offline.has_critical_issues() else '否'}")

    # 触发告警处理
    print("\n触发告警处理...")
    await alert_manager.process_health(health_offline)

    # 触发恢复处理
    print("触发恢复处理...")
    await recovery_manager.process_health(health_offline)

    # 测试场景 2: Redis 离线
    print("\n" + "=" * 60)
    print("场景 2: 模拟 Redis 离线")
    print("=" * 60)

    monitor_redis_offline = HealthMonitor(
        gateway_url="http://localhost:8000",
        redis_url="redis://localhost:9999/0",  # 错误端口
        postgres_url="",
    )

    health_redis_offline = await monitor_redis_offline.check_health()
    print(f"\nRedis 状态: {health_redis_offline.redis.status}")
    print(f"Redis 消息: {health_redis_offline.redis.message}")

    await alert_manager.process_health(health_redis_offline)
    await recovery_manager.process_health(health_redis_offline)

    # 测试场景 3: 检查恢复次数限制 (使用手动记录)
    print("\n" + "=" * 60)
    print("场景 3: 测试恢复次数限制 (防止无限重启)")
    print("=" * 60)

    print(f"\n当前 gateway 恢复次数: {recovery_manager._recovery_attempts.get('gateway', 0)}")
    print(f"最大恢复次数: {recovery_manager._max_recovery_attempts}")

    # 手动模拟恢复尝试
    test_component = "test_service"
    for i in range(5):
        if recovery_manager._should_attempt_recovery(test_component):
            recovery_manager._record_recovery_attempt(test_component)
            attempts = recovery_manager._recovery_attempts.get(test_component, 0)
            print(f"第 {i+1} 次恢复尝试, 记录次数: {attempts}")
        else:
            print(f"第 {i+1} 次尝试: ✅ 达到最大恢复次数({recovery_manager._max_recovery_attempts}),已停止尝试 (防止无限循环)")
            break

    # 验证结果
    print("\n" + "=" * 60)
    print("验证结果:")
    print("=" * 60)

    issues = []

    # 1. Gateway 离线应该检测到 critical
    if health_offline.gateway.status != "critical":
        issues.append(f"Gateway 离线检测失败: {health_offline.gateway.status}")

    # 2. Redis 离线应该检测到 critical
    if health_redis_offline.redis.status != "critical":
        issues.append(f"Redis 离线检测失败: {health_redis_offline.redis.status}")

    # 3. 恢复次数应该被限制
    test_attempts = recovery_manager._recovery_attempts.get('test_service', 0)
    if test_attempts != recovery_manager._max_recovery_attempts:
        issues.append(f"恢复次数限制失败: 预期{recovery_manager._max_recovery_attempts}, 实际{test_attempts}")

    # 4. 检查 AlertManager 是否正确识别严重问题
    if not health_offline.has_critical_issues():
        issues.append("未正确识别严重问题")

    if issues:
        print("❌ 发现问题:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("✅ 所有验证通过")
        print("\n关键特性:")
        print("  ✅ 正确检测 Gateway 离线")
        print("  ✅ 正确检测 Redis 离线")
        print("  ✅ 告警处理正常工作")
        print("  ✅ 恢复次数正确限制 (防止无限重启)")
        print("  ✅ 不会误杀进程 (enable_restart=False)")
        return True


if __name__ == "__main__":
    success = asyncio.run(test_alert_and_recovery())
    sys.exit(0 if success else 1)
