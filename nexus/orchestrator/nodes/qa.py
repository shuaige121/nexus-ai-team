"""
QA 节点实现

QA 节点负责对 Worker 产出进行独立审查，出具 PASS/FAIL 裁决。
QA 只读代码，不修改；裁决结果通过邮件上报给 Manager。
"""
from __future__ import annotations

import logging

from nexus.orchestrator.mail import send_mail
from nexus.orchestrator.state import NexusContractState
from nexus.orchestrator.tools.qa_tools import review_code, run_linter, run_tests, write_verdict

logger = logging.getLogger(__name__)


def qa_review(state: NexusContractState) -> dict:
    """
    QA 节点：审查 Worker 产出并出具裁决。

    流程：review_code → run_linter → run_tests → write_verdict → 邮件报告给 Manager。

    Args:
        state: 当前合同状态（worker_output 已由 Worker 填入）

    Returns:
        状态更新字典，包含 qa_verdict 和 qa_report
    """
    attempt = state.get("attempt_count", 1)
    logger.info(
        "[QA] review: contract=%s, attempt=%d",
        state["contract_id"],
        attempt,
    )

    worker_output = state["worker_output"]

    # 工具调用1：代码审查
    review_result = review_code(
        role="qa",
        worker_output=worker_output,
        attempt=attempt,
    )

    # 工具调用2：Linter 静态分析
    linter_result = run_linter(role="qa", code=worker_output)

    # 工具调用3：独立运行测试
    test_result = run_tests(role="qa", code=worker_output)

    # 工具调用4：综合出具裁决
    verdict, report = write_verdict(
        role="qa",
        review_result=review_result,
        linter_result=linter_result,
        test_result=test_result,
    )

    logger.info("[QA] verdict=%s for contract=%s", verdict, state["contract_id"])

    # QA 向 Manager 发送审查报告（Chain of Command：qa → manager）
    # from_role 由系统从 current_phase="qa_reviewing" 自动推断为 "qa"
    mail, rejection = send_mail(
        state_phase=state["current_phase"],
        to_role="manager",
        subject=f"QA 审查报告: {state['contract_id']} — {verdict}",
        body=(
            f"合同编号: {state['contract_id']}\n"
            f"审查次数: {attempt}\n"
            f"裁决: {verdict}\n\n"
            f"详细报告:\n{report}"
        ),
        msg_type="report",
    )

    updates: dict = {
        "current_phase": "manager_review",
        "qa_verdict": verdict,
        "qa_report": report,
    }
    if mail is not None:
        updates["mail_log"] = [mail]
    if rejection is not None:
        updates["mail_rejections"] = [rejection]
    return updates
