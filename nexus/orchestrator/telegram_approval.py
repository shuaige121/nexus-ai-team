"""
NEXUS Telegram 审批集成

发送审批请求到 Telegram，接收批准/拒绝回调。
强规则：只有批准和不批准，不批准必须写备注，CC只读。
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os

logger = logging.getLogger(__name__)

# Token resolved lazily from environment at call time
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


def _get_bot_token() -> str:
    """Return the bot token, raising RuntimeError if not configured."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or TELEGRAM_BOT_TOKEN.strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in environment")
    return token


async def send_approval_request(
    approver_chat_id: str,
    request_id: str,
    contract_id: str,
    title: str,
    summary: str,
    approver_display: str = "",
    cc_chat_ids: list[str] | None = None,
) -> dict:
    """Send an approval request to Telegram with an inline keyboard.

    Only two buttons are presented to the approver: approve and reject.
    CC recipients receive a read-only notification copy with no buttons.

    Args:
        approver_chat_id: Telegram chat ID of the designated approver.
        request_id: Unique approval request ID (e.g. "APR-A1B2C3D4").
        contract_id: The NEXUS contract being reviewed.
        title: Short human-readable title for the approval.
        summary: Multi-line summary of what is being approved.
        approver_display: Human-readable name of the approver shown in the message.
        cc_chat_ids: List of Telegram chat IDs that receive read-only notifications.

    Returns:
        dict with message_id (int) and status (str).
    """
    import telegram
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    token = _get_bot_token()
    bot = telegram.Bot(token=token)

    cc_chat_ids = cc_chat_ids or []
    approver_label = approver_display or approver_chat_id

    # --- Approver message (with action buttons) ---
    approver_text = (
        "📋 *审批请求*\n"
        "───────────────\n"
        f"*合同:* `{contract_id}`\n"
        f"*标题:* {title}\n\n"
        f"*摘要:*\n{summary}\n"
        "───────────────\n"
        f"*审批人:* {approver_label}\n"
    )
    if cc_chat_ids:
        approver_text += f"*CC:* {len(cc_chat_ids)} 人已抄送\n"

    # Exactly two buttons — no other options are permitted
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ 批准", callback_data=f"approve:{request_id}"
            ),
            InlineKeyboardButton(
                "❌ 不批准", callback_data=f"reject:{request_id}"
            ),
        ]
    ])

    # --- CC notification (read-only, no buttons) ---
    cc_text = (
        "📋 *审批通知 (抄送)*\n"
        "───────────────\n"
        f"*合同:* `{contract_id}`\n"
        f"*标题:* {title}\n\n"
        f"*摘要:*\n{summary}\n"
        "───────────────\n"
        f"*审批人:* {approver_label}\n"
        "⏳ 等待审批中...\n"
    )

    async with bot:
        # Send to approver with interactive buttons
        msg = await bot.send_message(
            chat_id=approver_chat_id,
            text=approver_text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        logger.info(
            "[TG_APPROVAL] sent request %s to approver %s (msg_id=%s)",
            request_id,
            approver_chat_id,
            msg.message_id,
        )

        # Send read-only copy to each CC recipient — no buttons, no interaction
        for cc_id in cc_chat_ids:
            try:
                await bot.send_message(
                    chat_id=cc_id,
                    text=cc_text,
                    parse_mode="Markdown",
                )
                logger.debug(
                    "[TG_APPROVAL] CC sent to %s for request %s", cc_id, request_id
                )
            except Exception as exc:
                logger.warning(
                    "[TG_APPROVAL] Failed to send CC to %s for request %s: %s",
                    cc_id,
                    request_id,
                    exc,
                )

    return {"message_id": msg.message_id, "status": "sent"}


async def send_decision_notification(
    chat_ids: list[str],
    request_id: str,
    contract_id: str,
    title: str,
    decision: str,
    rejection_notes: str = "",
    decided_by: str = "",
) -> None:
    """Broadcast the final approval decision to all relevant parties.

    The same read-only result message is sent to the approver and every CC
    recipient. No interactive elements are included.

    Args:
        chat_ids: All Telegram chat IDs to notify (approver + CC list combined).
        request_id: The approval request ID (used only for logging).
        contract_id: The NEXUS contract that was reviewed.
        title: Short title of the approval request.
        decision: Either "approved" or "rejected".
        rejection_notes: Mandatory text when decision is "rejected".
        decided_by: Display name of the person who made the decision.
    """
    import telegram

    token = _get_bot_token()
    bot = telegram.Bot(token=token)

    if decision == "approved":
        emoji = "✅"
        status_text = "已批准"
    else:
        emoji = "❌"
        status_text = "已拒绝"

    operator_label = decided_by or "未知"

    text = (
        f"{emoji} *审批结果*\n"
        "───────────────\n"
        f"*合同:* `{contract_id}`\n"
        f"*标题:* {title}\n"
        f"*结果:* {status_text}\n"
        f"*操作人:* {operator_label}\n"
    )

    if decision == "rejected" and rejection_notes:
        text += f"\n*拒绝原因:*\n{rejection_notes}\n"

    async with bot:
        for chat_id in chat_ids:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="Markdown",
                )
                logger.debug(
                    "[TG_APPROVAL] decision notification sent to %s for %s",
                    chat_id,
                    request_id,
                )
            except Exception as exc:
                logger.warning(
                    "[TG_APPROVAL] Failed to notify %s for request %s: %s",
                    chat_id,
                    request_id,
                    exc,
                )


