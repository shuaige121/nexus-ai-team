"""
Worker Accept 节点实现（功能1：Ownership 责任归属）

Worker 收到合同后，必须先明确回应 Accept 或 Reject，
而不是直接开始执行。这确保了责任归属的清晰性。

流程：
    manager_plan → worker_accept → (accept) → worker_execute
                                → (reject)  → manager_plan（重新分配）
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from nexus.orchestrator.mail import send_mail
from nexus.orchestrator.state import NexusContractState

logger = logging.getLogger(__name__)

# PoC 阶段：Worker 默认接受合同的概率控制。
# 真实场景中 Worker 会评估任务可行性、资源情况等再决策。
# 此处通过合同 ID 的简单规则模拟拒绝（方便测试覆盖 reject 路径）。
_REJECT_MARKER = "REJECT"  # 合同 ID 中包含此字符串时模拟拒绝


def worker_accept(state: NexusContractState) -> dict:
    """
    Worker Accept 节点：评估合同并回应 Accept 或 Reject。

    Worker 收到 Manager 的合同指令后，进行以下评估：
    1. 检查任务可行性（PoC 阶段：通过合同 ID 简单模拟）
    2. 检查自身资源与能力
    3. 在截止时间内回应接受或拒绝

    Args:
        state: 当前合同状态（manager_instruction 已由 Manager 填入）

    Returns:
        状态更新字典，包含：
        - contract_accepted: True/False
        - reject_reason: 拒绝时的原因（接受时为空字符串）
        - acceptance_deadline: 本次回应的截止时间
    """
    contract_id = state["contract_id"]
    instruction = state.get("manager_instruction", state["task_description"])

    logger.info("[WORKER_ACCEPT] 评估合同 contract=%s", contract_id)

    # 计算截止时间（PoC：当前时间 + 5 分钟）
    deadline = (datetime.now(tz=timezone.utc) + timedelta(minutes=5)).isoformat()

    # PoC 阶段模拟决策逻辑：
    # 合同 ID 中包含 "REJECT" 关键字时，Worker 拒绝任务
    should_reject = _REJECT_MARKER in contract_id.upper()

    if should_reject:
        # --- 拒绝路径 ---
        reject_reason = (
            f"Worker 评估后发现任务超出当前能力范围或资源不足。"
            f"合同 {contract_id} 的需求与现有技术栈不匹配，"
            f"建议 Manager 重新分配或调整任务范围。"
        )
        logger.warning(
            "[WORKER_ACCEPT] 拒绝合同 contract=%s, reason=%s",
            contract_id,
            reject_reason[:80],
        )

        # 向 Manager 发送拒绝通知
        mail, rejection = send_mail(
            state_phase="worker_rejected",
            to_role="manager",
            subject=f"合同拒绝通知: {contract_id}",
            body=(
                f"Worker 已评估合同 {contract_id}，决定拒绝接受。\n\n"
                f"拒绝原因：\n{reject_reason}\n\n"
                f"请 Manager 重新分配或调整任务范围。"
            ),
            msg_type="report",
        )

        return {
            "current_phase": "worker_rejected",
            "contract_accepted": False,
            "reject_reason": reject_reason,
            "acceptance_deadline": deadline,
            "mail_log": [mail] if mail else [],
        }

    else:
        # --- 接受路径 ---
        logger.info("[WORKER_ACCEPT] 接受合同 contract=%s", contract_id)

        # 向 Manager 发送接受确认
        mail, rejection = send_mail(
            state_phase="worker_accepted",
            to_role="manager",
            subject=f"合同接受确认: {contract_id}",
            body=(
                f"Worker 已确认接受合同 {contract_id}。\n\n"
                f"任务摘要：{instruction[:120]}\n\n"
                f"将立即开始执行，按时完成并汇报。"
            ),
            msg_type="info",
        )

        return {
            "current_phase": "worker_accepted",
            "contract_accepted": True,
            "reject_reason": "",
            "acceptance_deadline": deadline,
            "mail_log": [mail] if mail else [],
        }


def route_after_worker_accept(
    state: NexusContractState,
) -> str:
    """
    worker_accept 节点后的条件路由。

    决策逻辑：
    - contract_accepted == True  → "worker_execute"（进入正常执行流程）
    - contract_accepted == False → "manager_reassign"（退回 Manager 重新分配）
    - contract_accepted == None  → "manager_reassign"（未回应视为违规，退回处理）

    Args:
        state: 当前合同状态

    Returns:
        下一节点的名称字符串
    """
    accepted = state.get("contract_accepted")  # type: ignore[call-overload]

    if accepted is True:
        logger.info(
            "[ROUTER] route_after_worker_accept: ACCEPTED → worker_execute, contract=%s",
            state["contract_id"],
        )
        return "worker_execute"
    else:
        # False（明确拒绝）或 None（未回应，视为违规）都退回 Manager
        reason = "rejected" if accepted is False else "no_response_violation"
        logger.warning(
            "[ROUTER] route_after_worker_accept: %s → manager_reassign, contract=%s",
            reason,
            state["contract_id"],
        )
        return "manager_reassign"
