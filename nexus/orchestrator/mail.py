"""
NEXUS 内部邮件系统

负责在角色之间传递消息，并在发送前强制执行 Chain of Command 校验。

B-01 修复：from_role 不再由调用方传入，而是由系统根据 state 的 current_phase
自动推断。调用方无法伪造发件人身份。

B-02 修复：当 check_mail_permission() 拒绝一次通信时，违规记录会被写入
state 的 mail_rejections 字段，供事后审计。send_mail() 返回一个包含
mail_log 更新（成功时）或 mail_rejections 更新（违规时）的状态补丁字典，
由节点负责 merge 到 state 中。
"""
from __future__ import annotations

import logging
import warnings
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from nexus.orchestrator.permissions import PermissionError, check_mail_permission
from nexus.orchestrator.state import MailMessage, MailRejection

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# current_phase → 发件人角色 映射表
# 系统通过这个映射从 state.current_phase 推断合法的发件人身份，
# 杜绝调用方自行传入 from_role 伪造身份。
# --------------------------------------------------------------------------
_PHASE_TO_ROLE: dict[str, str] = {
    # 原有阶段
    "ceo_dispatch": "ceo",
    "ceo_approval": "ceo",
    "ceo_escalation": "ceo",
    "completed": "ceo",
    "manager_planning": "manager",
    "manager_review": "manager",
    "worker_executing": "worker",
    "qa_reviewing": "qa",
    # 兜底：escalated 由 manager 上报触发
    "escalated": "manager",
    # --- 功能1：Ownership 新增阶段 ---
    # worker_accept 节点：Worker 回应合同接受/拒绝
    "worker_accepted": "worker",    # Worker 接受合同，发确认邮件
    "worker_rejected": "worker",    # Worker 拒绝合同，发拒绝通知
    "worker_accepting": "manager",  # Manager 重新发合同给 Worker
    # manager_reassign 节点：Manager 重新分配或上报
    "manager_reassigning": "manager",
    # --- 功能2：DoubleCheck 新增阶段 ---
    # progress_check 节点：由 Manager 角色进行回查通知
    "check_on_track": "manager",
    "check_stuck": "manager",
    "check_escalation": "manager",
    "check_delayed": "manager",
}


def resolve_from_role(current_phase: str) -> str:
    """
    根据 current_phase 推断当前合法的发件人角色。

    Args:
        current_phase: state 中的当前执行阶段

    Returns:
        对应的发件人角色字符串

    Raises:
        ValueError: 无法从 current_phase 推断角色时抛出
    """
    role = _PHASE_TO_ROLE.get(current_phase)
    if role is None:
        raise ValueError(
            f"无法从 current_phase={current_phase!r} 推断发件人角色，"
            f"请在 _PHASE_TO_ROLE 中添加对应映射。"
        )
    return role


def send_mail(
    state_phase: str,
    to_role: str,
    subject: str,
    body: str,
    msg_type: str = "info",
    *,
    from_role: str | None = None,
) -> tuple[MailMessage | None, MailRejection | None]:
    """
    发送内部邮件，返回 (mail_message, rejection) 二元组。

    B-01：from_role 由系统根据 state_phase 自动推断，调用方不得指定。
    若调用方传入了 from_role 关键字参数，将记录警告并忽略该参数。

    B-02：如果权限校验失败，不抛出异常，而是返回 (None, rejection_record)，
    由节点将 rejection_record 追加到 state.mail_rejections 中以供审计。
    成功时返回 (mail_message, None)，节点将 mail_message 追加到 state.mail_log。

    Args:
        state_phase: 当前 state.current_phase，用于推断 from_role
        to_role: 收件人角色
        subject: 邮件主题
        body: 邮件正文
        msg_type: 消息类型，见 MailMessage.type 枚举
        from_role: 已废弃 — 调用方传入会被忽略并触发警告（B-01 防伪造）

    Returns:
        (MailMessage, None) — 发送成功
        (None, MailRejection) — 权限被拒，调用方应将 rejection 追加到
        state.mail_rejections

    Raises:
        ValueError: state_phase 无法映射到角色时抛出
    """
    # B-01：如果调用方传入了 from_role，忽略并警告
    if from_role is not None:
        warnings.warn(
            f"send_mail() 的 from_role 参数已废弃，传入值 {from_role!r} 将被忽略。"
            f"from_role 现由系统根据 state_phase={state_phase!r} 自动推断。",
            stacklevel=2,
        )

    # 从 current_phase 自动推断发件人身份（可能抛出 ValueError）
    inferred_from = resolve_from_role(state_phase)

    ts = datetime.now(tz=timezone.utc).isoformat()

    # B-02：执行权限校验，返回拒绝原因或 None
    rejection_reason = check_mail_permission(inferred_from, to_role)

    if rejection_reason is not None:
        # 记录违规到审计日志（不抛出异常）
        logger.warning(
            "[MAIL REJECTED] %s → %s | %s | reason: %s",
            inferred_from,
            to_role,
            msg_type,
            rejection_reason,
        )
        rejection: MailRejection = {
            "attempted_from": inferred_from,
            "attempted_to": to_role,
            "msg_type": msg_type,
            "reason": rejection_reason,
            "timestamp": ts,
        }
        return None, rejection

    # 校验通过，构建邮件消息
    logger.info("[MAIL] %s → %s | %s | %s", inferred_from, to_role, msg_type, subject)
    msg: MailMessage = {
        "from_role": inferred_from,
        "to_role": to_role,
        "type": msg_type,  # type: ignore[typeddict-item]
        "subject": f"[{ts}] {subject}",
        "body": body,
    }
    return msg, None


def format_mail_log(mail_log: list[MailMessage]) -> str:
    """
    将邮件日志格式化为可读字符串，便于调试输出。

    Args:
        mail_log: 邮件记录列表

    Returns:
        格式化后的多行字符串
    """
    if not mail_log:
        return "(无邮件记录)"
    lines = []
    for i, msg in enumerate(mail_log, start=1):
        lines.append(
            f"  [{i:02d}] {msg['from_role']} → {msg['to_role']} "
            f"({msg['type']}) — {msg['subject']}"
        )
    return "\n".join(lines)


def format_rejection_log(mail_rejections: list[MailRejection]) -> str:
    """
    将违规通信日志格式化为可读字符串，便于安全审计。

    Args:
        mail_rejections: 违规通信记录列表

    Returns:
        格式化后的多行字符串
    """
    if not mail_rejections:
        return "(无违规通信记录)"
    lines = []
    for i, rec in enumerate(mail_rejections, start=1):
        lines.append(
            f"  [{i:02d}] REJECTED {rec['attempted_from']} → {rec['attempted_to']} "
            f"({rec['msg_type']}) @ {rec['timestamp']}\n"
            f"        reason: {rec['reason']}"
        )
    return "\n".join(lines)
