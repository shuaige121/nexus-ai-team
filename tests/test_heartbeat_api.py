#!/usr/bin/env python3
"""UAT Test 3: 测试健康检查 API 集成"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import aiohttp

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_health_api():
    """测试健康检查 API 端点"""
    print("=" * 60)
    print("UAT Test 3: 健康检查 API 集成测试")
    print("=" * 60)

    # 检查 gateway 是否已启动
    print("\n检查 Gateway 是否运行...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8001/health", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status == 200:
                    print("✅ Gateway 已运行")
                    gateway_running = True
                else:
                    print(f"⚠️  Gateway 响应异常: {resp.status}")
                    gateway_running = False
    except Exception as e:
        print(f"❌ Gateway 未运行: {e}")
        gateway_running = False

    if not gateway_running:
        print("\n尝试启动 Gateway...")
        print("提示: 请在另一个终端运行: source venv/bin/activate && uvicorn gateway.main:app --port 8001 --reload")
        print("等待 5 秒...")
        await asyncio.sleep(5)

        # 再次检查
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8001/health", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        print("✅ Gateway 已启动")
                        gateway_running = True
        except Exception:
            pass

    if not gateway_running:
        print("\n❌ Gateway 未运行,跳过 API 测试")
        print("请手动启动 Gateway 后重新运行此测试")
        return False

    # 测试 /health 端点
    print("\n" + "=" * 60)
    print("测试 1: 基础健康检查 /health")
    print("=" * 60)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                print(f"状态码: {resp.status}")
                data = await resp.json()
                print("响应内容:")
                print(json.dumps(data, indent=2, ensure_ascii=False))

                if resp.status != 200:
                    print("❌ 状态码错误")
                    return False

                if "status" not in data:
                    print("❌ 响应缺少 status 字段")
                    return False

                print("✅ 基础健康检查通过")
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

    # 测试 /api/health/detailed 端点
    print("\n" + "=" * 60)
    print("测试 2: 详细健康检查 /api/health/detailed")
    print("=" * 60)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8001/api/health/detailed", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                print(f"状态码: {resp.status}")
                data = await resp.json()
                print("\n响应内容:")
                print(json.dumps(data, indent=2, ensure_ascii=False))

                # 验证响应格式
                print("\n" + "=" * 60)
                print("验证响应格式:")
                print("=" * 60)

                issues = []

                # 1. 检查必需字段
                required_fields = ["timestamp", "gateway", "redis", "postgres", "agents", "metrics"]
                for field in required_fields:
                    if field not in data:
                        issues.append(f"缺少必需字段: {field}")
                    else:
                        print(f"✅ 字段存在: {field}")

                # 2. 检查组件状态格式
                for component in ["gateway", "redis", "postgres", "agents"]:
                    if component in data:
                        comp_data = data[component]
                        if "status" not in comp_data:
                            issues.append(f"{component} 缺少 status 字段")
                        if "message" not in comp_data:
                            issues.append(f"{component} 缺少 message 字段")

                # 3. Gateway 应该是健康的 (因为我们能请求到它)
                if data.get("gateway", {}).get("status") != "healthy":
                    issues.append(f"Gateway 状态应为 healthy, 实际: {data.get('gateway', {}).get('status')}")

                # 4. 检查 Redis 状态
                redis_status = data.get("redis", {}).get("status")
                print(f"\nRedis 状态: {redis_status}")
                if redis_status == "healthy":
                    print("✅ Redis 连接正常")
                    if "used_memory_mb" in data.get("redis", {}):
                        print(f"   内存使用: {data['redis']['used_memory_mb']} MB")
                else:
                    print(f"⚠️  Redis 状态: {redis_status}")

                # 5. 检查响应时间
                print(f"\n响应时间戳: {data.get('timestamp')}")

                if issues:
                    print("\n❌ 发现问题:")
                    for issue in issues:
                        print(f"  - {issue}")
                    return False
                else:
                    print("\n✅ 所有验证通过")
                    return True

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_health_error_handling():
    """测试错误处理"""
    print("\n" + "=" * 60)
    print("测试 3: API 错误处理")
    print("=" * 60)

    # 测试不存在的端点
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8001/api/health/nonexistent", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                print(f"不存在端点状态码: {resp.status}")
                if resp.status == 404:
                    print("✅ 正确返回 404")
                else:
                    print(f"⚠️  预期 404, 实际 {resp.status}")
    except Exception as e:
        print(f"请求失败: {e}")

    return True


if __name__ == "__main__":
    async def main():
        success = await test_health_api()
        if success:
            await test_health_error_handling()
        return success

    success = asyncio.run(main())
    sys.exit(0 if success else 1)
