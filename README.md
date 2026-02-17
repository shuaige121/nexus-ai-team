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
│   ├── runner.py         # Enhanced spec-based test runner with security checks
│   ├── specs/            # JSON test specifications
│   └── tests/            # Mock tasks for testing
├── db/                   # Database layer with PostgreSQL/SQLite support
│   ├── schema.sql        # PostgreSQL schema (work_orders, sessions, audit, metrics)
│   ├── client.py         # Database client with automatic fallback
│   └── integration.py    # Integration helpers for gateway/pipeline
├── equipment/            # Automation scripts, cron jobs (Phase 3+)
├── heartbeat/            # Health monitoring and auto-recovery (Phase 4A)
│   ├── monitor.py        # System health checks
│   ├── alerts.py         # Telegram/logging notifications
│   ├── recovery.py       # Auto-recovery actions
│   ├── service.py        # Standalone service runner
│   └── README.md         # Installation and configuration
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

# Detailed health status
curl http://localhost:8000/api/health/detailed

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

# QA runner (basic validation)
python3 qa/runner.py --spec qa/specs/example_json_output.json

# QA runner with database logging
python3 qa/runner.py --spec qa/specs/work_order_response.json --log-to-db --work-order-id wo-123

# Run security check spec
python3 qa/runner.py --spec qa/specs/security_check.json

# Run Python code validation spec
python3 qa/runner.py --spec qa/specs/example_python_code.json

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
| `DATABASE_URL` | Optional | PostgreSQL URL (auto-falls back to SQLite if unavailable) |
| `SQLITE_DB_PATH` | Optional | SQLite database path (default: nexus.db) |

## QA Pipeline & Logging

### QA Validation Framework

The QA pipeline validates work outputs through multiple layers:

1. **Format Validation**: JSON schema validation, regex pattern matching
2. **Completeness Checks**: Required fields, forbidden placeholders (TODO, FIXME)
3. **Security Checks**: Detects sensitive information leakage (passwords, API keys, emails)
4. **Code Execution**: Validates Python code syntax and optionally executes in sandbox

#### QA Spec Structure

Create JSON specs in `qa/specs/` with the following structure:

```json
{
  "name": "Validation Name",
  "command": "echo 'test output'",
  "timeout_seconds": 10,
  "expected_exit_code": 0,
  "format": {
    "type": "json",
    "required_keys": ["status", "result"]
  },
  "completeness": {
    "required_substrings": ["success"],
    "forbidden_substrings": ["TODO", "placeholder"]
  },
  "security": {
    "enabled": true,
    "check_placeholders": true,
    "forbidden_patterns": ["sk-[a-zA-Z0-9]{20,}"]
  },
  "code_execution": {
    "enabled": true,
    "language": "python",
    "execute_in_sandbox": false
  }
}
```

#### Running QA Checks

```bash
# Basic validation
python3 qa/runner.py --spec qa/specs/example_json_output.json

# With database logging
python3 qa/runner.py \
  --spec qa/specs/work_order_response.json \
  --log-to-db \
  --work-order-id wo-123

# Generate JSON report
python3 qa/runner.py \
  --spec qa/specs/security_check.json \
  --report-json reports/security_check.json
```

### Database Logging

The system supports dual database backends with automatic fallback:

- **PostgreSQL**: Production-grade logging with full schema (preferred)
- **SQLite**: Automatic fallback for development/testing

#### Logged Data

1. **Work Orders**: Creation, status updates, completion times
2. **Agent Metrics**: Token usage, latency, cost per execution
3. **Audit Logs**: All system actions for compliance tracking
4. **Sessions**: User sessions across Telegram/Web GUI

#### Database Configuration

```bash
# PostgreSQL (recommended for production)
# Replace 'your-password' with a strong password
export DATABASE_URL="postgresql://nexus:your-password@localhost:5432/nexus"

# SQLite fallback (automatic if PostgreSQL unavailable)
export SQLITE_DB_PATH="./nexus.db"
```

#### Querying Metrics

```python
from db.client import get_db_client
from datetime import datetime, timedelta

client = get_db_client()

# Query metrics from last 24 hours
metrics = client.query_metrics(
    start_time=datetime.now() - timedelta(days=1),
    agent_name="ceo_agent",
    limit=100
)

# Calculate total cost
total_cost = sum(m["cost_usd"] for m in metrics)
```

#### Integration in Custom Code

```python
from db.integration import log_agent_execution, log_audit_event

# Log agent execution
log_agent_execution(
    work_order_id="wo-123",
    session_id="sess-456",
    agent_name="director_agent",
    role="director",
    model="claude-sonnet-4-5",
    provider="anthropic",
    success=True,
    latency_ms=1250,
    prompt_tokens=500,
    completion_tokens=200,
    cost_usd=0.0042
)

# Log audit event
log_audit_event(
    actor="system",
    action="work_order_created",
    status="success",
    work_order_id="wo-123",
    details={"difficulty": "normal", "owner": "director"}
)
```

## Development

### Code Style

- Python 3.12+ with type hints
- Formatting: `ruff format`
- Linting: `ruff check`
- Naming: `snake_case` for functions/variables, `PascalCase` for classes

### Development Phases

- **Phase 1**: Foundation — Gateway, Model Router, Admin Agent, Telegram Bot, DB Schema, QA
- **Phase 2**: Full Org Chart — CEO/Director/Intern routing, escalation, work order pipeline
- **Phase 3**: Interfaces + QA — Web GUI, full QA pipeline, equipment framework
- **Phase 4A (Current)**: Heartbeat Monitoring — Health checks, alerts, auto-recovery
- **Phase 4**: Self-Evolution — LoRA training, A/B testing
- **Phase 5**: Polish + Release — Docker full-stack, documentation, open source

### Heartbeat Monitoring (Phase 4A)

NEXUS includes an automated health monitoring and recovery system. See [heartbeat/README.md](heartbeat/README.md) for details.

**Features**:
- Periodic health checks for Gateway, Redis, PostgreSQL, Agents, GPU, Token Budget, Disk
- Telegram notifications for critical/warning alerts
- Auto-recovery: restart services, cleanup disk, handle stuck agents
- Flexible deployment: systemd service, cron job, or standalone

**Quick Start**:
```bash
# Install dependencies
pip install aiohttp psutil redis psycopg

# Run once
python -m heartbeat.service --once --enable-telegram --enable-recovery

# Run as service
python -m heartbeat.service --enable-telegram --enable-recovery

# Install systemd service
sudo cp heartbeat/nexus-heartbeat.service /etc/systemd/system/
sudo systemctl enable nexus-heartbeat
sudo systemctl start nexus-heartbeat
```

## License

MIT
