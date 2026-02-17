"""Telegram slash commands — /status /escalate /cost /audit.

These are registered as ``CommandHandler`` instances so Telegram autocompletes
them for users in the chat input.
"""

from __future__ import annotations

import datetime as dt
import logging

from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .format import escape_markdown_v2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Command definitions (name, description shown in Telegram UI)
# ---------------------------------------------------------------------------

BOT_COMMANDS: list[BotCommand] = [
    BotCommand("status", "Show NEXUS system status"),
    BotCommand("escalate", "Escalate current task to a higher-level agent"),
    BotCommand("cost", "Show token usage and cost summary"),
    BotCommand("audit", "Show recent audit log entries"),
]


# ---------------------------------------------------------------------------
# /status — system status overview
# ---------------------------------------------------------------------------

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Report high-level system status."""
    from .gateway_client import GatewayClient

    now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Try to fetch real status from gateway
    try:
        async with GatewayClient() as client:
            health_resp = await client._client.get("/health")
            health_resp.raise_for_status()
            gateway_status = "online"
    except Exception:
        gateway_status = "offline"

    lines = [
        "*NEXUS System Status*",
        "",
        f"Time: `{escape_markdown_v2(now)}`",
        f"Bot: online",
        f"Gateway: {gateway_status}",
        "",
        "_详细状态信息即将推出\\.\\.\\._",
    ]
    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="MarkdownV2",
    )


# ---------------------------------------------------------------------------
# /escalate — escalate to a higher-level agent
# ---------------------------------------------------------------------------

async def cmd_escalate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Escalate the current conversation to a more capable model."""
    reason = " ".join(context.args) if context.args else None
    user = update.effective_user

    if reason:
        body = escape_markdown_v2(reason)
        text = (
            f"*Escalation Requested*\n\n"
            f"From: @{escape_markdown_v2(user.username or str(user.id))}\n"
            f"Reason: {body}\n\n"
            f"_Routing to a higher\\-level agent\\.\\.\\._"
        )
    else:
        text = (
            f"*Escalation Requested*\n\n"
            f"From: @{escape_markdown_v2(user.username or str(user.id))}\n\n"
            f"_Routing to a higher\\-level agent\\.\\.\\._\n\n"
            f"Tip: `/escalate <reason>` to include context\\."
        )

    await update.effective_message.reply_text(text, parse_mode="MarkdownV2")

    # TODO: once the gateway/agent layer is wired, publish an escalation
    # work order to Redis Streams here.
    logger.info(
        "Escalation requested by user %s (chat %s). reason=%s",
        user.id if user else "?",
        update.effective_chat.id,
        reason or "(none)",
    )


# ---------------------------------------------------------------------------
# /cost — token usage & cost summary
# ---------------------------------------------------------------------------

async def cmd_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display token usage and estimated cost."""
    lines = [
        "*NEXUS Cost Summary*",
        "",
        "```",
        "Period        Tokens (in/out)     Cost",
        "─────────────────────────────────────────",
        "Today         –                   $0.00",
        "This week     –                   $0.00",
        "This month    –                   $0.00",
        "```",
        "",
        "_成本查询功能即将推出\\.\\.\\._",
    ]
    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="MarkdownV2",
    )


# ---------------------------------------------------------------------------
# /audit — recent audit log
# ---------------------------------------------------------------------------

async def cmd_audit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the latest audit log entries."""
    lines = [
        "*NEXUS Audit Log*",
        "",
        "_审计日志查询功能即将推出\\.\\.\\._",
        "",
        "Usage: `/audit` shows the last 10 entries\\.",
    ]
    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="MarkdownV2",
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

async def set_bot_commands(app: Application) -> None:
    """Set the Telegram command menu (call after bot.initialize)."""
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Telegram bot commands menu set: %s", [c.command for c in BOT_COMMANDS])


def register_commands(app: Application) -> None:
    """Register all NEXUS slash commands on the Application."""
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("escalate", cmd_escalate))
    app.add_handler(CommandHandler("cost", cmd_cost))
    app.add_handler(CommandHandler("audit", cmd_audit))
    logger.debug("Command handlers registered: /status /escalate /cost /audit")
