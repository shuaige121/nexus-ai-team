# OpenClaw vs NEXUS: CEO Architecture Synthesis

> Final Report | 2026-02-19 | Based on 4 Manager reports (12 research agents)

---

## Executive Summary

OpenClaw is a **288K-line production platform** with 3 months of maturity. Its core strengths are:
1. **8-layer config pipeline** with Zod validation
2. **Complexity-based model routing** (6 weighted signals -> fast/balanced/capable)
3. **Tool tier filtering** (3 tools for simple queries, 17+ for complex -- saves 77% tokens)
4. **Circuit breaker + fallback chains** per model
5. **Hybrid memory search** (SQLite + vector + FTS5)
6. **Plugin architecture** with unified registration API
7. **Channel abstraction** (2-tier: lightweight Dock + heavyweight Plugin)
8. **13 typed lifecycle hooks** with interception capability

NEXUS is a **26K-line greenfield prototype** at 3 days old. Its unique strengths are the company simulation model, contract pipeline, and multi-agent QA cycles. But it lacks most production infrastructure.

---

## Architecture Gap Matrix

| Capability | OpenClaw | NEXUS | Gap | Priority |
|-----------|----------|-------|-----|----------|
| Model Routing | 6-signal complexity scorer -> tier | Static model per dispatch | CRITICAL | P0 |
| Tool Filtering | 8-layer policy + tier-based subset | No filtering (full CLI) | CRITICAL | P0 |
| Fallback Chain | Ordered chain + circuit breaker | None | HIGH | P1 |
| Config System | JSON5+includes+env+Zod+8 defaults | Python dicts + .env | HIGH | P1 |
| Memory System | SQLite+vector+FTS5 hybrid search | None | HIGH | P1 |
| Cost Tracking | Per-session/day/model token+dollar | None | HIGH | P1 |
| Plugin/Equipment API | Unified register(api), 10+ methods | Basic install/uninstall | MEDIUM | P2 |
| Lifecycle Hooks | 13 typed events with interception | None | MEDIUM | P2 |
| Channel Abstraction | 2-tier Dock+Plugin, 20+ adapters | None (CLI only) | MEDIUM | P2 |
| Session Management | JSONL transcripts + lane serial | File markers only | MEDIUM | P2 |
| Cron/Scheduling | 3 schedule, 3 payload, 4 delivery | None | LOW | P3 |
| Security Audit | 20+ checks, deep probe mode | Basic auth only | LOW | P3 |
| Streaming | Block streaming chunked delivery | Full response only | LOW | P3 |

---

## Top 8 Patterns to Adopt (Prioritized)

### P0-1: Complexity Router (from query-router.ts)

**What**: 6 weighted signals (msg length 0.20, code blocks 0.25, media 0.15, keywords 0.15, multi-task 0.10, depth 0.15) produce 0-1 score. Score maps to fast/balanced/capable tier.

**Why**: NEXUS sends every task to the same model. A CEO memo and a code review should NOT use the same model. This alone could cut 60%+ of LLM costs.

**NEXUS impl**: Add `complexity_score()` to gateway dispatch. Score the contract text. Route to haiku/sonnet/opus based on thresholds.

### P0-2: Tool Tier Filtering (from pi-tools.ts)

**What**: Fast tier gets 3 tools, balanced ~14, capable gets all. 8-layer policy stack filters tools.

**Why**: Sending all tools in the system prompt wastes tokens on simple tasks. Fast queries with 3 tools save ~77% prompt tokens.

**NEXUS impl**: Define tool profiles per complexity tier in gateway config. Filter equipment/tools before injecting into agent context.

### P1-1: Circuit Breaker + Fallback (from model-fallback.ts + circuit-breaker.ts)

**What**: Per-model circuit breaker (closed->open->half-open, 3 failures to trip, 60s cooldown). Fallback chain tries models in order. Auth profile rotation for rate limit recovery.

**Why**: NEXUS currently has no resilience. If Claude API is down, everything stops.

**NEXUS impl**: Wrap LiteLLM calls in circuit breaker. Define fallback chain in config: opus->sonnet->haiku->gpt-4o.

### P1-2: Config Pipeline (from OpenClaw config system)

**What**: JSON5 -> $include -> env substitution -> Zod validation -> 8-layer defaults -> normalize.

**Why**: NEXUS config is scattered .env + Python dicts. No validation, no composition, no defaults.

