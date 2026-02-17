"""Gateway API client for Telegram bot."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class GatewayClient:
    """HTTP client for NEXUS Gateway API."""

    def __init__(self, base_url: str = "http://localhost:8000", api_secret: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_secret = api_secret
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        headers = {}
        if self.api_secret:
            headers["Authorization"] = f"Bearer {self.api_secret}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=60.0,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send_message(
        self, content: str, conversation: list[dict[str, str]] | None = None
    ) -> dict[str, Any]:
        """Send a message to the gateway."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        payload = {"content": content}
        if conversation:
            payload["conversation"] = conversation

        try:
            resp = await self._client.post("/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error("Gateway API error: %s", e)
            return {"ok": False, "error": str(e)}
