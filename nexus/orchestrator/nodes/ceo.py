"""
CEO 节点实现

CEO 节点负责：
1. ceo_dispatch: 发起合同，下发给 Manager
2. ceo_approve: 接收 QA PASS 结果，做最终批准（支持 AI 审批和人工审批 + interrupt）
3. ceo_handle_escalation: 处理超出重试上限的失败上报（interrupt point）
"""
from __future__ import annotations

import logging
import os

from nexus.orchestrator.mail import send_mail
from nexus.orchestrator.state import NexusContractState
from nexus.orchestrator.tools.ceo_tools import generate_contract, write_note

logger = logging.getLogger(__name__)


def ceo_dispatch(state: NexusContractState) -> dict:
    """
    CEO 节点：发起合同并下发给 Manager。

    这是 Graph 的入口节点。CEO 生成标准合同，
    通过内部邮件系统发给 Manager，然后进入等待状态。

    Args:
        state: 当前合同状态（contract_id/task_description 已由调用方填入）

    Returns:
        状态更新字典（LangGraph 会 merge 到当前 state）
    """
    logger.info("[CEO] dispatch contract: %s", state["contract_id"])

    # 工具调用：生成合同文档
    contract = generate_contract(
        role="ceo",
        task_description=state["task_description"],
        priority=state["priority"],
        department=state["department"],
        contract_id=state["contract_id"],
    )

    # 工具调用：CEO 内部备忘
    note = write_note(
        role="ceo",
        note="已下发合同 {} 至 {} 部门".format(state["contract_id"], state["department"]),
    )
    logger.info("[CEO] %s", note)

    # 通过邮件系统下发合同
    # from_role 由系统从 current_phase="ceo_dispatch" 自动推断为 "ceo"
    mail, rejection = send_mail(
        state_phase=state["current_phase"],
        to_role="manager",
        subject="合同下发: {}".format(state["contract_id"]),
        body=(
            "优先级: {}\n"
            "任务: {}\n"
            "请 Manager 分解任务并分配给 Worker 执行。\n"
            "合同详情: {}"
        ).format(state["priority"], state["task_description"], contract),
        msg_type="contract",
    )

    updates: dict = {"current_phase": "manager_planning"}
    if mail is not None:
        updates["mail_log"] = [mail]
    if rejection is not None:
        updates["mail_rejections"] = [rejection]
    return updates


