"""
Manager 节点实现

Manager 节点负责：
1. manager_plan: 接收 CEO 合同，分解任务，下发给 Worker
2. manager_review: 接收 Worker 完成报告，转发给 QA 或处理失败
"""
from __future__ import annotations

import logging

from nexus.orchestrator.mail import send_mail
from nexus.orchestrator.state import NexusContractState
from nexus.orchestrator.tools.manager_tools import (
    assign_worker,
    break_down_task,
    escalate,
    review_report,
)

logger = logging.getLogger(__name__)


def manager_plan(state: NexusContractState) -> dict:
    """
    Manager 节点：分解任务并向 Worker 下发执行指令。

    接收 CEO 下发的合同 → 调用 break_down_task 分解为子任务
    → 通过 assign_worker 生成具体指令 → 发送邮件给 Worker。

    Args:
        state: 当前合同状态（current_phase == "manager_planning"）

    Returns:
        状态更新字典，包含子任务列表和 Worker 指令
    """
    logger.info("[MANAGER] plan: contract=%s", state["contract_id"])

    # 工具调用：任务分解
    subtasks = break_down_task(
        role="manager",
        task_description=state["task_description"],
    )

    # 工具调用：生成 Worker 指令
    instruction = assign_worker(
        role="manager",
        worker_id="worker_001",
        subtasks=subtasks,
    )

    # 发送邮件给 Worker
    # from_role 由系统从 current_phase="manager_planning" 自动推断为 "manager"
    mail, rejection = send_mail(
        state_phase=state["current_phase"],
        to_role="worker",
        subject=f"任务分配: {state['contract_id']}",
        body=instruction,
        msg_type="contract",
    )

    logger.info("[MANAGER] dispatched %d subtasks to worker", len(subtasks))

    updates: dict = {
        "current_phase": "worker_executing",
        "subtasks": subtasks,
        "manager_instruction": instruction,
    }
    if mail is not None:
        updates["mail_log"] = [mail]
    if rejection is not None:
        updates["mail_rejections"] = [rejection]
    return updates


def manager_review_after_qa(state: NexusContractState) -> dict:
    """
    Manager 节点：在 QA 出具裁决后进行汇总审阅。

    如果 QA PASS → 上报 CEO 审批。
    如果 QA FAIL 且还有重试机会 → 重新分配 Worker。
    如果 QA FAIL 且超出重试上限 → 上报 CEO 进行上报处理。

    Args:
        state: 当前合同状态（qa_verdict 已填入）

    Returns:
        状态更新字典
    """
    verdict = state["qa_verdict"]
    attempt = state["attempt_count"]
    max_att = state["max_attempts"]

    logger.info(
        "[MANAGER] review_after_qa: verdict=%s, attempt=%d/%d",
        verdict,
        attempt,
        max_att,
    )

    # 工具调用：汇总审阅报告
    summary = review_report(
        role="manager",
        worker_output=state["worker_output"],
        qa_report=state["qa_report"],
    )
    logger.info("[MANAGER] %s", summary)

    # manager_review 阶段，from_role 由系统推断为 "manager"
    if verdict == "PASS":
        # QA 通过 → 上报 CEO 进行最终审批
        mail, rejection = send_mail(
            state_phase=state["current_phase"],
            to_role="ceo",
            subject=f"审批请求: {state['contract_id']} QA PASS",
            body=(
                f"合同 {state['contract_id']} 已通过 QA 审查（第 {attempt} 次）。\n"
                f"QA 报告:\n{state['qa_report']}\n"
                "请 CEO 审批并最终确认交付。"
            ),
            msg_type="approval_request",
        )
        updates: dict = {"current_phase": "ceo_approval"}
        if mail is not None:
            updates["mail_log"] = [mail]
        if rejection is not None:
            updates["mail_rejections"] = [rejection]
        return updates

    elif attempt >= max_att:
        # 超出重试上限 → 上报 CEO
        escalation_msg = escalate(
            role="manager",
            reason=f"经过 {attempt} 次重试仍未通过 QA: {state['qa_report'][:100]}",
            contract_id=state["contract_id"],
        )
        mail, rejection = send_mail(
            state_phase=state["current_phase"],
            to_role="ceo",
            subject=f"上报: {state['contract_id']} 超出重试上限",
            body=(
                f"{escalation_msg}\n"
                f"最后一次 QA 报告:\n{state['qa_report']}"
            ),
            msg_type="escalation",
        )
        updates = {
            "current_phase": "ceo_escalation",
            "escalated": True,
        }
        if mail is not None:
            updates["mail_log"] = [mail]
        if rejection is not None:
            updates["mail_rejections"] = [rejection]
        return updates

    else:
        # 还有重试机会 → 重新分配 Worker
        instruction = assign_worker(
            role="manager",
            worker_id="worker_001",
            subtasks=state.get("subtasks", [state["task_description"]]),
        )
        mail, rejection = send_mail(
            state_phase=state["current_phase"],
            to_role="worker",
            subject=f"重试请求: {state['contract_id']} (第 {attempt + 1} 次)",
            body=(
                f"QA 未通过，请根据以下反馈修改代码：\n"
                f"{state['qa_report']}\n\n"
                f"重新执行指令:\n{instruction}"
            ),
            msg_type="info",
        )
        updates = {
            "current_phase": "worker_executing",
            "manager_instruction": instruction,
        }
        if mail is not None:
            updates["mail_log"] = [mail]
        if rejection is not None:
            updates["mail_rejections"] = [rejection]
        return updates
