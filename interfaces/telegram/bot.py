"""Telegram bot — initialization, polling and webhook modes.

Usage::

    from interfaces.telegram.bot import create_telegram_bot

    bot_instance = create_telegram_bot()

    # Polling (development)
    await bot_instance.start()

    # Webhook (production)
    await bot_instance.start(mode="webhook", webhook_url="https://example.com/telegram/webhook")
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Literal

from telegram import Update
from telegram.ext import Application, ApplicationBuilder

from .commands import register_commands, set_bot_commands
from .handlers import register_handlers

logger = logging.getLogger(__name__)

RunMode = Literal["polling", "webhook"]

DEFAULT_WEBHOOK_PATH = "/telegram/webhook"
DEFAULT_WEBHOOK_HOST = "0.0.0.0"
DEFAULT_WEBHOOK_PORT = 8443


@dataclass
class WebhookConfig:
    """Configuration for webhook mode."""

    url: str
    path: str = DEFAULT_WEBHOOK_PATH
    host: str = DEFAULT_WEBHOOK_HOST
    port: int = DEFAULT_WEBHOOK_PORT
    secret_token: str | None = None


@dataclass
class TelegramBotInstance:
    """Holds the built Application and provides start/stop helpers."""

    app: Application
    mode: RunMode = "polling"
    _running: bool = field(default=False, init=False, repr=False)

    async def start(
        self,
        *,
        mode: RunMode = "polling",
        drop_pending_updates: bool = False,
        webhook: WebhookConfig | None = None,
        webhook_url: str | None = None,
    ) -> None:
        """Start the bot in the specified mode.

        Parameters
        ----------
        mode:
            ``"polling"`` for long-polling (dev), ``"webhook"`` for HTTP webhook (prod).
        drop_pending_updates:
            Whether to discard updates that arrived while the bot was offline.
        webhook:
            Full webhook configuration. Required when *mode* is ``"webhook"``
            unless *webhook_url* is provided as a shortcut.
        webhook_url:
            Shortcut — if given and *webhook* is ``None``, a :class:`WebhookConfig` is
            built with defaults.
        """
        self.mode = mode

        await self.app.initialize()
        await set_bot_commands(self.app)
        await self.app.start()

        if mode == "polling":
            await self._start_polling(drop_pending_updates)
        else:
            cfg = webhook or (WebhookConfig(url=webhook_url) if webhook_url else None)
            if cfg is None:
                raise ValueError("Webhook mode requires webhook_url or a WebhookConfig.")
            await self._start_webhook(cfg, drop_pending_updates)

        self._running = True
        logger.info("Telegram bot started in %s mode", mode)

    async def stop(self) -> None:
        """Gracefully shut down the bot."""
        if not self._running:
            return

        if self.app.updater.running:
            await self.app.updater.stop()

        await self.app.stop()
        await self.app.shutdown()
        self._running = False
        logger.info("Telegram bot stopped")

    # -- private helpers -----------------------------------------------------

    async def _start_polling(self, drop_pending_updates: bool) -> None:
        """Delete any existing webhook and start long-polling."""
        await self.app.bot.delete_webhook(drop_pending_updates=drop_pending_updates)
        await self.app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=drop_pending_updates,
        )
        logger.info("Polling started")

    async def _start_webhook(self, cfg: WebhookConfig, drop_pending_updates: bool) -> None:
        """Set the Telegram webhook and start the local HTTP listener."""
        webhook_url = cfg.url.rstrip("/") + cfg.path

        await self.app.bot.set_webhook(
            url=webhook_url,
            secret_token=cfg.secret_token,
            drop_pending_updates=drop_pending_updates,
            allowed_updates=Update.ALL_TYPES,
        )
        await self.app.updater.start_webhook(
            listen=cfg.host,
            port=cfg.port,
            url_path=cfg.path.lstrip("/"),
            webhook_url=webhook_url,
            secret_token=cfg.secret_token,
        )
        logger.info("Webhook started at %s (listen %s:%d)", webhook_url, cfg.host, cfg.port)


def _resolve_token(token: str | None = None) -> str:
    """Resolve the bot token from argument or environment variable."""
    resolved = (token or "").strip() or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not resolved:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is required. "
            "Set it as an environment variable or pass it to create_telegram_bot()."
        )
    return resolved


def create_telegram_bot(
    token: str | None = None,
    *,
    on_message=None,
) -> TelegramBotInstance:
    """Build a fully-configured :class:`TelegramBotInstance`.

    Parameters
    ----------
    token:
        Bot token. Falls back to ``TELEGRAM_BOT_TOKEN`` env var.
    on_message:
        Optional async callback ``(update, context, inbound_message) -> None``
        invoked for every parsed inbound message. When ``None`` the built-in
        echo handler is used.
    """
    resolved_token = _resolve_token(token)

    app = (
        ApplicationBuilder()
        .token(resolved_token)
        .concurrent_updates(True)
        .build()
    )

    register_commands(app)
    register_handlers(app, on_message=on_message)

    # Global error handler
    app.add_error_handler(_error_handler)

    return TelegramBotInstance(app=app)


async def _error_handler(update: object, context) -> None:
    """Log unhandled errors from handlers."""
    logger.error("Unhandled Telegram bot error: %s", context.error, exc_info=context.error)
