# NEXUS — Neural Executive Unified System

## Project Overview v2.0

**A virtual company staffed by AI, built to serve you — the Board of Directors.**

---

## 1. What Is NEXUS

NEXUS is an AI operating system that runs like a real company. It has employees (LLMs), equipment (scripts and tools), and a management hierarchy — all working to serve one client: you.

The CEO has full root access to an Ubuntu 24 server. It hires and fires employees (swaps models), purchases equipment (installs skills/tools), creates new teams (spins up new agents), and removes dead weight. You, as the Board of Directors, can replace even the CEO itself. But the company architecture persists — no individual is irreplaceable.

Talk to your company via **Telegram Bot** or a **LAN Web GUI** from any device on your network.

---

## 2. Core Principles

### 2.1 Machines Do Machine Work, Employees Do Thinking Work

| Task Type | Handled By | Examples |
| --- | --- | --- |
| Deterministic, repeatable | **Equipment** (scripts) | Web scraping, scheduled messages, file backups, data pipeline, API polling, report generation |
| Requires understanding/judgment | **Employees** (LLMs) | Code writing, email drafting, architecture decisions, ambiguous requests, creative work |

### 2.2 Tiered Payroll

| Role | Model | Deployment | Cost | Analogy |
| --- | --- | --- | --- | --- |
| Board of Directors | Human (you) | N/A | Free | You set direction, override anything |
| CEO | Claude Opus 4.6 | Anthropic API | $5/$25 per M tokens | Executive |
| Director | Claude Sonnet 4.5 | Anthropic API | $3/$15 per M tokens | Senior employee |
| Intern | Claude Haiku 3.5 | Anthropic API | $0.80/$4 per M tokens | Junior |
| Admin | Qwen3 8B/14B | Local GPU (CUDA) | Free (electricity) | Receptionist/Router |
| CTO/Ops | Script toolchain | Local server | Free | Infrastructure |

### 2.3 Someone Must Own the Result — No Half-Finished Work

```
Build -> Test (as real user) -> Debug -> Re-test -> Deliver
```

QA Flow:
```
Employee builds output
       |
Employee self-tests (run it, use it, break it)
       |
Admin validates (format check, error check, completeness)
       |
[If pass] -> Deliver to Board
[If fail] -> Return to employee with specific failure report
       |
3 failures -> Escalate to Director/CEO
```

### 2.4 The Architecture Survives Any Individual

The company is a **framework**, not a collection of individuals.

---

## 3. System Architecture

### 3.1 User Interfaces

```
Phone (Telegram Bot) ---+
                        +---> FastAPI Gateway ---> Admin (local) ---> Cloud Models
Browser (LAN GUI) ------+
```

### 3.2 Request Flow

```
User sends message (Telegram or Web GUI)
       |
FastAPI Gateway (auth, rate limit, logging)
       |
Admin (Qwen3 8B, local, free)
  - Compresses into ~1K token work order
  - Classifies: trivial / normal / complex / unclear
       |
Routing:
  trivial -> Intern (Haiku)
  normal  -> Director (Sonnet)
  complex -> CEO (Opus)
  unclear -> Admin asks user for clarification (free)
       |
Employee executes -> Self-tests -> Admin validates -> Deliver or loop
```

### 3.3 Work Order Format

```json
{
  "id": "WO-20260216-0042",
  "intent": "build_feature",
  "difficulty": "normal",
  "owner": "director",
  "compressed_context": "...",
  "relevant_files": ["main.py", "models/user.py"],
  "qa_requirements": "Must run without errors.",
  "deadline": null
}
```

---

## 4. Tech Stack

| Component | Technology | Purpose |
| --- | --- | --- |
| Agent Framework | LangGraph | Graph-based state machine |
| Local Inference | Ollama (CUDA) | Local models, hot-swap |
| API Proxy | LiteLLM | Unified API, cost tracking |
| Gateway | FastAPI | Async API server, WebSocket |
| Telegram | python-telegram-bot | Async Telegram bot |
| Web GUI | React + Tailwind | LAN dashboard |
| Message Queue | Redis Streams | Inter-agent comms |
| Database | PostgreSQL | Logs, work orders, audit |
| Vector Memory | ChromaDB | Conversation history |
| Monitoring | Grafana + Prometheus | Dashboards, alerting |
| LoRA Training | Unsloth | Fine-tune local models |
| Local Model | Qwen3 8B Q4 | Default Admin model |

---

## 5. Repo Structure

```
nexus-ai-team/
├── gateway/           # FastAPI gateway, auth, WebSocket
├── agents/            # LangGraph agent definitions
├── prompts/           # Role system prompts (LOCKED/TUNABLE/LEARNED)
├── equipment/         # Automation scripts, cron jobs, scrapers
├── interfaces/
│   ├── telegram/      # Telegram bot
│   └── webgui/        # React LAN dashboard
├── heartbeat/         # Health reports, anomaly detection
├── evolution/         # LoRA training, A/B testing, prompt mutation
├── qa/                # QA validation framework
├── dashboard/         # Grafana configs, Prometheus metrics
├── docker-compose.yml
├── docs/
├── README.md
└── LICENSE
```

---

## 6. Development Phases

### Phase 1: Foundation (Week 1-2)
- Ubuntu server setup, Ollama + CUDA, FastAPI gateway
- Admin agent with compression + routing logic
- Single executor (Sonnet) — end-to-end message flow
- Basic QA validation

### Phase 2: Full Org Chart (Week 3-4)
- Add CEO (Opus), Intern (Haiku), complete routing
- Escalation system
- Telegram bot interface
- Work order format with owner assignment

### Phase 3: Interfaces + QA (Week 5-6)
- LAN Web GUI (React dashboard)
- QA framework pipeline
- PostgreSQL logging
- Equipment framework

### Phase 4: Self-Evolution (Week 7-9)
- Heartbeat monitoring
- LoRA training pipeline (Unsloth)
- A/B testing framework
- CEO prompt self-modification
- Chairman control panel

### Phase 5: Polish + Release (Week 10-12)
- Proactive email/calendar scanning
- Prompt caching optimization
- Docker Compose full-stack
- Documentation, demo video, open source release

---

## 7. Success Metrics

| Metric | Target |
| --- | --- |
| Token cost savings vs. direct API | >85% |
| Admin routing accuracy | >85% |
| QA pass rate (first attempt) | >80% |
| Board rejection rate | <5% |
| Response time (simple) | <5s |
| Response time (complex) | <30s |
| Equipment reliability | >99% |
