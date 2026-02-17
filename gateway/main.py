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
from nexus_v1.admin import AdminAgent
from nexus_v1.model_router import ModelRouter
from pipeline import Dispatcher, QueueManager, WorkOrderDB

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("gateway")

# Global pipeline components
db: WorkOrderDB | None = None
queue: QueueManager | None = None
dispatcher: Dispatcher | None = None
admin_agent: AdminAgent | None = None


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hooks
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, queue, dispatcher, admin_agent

    logger.info("NEXUS Gateway starting on %s:%s", settings.host, settings.port)
    if not settings.api_secret:
        logger.warning("API_SECRET not set — auth is DISABLED (dev mode)")

    # Initialize pipeline
    try:
        db = WorkOrderDB(settings.database_url)
        await db.connect()

        queue = QueueManager(settings.redis_url)
        await queue.connect()

        router = ModelRouter()
        dispatcher = Dispatcher(db, queue, router)
        await dispatcher.start()

        admin_agent = AdminAgent(router=router, use_llm=False)  # LLM disabled for faster startup

        logger.info("Pipeline initialized and dispatcher started")
    except Exception:
        logger.exception("Failed to initialize pipeline")

    yield

    # Cleanup
    if dispatcher:
        await dispatcher.stop()
    if queue:
        await queue.close()
    if db:
        await db.close()

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


@app.get("/api/agents", tags=["agents"])
async def list_agents():
    """List all agents and their current status."""
    from nexus_v1.config import get_tiered_payroll_models

    try:
        agents = get_tiered_payroll_models()
        result = []
        for role, target in agents.items():
            result.append({
                "id": role,
                "role": role,
                "model": target.model,
                "provider": target.provider,
                "max_tokens": target.max_tokens,
                "temperature": target.temperature,
                "status": "active",  # Could be extended with real status tracking
            })
        return {"ok": True, "agents": result}
    except Exception as e:
        logger.exception("Failed to list agents")
        return {"ok": False, "error": str(e)}


@app.get("/api/work-orders", tags=["work-orders"])
async def list_work_orders(status: str | None = None, owner: str | None = None, limit: int = 50):
    """Query work orders with optional filtering by status and owner."""
    if not db:
        return {"ok": False, "error": "Database not initialized"}

    try:
        query = "SELECT * FROM work_orders WHERE 1=1"
        params = []

        if status:
            query += " AND status = %s"
            params.append(status)

        if owner:
            query += " AND owner = %s"
            params.append(owner)

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        async with db._conn.cursor() as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()

        return {"ok": True, "work_orders": rows, "count": len(rows)}
    except Exception as e:
        logger.exception("Failed to query work orders")
        return {"ok": False, "error": str(e)}


@app.get("/api/metrics", tags=["metrics"])
async def get_metrics(period: str = "today"):
    """Get system metrics including token usage, request count, and costs."""
    if not db:
        return {"ok": False, "error": "Database not initialized"}

    try:
        # Get cost summary
        cost_summary = await db.get_cost_summary(period=period)

        # Get system status
        system_status = await db.get_system_status()

        # Get recent audit logs for request count
        audit_logs = await db.get_recent_audit_logs(limit=100)

        return {
            "ok": True,
            "period": period,
            "token_usage": {
                "prompt_tokens": cost_summary["prompt_tokens"],
                "completion_tokens": cost_summary["completion_tokens"],
                "total_tokens": cost_summary["total_tokens"],
            },
            "cost": {
                "total_usd": cost_summary["total_cost"],
            },
            "work_orders": system_status["work_orders"],
            "request_count": len(audit_logs),
            "timestamp": system_status["timestamp"],
        }
    except Exception as e:
        logger.exception("Failed to get metrics")
        return {"ok": False, "error": str(e)}


@app.post("/api/chat", tags=["chat"])
async def chat(message: dict):
    """HTTP fallback for sending a chat message (non-WebSocket clients)."""
    content = message.get("content", "")
    if not content:
        return {"ok": False, "error": "Empty message"}

    if not admin_agent or not db or not queue:
        return {"ok": False, "error": "Pipeline not initialized"}

    try:
        # Create work order via Admin agent
        wo = admin_agent.create_work_order(user_message=content)

        # Store work order in DB
        await db.create_work_order(
            wo_id=wo.id,
            intent=wo.intent,
            difficulty=wo.difficulty,
            owner=wo.owner,
            compressed_context=wo.compressed_context,
            relevant_files=wo.relevant_files,
            qa_requirements=wo.qa_requirements,
        )

        # Enqueue to Redis Streams
        await queue.enqueue(
            wo.id,
            {
                "user_message": content,
                "conversation": [],
                "session_id": None,
            },
        )

        return {
            "ok": True,
            "work_order_id": wo.id,
            "difficulty": wo.difficulty,
            "owner": wo.owner,
        }
    except Exception as e:
        logger.exception("Failed to process chat message")
        return {"ok": False, "error": str(e)}


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
