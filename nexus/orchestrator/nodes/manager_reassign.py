"""
Manager Reassign 节点实现（功能1：Ownership 责任归属）

当 Worker 拒绝合同或未在截止时间内回应时，
Manager 需要重新评估任务并重新分配或调整合同内容。

流程：
    worker_accept (reject) → manager_reassign → manager_plan（重新分配）
                                              → ceo_handle_escalation（无可用 Worker）
"""
from __future__ import annotations

import logging

from nexus.orchestrator.mail import send_mail
from nexus.orchestrator.state import NexusContractState
from nexus.orchestrator.tools.manager_tools import assign_worker, escalate

logger = logging.getLogger(__name__)


def manager_reassign(state: NexusContractState) -> dict:
    """
    Manager Reassign 节点：处理 Worker 拒绝或未回应的情况。

    当 Worker 拒绝合同时，Manager 有以下选项：
    1. 调整任务描述/拆分后重新分配（默认行为，PoC 阶段）
    2. 上报 CEO 说明无可用 Worker（超出 attempt_count 时）

    PoC 阶段简化：
    - 如果 attempt_count < max_attempts → 重新下发（回到 manager_plan 重建指令）
    - 如果 attempt_count >= max_attempts → 上报 CEO

    Args:
        state: 当前合同状态（reject_reason 已由 worker_accept 填入）

    Returns:
        状态更新字典
    """
    contract_id = state["contract_id"]
    reject_reason = state.get("reject_reason", "原因未知")
    attempt_count = state.get("attempt_count", 0)
    max_attempts = state.get("max_attempts", 3)

    logger.warning(
        "[MANAGER_REASSIGN] Worker 拒绝合同 contract=%s, attempt=%d/%d, reason=%s",
        contract_id,
        attempt_count,
        max_attempts,
        reject_reason[:80],
    )

    if attempt_count >= max_attempts:
        # 超出重试上限，上报 CEO
        escalation_msg = escalate(
            role="manager",
            reason=(
                f"Worker 拒绝合同，且已达到最大分配次数 {max_attempts}。\n"
                f"拒绝原因：{reject_reason}"
            ),
            contract_id=contract_id,
        )
        mail, rejection = send_mail(
            state_phase="manager_reassigning",
            to_role="ceo",
            subject=f"上报: {contract_id} Worker 拒绝且无法重新分配",
            body=(
                f"{escalation_msg}\n\n"
                f"已尝试分配 {attempt_count} 次，均未获 Worker 接受。\n"
                f"需要 CEO 介入：重新定义任务范围或引入新资源。"
            ),
            msg_type="escalation",
        )
        return {
            "current_phase": "ceo_escalation",
            "escalated": True,
            "mail_log": [mail] if mail else [],
        }

    else:
        # 还有机会 → 重新拆解任务后下发
        # 调整指令（PoC：在原指令基础上追加"简化版"提示）
        new_instruction = assign_worker(
            role="manager",
            worker_id="worker_001",
            subtasks=state.get("subtasks", [state["task_description"]]),
        )
        adjusted_instruction = (
            f"[重新分配 - 第 {attempt_count + 1} 次]\n"
            f"上次 Worker 拒绝原因：{reject_reason[:200]}\n\n"
            f"调整后指令：\n{new_instruction}"
        )

        mail, rejection = send_mail(
            state_phase="worker_accepting",
            to_role="worker",
            subject=f"重新分配合同: {contract_id}（第 {attempt_count + 1} 次）",
            body=adjusted_instruction,
            msg_type="contract",
        )

        logger.info(
            "[MANAGER_REASSIGN] 重新分配合同 contract=%s, attempt=%d",
            contract_id,
            attempt_count + 1,
        )

        return {
            "current_phase": "worker_accepting",
            "manager_instruction": adjusted_instruction,
            # 重置 contract_accepted 为 None，等待新的 Worker 回应
            "contract_accepted": None,
            "reject_reason": "",
            "attempt_count": attempt_count + 1,
            "mail_log": [mail] if mail else [],
        }
