"""WebSocket handler for real-time dashboard updates."""

import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


class DashboardWSManager:
    """Manages WebSocket connections for dashboard live updates."""

    def __init__(self):
        self.connections: list[WebSocket] = []
        self._seq = 0

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
        await self._send(ws, {
            "type": "event",
            "event": "connected",
            "payload": {"message": "已连接到实时更新频道"},
            "seq": self._next_seq()
        })

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, event: str, payload: dict[str, Any]):
        frame = {
            "type": "event",
            "event": event,
            "payload": payload,
            "seq": self._next_seq()
        }
        dead = []
        for ws in self.connections:
            try:
                await self._send(ws, frame)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def _send(self, ws: WebSocket, data: dict):
        await ws.send_json(data)

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq


manager = DashboardWSManager()


async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)