**NEXUS impl**: Use Pydantic Settings with layered defaults. Add YAML config file with $include support. Validate everything at startup.

### P1-3: Memory System (from memory/manager.ts)

**What**: SQLite + sqlite-vec for embeddings + FTS5 for keyword search. Hybrid weighted merge. Incremental delta sync from session transcripts.

**Why**: NEXUS agents have no memory across sessions. Each contract starts from zero context.

**NEXUS impl**: Add a memory module using ChromaDB or SQLite+embeddings. Index contract results. Let agents search past work.

### P1-4: Cost Tracking (from session-cost-usage.ts)

**What**: Per-session token tracking (input/output/cache), daily aggregates, model-level breakdown, dollar cost estimation.

**Why**: NEXUS has a budget guard but no visibility into actual spend patterns.

**NEXUS impl**: Log token usage per contract. Daily/weekly cost reports. Dashboard visualization.

### P2-1: Equipment Registration API (from plugin system)

**What**: Unified `register(api)` with api.registerTool(), api.registerHook(), api.registerCommand(), etc. JSON Schema config validation. 4-tier discovery.

**Why**: NEXUS equipment is basic install/uninstall. No structured API, no capability declaration.

**NEXUS impl**: Define EquipmentAPI class. Equipment calls `api.register_tool()`, `api.register_hook()`. Discovery scans equipment/ directory.

### P2-2: Lifecycle Hooks (from hook system)

**What**: 13 typed events (before_agent_start, before_tool_call, message_sending, etc.). Hooks can intercept and block/modify. Both internal pub-sub and plugin hooks.

**Why**: NEXUS has no pipeline interception. Cannot add logging, validation, or approval gates without modifying core code.

**NEXUS impl**: Define NEXUS hook points: before_dispatch, after_worker_complete, before_qa_review, after_qa_verdict, on_pipeline_error. Equipment can register handlers.

---

## Implementation Roadmap

### Phase 3A: Smart Routing (est. ~2K lines)
- Complexity scorer in gateway
- Model tier mapping (fast/balanced/capable)
- Tool profile filtering per tier
- Config-driven thresholds

### Phase 3B: Resilience (est. ~1.5K lines)
- Circuit breaker per model
- Ordered fallback chain
- LiteLLM wrapper with retry + backoff
- Auth key rotation

### Phase 3C: Memory (est. ~2K lines)
- SQLite + embedding storage
- Contract result indexing
- Hybrid search (vector + keyword)
- Delta sync from new contracts

### Phase 3D: Observability (est. ~1K lines)
- Token usage logging per contract
- Cost estimation per model
- Daily/weekly aggregation
- Dashboard cost panel

### Phase 4A: Equipment API (est. ~2K lines)
- EquipmentAPI registration pattern
- JSON Schema config validation
- Multi-tier discovery
- Capability declaration

### Phase 4B: Lifecycle Hooks (est. ~1.5K lines)
- Hook event types definition
- Handler registration + dispatch
- Interception support (block/modify)
- Built-in hooks (logging, cost guard)

### Phase 4C: Config Overhaul (est. ~1K lines)
- YAML config with Pydantic validation
- Layered defaults
- Per-agent config overrides
- Config hot-reload

---

## What NEXUS Has That OpenClaw Doesn't

NEXUS is NOT just a smaller OpenClaw. It has unique concepts:

| NEXUS Unique | Value |
|-------------|-------|
| Company simulation | Org chart, departments, CEO->Manager->Worker hierarchy |
| Contract pipeline | Structured Worker->QA->PASS/FAIL cycles with max rounds |
| Agent JD system | RACE profile, personality, resume per agent |
| Dynamic org chart | Scan, diff, hook, auto-update |
| Heartbeat + recovery | Per-agent health monitoring with Redis persistence |
| Skill marketplace | Submit -> review -> approve workflow |
| QA runner | Automated quality assurance with structured verdicts |

These organizational patterns are NEXUS's competitive advantage. OpenClaw is a tool; NEXUS is an organization.

---

## Bottom Line

NEXUS needs ~10K lines of infrastructure code across 6 work packages to reach OpenClaw-level robustness. The most impactful additions are:

1. **Complexity router** -- cuts LLM costs 60%+
2. **Tool tier filtering** -- cuts prompt tokens 77%
3. **Circuit breaker + fallbacks** -- eliminates single-model dependency
4. **Memory system** -- enables cross-session learning

These 4 alone would transform NEXUS from prototype to production-grade.
