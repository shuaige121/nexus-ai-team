"""FastAPI dashboard app for AgentOffice."""

import hmac
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from dashboard.backend.db import init_db
from dashboard.backend.routes import (
    activate,
    agents,
    analytics,
    contracts,
    departments,
    org,
    settings,
)
from dashboard.backend.ws import ws_endpoint

logger = logging.getLogger("dashboard.auth")

# M8: Paths that skip bearer token auth
_DASHBOARD_PUBLIC_PATHS: set[str] = {"/health", "/docs", "/openapi.json", "/redoc"}


class DashboardAuthMiddleware:
    """Simple bearer token middleware checking API_SECRET."""

    def __init__(self, app):
        self.app = app
        self.api_secret = os.getenv("API_SECRET", "")

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Skip auth for public paths and non-API routes (static files, frontend)
        if path in _DASHBOARD_PUBLIC_PATHS or not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        # If no API_SECRET configured, allow all (dev mode)
        if not self.api_secret:
            await self.app(scope, receive, send)
            return

        # Extract bearer token from headers
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        token = None
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:]

        if not token or not hmac.compare_digest(token.encode(), self.api_secret.encode()):
            if scope["type"] == "http":
                response = JSONResponse({"detail": "Unauthorized"}, status_code=401)
                await response(scope, receive, send)
                return
            # For websocket, just close
            await send({"type": "websocket.close", "code": 4001})
            return

        await self.app(scope, receive, send)


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

# M8: Auth middleware
app.add_middleware(DashboardAuthMiddleware)

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
