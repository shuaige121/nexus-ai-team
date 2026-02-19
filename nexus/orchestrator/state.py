"""
NexusContractState — LangGraph 状态模式定义

整个 Contract 生命周期的共享状态。
"""
from __future__ import annotations

from operator import add
from typing import Annotated, Literal, TypedDict


class MailMessage(TypedDict):
    """内部邮件消息结构。每条邮件都会记录在 mail_log 中以便审计。"""

    from_role: str
    to_role: str
    type: Literal["contract", "report", "approval_request", "info", "escalation"]
    subject: str
    body: str


class MailRejection(TypedDict):
    """
    违规通信记录。

    当 send_mail() 权限校验失败时（B-02），不抛出异常，
    而是将拒绝记录追加到 state.mail_rejections 供审计。
    """

    attempted_from: str
    attempted_to: str
    msg_type: str
    reason: str
    timestamp: str


class NexusContractState(TypedDict):
    """
    NEXUS 合同执行状态。

    使用 Annotated[list, add] 保证 mail_log / mail_rejections
    在并行节点中正确合并（追加语义）。
    """

    # --- 合同元信息 ---
    contract_id: str
    task_description: str
    priority: Literal["low", "medium", "high", "critical"]
    department: str

    # --- 执行阶段 ---
    # 当前所在阶段，便于调试和日志追踪
    current_phase: str

    # Worker 产出（代码/报告等纯文本）
    worker_output: str

    # Worker 产出的完整代码（未截断）
    worker_raw_code: str

    # QA 裁决结果
    qa_verdict: Literal["PASS", "FAIL", ""]

    # QA 详细报告
    qa_report: str

    # 当前已重试次数
    attempt_count: int

    # 最大允许重试次数（超过则上报 CEO）
    max_attempts: int

    # Manager 分解后的子任务列表（简化为字符串列表）
    subtasks: list[str]

    # Manager 对 Worker 的具体指令
    manager_instruction: str

    # --- 通信记录 ---
    # Annotated[list, add] 让 LangGraph 在 reducer 阶段执行列表追加
    mail_log: Annotated[list[MailMessage], add]

    # 违规通信审计记录（B-02：不合规发送不抛异常，记录于此）
    mail_rejections: Annotated[list[MailRejection], add]

    # --- 最终产出 ---
    final_result: str
    ceo_approved: bool

    # 失败上报标志（超过重试上限时设为 True）
    escalated: bool

    # =========================================================================
    # 功能1：Ownership（责任归属）
    # =========================================================================

    # Worker 对合同的回应：None=未回应, True=接受, False=拒绝
    contract_accepted: bool | None

    # Worker 拒绝合同时填写的原因（接受时为空字符串）
    reject_reason: str

    # Worker 应在此截止时间前回应（ISO 格式字符串）
    acceptance_deadline: str

    # =========================================================================
    # 功能2：DoubleCheck 模式（定时回查）
    # =========================================================================

    # 多少秒后触发回查（None 表示不启用回查）
    check_after_seconds: int | None

    # 已回查次数
    check_count: int

    # 最大允许回查次数（超过仍未完成则上报）
    max_checks: int

    # 上次回查时间（ISO 格式字符串）
    last_check_time: str

    # 回查结果："on_track" / "delayed" / "stuck" / ""（未开始回查）
    check_result: str

    # =========================================================================
    # 功能3：Approval（审批流程）
    # =========================================================================

    # 当前审批请求 ID（空字符串表示无进行中审批）
    approval_request_id: str

    # 审批状态：pending / approved / rejected / （未发起）
    approval_status: str

    # 拒绝备注（审批通过时为空字符串）
    approval_rejection_notes: str

    # 审批人类型：ai 或 human
    approver_type: str

    # 审批人标识：human 时为 Telegram chat ID，AI 时为 "ai_ceo"
    approver_id: str

    # 抄送列表：Telegram chat ID 列表
    approval_cc_list: list[str]
