"""NEXUS Gateway — FastAPI entry point.

Run with:
    uvicorn gateway.main:app --reload
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from gateway.auth import AuthMiddleware
from gateway.config import settings
from gateway.rate_limiter import RateLimiterMiddleware
from gateway.schemas import HealthResponse
from gateway.ws import manager
from gateway.skill_registry import SkillRegistry
from nexus_v1.admin import AdminAgent
from nexus_v1.model_router import ModelRouter
from pipeline import Dispatcher, QueueManager, WorkOrderDB

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("gateway")

# ---------------------------------------------------------------------------
# Pydantic request / response models for POST endpoints (H4)
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    agent: str = Field(default="ceo")


class WorkOrderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="")
    priority: str = Field(default="medium", pattern=r"^(low|medium|high|critical)$")
    assigned_to: str | None = None


class WorkOrderUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(pending|in_progress|completed|failed|cancelled)$")


class ErrorResponse(BaseModel):
    ok: bool = False
    error: str
    request_id: str | None = None


# ---------------------------------------------------------------------------
# Request-ID middleware (M6)
# ---------------------------------------------------------------------------


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique UUID4 request-id to every HTTP request/response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# Global pipeline components
db: WorkOrderDB | None = None
queue: QueueManager | None = None
dispatcher: Dispatcher | None = None
admin_agent: AdminAgent | None = None
health_broadcast_task: asyncio.Task | None = None


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hooks
# ---------------------------------------------------------------------------


async def health_broadcast_loop():
    """Background task to periodically broadcast health status via WebSocket."""
    await asyncio.sleep(10)  # Wait for startup

    while True:
        try:
            # Only broadcast if there are active WebSocket connections
            if manager.active_count > 0:
                health_report = {
                    "timestamp": datetime.now().isoformat(),
                    "gateway": {"status": "healthy", "message": "Gateway responding"},
                    "redis": {"status": "unknown", "message": "Not checked"},
                    "postgres": {"status": "unknown", "message": "Not checked"},
                }

                # Check Redis
                if queue:
                    try:
                        await queue._redis.ping()
                        health_report["redis"] = {
                            "status": "healthy",
                            "message": "Redis connected",
                        }
                    except Exception:
                        health_report["redis"] = {
                            "status": "critical",
                            "message": "Redis unreachable",
                        }

                # Check PostgreSQL via connection pool (M4)
                if db:
                    try:
                        async with db.get_connection() as conn:
                            async with conn.cursor() as cur:
                                await cur.execute("SELECT 1")
                        health_report["postgres"] = {
                            "status": "healthy",
                            "message": "PostgreSQL connected",
                        }
                    except Exception:
                        health_report["postgres"] = {
                            "status": "critical",
                            "message": "PostgreSQL unreachable",
                        }

                # Broadcast to WebSocket clients
                await manager.broadcast_health_status(health_report)

        except Exception:
            logger.exception("Error in health broadcast loop")

        await asyncio.sleep(60)  # Check every 60 seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, queue, dispatcher, admin_agent, health_broadcast_task

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

        admin_agent = AdminAgent(router=router, use_llm=False)

        # Start health broadcast task
        health_broadcast_task = asyncio.create_task(health_broadcast_loop())

        logger.info("Pipeline initialized and dispatcher started")
    except Exception:
        logger.exception("Failed to initialize pipeline")

    yield

    # Cleanup
    if health_broadcast_task:
        health_broadcast_task.cancel()
        try:
            await health_broadcast_task
        except asyncio.CancelledError:
            pass
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

# 3. Request ID (M6)
app.add_middleware(RequestIDMiddleware)

# 4. Auth — innermost (runs first on request)
app.add_middleware(AuthMiddleware)


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    return HealthResponse()


@app.get("/api/health/detailed", tags=["system"])
async def detailed_health():
    """Detailed system health check for monitoring."""
    health_report = {
        "timestamp": datetime.now().isoformat(),
        "gateway": {"status": "healthy", "message": "Gateway responding"},
        "redis": {"status": "unknown", "message": "Not checked"},
        "postgres": {"status": "unknown", "message": "Not checked"},
        "agents": {"status": "unknown", "message": "Not checked"},
        "metrics": {},
    }

    # Check Redis
    if queue:
        try:
            await queue._redis.ping()
            info = await queue._redis.info("memory")
            used_memory_mb = info.get("used_memory", 0) / 1024 / 1024
            health_report["redis"] = {
                "status": "healthy",
                "message": "Redis connected",
                "used_memory_mb": round(used_memory_mb, 2),
            }
        except Exception as e:
            health_report["redis"] = {
                "status": "critical",
                "message": f"Redis error: {e}",
            }

    # Check PostgreSQL via connection pool (M4)
    if db:
        try:
            async with db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT COUNT(*) FROM work_orders WHERE status = 'in_progress'"
                    )
                    result = await cur.fetchone()
                    in_progress_count = result[0] if result else 0

                    await cur.execute("SELECT COUNT(*) FROM work_orders")
                    result = await cur.fetchone()
                    total_count = result[0] if result else 0

            health_report["postgres"] = {
                "status": "healthy",
                "message": "PostgreSQL connected",
                "work_orders_total": total_count,
                "work_orders_in_progress": in_progress_count,
            }

            # Check for stale work orders
            async with db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT COUNT(*) FROM work_orders"
                        " WHERE status = 'in_progress'"
                        " AND updated_at < NOW() - INTERVAL '5 minutes'"
                    )
                    result = await cur.fetchone()
                    stale_count = result[0] if result else 0

            if stale_count > 0:
                health_report["agents"] = {
                    "status": "degraded",
                    "message": f"{stale_count} agent(s) may be stuck",
                    "stale_work_orders": stale_count,
                }
            else:
                health_report["agents"] = {
                    "status": "healthy",
                    "message": "Agents active",
                }

        except Exception as e:
            health_report["postgres"] = {
                "status": "critical",
                "message": f"PostgreSQL error: {e}",
            }

    # Add system metrics
    try:
        cost_summary = await db.get_cost_summary(period="today") if db else {}
        health_report["metrics"] = {
            "tokens_today": cost_summary.get("total_tokens", 0),
            "cost_today_usd": cost_summary.get("total_cost", 0),
        }
    except Exception:
        pass

    # Determine overall status
    statuses = [
        health_report["gateway"]["status"],
        health_report["redis"]["status"],
        health_report["postgres"]["status"],
        health_report["agents"]["status"],
    ]

    if any(s == "critical" for s in statuses):
        overall_status = "critical"
    elif any(s == "degraded" for s in statuses):
        overall_status = "degraded"
    elif all(s == "healthy" for s in statuses if s != "unknown"):
        overall_status = "healthy"
    else:
        overall_status = "unknown"

    health_report["overall_status"] = overall_status

    return health_report


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
                "status": "active",
            })
        return {"ok": True, "agents": result}
    except Exception as e:
        logger.exception("Failed to list agents")
        return {"ok": False, "error": str(e)}


@app.get("/api/skills", tags=["skills"])
async def list_skills():
    """List all installed Nexus skills and their capabilities."""
    try:
        sr = SkillRegistry()
        skills = sr.list_skills()
        capabilities = sr.get_capabilities()
        return {
            "ok": True,
            "skills": skills,
            "capabilities": capabilities,
            "count": len(skills),
        }
    except Exception as e:
        logger.exception("Failed to list skills")
        return {"ok": False, "error": str(e)}


@app.get("/api/work-orders", tags=["work-orders"])
async def list_work_orders(
    status: str | None = None, owner: str | None = None, limit: int = 50
):
    """Query work orders with optional filtering by status and owner."""
    if not db:
        return {"ok": False, "error": "Database not initialized"}

    try:
        query = "SELECT * FROM work_orders WHERE 1=1"
        params: list = []

        if status:
            query += " AND status = %s"
            params.append(status)

        if owner:
            query += " AND owner = %s"
            params.append(owner)

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        async with db.get_connection() as conn:
            async with conn.cursor() as cur:
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
        cost_summary = await db.get_cost_summary(period=period)
        system_status = await db.get_system_status()
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
async def chat(body: ChatRequest):
    """HTTP fallback for sending a chat message (non-WebSocket clients)."""
    if not admin_agent or not db or not queue:
        return {"ok": False, "error": "Pipeline not initialized"}

    try:
        wo = admin_agent.create_work_order(user_message=body.content)

        await db.create_work_order(
            wo_id=wo.id,
            intent=wo.intent,
            difficulty=wo.difficulty,
            owner=wo.owner,
            compressed_context=wo.compressed_context,
            relevant_files=wo.relevant_files,
            qa_requirements=wo.qa_requirements,
        )

        await queue.enqueue(
            wo.id,
            {
                "user_message": body.content,
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
