"""FastAPI dashboard app for AgentOffice."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from dashboard.backend.db import init_db
from dashboard.backend.ws import ws_endpoint
from dashboard.backend.routes import org, agents, contracts, analytics, activate, departments, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("AgentOffice Dashboard 启动完成")
    yield
    print("AgentOffice Dashboard 关闭")


app = FastAPI(
    title="AgentOffice Dashboard",
    description="AgentOffice 可视化管理仪表盘 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(org.router)
app.include_router(agents.router)
app.include_router(contracts.router)
app.include_router(analytics.router)
app.include_router(activate.router)
app.include_router(departments.router)
app.include_router(settings.router)

# WebSocket
app.websocket("/ws/live")(ws_endpoint)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agentoffice-dashboard"}


# Serve frontend static files in production
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
