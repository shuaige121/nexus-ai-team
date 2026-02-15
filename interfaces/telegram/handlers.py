"""Telegram message handlers — text, photo, voice, and command dispatching."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from telegram import PhotoSize, Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)

from .format import escape_markdown_v2

logger = logging.getLogger(__name__)

MessageKind = Literal["text", "photo", "voice"]
ChatScope = Literal["private", "group"]

# Type alias for the user-supplied message callback
OnMessageCallback = Callable[
    [Update, ContextTypes.DEFAULT_TYPE, "InboundMessage"],
    Awaitable[None],
]


@dataclass(frozen=True)
class InboundMessage:
    """Normalised representation of a Telegram inbound message."""

    kind: MessageKind
    scope: ChatScope
    chat_type: str
    chat_id: int
    message_id: int
    from_id: int | None = None
    username: str | None = None
    text: str | None = None
    caption: str | None = None
    photo_file_id: str | None = None
    voice_file_id: str | None = None
    voice_duration_seconds: int | None = None


def _resolve_chat_scope(chat_type: str) -> ChatScope | None:
    if chat_type == "private":
        return "private"
    if chat_type in ("group", "supergroup"):
        return "group"
    return None


def parse_inbound_message(update: Update) -> InboundMessage | None:
    """Parse an ``Update`` into a normalised :class:`InboundMessage`, or ``None``."""
    message = update.effective_message
    if message is None:
        return None

    chat = update.effective_chat
    if chat is None:
        return None

    scope = _resolve_chat_scope(chat.type)
    if scope is None:
        return None

    base = dict(
        scope=scope,
        chat_type=chat.type,
        chat_id=chat.id,
        message_id=message.message_id,
        from_id=message.from_user.id if message.from_user else None,
        username=message.from_user.username if message.from_user else None,
    )

    # Text message
    if message.text is not None:
        return InboundMessage(kind="text", text=message.text, **base)

    # Photo message — pick the highest resolution
    if message.photo:
        largest: PhotoSize = message.photo[-1]
        return InboundMessage(
            kind="photo",
            caption=message.caption,
            photo_file_id=largest.file_id,
            **base,
        )

    # Voice message
    if message.voice:
        return InboundMessage(
            kind="voice",
            caption=message.caption,
            voice_file_id=message.voice.file_id,
            voice_duration_seconds=message.voice.duration,
            **base,
        )

    return None


# ---------------------------------------------------------------------------
# Default handler (echo-back, will be replaced by gateway integration)
# ---------------------------------------------------------------------------

async def _default_on_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    msg: InboundMessage,
) -> None:
    """Built-in echo handler used when no custom callback is provided."""
    if msg.kind == "text":
        body = escape_markdown_v2(msg.text or "")
        await update.effective_message.reply_text(
            f"*NEXUS 收到文本消息*\n\n{body}",
            parse_mode="MarkdownV2",
        )
        return

    if msg.kind == "photo":
        caption = f"\n\n说明: {escape_markdown_v2(msg.caption)}" if msg.caption else ""
        await update.effective_message.reply_text(
            f"*NEXUS 收到图片消息*{caption}",
            parse_mode="MarkdownV2",
        )
        return

    if msg.kind == "voice":
        duration = (
            f"\n\n时长: *{msg.voice_duration_seconds}* 秒"
            if msg.voice_duration_seconds is not None
            else ""
        )
        await update.effective_message.reply_text(
            f"*NEXUS 收到语音消息*{duration}",
            parse_mode="MarkdownV2",
        )
        return


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------

def register_handlers(
    app: Application,
    *,
    on_message: OnMessageCallback | None = None,
) -> None:
    """Register message handlers on the Application.

    Handlers are added for text, photo, and voice messages.
    Command messages (``/foo``) are **excluded** here — they are handled by
    :func:`commands.register_commands`.
    """
    callback = on_message or _default_on_message

    async def _handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        parsed = parse_inbound_message(update)
        if parsed is None:
            logger.debug("Unsupported message type from chat %s, skipping", update.effective_chat)
            return
        await callback(update, context, parsed)

    # Text messages (exclude commands so they go to CommandHandlers)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle))
    # Photos
    app.add_handler(MessageHandler(filters.PHOTO, _handle))
    # Voice
    app.add_handler(MessageHandler(filters.VOICE, _handle))

    logger.debug("Telegram message handlers registered (text, photo, voice)")
