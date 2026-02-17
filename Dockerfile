# ══════════════════════════════════════════════════════════════════════════════
# NEXUS Gateway — Multi-stage Dockerfile
# ══════════════════════════════════════════════════════════════════════════════
#
# Stages:
#   1. base       — Common Python dependencies
#   2. builder    — Install application dependencies
#   3. production — Minimal runtime image
#   4. development — Dev mode with hot reload
#
# Build examples:
#   docker build -t nexus-gateway:latest .
#   docker build --target development -t nexus-gateway:dev .
#

# ── Stage 1: Base ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Stage 2: Builder ──────────────────────────────────────────────────────────
FROM base AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e .

# ── Stage 3: Production ───────────────────────────────────────────────────────
FROM base AS production

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY gateway ./gateway
COPY nexus_v1 ./nexus_v1
COPY pipeline ./pipeline
COPY db ./db
COPY agents ./agents
COPY interfaces ./interfaces
COPY equipment ./equipment
COPY company ./company
COPY agentoffice ./agentoffice
COPY qa ./qa
COPY heartbeat ./heartbeat
COPY dashboard ./dashboard

# Create non-root user
RUN useradd -m -u 1000 nexus && \
    chown -R nexus:nexus /app

USER nexus

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Stage 4: Development ──────────────────────────────────────────────────────
FROM builder AS development

# Install development dependencies
RUN pip install --no-cache-dir \
    ruff \
    pytest \
    pytest-asyncio \
    ipython

# Copy application code (will be overridden by volume mount in dev)
COPY . .

# Development runs as root for easier file permissions with volume mounts
USER root

EXPOSE 8000

# Run with auto-reload for development
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
