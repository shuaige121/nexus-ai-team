"""WebSocket connection manager and endpoint handler."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections import deque
from datetime import UTC, datetime

from fastapi import WebSocket

from gateway.auth import verify_ws_token
from gateway.schemas import WSEvent, WSRequest, WSResponse

logger = logging.getLogger("gateway.ws")

# Rate limiting constants
MAX_MESSAGES_PER_MINUTE: int = 30
RATE_WINDOW_SECONDS: float = 60.0
MAX_PAYLOAD_BYTES: int = 64 * 1024  # 64 KB

# Ping/pong constants
PING_INTERVAL_SECONDS: float = 30.0
PONG_TIMEOUT_SECONDS: float = 10.0


class ConnectionManager:
    """Track active WebSocket connections and broadcast events."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._seq: int = 0
        self._message_timestamps: dict[str, deque[float]] = {}
        self._pong_waiters: dict[str, asyncio.Event] = {}
        self._keepalive_task: asyncio.Task | None = None

    def start_keepalive(self) -> None:
        """Start the background ping/pong keepalive task."""
        if self._keepalive_task is None or self._keepalive_task.done():
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    def stop_keepalive(self) -> None:
        """Cancel the keepalive task."""
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()

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
        self._message_timestamps[conn_id] = deque()
        logger.info("WS connected: %s (total: %d)", conn_id, self.active_count)

        # Send welcome event
        await self._send_event(
            websocket,
            "connected",
            {"conn_id": conn_id, "server_time": datetime.now(UTC).isoformat()},
        )

        # Auto-start keepalive when first connection arrives
        self.start_keepalive()
        return True

    def disconnect(self, conn_id: str) -> None:
        self._connections.pop(conn_id, None)
        self._message_timestamps.pop(conn_id, None)
        self._pong_waiters.pop(conn_id, None)
        logger.info("WS disconnected: %s (total: %d)", conn_id, self.active_count)

    def _check_rate_limit(self, conn_id: str) -> bool:
        """Return True if the connection is within rate limits."""
        now = time.monotonic()
        timestamps = self._message_timestamps.get(conn_id)
        if timestamps is None:
            return False

        # Evict timestamps outside the sliding window
        while timestamps and timestamps[0] < now - RATE_WINDOW_SECONDS:
            timestamps.popleft()

        if len(timestamps) >= MAX_MESSAGES_PER_MINUTE:
            return False

        timestamps.append(now)
        return True

    async def handle_message(self, conn_id: str, raw: str) -> None:
        """Parse incoming frame and dispatch."""
        ws = self._connections.get(conn_id)
        if not ws:
            return

        # Payload size check
        if len(raw.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            await self._send_response(
                ws, "?", ok=False,
                error=f"Payload too large (max {MAX_PAYLOAD_BYTES} bytes)",
            )
            self.disconnect(conn_id)
            await ws.close(code=1009, reason="Payload too large")
            return

        # Rate limit check
        if not self._check_rate_limit(conn_id):
            await self._send_response(
                ws, "?", ok=False,
                error=f"Rate limit exceeded ({MAX_MESSAGES_PER_MINUTE} msg/min)",
            )
            self.disconnect(conn_id)
            await ws.close(code=1008, reason="Rate limit exceeded")
            return

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_response(ws, "?", ok=False, error="Invalid JSON")
            return

        frame_type = data.get("type")

        if frame_type == "pong":
            # Handle pong response from client
            event = self._pong_waiters.get(conn_id)
            if event:
                event.set()
            return

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

    # --- keepalive ---

    async def _keepalive_loop(self) -> None:
        """Periodically ping all connections and remove dead ones."""
        try:
            while True:
                await asyncio.sleep(PING_INTERVAL_SECONDS)
                if not self._connections:
                    continue
                await self._ping_all()
        except asyncio.CancelledError:
            return

    async def _ping_all(self) -> None:
        """Send ping to every connection and wait for pong."""
        dead: list[str] = []
        tasks: list[tuple[str, asyncio.Task]] = []

        for conn_id, ws in list(self._connections.items()):
            event = asyncio.Event()
            self._pong_waiters[conn_id] = event
            try:
                ping_frame = json.dumps({"type": "ping", "ts": time.time()})
                await ws.send_text(ping_frame)
                task = asyncio.create_task(self._wait_pong(conn_id, event))
                tasks.append((conn_id, task))
            except Exception:
                dead.append(conn_id)

        for conn_id, task in tasks:
            responded = await task
            if not responded:
                dead.append(conn_id)

        for cid in dead:
            logger.info("Removing dead connection: %s (no pong)", cid)
            ws = self._connections.get(cid)
            self.disconnect(cid)
            if ws:
                with contextlib.suppress(Exception):
                    await ws.close(code=1001, reason="Ping timeout")

    async def _wait_pong(self, conn_id: str, event: asyncio.Event) -> bool:
        """Wait for a pong response within timeout. Returns True if received."""
        try:
            await asyncio.wait_for(event.wait(), timeout=PONG_TIMEOUT_SECONDS)
            return True
        except TimeoutError:
            return False
        finally:
            self._pong_waiters.pop(conn_id, None)

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
