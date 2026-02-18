"""
CEO 节点实现

CEO 节点负责：
1. ceo_dispatch: 发起合同，下发给 Manager
2. ceo_approve: 接收 QA PASS 结果，做最终批准（interrupt point）
3. ceo_handle_escalation: 处理超出重试上限的失败上报（interrupt point）
"""
from __future__ import annotations

import logging

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
        note=f"已下发合同 {state['contract_id']} 至 {state['department']} 部门",
    )
    logger.info("[CEO] %s", note)

    # 通过邮件系统下发合同
    # from_role 由系统从 current_phase="ceo_dispatch" 自动推断为 "ceo"
    mail, rejection = send_mail(
        state_phase=state["current_phase"],
        to_role="manager",
        subject=f"合同下发: {state['contract_id']}",
        body=(
            f"优先级: {state['priority']}\n"
            f"任务: {state['task_description']}\n"
            f"请 Manager 分解任务并分配给 Worker 执行。\n"
            f"合同详情: {contract}"
        ),
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
    CEO 节点：审批 QA PASS 的结果。

    此节点通常作为 interrupt point，在真实系统中等待人工确认。
    PoC 阶段自动批准。

    Args:
        state: 当前合同状态（qa_verdict == "PASS"）

    Returns:
        状态更新字典，设置 ceo_approved=True 和 final_result
    """
    logger.info("[CEO] approve contract: %s (QA PASS)", state["contract_id"])

    # from_role 由系统从 current_phase="ceo_approval" 自动推断为 "ceo"
    approval_mail, rejection = send_mail(
        state_phase=state["current_phase"],
        to_role="manager",
        subject=f"合同批准: {state['contract_id']}",
        body=(
            f"QA 审查通过，本 CEO 正式批准合同 {state['contract_id']} 的交付结果。\n"
            f"QA 报告摘要:\n{state['qa_report']}\n"
            "项目正式结束，请归档所有文档。"
        ),
        msg_type="approval_request",
    )

    final_result = (
        f"合同 {state['contract_id']} 已完成并获 CEO 批准。\n"
        f"Worker 输出预览:\n{state['worker_output'][:200]}\n"
        f"QA 报告:\n{state['qa_report']}"
    )

    updates: dict = {
        "current_phase": "completed",
        "ceo_approved": True,
        "final_result": final_result,
    }
    if approval_mail is not None:
        updates["mail_log"] = [approval_mail]
    if rejection is not None:
        updates["mail_rejections"] = [rejection]
    return updates


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
            f"合同 {state['contract_id']} 经过 {state['attempt_count']} 次重试仍未通过 QA，"
            "已由 CEO 标记为失败并关闭。"
        ),
    )
    logger.warning("[CEO] %s", escalation_note)

    final_result = (
        f"合同 {state['contract_id']} 执行失败。\n"
        f"重试次数: {state['attempt_count']}/{state['max_attempts']}\n"
        f"最后一次 QA 报告:\n{state['qa_report']}\n"
        "CEO 决定: 关闭本合同，需要人工介入重新制定方案。"
    )

    return {
        "current_phase": "escalated",
        "escalated": True,
        "final_result": final_result,
        "ceo_approved": False,
    }
