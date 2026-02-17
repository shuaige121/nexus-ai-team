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

    async def broadcast_health_status(self, health_report: dict) -> None:
        """Broadcast health status change to all connected clients."""
        await self.broadcast("health.update", health_report)

    # --- internal helpers ---

    async def _dispatch_request(self, ws: WebSocket, req: WSRequest) -> None:
        """Route a request to the appropriate handler."""
        from gateway.main import admin_agent, db, queue

        method = req.method

        if method == "ping":
            await self._send_response(ws, req.id, ok=True, payload={"pong": True})
        elif method == "chat.send":
            if not admin_agent or not db or not queue:
                await self._send_response(ws, req.id, ok=False, error="Pipeline not initialized")
                return

            try:
                user_message = req.params.get("content", "")
                if not user_message:
                    await self._send_response(ws, req.id, ok=False, error="Empty message")
                    return

                # Create work order
                wo = admin_agent.create_work_order(user_message=user_message)

                # Store in DB
                await db.create_work_order(
                    wo_id=wo.id,
                    intent=wo.intent,
                    difficulty=wo.difficulty,
                    owner=wo.owner,
                    compressed_context=wo.compressed_context,
                    relevant_files=wo.relevant_files,
                    qa_requirements=wo.qa_requirements,
                )

                # Enqueue
                await queue.enqueue(
                    wo.id,
                    {
                        "user_message": user_message,
                        "conversation": req.params.get("conversation", []),
                        "session_id": req.params.get("session_id"),
                    },
                )

                await self._send_response(
                    ws,
                    req.id,
                    ok=True,
                    payload={"work_order_id": wo.id, "difficulty": wo.difficulty, "owner": wo.owner},
                )
                await self._send_event(
                    ws,
                    "chat.ack",
                    {"work_order_id": wo.id, "status": "queued"},
                )
            except Exception as e:
                logger.exception("Failed to process chat.send")
                await self._send_response(ws, req.id, ok=False, error=str(e))
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
