"""Telegram MarkdownV2 escaping and text splitting utilities."""

from __future__ import annotations

import re

_MARKDOWN_V2_SPECIAL = re.compile(r"([_*\[\]()~`>#+\-=|{}.!])")

TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2 parse mode."""
    return _MARKDOWN_V2_SPECIAL.sub(r"\\\1", text)


def split_telegram_text(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """Split long text into Telegram-safe chunks (max 4096 chars each).

    Tries to break on newline boundaries when possible.
    """
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    cursor = 0

    while cursor < len(text):
        remaining = len(text) - cursor
        if remaining <= max_length:
            chunks.append(text[cursor:])
            break

        window_end = cursor + max_length
        window_text = text[cursor:window_end]
        last_newline = window_text.rfind("\n")
        cut = cursor + last_newline if last_newline > 0 else window_end
        chunks.append(text[cursor:cut])
        cursor = cut

    return chunks
