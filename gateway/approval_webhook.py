"""
Telegram Webhook router for NEXUS approval callbacks.

Handles inbound Telegram updates delivered via webhook POST to /webhook/telegram.

Flow:
  - User clicks "Approve"  (callback_data="approve:<request_id>")
      -> Immediately approves; notifies all parties.
  - User clicks "Reject"   (callback_data="reject:<request_id>")
      -> Asks the user to type a reason (ForceReply).
      -> Next text message from that user is treated as the rejection note.
      -> Rejects with note; notifies all parties.

CC recipients receive only passive notifications and cannot interact with buttons.
"""
from __future__ import annotations

import logging
import hmac
import os
import threading

from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])

# Module-level state: maps user_id -> request_id for pending rejection notes.
# MVP in-memory store; replace with Redis for multi-process deployments.
_pending_rejections: dict[str, str] = {}


def _resume_graph(contract_id: str, human_response: dict) -> None:
    """Resume the LangGraph graph from interrupt in a background thread."""
    try:
        from nexus.orchestrator.checkpoint import get_checkpointer
        from nexus.orchestrator.graph import build_graph_with_interrupts
        from langgraph.types import Command

        checkpointer = get_checkpointer()
        graph = build_graph_with_interrupts(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": contract_id}}

        def _run():
            try:
                for event in graph.stream(Command(resume=human_response), config=config):
                    pass  # Let graph run to completion
            except Exception as e:
                logger.error("[WEBHOOK] Graph resume failed for %s: %s", contract_id, e)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        logger.info("[WEBHOOK] Graph resume started for contract %s", contract_id)
    except Exception as e:
        logger.error("[WEBHOOK] Failed to resume graph: %s", e)


@router.post("/telegram")
async def telegram_webhook(request: Request) -> Response:
    """Process inbound Telegram webhook updates.

    Handles:
    - callback_query with approve:<id> or reject:<id>
    - text messages used as rejection notes
    """
    import telegram

    # --- Webhook signature verification (P2-15) ---
    from gateway.config import settings
    expected_token = settings.telegram_webhook_secret
    if expected_token:
        received_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(expected_token, received_token):
            logger.warning("[WEBHOOK] Invalid secret token from %s", request.client.host)
            return Response(status_code=403)

    data = await request.json()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.error("[WEBHOOK] TELEGRAM_BOT_TOKEN not set — cannot respond to callbacks")
        return Response(status_code=200)

    bot = telegram.Bot(token=token)

    # ------------------------------------------------------------------
    # Branch 1: button click (callback_query)
    # ------------------------------------------------------------------
    if "callback_query" in data:
        callback = data["callback_query"]
        callback_id = callback["id"]
        callback_data = callback.get("data", "")
        user = callback["from"]
        user_id = str(user["id"])
        user_name = user.get("first_name", user_id)
        chat_id = str(callback["message"]["chat"]["id"])
        message_id = callback["message"]["message_id"]

        from nexus.orchestrator.approval import ApprovalStatus, approval_store
        from nexus.orchestrator.telegram_approval import send_decision_notification_sync

        # ---- APPROVE ----
        if callback_data.startswith("approve:"):
            request_id = callback_data.split(":", 1)[1]
            req = approval_store.get(request_id)

            async with bot:
                if not req:
                    await bot.answer_callback_query(
                        callback_id, text="审批请求不存在"
                    )
                    return Response(status_code=200)

                if req.status != ApprovalStatus.PENDING:
                    await bot.answer_callback_query(
                        callback_id,
                        text=f"已处理: {req.status.value}",
                    )
                    return Response(status_code=200)

                # Enforce: only the designated approver may act
                if req.approver_id != user_id:
                    await bot.answer_callback_query(
                        callback_id,
                        text="你不是审批人，无权操作",
                    )
                    return Response(status_code=200)

                # Record approval — one click, immediately done
                req.approve(by=user_name)

                await bot.answer_callback_query(
                    callback_id, text="✅ 已批准"
                )
                # Remove the inline keyboard from the original message
                await bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=None,
                )

            # Notify approver + all CC recipients of the decision
            all_ids = [req.approver_id] + req.cc_list
            send_decision_notification_sync(
                chat_ids=all_ids,
                request_id=request_id,
                contract_id=req.contract_id,
                title=req.title,
                decision="approved",
                decided_by=user_name,
            )

            # Resume the LangGraph graph from interrupt
            _resume_graph(req.contract_id, {"action": "approve"})
            logger.info(
                "[WEBHOOK] Approved %s by %s for contract %s",
                request_id,
                user_name,
                req.contract_id,
            )

        # ---- REJECT (step 1: ask for notes) ----
        elif callback_data.startswith("reject:"):
            request_id = callback_data.split(":", 1)[1]
            req = approval_store.get(request_id)

            async with bot:
                if not req:
                    await bot.answer_callback_query(
                        callback_id, text="审批请求不存在"
                    )
                    return Response(status_code=200)

                if req.status != ApprovalStatus.PENDING:
                    await bot.answer_callback_query(
                        callback_id,
                        text=f"已处理: {req.status.value}",
                    )
                    return Response(status_code=200)

                if req.approver_id != user_id:
                    await bot.answer_callback_query(
                        callback_id,
                        text="你不是审批人，无权操作",
                    )
                    return Response(status_code=200)

                # Prompt for rejection reason — not final until note is provided
                await bot.answer_callback_query(
                    callback_id, text="请回复拒绝原因"
                )
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"❌ 你选择了不批准 `{request_id}`\n\n"
                        f"*请回复此消息，写明拒绝原因:*\n"
                        f"（直接输入文字即可）"
                    ),
                    parse_mode="Markdown",
                    reply_markup=telegram.ForceReply(selective=True),
                )

            # Register pending rejection — next text from this user finalises it
            _pending_rejections[user_id] = request_id
            logger.info(
                "[WEBHOOK] Reject pending for %s from user %s — awaiting notes",
                request_id,
                user_id,
            )

    # ------------------------------------------------------------------
    # Branch 2: text message — may be a rejection note
    # ------------------------------------------------------------------
    elif "message" in data and "text" in data.get("message", {}):
        message = data["message"]
        user_id = str(message["from"]["id"])
        user_name = message["from"].get("first_name", user_id)
        chat_id = str(message["chat"]["id"])
        text = message["text"]

        if user_id not in _pending_rejections:
            # Not a rejection note — ignore (handled by main bot if running)
            return Response(status_code=200)

        request_id = _pending_rejections.pop(user_id)

        from nexus.orchestrator.approval import approval_store
        from nexus.orchestrator.telegram_approval import send_decision_notification_sync

        req = approval_store.get(request_id)
        if not req:
            logger.warning(
                "[WEBHOOK] Received rejection note for unknown request %s", request_id
            )
            return Response(status_code=200)

        async with bot:
            try:
                # reject() enforces non-empty notes internally
                req.reject(by=user_name, notes=text)

                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"❌ 已拒绝 `{request_id}`\n"
                        f"原因: {text}"
                    ),
                    parse_mode="Markdown",
                )

                # Notify approver + all CC recipients
                all_ids = [req.approver_id] + req.cc_list
                send_decision_notification_sync(
                    chat_ids=all_ids,
                    request_id=request_id,
                    contract_id=req.contract_id,
                    title=req.title,
                    decision="rejected",
                    rejection_notes=text,
                    decided_by=user_name,
                )

                # Resume the LangGraph graph from interrupt with rejection result
                _resume_graph(req.contract_id, {"action": "reject", "notes": text})
                logger.info(
                    "[WEBHOOK] Rejected %s by %s with notes for contract %s",
                    request_id,
                    user_name,
                    req.contract_id,
                )

            except ValueError as exc:
                # ApprovalRequest.reject() raises ValueError for empty notes or wrong state
                logger.warning("[WEBHOOK] Rejection failed for %s: %s", request_id, exc)
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"错误: {exc}",
                )

    return Response(status_code=200)
