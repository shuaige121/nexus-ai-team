#!/usr/bin/env python3
"""
Final UAT Test Suite for Phase 3C Equipment
Runs all tests and generates comprehensive report
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class UATRunner:
    """UAT test suite runner"""

    def __init__(self):
        self.results = []
        self.start_time = datetime.now()

    def run_test(self, test_name: str, test_script: str):
        """Run a single test script"""
        print("\n" + "="*70)
        print(f"运行测试: {test_name}")
        print("="*70)

        try:
            # Run test script
            result = subprocess.run(
                [sys.executable, test_script],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=60
            )

            # Print output
            if result.stdout:
                print(result.stdout)
            if result.stderr and result.returncode != 0:
                print("STDERR:", result.stderr)

            # Record result
            success = result.returncode == 0
            self.results.append({
                'name': test_name,
                'script': test_script,
                'success': success,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            })

            return success

        except subprocess.TimeoutExpired:
            print(f"\n✗ 测试超时 (60秒)")
            self.results.append({
                'name': test_name,
                'script': test_script,
                'success': False,
                'returncode': -1,
                'error': '测试超时'
            })
            return False

        except Exception as e:
            print(f"\n✗ 测试异常: {e}")
            self.results.append({
                'name': test_name,
                'script': test_script,
                'success': False,
                'returncode': -1,
                'error': str(e)
            })
            return False

    def generate_report(self):
        """Generate final UAT report"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        print("\n" + "="*70)
        print("Phase 3C Equipment - UAT 测试总结报告")
        print("="*70)

        print(f"\n测试时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"测试耗时: {duration:.2f} 秒")
        print(f"\n分支: phase3c-equipment")
        print(f"仓库: /home/leonard/Desktop/nexus-ai-team")

        # Summary
        total = len(self.results)
        passed = sum(1 for r in self.results if r['success'])
        failed = total - passed

        print("\n" + "-"*70)
        print("测试结果统计")
        print("-"*70)
        print(f"总计: {total}")
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        print(f"成功率: {(passed/total*100):.1f}%")

        # Detailed results
        print("\n" + "-"*70)
        print("详细测试结果")
        print("-"*70)

        for i, result in enumerate(self.results, 1):
            status = "✓ PASS" if result['success'] else "✗ FAIL"
            print(f"\n{i}. {status} - {result['name']}")
            print(f"   脚本: {result['script']}")
            if not result['success']:
                if 'error' in result:
                    print(f"   错误: {result['error']}")
                elif result['stderr']:
                    print(f"   错误: {result['stderr'][:200]}")

        # Final verdict
        print("\n" + "="*70)
        if failed == 0:
            print("✓ UAT 测试完全通过")
            print("="*70)
            print("\nUAT_RESULT:PASS")
            return True
        else:
            print("✗ UAT 测试失败")
            print("="*70)
            failures = [r['name'] for r in self.results if not r['success']]
            print(f"\nUAT_RESULT:FAIL:{';'.join(failures)}")
            return False


def main():
    """Run all UAT tests"""
    runner = UATRunner()

    # Define test suite
    tests = [
        ("测试 1 & 2: 设备注册、执行和列表", "test_equipment_uat.py"),
        ("测试 2b: 设备 API 端点", "test_equipment_api.py"),
        ("测试 3: Admin 路由判断", "test_admin_routing.py"),
        ("测试 4: 安全审计", "test_security_audit_equipment.py"),
    ]

    # Run all tests
    for test_name, test_script in tests:
        runner.run_test(test_name, test_script)

    # Generate final report
    success = runner.generate_report()

    return success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ UAT 运行器异常: {e}")
        import traceback
        traceback.print_exc()
        print("\nUAT_RESULT:FAIL:UAT运行器异常")
        sys.exit(1)
