"""WebSocket connection manager and endpoint handler."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import WebSocket

from gateway.auth import verify_ws_token
from gateway.schemas import WSEvent, WSRequest, WSResponse

logger = logging.getLogger("gateway.ws")


class ConnectionManager:
    """Track active WebSocket connections and broadcast events."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._seq: int = 0

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def connect(self, conn_id: str, websocket: WebSocket) -> bool:
        """Authenticate and accept a WebSocket connection."""
        if not await verify_ws_token(websocket):
            await websocket.close(code=4001, reason="Unauthorized")
            return False

        await websocket.accept()
        self._connections[conn_id] = websocket
        logger.info("WS connected: %s (total: %d)", conn_id, self.active_count)

        # Send welcome event
        await self._send_event(
            websocket,
            "connected",
            {"conn_id": conn_id, "server_time": datetime.utcnow().isoformat()},
        )
        return True

    def disconnect(self, conn_id: str) -> None:
        self._connections.pop(conn_id, None)
        logger.info("WS disconnected: %s (total: %d)", conn_id, self.active_count)

    async def handle_message(self, conn_id: str, raw: str) -> None:
        """Parse incoming frame and dispatch."""
        ws = self._connections.get(conn_id)
        if not ws:
            return

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_response(ws, "?", ok=False, error="Invalid JSON")
            return

        frame_type = data.get("type")

        if frame_type == "req":
            req = WSRequest(**data)
            await self._dispatch_request(ws, req)
        else:
            await self._send_response(ws, data.get("id", "?"), ok=False, error="Unknown frame type")

    async def broadcast(self, event: str, payload: dict | None = None) -> None:
        """Send an event to all connected clients."""
        self._seq += 1
        frame = WSEvent(event=event, payload=payload or {}, seq=self._seq)
        dead: list[str] = []
        for conn_id, ws in self._connections.items():
            try:
                await ws.send_text(frame.model_dump_json())
            except Exception:
                dead.append(conn_id)
        for cid in dead:
            self.disconnect(cid)

    # --- internal helpers ---

    async def _dispatch_request(self, ws: WebSocket, req: WSRequest) -> None:
        """Route a request to the appropriate handler."""
        method = req.method

        if method == "ping":
            await self._send_response(ws, req.id, ok=True, payload={"pong": True})
        elif method == "chat.send":
            # Placeholder — will be wired to the agent pipeline
            await self._send_response(
                ws,
                req.id,
                ok=True,
                payload={"message": "Received. Processing via agent pipeline..."},
            )
            await self._send_event(
                ws,
                "chat.ack",
                {"request_id": req.id, "status": "queued"},
            )
        else:
            await self._send_response(ws, req.id, ok=False, error=f"Unknown method: {method}")

    async def _send_response(
        self,
        ws: WebSocket,
        req_id: str,
        *,
        ok: bool,
        payload: dict | None = None,
        error: str | None = None,
    ) -> None:
        resp = WSResponse(id=req_id, ok=ok, payload=payload, error=error)
        await ws.send_text(resp.model_dump_json())

    async def _send_event(self, ws: WebSocket, event: str, payload: dict) -> None:
        self._seq += 1
        frame = WSEvent(event=event, payload=payload, seq=self._seq)
        await ws.send_text(frame.model_dump_json())


manager = ConnectionManager()
