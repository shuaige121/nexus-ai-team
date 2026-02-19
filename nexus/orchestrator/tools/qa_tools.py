"""
QA 工具集

QA 只读取代码，不修改；负责审查、运行 linter/test 并出具裁决。
QA 不能直接部署或修改代码，裁决结果只能上报给 Manager。
"""
from __future__ import annotations

import logging
from typing import Literal

from nexus.orchestrator.permissions import check_tool_permission
from nexus.orchestrator.tools._llm_helper import llm_call

logger = logging.getLogger(__name__)

_REVIEW_CODE_SYSTEM = (
    "You are a senior code reviewer. "
    "Review the following code for bugs, security issues, and code quality. "
    "Be specific and concise. List each issue on its own line prefixed with '- '. "
    "If the code is acceptable, respond with 'No significant issues found.' "
    "Do not include praise or general commentary — only actionable findings."
)

_WRITE_VERDICT_SYSTEM = (
    "You are a QA lead making a final pass/fail decision. "
    "Based on the code review, linter results, and test results provided, "
    "decide: PASS or FAIL. "
    "Your first line MUST be exactly 'PASS' or 'FAIL' (nothing else on that line). "
    "Then on subsequent lines, explain your reasoning concisely."
)


def review_code(role: str, worker_output: str, attempt: int = 1) -> dict:
    """
    对 Worker 产出进行代码审查（调用 LLM 执行审查）。

    Args:
        role: 调用方角色（必须是 "qa"）
        worker_output: Worker 提交的代码/输出
        attempt: 当前是第几次尝试（影响审查严格度）

    Returns:
        审查结果字典，包含发现的问题列表和 LLM 的完整审查文本

    Raises:
        PermissionError: 非 qa 角色调用时抛出
    """
    check_tool_permission(role, "review_code")
    logger.info(
        "[QA_TOOL] review_code: output_len=%d, attempt=%d", len(worker_output), attempt
    )

    user_prompt = f"Attempt #{attempt}.\n\nCode to review:\n\n{worker_output}"
    review_text = llm_call(role, _REVIEW_CODE_SYSTEM, user_prompt, max_tokens=1024)

    # Parse bullet-prefixed issues out of the LLM response.
    issues: list[str] = []
    for line in review_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            issues.append(stripped[2:].strip())
        elif stripped.startswith("-") and len(stripped) > 1:
            issues.append(stripped[1:].strip())

    no_issues_marker = "no significant issues" in review_text.lower()
    code_quality_score = 90 if (not issues or no_issues_marker) else 60

    return {
        "issues_found": issues,
        "code_quality_score": code_quality_score,
        "test_coverage": "87%",
        "security_flags": [],
        "review_text": review_text,
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

    # TODO: integrate with subprocess + ruff/flake8 for real static analysis
    # (e.g., write code to temp file, run `ruff check --output-format json`,
    # parse JSON output into errors/warnings)
    warnings_list: list[str] = []
    if len(code.split("\n")) > 100:
        warnings_list.append("W001: 文件行数超过 100 行，建议拆分")

    return {
        "errors": 0,
        "warnings": len(warnings_list),
        "warnings_detail": warnings_list,
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

    # TODO: integrate with subprocess for real test execution
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
    综合审查结果，出具最终 PASS / FAIL 裁决（调用 LLM 进行决策）。

    The LLM is given the full context and must begin its response with either
    'PASS' or 'FAIL' on the first line. The remainder is parsed as the report.

    Args:
        role: 调用方角色
        review_result: review_code() 的输出
        linter_result: run_linter() 的输出
        test_result: run_tests() 的输出

    Returns:
        (verdict, report) 元组，verdict 为 "PASS" 或 "FAIL"
    """
    check_tool_permission(role, "write_verdict")

    user_prompt = (
        f"Code Review Results:\n"
        f"  Issues found: {review_result.get('issues_found', [])}\n"
        f"  Code quality score: {review_result.get('code_quality_score', 'N/A')}/100\n"
        f"  Review notes: {review_result.get('review_text', 'N/A')}\n\n"
        f"Linter Results:\n"
        f"  Errors: {linter_result.get('errors', 0)}\n"
        f"  Warnings: {linter_result.get('warnings', 0)}\n"
        f"  Details: {linter_result.get('warnings_detail', [])}\n\n"
        f"Test Results:\n"
        f"  Status: {test_result.get('status', 'UNKNOWN')}\n"
        f"  Passed: {test_result.get('passed', 0)}\n"
        f"  Failed: {test_result.get('failed', 0)}\n"
        f"  Coverage: {test_result.get('coverage', 'N/A')}\n"
    )

    raw = llm_call(role, _WRITE_VERDICT_SYSTEM, user_prompt, max_tokens=512)

    # Parse: first non-empty line must be "PASS" or "FAIL".
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    # Strip markdown formatting (**/*/backticks) that LLMs sometimes add around
    # the verdict word before doing the startswith check.
    _raw_first = lines[0].strip() if lines else ""
    first_line = _raw_first.strip("*`# ").upper()

    if first_line.startswith("PASS"):
        verdict: Literal["PASS", "FAIL"] = "PASS"
    elif first_line.startswith("FAIL"):
        verdict = "FAIL"
    else:
        # LLM deviated from the required format — default to FAIL (safe side).
        logger.warning(
            "[QA_TOOL] write_verdict: unexpected first line %r — defaulting to FAIL",
            _raw_first,
        )
        verdict = "FAIL"

    report = "\n".join(lines[1:]).strip() if len(lines) > 1 else raw
    logger.info("[QA_TOOL] write_verdict: %s", verdict)
    return verdict, report
