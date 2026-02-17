# NEXUS — Neural Executive Unified System

> **An AI company that works for you.** Talk to your org via Telegram Bot or Web GUI. You're the Board of Directors.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

---

## 📋 Table of Contents

- [What Is NEXUS](#what-is-nexus)
- [Architecture](#architecture)
- [Features](#features)
- [Quick Start with Docker](#quick-start-with-docker)
- [Manual Installation](#manual-installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Development](#development)
- [Monitoring & Health Checks](#monitoring--health-checks)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## 🤖 What Is NEXUS

NEXUS is an **AI operating system** that runs like a real company. It has employees (LLMs), equipment (scripts and tools), and a management hierarchy — all working to serve one client: **you**.

### The Team

- **CEO** (Claude Opus 4.6) — Handles complex, strategic tasks
- **Director** (Claude Sonnet 4.5) — Handles normal, day-to-day tasks
- **Intern** (Claude Haiku 3.5) — Handles trivial, routine tasks
- **Admin** (Qwen3 8B, local) — Routes requests and compresses context for free

### Why NEXUS?

- ✅ **Cost-optimized**: Cheap models handle simple tasks, expensive models only for complex work
- ✅ **Scalable**: Redis queue + async pipeline handles high throughput
- ✅ **Observable**: Full logging, metrics, and audit trails in PostgreSQL
- ✅ **Production-ready**: Docker Compose, health checks, auto-recovery
- ✅ **Multi-channel**: Telegram, Web GUI, REST API, WebSocket

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User Interfaces                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  Telegram   │  │   Web GUI   │  │  REST API   │  │ WebSocket │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘ │
└─────────┼─────────────────┼─────────────────┼──────────────┼────────┘
          │                 │                 │              │
          └─────────────────┴─────────────────┴──────────────┘
                                      │
                    ┌─────────────────▼──────────────────┐
                    │      FastAPI Gateway              │
                    │  (Auth, Rate Limit, CORS, WS)     │
                    └─────────────────┬──────────────────┘
                                      │
                    ┌─────────────────▼──────────────────┐
                    │      Admin Agent (Qwen3 8B)       │
                    │  Compress Context + Classify      │
                    └─────────────────┬──────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
    ┌─────▼─────┐            ┌────────▼────────┐         ┌──────▼──────┐
    │  Intern   │            │    Director     │         │     CEO     │
    │  (Haiku)  │            │   (Sonnet 4.5)  │         │ (Opus 4.6)  │
    │ Trivial   │            │     Normal      │         │   Complex   │
    └─────┬─────┘            └────────┬────────┘         └──────┬──────┘
          │                           │                           │
          └───────────────────────────┼───────────────────────────┘
                                      │
                    ┌─────────────────▼──────────────────┐
                    │        QA Validation              │
                    │  (Format, Security, Completeness) │
                    └─────────────────┬──────────────────┘
                                      │
                              ┌───────▼────────┐
                              │    Deliver     │
                              │ or Retry (3x)  │
                              └────────────────┘

┌───────────────────────────────────────────────────────────────────────┐
│                         Infrastructure Layer                          │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  PostgreSQL  │  │    Redis     │  │   Ollama     │              │
│  │  (Metrics &  │  │  (Queue &    │  │  (Local LLM  │              │
│  │   Logging)   │  │   Cache)     │  │   Inference) │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└───────────────────────────────────────────────────────────────────────┘
```

### Request Flow

1. **User** sends a message via Telegram, Web GUI, or API
2. **Gateway** authenticates, rate-limits, and logs the request
3. **Admin Agent** (Qwen3, local, free) compresses context and classifies difficulty
4. **Router** assigns to appropriate employee: Intern (trivial) / Director (normal) / CEO (complex)
5. **Employee** executes the task, performs self-checks
6. **QA Validator** validates format, security, completeness
7. **Delivery** — if QA passes, deliver result. Otherwise retry up to 3 times

---

## ✨ Features

### Core Features
- ✅ **Tiered AI Agents**: Cost-optimized routing (Haiku → Sonnet → Opus)
- ✅ **Admin Agent**: Free local LLM (Qwen3 8B) for classification and context compression
- ✅ **Multi-channel**: Telegram Bot, Web GUI (React), REST API, WebSocket
- ✅ **Auth & Security**: JWT tokens, rate limiting, CORS, security validation
- ✅ **Async Pipeline**: Redis Streams for queueing, dispatcher with retry logic
- ✅ **Comprehensive Logging**: PostgreSQL with work orders, audit logs, metrics
- ✅ **QA Framework**: Automated validation (format, security, completeness checks)

### Phase 4A Features (Latest)
- ✅ **Heartbeat Monitoring**: Automated health checks for all services
- ✅ **Auto-recovery**: Restart services, cleanup disk, handle stuck agents
- ✅ **Telegram Alerts**: Real-time notifications for critical issues
- ✅ **Health Dashboard**: WebSocket-based live monitoring

### Phase 5 Features (Current)
- ✅ **Docker Compose**: Full-stack deployment with one command
- ✅ **Production-ready**: Multi-stage builds, health checks, minimal images
- ✅ **Makefile**: Simple commands for common operations
- ✅ **Comprehensive Docs**: Complete installation, configuration, API reference

---

## 🚀 Quick Start with Docker

### Prerequisites

- **Docker** 20.10+ and **Docker Compose** v2.0+
- **Git** for cloning the repository

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/nexus-ai-team.git
cd nexus-ai-team

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys and configuration
# REQUIRED: Set ANTHROPIC_API_KEY, JWT_SECRET, POSTGRES_PASSWORD, REDIS_PASSWORD

# 3. Start all services
make up

# Or manually:
docker compose up -d

# 4. Check service status
make ps

# 5. View logs
make logs
```

### Verify Installation

```bash
# Check health
make health

# Or manually:
curl http://localhost:8000/health
# Expected: {"status":"ok","timestamp":"..."}

# Access services
# Gateway API: http://localhost:8000
# Swagger docs: http://localhost:8000/docs
# Dashboard: http://localhost:3000
```

### Quick Commands

```bash
make up            # Start all services
make down          # Stop all services
make restart       # Restart services
make logs          # View all logs
make logs-gateway  # View gateway logs only
make ps            # Show running containers
make health        # Check service health
make build         # Build Docker images
make clean         # Stop and remove volumes (⚠️ deletes data)
```

---

## 🔧 Manual Installation

For development or when Docker is not available.

### Prerequisites

- **Python 3.12+**
- **PostgreSQL 16** (optional, falls back to SQLite)
- **Redis 7.2+** (optional)
- **Node.js 20+** (for Web GUI)
- **Ollama** (optional, for local Qwen3 model)

### Step 1: Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install NEXUS
pip install -e ".[dev]"
```

### Step 2: Start Infrastructure

```bash
# Option A: Docker Compose (recommended)
docker compose up -d postgres redis

# Option B: Manual PostgreSQL
sudo systemctl start postgresql
createdb nexus
psql nexus < db/schema.sql

# Option C: Automatic SQLite fallback
# If PostgreSQL is unavailable, NEXUS will automatically use SQLite
# No additional configuration needed!
```

### Step 3: Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### Step 4: Start Gateway

```bash
uvicorn gateway.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 5: Start Web GUI (Optional)

```bash
cd dashboard/frontend
npm install
npm run dev
```

### Step 6: Start Telegram Bot (Optional)

```bash
# Set your bot token
export TELEGRAM_BOT_TOKEN="your-token-here"

# Run bot
python -c "
import asyncio
from interfaces.telegram import create_telegram_bot

async def main():
    bot = create_telegram_bot()
    await bot.start()

asyncio.run(main())
"
```

---

## ⚙️ Configuration

### Environment Variables

All configuration is managed via `.env` file. See `.env.example` for complete reference.

#### Required Variables

```bash
# Auth (REQUIRED for production)
JWT_SECRET=your-strong-secret-key-min-32-chars-use-openssl-rand-hex-32

# Database (PostgreSQL recommended, SQLite auto-fallback)
DATABASE_URL=postgresql://nexus:strong-password@localhost:5432/nexus

# Redis (for queue and cache)
REDIS_URL=redis://:strong-password@localhost:6379/0

# AI Providers (at least one required)
ANTHROPIC_API_KEY=sk-ant-your-api-key
```

#### Optional Variables

```bash
# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false
LOG_LEVEL=info

# Auth
API_SECRET=              # Bearer token for gateway auth (empty = no auth)
JWT_EXPIRE_MINUTES=60

# Rate Limiting
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60

# CORS
CORS_ORIGINS=*           # Comma-separated origins

# AI Providers
OPENAI_API_KEY=sk-your-openai-key
OLLAMA_BASE_URL=http://localhost:11434
LITELLM_BASE_URL=http://localhost:4000

# Telegram
TELEGRAM_BOT_TOKEN=your-telegram-bot-token

# Docker
POSTGRES_PASSWORD=nexus_postgres_password
REDIS_PASSWORD=nexus_redis_password
```

### Docker Configuration

```bash
# Build target: 'production' or 'development'
DOCKER_BUILD_TARGET=production
DASHBOARD_BUILD_TARGET=production

# Volume mode: 'ro' (read-only) or 'rw' (read-write for development)
VOLUME_MODE=ro

# Image version
VERSION=latest
```

---

## 💡 Usage

### REST API

```bash
# Health check
curl http://localhost:8000/health

# Detailed health
curl http://localhost:8000/api/health/detailed | jq

# Send chat message
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"content": "Write a Python function to calculate factorial"}'

# List work orders
curl http://localhost:8000/api/work-orders | jq

# Filter work orders
curl "http://localhost:8000/api/work-orders?status=completed&limit=10" | jq

# Get metrics
curl "http://localhost:8000/api/metrics?period=today" | jq

# List agents
curl http://localhost:8000/api/agents | jq
```

### WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'your-jwt-token'
  }));

  ws.send(JSON.stringify({
    type: 'chat',
    content: 'Hello NEXUS!'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

### Telegram Bot

```
/start              Start conversation
/status             Show system status
/cost               Show token usage and costs
/escalate           Escalate current task to higher agent
/audit              Show recent audit logs
/help               Show help message
```

### Web GUI

Navigate to `http://localhost:3000` (or port specified in `DASHBOARD_PORT`)

Features:
- **Chat**: Real-time conversation with WebSocket
- **Agents**: View all agents and their status
- **Work Orders**: Browse, filter, and monitor tasks
- **Metrics**: Token usage, costs, and system performance
- **Health Dashboard**: Live monitoring with auto-refresh

---

## 📚 API Reference

### Health Endpoints

#### `GET /health`

Basic health check.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-02-18T10:30:00Z"
}
```

#### `GET /api/health/detailed`

Comprehensive health status including all services.

**Response:**
```json
{
  "overall_status": "healthy",
  "timestamp": "2026-02-18T10:30:00Z",
  "gateway": {
    "status": "healthy",
    "message": "Gateway responding"
  },
  "redis": {
    "status": "healthy",
    "message": "Redis connected",
    "used_memory_mb": 15.32
  },
  "postgres": {
    "status": "healthy",
    "message": "PostgreSQL connected",
    "work_orders_total": 42,
    "work_orders_in_progress": 3
  },
  "agents": {
    "status": "healthy",
    "message": "Agents active"
  },
  "metrics": {
    "tokens_today": 125000,
    "cost_today_usd": 0.87
  }
}
```

### Chat Endpoints

#### `POST /api/chat`

Send a chat message (HTTP fallback for non-WebSocket clients).

**Request:**
```json
{
  "content": "Create a REST API for user authentication"
}
```

**Response:**
```json
{
  "ok": true,
  "work_order_id": "wo-abc123def456",
  "difficulty": "normal",
  "owner": "director"
}
```

### Work Order Endpoints

#### `GET /api/work-orders`

Query work orders with optional filters.

**Query Parameters:**
- `status` (optional): Filter by status (queued, in_progress, completed, failed, cancelled)
- `owner` (optional): Filter by owner (admin, intern, director, ceo)
- `limit` (optional, default=50): Maximum number of results

**Response:**
```json
{
  "ok": true,
  "work_orders": [...],
  "count": 10
}
```

### Agent Endpoints

#### `GET /api/agents`

List all agents and their configuration.

**Response:**
```json
{
  "ok": true,
  "agents": [
    {
      "id": "ceo",
      "role": "ceo",
      "model": "claude-opus-4-6",
      "provider": "anthropic",
      "max_tokens": 8192,
      "temperature": 0.7,
      "status": "active"
    },
    ...
  ]
}
```

### Metrics Endpoints

#### `GET /api/metrics`

Get system metrics including token usage and costs.

**Query Parameters:**
- `period` (optional, default=today): Time period (today, week, month, all)

**Response:**
```json
{
  "ok": true,
  "period": "today",
  "token_usage": {
    "prompt_tokens": 50000,
    "completion_tokens": 25000,
    "total_tokens": 75000
  },
  "cost": {
    "total_usd": 0.42
  },
  "work_orders": {
    "total": 42,
    "completed": 38,
    "in_progress": 3,
    "failed": 1
  },
  "request_count": 156,
  "timestamp": "2026-02-18T10:30:00Z"
}
```

---

## 🛠️ Development

### Code Style

- **Python 3.12+** with type hints
- **Formatting**: `ruff format`
- **Linting**: `ruff check`
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes

### Running Tests

```bash
# Unit tests
pytest

# QA validation tests
python qa/runner.py --spec qa/specs/example_json_output.json

# Security checks
python qa/runner.py --spec qa/specs/security_check.json

# With database logging
python qa/runner.py --spec qa/specs/work_order_response.json --log-to-db
```

### Development Mode with Docker

```bash
# Start in development mode (hot reload, development dependencies)
make dev

# Or manually:
DOCKER_BUILD_TARGET=development DASHBOARD_BUILD_TARGET=development docker compose up

# Open shell in container
make shell

# View logs
make logs-gateway
```

### Project Roadmap

- ✅ **Phase 1**: Foundation — Gateway, Model Router, Admin Agent, Telegram Bot
- ✅ **Phase 2**: Full Org Chart — CEO/Director/Intern routing, work order pipeline
- ✅ **Phase 3**: Interfaces + QA — Web GUI, QA pipeline, equipment framework
- ✅ **Phase 4A**: Heartbeat Monitoring — Health checks, alerts, auto-recovery
- ✅ **Phase 5**: Docker + Documentation + Release — Production deployment, comprehensive docs
- 🔄 **Phase 6**: Self-Evolution — LoRA training, A/B testing, continuous improvement

---

## 🏥 Monitoring & Health Checks

### Heartbeat Monitoring

NEXUS includes an automated health monitoring and recovery system. See [heartbeat/README.md](heartbeat/README.md) for detailed documentation.

**Features**:
- Periodic health checks for Gateway, Redis, PostgreSQL, Agents, GPU, Token Budget, Disk
- Telegram notifications for critical/warning alerts
- Auto-recovery: restart services, cleanup disk, handle stuck agents
- Flexible deployment: systemd service, cron job, or standalone

**Quick Start**:
```bash
# Run once
python -m heartbeat.service --once --enable-telegram --enable-recovery

# Run as continuous service (every 5 minutes)
python -m heartbeat.service --enable-telegram --enable-recovery

# Install as systemd service
sudo cp heartbeat/nexus-heartbeat.service /etc/systemd/system/
sudo systemctl enable nexus-heartbeat
sudo systemctl start nexus-heartbeat
```

### Health Check Endpoints

```bash
# Basic health
curl http://localhost:8000/health

# Detailed health with all services
curl http://localhost:8000/api/health/detailed

# Dashboard health (nginx)
curl http://localhost:3000/health
```

### Logs

```bash
# All services
make logs

# Specific service
make logs-gateway
make logs-postgres
make logs-redis
make logs-dashboard

# Follow logs (real-time)
docker compose logs -f gateway

# Last 100 lines
docker compose logs --tail=100 gateway
```

---

## 📁 Project Structure

```
nexus-ai-team/
├── gateway/              # FastAPI gateway (auth, rate limit, WebSocket)
│   ├── main.py           # App entry point + routes
│   ├── auth.py           # JWT authentication middleware
│   ├── config.py         # Pydantic settings from environment
│   ├── rate_limiter.py   # Sliding-window rate limiter
│   ├── schemas.py        # Request/response models
│   └── ws.py             # WebSocket connection manager
├── nexus_v1/             # AI agents
│   ├── config.py         # Tiered payroll model config
│   ├── model_router.py   # LiteLLM-based unified router
│   └── admin.py          # Admin agent (compress + classify + route)
├── pipeline/             # Work order pipeline
│   ├── dispatcher.py     # Async task dispatcher with retry logic
│   ├── queue.py          # Redis Streams queue manager
│   └── work_order.py     # Work order database operations
├── interfaces/           # User interfaces
│   └── telegram/         # Telegram bot
│       ├── bot.py        # Bot initialization
│       ├── handlers.py   # Message handlers
│       ├── commands.py   # Slash commands
│       └── format.py     # MarkdownV2 formatting
├── dashboard/            # Web GUI
│   ├── frontend/         # React + Vite
│   │   ├── src/          # React components
│   │   ├── Dockerfile    # Multi-stage build
│   │   └── nginx.conf    # Production web server config
│   └── backend/          # FastAPI backend (legacy, being migrated to gateway/)
├── qa/                   # QA validation framework
│   ├── runner.py         # Spec-based test runner with security checks
│   ├── specs/            # JSON test specifications
│   └── tests/            # Mock tasks for testing
├── db/                   # Database layer
│   ├── schema.sql        # PostgreSQL schema (work_orders, sessions, audit, metrics)
│   ├── client.py         # Database client with automatic fallback
│   └── integration.py    # Integration helpers
├── heartbeat/            # Health monitoring and auto-recovery
│   ├── monitor.py        # System health checks
│   ├── alerts.py         # Telegram/logging notifications
│   ├── recovery.py       # Auto-recovery actions
│   ├── service.py        # Standalone service runner
│   └── README.md         # Detailed documentation
├── equipment/            # Automation scripts and tools
├── docker/               # Docker configuration
│   └── init.sql          # PostgreSQL initialization script
├── Dockerfile            # Gateway multi-stage build
├── docker-compose.yml    # Full-stack deployment
├── Makefile              # Quick commands (make up, make down, etc.)
├── pyproject.toml        # Python project config + dependencies
├── .env.example          # Environment variable template
├── LICENSE               # MIT License
└── README.md             # This file
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes using conventional commits:
   - `feat: add new feature`
   - `fix: resolve bug`
   - `docs: update documentation`
   - `refactor: improve code structure`
   - `test: add tests`
4. **Push** to your branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Code Standards

- Follow existing code style (PEP 8 for Python, ESLint for JavaScript)
- Add tests for new features
- Update documentation as needed
- Ensure all tests pass: `make test`

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Anthropic** for Claude API
- **LiteLLM** for unified LLM interface
- **FastAPI** for the excellent web framework
- **Redis** and **PostgreSQL** for robust infrastructure
- The open-source community for countless tools and libraries

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/nexus-ai-team/issues)
- **Documentation**: [Full docs](https://github.com/yourusername/nexus-ai-team/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/nexus-ai-team/discussions)

---

**Made with ❤️ by the NEXUS team**

*NEXUS — Your AI company, always at your service.*
