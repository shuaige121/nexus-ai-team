#!/usr/bin/env python3
"""UAT Test 1: 测试 heartbeat monitor 单次检查"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from heartbeat.monitor import HealthMonitor


async def test_single_health_check():
    """测试单次健康检查"""
    print("=" * 60)
    print("UAT Test 1: Heartbeat Monitor - 单次健康检查")
    print("=" * 60)

    # 创建 monitor (不启动后台循环)
    monitor = HealthMonitor(
        gateway_url="http://localhost:8000",
        redis_url="redis://localhost:6379/0",
        postgres_url="",  # 暂不配置
        ollama_url="http://localhost:11434",
        check_interval=30,
    )

    print("\n正在执行健康检查...")
    health = await monitor.check_health()

    print("\n" + "=" * 60)
    print("健康检查结果:")
    print("=" * 60)
    print(f"整体状态: {'✅ 健康' if health.is_healthy() else '❌ 不健康'}")
    print(f"有严重问题: {'⚠️  是' if health.has_critical_issues() else '✅ 否'}")
    print(f"检查时间: {health.timestamp}")

    print("\n各组件状态:")
    print("-" * 60)

    components = [
        health.gateway,
        health.redis,
        health.postgres,
        health.agents,
        health.gpu,
        health.budget,
        health.disk,
    ]

    for comp in components:
        status_emoji = {
            "healthy": "✅",
            "degraded": "⚠️ ",
            "critical": "🚨",
            "unknown": "❓",
        }.get(comp.status, "?")

        print(f"{status_emoji} {comp.component:12s} | {comp.status:10s} | {comp.message}")
        if comp.details:
            for key, value in comp.details.items():
                print(f"   └─ {key}: {value}")

    print("\n" + "=" * 60)
    print("JSON 格式输出:")
    print("=" * 60)
    import json
    print(json.dumps(health.to_dict(), indent=2, ensure_ascii=False))

    # 验证核心功能
    print("\n" + "=" * 60)
    print("验证结果:")
    print("=" * 60)

    issues = []

    # 1. Gateway 状态 (预期离线或健康)
    if health.gateway.status not in ["healthy", "critical"]:
        issues.append(f"Gateway 状态异常: {health.gateway.status}")

    # 2. Redis 状态 (预期离线或健康)
    if health.redis.status not in ["healthy", "critical"]:
        issues.append(f"Redis 状态异常: {health.redis.status}")

    # 3. PostgreSQL 应该是 unknown (未配置)
    if health.postgres.status != "unknown":
        issues.append(f"PostgreSQL 状态应为 unknown, 实际: {health.postgres.status}")

    # 4. Disk 检查应该成功
    if health.disk.status == "unknown":
        issues.append("磁盘检查未返回有效状态")

    # 5. 检查返回值格式
    if not isinstance(health.to_dict(), dict):
        issues.append("to_dict() 未返回字典")

    if issues:
        print("❌ 发现问题:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("✅ 所有验证通过")
        return True


if __name__ == "__main__":
    success = asyncio.run(test_single_health_check())
    sys.exit(0 if success else 1)