# ---------------------------------------------------------------------------
# Synchronous wrappers — safe for both sync and async calling contexts
# ---------------------------------------------------------------------------


def send_approval_request_sync(
    approver_chat_id: str,
    request_id: str,
    contract_id: str,
    title: str,
    summary: str,
    approver_display: str = "",
    cc_chat_ids: list[str] | None = None,
) -> dict:
    """Synchronous wrapper around send_approval_request.

    Works correctly whether called from a sync context (LangGraph node) or
    from within an existing async event loop (FastAPI request handler).
    """
    coro = send_approval_request(
        approver_chat_id,
        request_id,
        contract_id,
        title,
        summary,
        approver_display,
        cc_chat_ids,
    )
    try:
        asyncio.get_running_loop()
        # Already in async context — run in a separate thread to avoid conflict
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    except RuntimeError:
        # No running loop — safe to create one
        return asyncio.run(coro)


def send_decision_notification_sync(
    chat_ids: list[str],
    request_id: str,
    contract_id: str,
    title: str,
    decision: str,
    rejection_notes: str = "",
    decided_by: str = "",
) -> None:
    """Synchronous wrapper around send_decision_notification.

    Works correctly whether called from a sync context (LangGraph node) or
    from within an existing async event loop (FastAPI request handler).
    """
    coro = send_decision_notification(
        chat_ids,
        request_id,
        contract_id,
        title,
        decision,
        rejection_notes,
        decided_by,
    )
    try:
        asyncio.get_running_loop()
        # Already in async context — run in a separate thread to avoid conflict
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            future.result(timeout=30)
    except RuntimeError:
        # No running loop — safe to create one
        asyncio.run(coro)


# ---------------------------------------------------------------------------
# Webhook setup — includes secret_token for signature verification (P2-15)
# ---------------------------------------------------------------------------


async def set_webhook(url: str, secret_token: str = "") -> bool:
    """Register the Telegram webhook URL with an optional secret_token.

    When *secret_token* is provided Telegram will include it in every webhook
    request as the X-Telegram-Bot-Api-Secret-Token header, allowing the
    receiving server to verify that the request genuinely originated from
    Telegram.

    Args:
        url: The HTTPS URL Telegram should POST updates to.
        secret_token: A 1-256 character string used for webhook verification.
                      If empty, falls back to the TELEGRAM_WEBHOOK_SECRET env var.

    Returns:
        True if Telegram accepted the webhook registration.
    """
    import telegram

    token = _get_bot_token()
    bot = telegram.Bot(token=token)

    # Resolve secret: explicit parameter > environment variable
    secret = secret_token or os.getenv("TELEGRAM_WEBHOOK_SECRET", "")

    async with bot:
        result = await bot.set_webhook(url=url, secret_token=secret or None)
        logger.info(
            "[TG_APPROVAL] Webhook set to %s (secret_token=%s)",
            url,
            "configured" if secret else "none",
        )
        return result


def set_webhook_sync(url: str, secret_token: str = "") -> bool:
    """Synchronous wrapper around set_webhook."""
    coro = set_webhook(url, secret_token)
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    except RuntimeError:
        return asyncio.run(coro)
