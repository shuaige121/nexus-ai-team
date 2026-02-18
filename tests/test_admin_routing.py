#!/usr/bin/env python3
"""
Test Admin Agent's equipment detection and routing
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from nexus_v1.admin import AdminAgent
from nexus_v1.model_router import ModelRouter


def test_admin_equipment_routing():
    """Test 3: 模拟 Admin 判断 - 测试 Admin Agent 是否能正确识别 equipment 请求"""
    print("\n" + "="*60)
    print("测试 3: Admin Agent 设备路由判断")
    print("="*60)

    # Initialize admin agent without LLM (use heuristic mode for testing)
    router = ModelRouter()
    admin = AdminAgent(router=router, use_llm=False)

    test_cases = [
        # Health check requests
        {
            "request": "检查系统健康状态",
            "expected_equipment": "health_check",
            "description": "中文：检查系统健康"
        },
        {
            "request": "Show me system health",
            "expected_equipment": "health_check",
            "description": "英文：系统健康"
        },
        {
            "request": "What's the CPU usage?",
            "expected_equipment": "health_check",
            "description": "英文：CPU 使用率"
        },
        {
            "request": "系统健康检查",
            "expected_equipment": "health_check",
            "description": "中文：健康检查"
        },
        # Log rotation requests
        {
            "request": "Rotate logs",
            "expected_equipment": "log_rotate",
            "description": "英文：轮转日志"
        },
        {
            "request": "日志清理",
            "expected_equipment": "log_rotate",
            "description": "中文：日志清理"
        },
        # Backup requests
        {
            "request": "Backup the project",
            "expected_equipment": "backup",
            "description": "英文：备份项目"
        },
        {
            "request": "备份项目",
            "expected_equipment": "backup",
            "description": "中文：备份"
        },
        # Cost report requests
        {
            "request": "Generate token cost report",
            "expected_equipment": "cost_report",
            "description": "英文：成本报告"
        },
        {
            "request": "成本报告",
            "expected_equipment": "cost_report",
            "description": "中文：成本报告"
        },
        # Non-equipment requests (should NOT match)
        {
            "request": "Implement user authentication",
            "expected_equipment": None,
            "description": "非设备：功能开发"
        },
        {
            "request": "Fix the bug in login.py",
            "expected_equipment": None,
            "description": "非设备：修复 bug"
        },
    ]

    passed = 0
    failed = 0
    failures = []

    print("\n测试用例:")
    for i, test_case in enumerate(test_cases, 1):
        request = test_case["request"]
        expected = test_case["expected_equipment"]
        description = test_case["description"]

        # Classify request
        route = admin.classify_request(request)
        detected = route.equipment_name

        # Check if detection is correct
        if detected == expected:
            status = "✓"
            passed += 1
        else:
            status = "✗"
            failed += 1
            failures.append({
                "description": description,
                "request": request,
                "expected": expected,
                "detected": detected
            })

        print(f"\n{i}. {status} {description}")
        print(f"   请求: \"{request}\"")
        print(f"   期望设备: {expected or '(无)'}")
        print(f"   检测设备: {detected or '(无)'}")
        print(f"   意图: {route.intent}")
        print(f"   难度: {route.difficulty}")
        print(f"   负责人: {route.owner}")

    # Summary
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"总计: {len(test_cases)}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")

    if failures:
        print("\n失败的测试:")
        for failure in failures:
            print(f"  - {failure['description']}")
            print(f"    请求: \"{failure['request']}\"")
            print(f"    期望: {failure['expected']}, 实际: {failure['detected']}")

    return failed == 0


def test_equipment_integration():
    """Test equipment integration with work order creation"""
    print("\n" + "="*60)
    print("测试 3b: Equipment 与 Work Order 集成")
    print("="*60)

    router = ModelRouter()
    admin = AdminAgent(router=router, use_llm=False)

    # Test creating work order with equipment detection
    test_request = "系统健康检查"
    print(f"\n请求: \"{test_request}\"")

    work_order = admin.create_work_order(test_request)

    print(f"\nWork Order:")
    print(f"  ID: {work_order.id}")
    print(f"  意图: {work_order.intent}")
    print(f"  难度: {work_order.difficulty}")
    print(f"  负责人: {work_order.owner}")
    print(f"  设备: {work_order.equipment_name}")
    print(f"  压缩上下文: {work_order.compressed_context[:100]}...")

    if work_order.equipment_name == "health_check":
        print("\n✓ Work Order 正确识别了 equipment")
        return True
    else:
        print(f"\n✗ Work Order 未能识别 equipment (期望: health_check, 实际: {work_order.equipment_name})")
        return False


if __name__ == "__main__":
    try:
        print("\n" + "="*60)
        print("Phase 3C Equipment - Admin 路由测试")
        print("="*60)

        test1_passed = test_admin_equipment_routing()
        test2_passed = test_equipment_integration()

        print("\n" + "="*60)
        print("最终结果")
        print("="*60)

        if test1_passed and test2_passed:
            print("✓ 所有 Admin 路由测试通过")
            sys.exit(0)
        else:
            print("✗ 部分 Admin 路由测试失败")
            if not test1_passed:
                print("  - 设备检测测试失败")
            if not test2_passed:
                print("  - Work Order 集成测试失败")
            sys.exit(1)

    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
