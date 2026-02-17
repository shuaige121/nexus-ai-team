# NEXUS — Neural Executive Unified System

An AI company that works for you. Talk to your org via Telegram Bot or LAN Web GUI. You're the Board of Directors.

## What Is NEXUS

NEXUS is an AI operating system that runs like a real company. It has employees (LLMs), equipment (scripts and tools), and a management hierarchy — all working to serve one client: **you**.

- **CEO** (Claude Opus 4.6) — handles complex tasks
- **Director** (Claude Sonnet 4.5) — handles normal tasks
- **Intern** (Claude Haiku 3.5) — handles trivial tasks
- **Admin** (Qwen3 8B, local) — routes requests for free

## Architecture

```
User (Telegram / Web GUI)
        │
   FastAPI Gateway (auth, rate limit, WebSocket)
        │
   Admin Agent (compress + classify)
        │
   ┌────┴─────┬──────────┐
trivial    normal     complex
 Intern   Director     CEO
 (Haiku)  (Sonnet)   (Opus)
        │
   QA Validation → Deliver or Retry
```

### Request Flow

1. User sends a message via Telegram or Web GUI
2. FastAPI Gateway authenticates, rate-limits, and logs the request
3. Admin Agent (Qwen3, local, free) compresses context and classifies difficulty
4. Request is routed to the appropriate employee (Intern / Director / CEO)
5. Employee executes, self-tests, QA validates, then delivers or retries

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Gateway | FastAPI (async, WebSocket) |
| Model Router | LiteLLM (unified API proxy) |
| Local Inference | Ollama (Qwen3 8B, CUDA) |
| Telegram Bot | python-telegram-bot v22 |
| Message Queue | Redis Streams |
| Database | PostgreSQL 16 |
| QA Framework | Custom spec-based validator |
| Container | Docker Compose |

## Project Structure

```
nexus-ai-team/
├── gateway/              # FastAPI gateway (auth, rate limit, WebSocket)
│   ├── main.py           # App entry point + routes
│   ├── auth.py           # Bearer token + JWT middleware
│   ├── config.py         # Pydantic Settings from env
│   ├── rate_limiter.py   # Sliding-window rate limiter
│   ├── schemas.py        # Request/response models
│   └── ws.py             # WebSocket connection manager
├── agents/               # AI agent definitions
│   ├── config.py         # Tiered payroll model config
│   ├── model_router.py   # LiteLLM-based unified router
│   └── admin.py          # Admin agent (compress + classify + route)
├── interfaces/
│   └── telegram/         # Telegram bot interface
│       ├── bot.py        # Bot init, polling/webhook modes
│       ├── handlers.py   # Text, photo, voice message handlers
│       ├── commands.py   # /status /escalate /cost /audit
│       └── format.py     # MarkdownV2 escaping + text splitting
├── qa/                   # QA validation framework
│   ├── runner.py         # Spec-based test runner
│   ├── specs/            # JSON test specifications
│   └── tests/            # Mock tasks for testing
├── db/
│   └── schema.sql        # PostgreSQL schema (work_orders, sessions, audit, metrics)
├── equipment/            # Automation scripts, cron jobs (Phase 3+)
├── docker-compose.yml    # PostgreSQL + Redis + App services
├── pyproject.toml        # Python project config + dependencies
├── .env.example          # All required environment variables
└── .gitignore
```

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (for PostgreSQL + Redis)
- Ollama (optional, for local Qwen3 model)
- Node.js 18+ (for Web GUI frontend)

### Installation

```bash
# Clone
git clone git@github.com:shuaige121/nexus-ai-team.git
cd nexus-ai-team

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your API keys and settings
```

### Start Infrastructure

```bash
# Start PostgreSQL + Redis
docker compose --env-file .env up -d postgres redis

# Start the gateway
uvicorn gateway.main:app --reload --host 0.0.0.0 --port 8000
```

### Test the Gateway

```bash
# Health check
curl http://localhost:8000/health

# Send a chat message
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello NEXUS"}'

# Get work orders
curl http://localhost:8000/api/work-orders

# Get metrics
curl http://localhost:8000/api/metrics?period=today

# Swagger docs
open http://localhost:8000/docs
```

### Start Web GUI

The Web GUI provides a visual interface to interact with NEXUS. It includes:
- **Chat**: Real-time conversation with your AI team via WebSocket
- **Agents**: View all agents and their current status
- **Work Orders**: Browse and filter work orders by status/owner
- **Metrics**: Monitor token usage, costs, and system performance

```bash
# Install frontend dependencies
cd dashboard/frontend
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

The dashboard will be available at `http://localhost:5173` (dev) or served by the gateway at `http://localhost:8000` (production).

### Start Telegram Bot

```bash
export TELEGRAM_BOT_TOKEN="your-token-here"
python3 -c "
import asyncio
from interfaces.telegram import create_telegram_bot

async def main():
    bot = create_telegram_bot()
    await bot.start()

asyncio.run(main())
"
```

### Run Tests

```bash
# Unit tests
python3 -m unittest agents.test_litellm_dry_run -v

# QA runner
python3 qa/runner.py --spec qa/specs/sample_success.json

# Lint
ruff check agents gateway interfaces qa
```

## Environment Variables

See `.env.example` for the complete list. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude models |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token from @BotFather |
| `OPENAI_API_KEY` | Optional | OpenAI API key (fallback) |
| `OLLAMA_BASE_URL` | Optional | Ollama server URL (default: localhost:11434) |
| `API_SECRET` | Optional | Bearer token for gateway auth (empty = no auth) |
| `REDIS_URL` | Optional | Redis connection URL |

## Development

### Code Style

- Python 3.12+ with type hints
- Formatting: `ruff format`
- Linting: `ruff check`
- Naming: `snake_case` for functions/variables, `PascalCase` for classes

### Development Phases

- **Phase 1 (Current)**: Foundation — Gateway, Model Router, Admin Agent, Telegram Bot, DB Schema, QA
- **Phase 2**: Full Org Chart — CEO/Director/Intern routing, escalation, work order pipeline
- **Phase 3**: Interfaces + QA — Web GUI, full QA pipeline, equipment framework
- **Phase 4**: Self-Evolution — Heartbeat monitoring, LoRA training, A/B testing
- **Phase 5**: Polish + Release — Docker full-stack, documentation, open source

## License

MIT