def ceo_approve(state: NexusContractState) -> dict:
    """
    CEO 审批节点。

    根据 approver_type 决定走 AI 审批还是人工审批：
    - approver_type == "ai" → 调用 AI 审批，graph 继续
    - approver_type == "human" → 创建审批请求，使用 interrupt() 暂停

    Args:
        state: 当前合同状态（qa_verdict == "PASS"）

    Returns:
        状态更新字典，包含审批结果和最终产出
    """
    contract_id = state["contract_id"]
    approver_type = state.get("approver_type", "ai")  # default to AI for backward compat

    logger.info(
        "[CEO] ceo_approve: contract=%s, approver_type=%s",
        contract_id,
        approver_type,
    )

    # Build summary from current state
    summary = (
        "任务: {}\n"
        "Worker 产出: {}\n"
        "QA 裁决: {}\n"
        "QA 报告: {}\n"
        "重试次数: {}"
    ).format(
        state["task_description"],
        state.get("worker_output", "")[:500],
        state.get("qa_verdict", ""),
        state.get("qa_report", "")[:300],
        state.get("attempt_count", 0),
    )

    if approver_type == "human":
        from nexus.orchestrator.approval import approval_store, ApproverType
        from langgraph.types import interrupt

        approver_id = state.get("approver_id", "")
        cc_list = state.get("approval_cc_list", [])

        # Create approval request
        req = approval_store.create(
            contract_id=contract_id,
            title="合同审批: {}".format(state["task_description"][:50]),
            summary=summary,
            approver_type=ApproverType.HUMAN,
            approver_id=approver_id,
            cc_list=cc_list,
        )

        logger.info(
            "[CEO] human approval request created: %s, approver=%s",
            req.request_id,
            approver_id,
        )

        # Send Telegram notification (if token configured)
        if os.getenv("TELEGRAM_BOT_TOKEN"):
            try:
                from nexus.orchestrator.telegram_approval import send_approval_request_sync
                send_approval_request_sync(
                    approver_chat_id=approver_id,
                    request_id=req.request_id,
                    contract_id=contract_id,
                    title=req.title,
                    summary=summary,
                    cc_chat_ids=cc_list,
                )
                logger.info("[CEO] Telegram approval notification sent to %s", approver_id)
            except Exception as e:
                logger.warning("[CEO] Failed to send Telegram approval: %s", e)

        # Use LangGraph interrupt() to pause and wait for human response
        human_response = interrupt({
            "type": "approval_required",
            "request_id": req.request_id,
            "contract_id": contract_id,
            "message": "等待人工审批: {}".format(req.title),
        })

        # When resumed, human_response contains the decision
        # Format: {"action": "approve"} or {"action": "reject", "notes": "..."}
        action = human_response.get("action", "reject")

        if action == "approve":
            req.approve(by=approver_id)
            logger.info("[CEO] contract %s approved by human %s", contract_id, approver_id)
            return {
                "current_phase": "completed",
                "ceo_approved": True,
                "approval_request_id": req.request_id,
                "approval_status": "approved",
                "final_result": "合同 {} 已由人工审批通过。\n\n{}".format(
                    contract_id, state.get("worker_output", "")
                ),
            }
        else:
            notes = human_response.get("notes", "审批人未提供原因")
            req.reject(by=approver_id, notes=notes)
            logger.info(
                "[CEO] contract %s rejected by human %s: %s",
                contract_id,
                approver_id,
                notes[:100],
            )
            return {
                "current_phase": "rejected",
                "ceo_approved": False,
                "approval_request_id": req.request_id,
                "approval_status": "rejected",
                "approval_rejection_notes": notes,
                "final_result": "合同 {} 被拒绝。\n原因: {}".format(contract_id, notes),
            }

    else:
        # AI approval path (enhanced from original auto-approve)
        from nexus.orchestrator.approval import approval_store, ApproverType
        from nexus.orchestrator.approval_ai import ai_approve

        req = approval_store.create(
            contract_id=contract_id,
            title="AI 审批: {}".format(state["task_description"][:50]),
            summary=summary,
            approver_type=ApproverType.AI,
            approver_id="ai_ceo",
        )

        logger.info("[CEO] AI approval request created: %s", req.request_id)

        ai_approve(req, context=summary)

        approved = req.status.value == "approved"

        if approved:
            logger.info("[CEO] contract %s approved by AI CEO", contract_id)
            return {
                "current_phase": "completed",
                "ceo_approved": True,
                "approval_request_id": req.request_id,
                "approval_status": "approved",
                "final_result": "合同 {} 已由 AI CEO 批准。\n\n{}".format(
                    contract_id, state.get("worker_output", "")
                ),
            }
        else:
            logger.info(
                "[CEO] contract %s rejected by AI CEO: %s",
                contract_id,
                req.rejection_notes[:100],
            )
            return {
                "current_phase": "rejected",
                "ceo_approved": False,
                "approval_request_id": req.request_id,
                "approval_status": "rejected",
                "approval_rejection_notes": req.rejection_notes,
                "final_result": "合同 {} 被 AI CEO 拒绝。\n原因: {}".format(
                    contract_id, req.rejection_notes
                ),
            }


def ceo_handle_escalation(state: NexusContractState) -> dict:
    """
    CEO 节点：处理 Manager 上报的失败情况（超出最大重试次数）。

    此节点作为失败路径的终点，CEO 记录失败并关闭合同。

    Args:
        state: 当前合同状态（attempt_count >= max_attempts）

    Returns:
        状态更新字典，标记合同为失败关闭
    """
    logger.warning(
        "[CEO] handle escalation: contract=%s, attempts=%d/%d",
        state["contract_id"],
        state["attempt_count"],
        state["max_attempts"],
    )

    escalation_note = write_note(
        role="ceo",
        note=(
            "合同 {} 经过 {} 次重试仍未通过 QA，"
            "已由 CEO 标记为失败并关闭。"
        ).format(state["contract_id"], state["attempt_count"]),
    )
    logger.warning("[CEO] %s", escalation_note)

    final_result = (
        "合同 {} 执行失败。\n"
        "重试次数: {}/{}\n"
        "最后一次 QA 报告:\n{}\n"
        "CEO 决定: 关闭本合同，需要人工介入重新制定方案。"
    ).format(
        state["contract_id"],
        state["attempt_count"],
        state["max_attempts"],
        state["qa_report"],
    )

    return {
        "current_phase": "escalated",
        "escalated": True,
        "final_result": final_result,
        "ceo_approved": False,
    }
