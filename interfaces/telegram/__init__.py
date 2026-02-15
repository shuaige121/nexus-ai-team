"""NEXUS Telegram bot interface.

Quick start::

    from interfaces.telegram import create_telegram_bot

    bot = create_telegram_bot()
    await bot.start()           # polling mode (dev)
    await bot.start(mode="webhook", webhook_url="https://example.com")  # prod
    await bot.stop()
"""

from .bot import RunMode, TelegramBotInstance, WebhookConfig, create_telegram_bot
from .commands import BOT_COMMANDS
from .format import escape_markdown_v2, split_telegram_text
from .handlers import InboundMessage, OnMessageCallback, parse_inbound_message

__all__ = [
    "create_telegram_bot",
    "TelegramBotInstance",
    "WebhookConfig",
    "RunMode",
    "InboundMessage",
    "parse_inbound_message",
    "OnMessageCallback",
    "BOT_COMMANDS",
    "escape_markdown_v2",
    "split_telegram_text",
]
