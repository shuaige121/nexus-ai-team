"""
QA 工具集

QA 只读取代码，不修改；负责审查、运行 linter/test 并出具裁决。
QA 不能直接部署或修改代码，裁决结果只能上报给 Manager。
"""
from __future__ import annotations

import logging
from typing import Literal

from nexus.orchestrator.permissions import check_tool_permission

logger = logging.getLogger(__name__)


def review_code(role: str, worker_output: str, attempt: int = 1) -> dict:
    """
    对 Worker 产出进行代码审查。

    Args:
        role: 调用方角色（必须是 "qa"）
        worker_output: Worker 提交的代码/输出
        attempt: 当前是第几次尝试（影响审查严格度）

    Returns:
        审查结果字典，包含发现的问题列表

    Raises:
        PermissionError: 非 qa 角色调用时抛出
    """
    check_tool_permission(role, "review_code")
    logger.info("[QA_TOOL] review_code: output_len=%d, attempt=%d", len(worker_output), attempt)

    # PoC 阶段：模拟代码审查逻辑
    # 第一次总是 PASS（演示正常流程），可在测试中覆盖
    issues: list[str] = []

    # 简单规则检查（模拟 linter）
    if "TODO" in worker_output:
        issues.append("发现未完成的 TODO 注释")
    if "pass\n" in worker_output.lower():
        issues.append("发现空的 pass 语句，疑似未实现逻辑")
    if len(worker_output) < 50:
        issues.append("代码过短，可能实现不完整")

    return {
        "issues_found": issues,
        "code_quality_score": 90 if not issues else 60,
        "test_coverage": "87%",
        "security_flags": [],
    }


def run_linter(role: str, code: str) -> dict:
    """
    运行 linter 静态分析。

    Args:
        role: 调用方角色
        code: 待分析代码

    Returns:
        linter 结果字典
    """
    check_tool_permission(role, "run_linter")
    logger.info("[QA_TOOL] run_linter: code_len=%d", len(code))

    # PoC：模拟 ruff/flake8 输出
    warnings = []
    if len(code.split("\n")) > 100:
        warnings.append("W001: 文件行数超过 100 行，建议拆分")

    return {
        "errors": 0,
        "warnings": len(warnings),
        "warnings_detail": warnings,
        "linter": "ruff (mock)",
    }


def run_tests(role: str, code: str) -> dict:
    """
    QA 独立运行测试套件（与 Worker 的 run_tests 独立）。

    Args:
        role: 调用方角色
        code: 待测试代码

    Returns:
        测试结果字典
    """
    check_tool_permission(role, "run_tests")
    logger.info("[QA_TOOL] run_tests: code_len=%d", len(code))

    return {
        "passed": 5,
        "failed": 0,
        "coverage": "87%",
        "duration": "0.38s",
        "status": "GREEN",
    }


def write_verdict(
    role: str,
    review_result: dict,
    linter_result: dict,
    test_result: dict,
) -> tuple[Literal["PASS", "FAIL"], str]:
    """
    综合审查结果，出具最终 PASS / FAIL 裁决。

    裁决规则：
    - 有任何 linter error → FAIL
    - 有代码问题 (issues_found 非空) → FAIL
    - 测试 status != GREEN → FAIL
    - 其余情况 → PASS

    Args:
        role: 调用方角色
        review_result: review_code() 的输出
        linter_result: run_linter() 的输出
        test_result: run_tests() 的输出

    Returns:
        (verdict, report) 元组
    """
    check_tool_permission(role, "write_verdict")

    reasons_fail: list[str] = []

    if linter_result.get("errors", 0) > 0:
        reasons_fail.append(f"Linter 报错 {linter_result['errors']} 个")

    if review_result.get("issues_found"):
        reasons_fail.append(f"代码审查发现问题: {', '.join(review_result['issues_found'])}")

    if test_result.get("status") != "GREEN":
        reasons_fail.append(f"测试未通过: {test_result.get('status', 'UNKNOWN')}")

    if reasons_fail:
        verdict: Literal["PASS", "FAIL"] = "FAIL"
        report = (
            f"QA 裁决: FAIL\n"
            f"失败原因:\n" + "\n".join(f"  - {r}" for r in reasons_fail) + "\n"
            f"代码质量分: {review_result.get('code_quality_score', 0)}/100\n"
            f"测试覆盖率: {test_result.get('coverage', 'N/A')}"
        )
    else:
        verdict = "PASS"
        report = (
            f"QA 裁决: PASS\n"
            f"代码质量分: {review_result.get('code_quality_score', 100)}/100\n"
            f"测试覆盖率: {test_result.get('coverage', 'N/A')}\n"
            f"Linter 警告: {linter_result.get('warnings', 0)} 个\n"
            f"所有检查项通过，可以上报 Manager 批准。"
        )

    logger.info("[QA_TOOL] write_verdict: %s", verdict)
    return verdict, report
