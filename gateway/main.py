"""NEXUS Gateway — FastAPI entry point.

Run with:
    uvicorn gateway.main:app --reload
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from gateway.auth import AuthMiddleware
from gateway.config import settings
from gateway.rate_limiter import RateLimiterMiddleware
from gateway.schemas import HealthResponse
from gateway.ws import manager

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("gateway")


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hooks
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("NEXUS Gateway starting on %s:%s", settings.host, settings.port)
    if not settings.api_secret:
        logger.warning("API_SECRET not set — auth is DISABLED (dev mode)")
    yield
    logger.info("NEXUS Gateway shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="NEXUS Gateway",
    version="0.1.0",
    description="Neural Executive Unified System — API Gateway",
    lifespan=lifespan,
)

# --- Middleware (order matters: last added = first executed) ---

# 1. CORS — outermost
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Rate limiter
app.add_middleware(RateLimiterMiddleware)

# 3. Auth — innermost (runs first on request)
app.add_middleware(AuthMiddleware)


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    return HealthResponse()


@app.post("/api/chat", tags=["chat"])
async def chat(message: dict):
    """
    Process user message through complete Phase 2A execution pipeline.
    Flow: Admin → Route → Execute (with escalation) → QA → Return
    """
    content = message.get("content", "")
    if not content:
        return {"ok": False, "error": "Empty message"}

    # Import here to avoid circular dependencies
    from agents.execution.pipeline import ExecutionPipeline

    # Optional conversation history
    conversation = message.get("conversation", [])

    # Process through complete pipeline
    try:
        pipeline = ExecutionPipeline()
        result = await pipeline.process(content, conversation or None)

        response = {
            "ok": result.success,
            "work_order_id": result.work_order_id,
            "output": result.output,
            "qa_passed": result.qa_passed,
            "escalation": result.escalation_info,
        }

        # If Board intervention needed, include notification
        if result.board_notification:
            response["board_notification"] = result.board_notification
            response["requires_board"] = True

        return response

    except Exception as exc:
        logger.exception("Pipeline execution failed")
        return {
            "ok": False,
            "error": f"Pipeline error: {str(exc)}",
        }


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    conn_id = uuid.uuid4().hex[:12]

    connected = await manager.connect(conn_id, websocket)
    if not connected:
        return

    try:
        while True:
            raw = await websocket.receive_text()
            await manager.handle_message(conn_id, raw)
    except WebSocketDisconnect:
        manager.disconnect(conn_id)
    except Exception:
        logger.exception("WS error for %s", conn_id)
        manager.disconnect(conn_id)
