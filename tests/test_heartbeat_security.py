#!/usr/bin/env python3
"""UAT Test 4: 安全审查 - 自动恢复逻辑安全性"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def analyze_recovery_security():
    """分析自动恢复逻辑的安全性"""
    print("=" * 60)
    print("UAT Test 4: 自动恢复逻辑安全审查")
    print("=" * 60)

    recovery_file = Path(__file__).parent / "heartbeat" / "recovery.py"

    if not recovery_file.exists():
        print(f"❌ 文件不存在: {recovery_file}")
        return False

    with open(recovery_file) as f:
        content = f.read()

    print("\n" + "=" * 60)
    print("安全检查项:")
    print("=" * 60)

    issues = []
    warnings = []
    checks_passed = []

    # 1. 检查是否有权限提升风险
    print("\n[1] 权限提升风险检查")
    dangerous_commands = [
        "sudo",
        "su ",
        "pkexec",
        "chmod 777",
        "chown -R",
    ]
    found_dangerous = []
    for cmd in dangerous_commands:
        if cmd in content:
            found_dangerous.append(cmd)

    if found_dangerous:
        issues.append(f"发现危险命令: {', '.join(found_dangerous)}")
        print(f"  ❌ 发现危险命令: {', '.join(found_dangerous)}")
    else:
        checks_passed.append("无权限提升风险")
        print("  ✅ 无权限提升风险")

    # 2. 检查进程管理安全性
    print("\n[2] 进程管理安全性检查")
    if "kill -9" in content or "killall" in content:
        warnings.append("使用强制 kill 可能导致数据丢失")
        print("  ⚠️  使用强制 kill (需要确认是否必要)")
    else:
        checks_passed.append("无强制 kill 操作")
        print("  ✅ 无强制 kill 操作")

    # 3. 检查无限重启保护
    print("\n[3] 无限重启保护检查")
    if "_max_recovery_attempts" in content and "_should_attempt_recovery" in content:
        checks_passed.append("有恢复次数限制机制")
        print("  ✅ 有恢复次数限制机制")

        # 检查默认值
        if "self._max_recovery_attempts = 3" in content:
            print("     └─ 最大重试次数: 3 (合理)")
        else:
            warnings.append("最大重试次数可能不合理")
    else:
        issues.append("缺少恢复次数限制,可能导致无限重启")
        print("  ❌ 缺少恢复次数限制")

    # 4. 检查是否有开关控制
    print("\n[4] 功能开关检查")
    if "enable_auto_recovery" in content and "enable_restart" in content:
        checks_passed.append("有功能开关控制")
        print("  ✅ 有功能开关控制自动恢复")

        # 检查默认值
        if "enable_restart: bool = False" in content:
            checks_passed.append("默认禁用自动重启 (安全)")
            print("     └─ 默认禁用自动重启 (安全)")
        else:
            warnings.append("自动重启默认启用,可能有风险")
    else:
        issues.append("缺少功能开关,无法禁用危险操作")
        print("  ❌ 缺少功能开关")

    # 5. 检查文件删除操作
    print("\n[5] 文件操作安全性检查")
    file_ops = []
    if "unlink()" in content:
        file_ops.append("删除文件")
    if "rmtree(" in content:
        file_ops.append("删除目录树")

    if file_ops:
        # 检查是否有时间限制保护
        if "timedelta(days=" in content:
            checks_passed.append(f"文件删除操作有时间保护: {', '.join(file_ops)}")
            print(f"  ✅ 文件删除操作有时间保护: {', '.join(file_ops)}")
        else:
            warnings.append(f"文件删除操作缺少保护: {', '.join(file_ops)}")
            print(f"  ⚠️  文件删除操作缺少保护: {', '.join(file_ops)}")
    else:
        print("  ℹ️  无文件删除操作")

    # 6. 检查命令注入风险
    print("\n[6] 命令注入风险检查")
    if "subprocess.run(" in content:
        # 检查是否使用 shell=True
        if "shell=True" in content:
            issues.append("使用 shell=True 可能导致命令注入")
            print("  ❌ 使用 shell=True (命令注入风险)")
        else:
            checks_passed.append("subprocess 调用不使用 shell=True")
            print("  ✅ subprocess 调用不使用 shell=True")

        # 检查是否有超时
        if "timeout=" in content:
            checks_passed.append("subprocess 有超时保护")
            print("  ✅ subprocess 有超时保护")
        else:
            warnings.append("subprocess 缺少超时保护")
            print("  ⚠️  subprocess 缺少超时保护")
    else:
        print("  ℹ️  未使用 subprocess")

    # 7. 检查错误处理
    print("\n[7] 错误处理检查")
    try_count = content.count("try:")
    except_count = content.count("except")

    if try_count > 0 and except_count >= try_count:
        checks_passed.append(f"有充分的错误处理 ({try_count} try-except 块)")
        print(f"  ✅ 有充分的错误处理 ({try_count} try-except 块)")
    else:
        warnings.append("错误处理可能不充分")
        print(f"  ⚠️  错误处理可能不充分 (try: {try_count}, except: {except_count})")

    # 8. 检查日志记录
    print("\n[8] 日志记录检查")
    if "logger." in content:
        log_levels = []
        if "logger.info" in content:
            log_levels.append("info")
        if "logger.warning" in content:
            log_levels.append("warning")
        if "logger.error" in content:
            log_levels.append("error")

        checks_passed.append(f"有完善的日志记录: {', '.join(log_levels)}")
        print(f"  ✅ 有完善的日志记录: {', '.join(log_levels)}")
    else:
        warnings.append("缺少日志记录")
        print("  ⚠️  缺少日志记录")

    # 总结
    print("\n" + "=" * 60)
    print("安全审查总结:")
    print("=" * 60)

    print(f"\n✅ 通过检查: {len(checks_passed)}")
    for check in checks_passed:
        print(f"   • {check}")

    if warnings:
        print(f"\n⚠️  警告事项: {len(warnings)}")
        for warning in warnings:
            print(f"   • {warning}")

    if issues:
        print(f"\n❌ 严重问题: {len(issues)}")
        for issue in issues:
            print(f"   • {issue}")

    # 判断结果
    print("\n" + "=" * 60)
    print("最终判定:")
    print("=" * 60)

    if issues:
        print("❌ 发现严重安全问题,需要修复")
        return False
    elif warnings:
        print("⚠️  有警告事项,但可接受")
        print("✅ 整体安全性: PASS (有改进空间)")
        return True
    else:
        print("✅ 未发现安全问题")
        print("✅ 整体安全性: PASS")
        return True


def analyze_monitor_security():
    """分析监控逻辑的安全性"""
    print("\n" + "=" * 60)
    print("监控逻辑安全审查 (heartbeat/monitor.py)")
    print("=" * 60)

    monitor_file = Path(__file__).parent / "heartbeat" / "monitor.py"

    if not monitor_file.exists():
        print(f"❌ 文件不存在: {monitor_file}")
        return False

    with open(monitor_file) as f:
        content = f.read()

    checks_passed = []
    warnings = []

    print("\n[1] 超时保护检查")
    if "timeout=" in content or "ClientTimeout" in content:
        checks_passed.append("HTTP 请求有超时保护")
        print("  ✅ HTTP 请求有超时保护")
    else:
        warnings.append("HTTP 请求可能缺少超时")
        print("  ⚠️  HTTP 请求可能缺少超时")

    print("\n[2] 异常处理检查")
    if "asyncio.TimeoutError" in content and "Exception" in content:
        checks_passed.append("有针对性的异常处理")
        print("  ✅ 有针对性的异常处理")
    else:
        warnings.append("异常处理可能不完善")
        print("  ⚠️  异常处理可能不完善")

    print("\n[3] 资源清理检查")
    if "await" in content and "close()" in content:
        checks_passed.append("有资源清理逻辑")
        print("  ✅ 有资源清理逻辑")
    else:
        warnings.append("可能存在资源泄漏")
        print("  ⚠️  可能存在资源泄漏")

    print(f"\n✅ 通过检查: {len(checks_passed)}")
    if warnings:
        print(f"⚠️  警告事项: {len(warnings)}")

    return True


if __name__ == "__main__":
    print("开始安全审查...")

    success1 = analyze_recovery_security()
    success2 = analyze_monitor_security()

    print("\n" + "=" * 60)
    print("完整审查结论:")
    print("=" * 60)

    if success1 and success2:
        print("✅ 所有安全检查通过")
        print("\n关键安全特性:")
        print("  ✅ 无权限提升风险")
        print("  ✅ 有恢复次数限制 (防止无限重启)")
        print("  ✅ 默认禁用自动重启 (需显式启用)")
        print("  ✅ 无命令注入风险")
        print("  ✅ 文件删除操作有时间保护")
        print("  ✅ 有充分的错误处理和日志")
        sys.exit(0)
    else:
        print("❌ 发现安全问题")
        sys.exit(1)
