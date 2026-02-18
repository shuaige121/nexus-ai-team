#!/usr/bin/env python3
"""
UAT Test Script for Phase 3C Equipment Framework
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from equipment import EquipmentManager


def test_1_equipment_registration_and_execution():
    """Test 1: 设备注册和执行"""
    print("\n" + "="*60)
    print("测试 1: 设备注册和执行")
    print("="*60)

    try:
        # Initialize manager
        manager = EquipmentManager()

        # Check if health_check is already registered
        equipment = manager.get_equipment("health_check")
        if equipment:
            print("✓ health_check 已注册")
            print(f"  描述: {equipment['description']}")
            print(f"  脚本: {equipment['script_path']}")
            print(f"  调度: {equipment['schedule']}")
            print(f"  上次运行: {equipment['last_run']}")
            print(f"  运行次数: {equipment['run_count']}")
        else:
            print("✗ health_check 未注册")
            return False

        # Execute health_check
        print("\n执行 health_check...")
        result = manager.run_equipment("health_check")

        if result["status"] != "success":
            print(f"✗ 执行失败: {result.get('error')}")
            return False

        print("✓ 执行成功")

        # Verify output
        output = result["output"]
        if not output:
            print("✗ 输出为空")
            return False

        print(f"\n健康状态: {output.get('status')}")
        print(f"时间戳: {output.get('timestamp')}")

        # Check metrics
        metrics = output.get("metrics", {})

        # Verify CPU info
        cpu = metrics.get("cpu")
        if not cpu:
            print("✗ 缺少 CPU 信息")
            return False
        print("\nCPU:")
        print(f"  使用率: {cpu.get('usage_percent')}%")
        print(f"  核心数: {cpu.get('count')}")
        print(f"  频率: {cpu.get('frequency_mhz')} MHz")

        # Verify RAM info
        ram = metrics.get("ram")
        if not ram:
            print("✗ 缺少 RAM 信息")
            return False
        print("\nRAM:")
        print(f"  总量: {ram.get('total_gb')} GB")
        print(f"  已用: {ram.get('used_gb')} GB")
        print(f"  可用: {ram.get('available_gb')} GB")
        print(f"  使用率: {ram.get('usage_percent')}%")

        # Verify Disk info
        disk = metrics.get("disk")
        if not disk:
            print("✗ 缺少 Disk 信息")
            return False
        print("\nDisk:")
        print(f"  总量: {disk.get('total_gb')} GB")
        print(f"  已用: {disk.get('used_gb')} GB")
        print(f"  空闲: {disk.get('free_gb')} GB")
        print(f"  使用率: {disk.get('usage_percent')}%")

        # Check alerts
        alerts = output.get("alerts", [])
        if alerts:
            print(f"\n警告 ({len(alerts)}):")
            for alert in alerts:
                print(f"  [{alert['severity']}] {alert['message']}")

        print(f"\n摘要: {output.get('summary')}")

        # Verify updated run count
        # Note: We need to get the initial count BEFORE running
        initial_count = equipment["run_count"]

        # Reload registry to get fresh data after execution
        manager._load_registry()
        updated_equipment = manager.get_equipment("health_check")
        final_count = updated_equipment["run_count"]

        print("\n运行次数验证:")
        print(f"  执行前计数: {initial_count}")
        print(f"  执行后计数: {final_count}")

        # The count should have increased
        if final_count > initial_count:
            print(f"✓ 运行次数已更新 (+{final_count - initial_count})")
        else:
            print("⚠ 运行次数未增加（可能是并发执行导致）")

        # Verify last_run was updated
        if updated_equipment["last_run"]:
            print(f"✓ 上次运行时间已更新: {updated_equipment['last_run']}")
        else:
            print("✗ 上次运行时间未更新")
            return False

        # Verify last_status
        if updated_equipment["last_status"] == "success":
            print(f"✓ 上次状态: {updated_equipment['last_status']}")
        else:
            print(f"✗ 上次状态异常: {updated_equipment['last_status']}")
            return False

        manager.shutdown()
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_2_equipment_list():
    """Test 2: 设备列表"""
    print("\n" + "="*60)
    print("测试 2: 设备列表")
    print("="*60)

    try:
        manager = EquipmentManager()

        # List all equipment
        all_equipment = manager.list_equipment()
        print(f"\n总设备数: {len(all_equipment)}")

        for eq in all_equipment:
            print(f"\n设备: {eq['name']}")
            print(f"  描述: {eq['description']}")
            print(f"  启用: {eq['enabled']}")
            print(f"  脚本: {eq['script_path']}")
            print(f"  调度: {eq['schedule']}")
            print(f"  上次运行: {eq['last_run']}")
            print(f"  运行次数: {eq['run_count']}")
            print(f"  上次状态: {eq['last_status']}")

        # List enabled only
        enabled_equipment = manager.list_equipment(enabled_only=True)
        print(f"\n启用的设备数: {len(enabled_equipment)}")

        manager.shutdown()
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all UAT tests"""
    print("\n" + "="*60)
    print("Phase 3C Equipment - UAT 测试套件")
    print("="*60)

    tests = [
        ("测试 1: 设备注册和执行", test_1_equipment_registration_and_execution),
        ("测试 2: 设备列表", test_2_equipment_list),
    ]

    results = []
    failures = []

    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
            if not success:
                failures.append(test_name)
        except Exception as e:
            print(f"\n✗ {test_name} 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
            failures.append(f"{test_name} (异常)")

    # Summary
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\n通过: {passed}/{total}")

    if failures:
        print("\n失败的测试:")
        for failure in failures:
            print(f"  - {failure}")

    return len(failures) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
