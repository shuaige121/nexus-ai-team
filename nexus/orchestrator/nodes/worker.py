"""
Worker 节点实现

Worker 节点负责实际代码生成、本地测试和 git commit。
Worker 只能在 task branch 上工作，完成后向 Manager 汇报。
"""
from __future__ import annotations

import logging

from nexus.orchestrator.mail import send_mail
from nexus.orchestrator.state import NexusContractState
from nexus.orchestrator.tools.worker_tools import git_commit, run_tests, write_code

logger = logging.getLogger(__name__)


def worker_execute(state: NexusContractState) -> dict:
    """
    Worker 节点：执行代码编写、测试和提交。

    流程：write_code → run_tests → git_commit → 报告给 Manager。

    Args:
        state: 当前合同状态（manager_instruction 已由 Manager 填入）

    Returns:
        状态更新字典，包含 worker_output 和递增的 attempt_count
    """
    attempt = state.get("attempt_count", 0) + 1
    logger.info(
        "[WORKER] execute: contract=%s, attempt=%d",
        state["contract_id"],
        attempt,
    )

    # 工具调用1：编写代码（第 N 次尝试）
    # 重试时将 QA 反馈和/或 CEO 拒绝反馈注入指令，让 Worker 针对性修复
    ceo_feedback = state.get("ceo_rejection_feedback", "")
    qa_feedback = state.get("qa_report", "")
    base_instruction = state.get("manager_instruction", state["task_description"])

    if attempt > 1 and (qa_feedback or ceo_feedback):
        parts = []
        if ceo_feedback:
            parts.append(
                "CEO 拒绝了你上次的产出，反馈如下：\n\n"
                "--- CEO 反馈 ---\n"
                + ceo_feedback
                + "\n--- CEO 反馈结束 ---\n"
            )
        if qa_feedback:
            parts.append(
                "QA 的反馈如下：\n\n"
                "--- QA 反馈 ---\n"
                + qa_feedback
                + "\n--- QA 反馈结束 ---\n"
            )
        parts.append(
            "原始任务: " + base_instruction
            + "\n\n请根据以上反馈针对性修复，不要重新从头写。"
        )
        instruction = "\n\n".join(parts)
    else:
        instruction = base_instruction

    code = write_code(
        role="worker",
        instruction=instruction,
        attempt=attempt,
    )

    # 工具调用2：本地运行测试
    test_result = run_tests(role="worker", code=code)
    logger.info("[WORKER] local tests: %s", test_result)

    # 工具调用3：提交到 feature branch（禁止提交到 main）
    branch = f"feature/{state['contract_id']}-attempt-{attempt}"
    commit_ref = git_commit(
        role="worker",
        code=code,
        message=(
            f"feat: 合同 {state['contract_id']} 第 {attempt} 次实现\n"
            f"任务: {state['task_description'][:60]}"
        ),
        branch=branch,
    )
    logger.info("[WORKER] committed: %s", commit_ref)

    # 整合 Worker 产出报告
    worker_output = (
        f"=== Worker 执行报告（第 {attempt} 次）===\n"
        f"Commit: {commit_ref}\n"
        f"本地测试: {test_result['passed']} 通过, {test_result['failed']} 失败, "
        f"覆盖率 {test_result['coverage']}\n"
        f"代码预览:\n{code[:400]}"
    )

    # 向 Manager 汇报完成（Chain of Command：worker → manager）
    # from_role 由系统从 current_phase="worker_executing" 自动推断为 "worker"
    mail, rejection = send_mail(
        state_phase=state["current_phase"],
        to_role="manager",
        subject=f"任务完成报告: {state['contract_id']} 第 {attempt} 次",
        body=worker_output,
        msg_type="report",
    )

    updates: dict = {
        "current_phase": "qa_reviewing",
        "worker_output": worker_output,
        "worker_raw_code": code,
        "attempt_count": attempt,
    }
    if mail is not None:
        updates["mail_log"] = [mail]
    if rejection is not None:
        updates["mail_rejections"] = [rejection]
    return updates
