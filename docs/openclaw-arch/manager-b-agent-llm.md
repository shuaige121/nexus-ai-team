# OpenClaw Architecture: Agent & LLM System

> Generated: 2026-02-19 by Manager B (Agent System & LLM Infrastructure)
> Source: `/home/leonard/openclaw/src/agents/`, `src/memory/`, `src/auto-reply/`

---

## 1. Agent Lifecycle

### Agent Identity & Configuration
- **Agent scope** (`agent-scope.ts`): Each agent has an ID, resolved via `resolveSessionAgentId()` from session keys. Agents are defined in `openclaw.json` under `agents.list[]`, each with its own model, workspace, tools, memory, sandbox, and identity config.
- **Defaults**: Provider=`anthropic`, Model=`claude-opus-4-6`, Context=200K tokens (`defaults.ts`).
- **Multi-agent**: Agents are identified by session keys like `agent:<agentId>:session:<sessionId>`. The `parseAgentSessionKey()` function extracts agent ID from composite keys.

### Agent Execution Flow
1. Inbound message arrives via gateway (Telegram, WhatsApp, Slack, Discord, WebChat, etc.)
2. `dispatchInboundMessage()` routes through `dispatch-from-config.ts`
3. `getReplyFromConfig()` resolves agent, session state, model, directives
4. Smart router (`query-router.ts`) classifies complexity and selects model tier
5. `runReplyAgent()` orchestrates the full turn: tools, streaming, block replies, typing indicators
6. `runAgentTurnWithFallback()` wraps execution in `runWithModelFallback()` for resilience
7. `runEmbeddedPiAgent()` actually runs the LLM call via pi-ai SDK with session lane queuing
8. Results flow back through block-reply pipeline, TTS, and dispatcher to the channel

### Session Management
- Sessions stored as JSONL transcripts in `~/.openclaw/agents/<agentId>/sessions/`
- Session store tracks metadata: totalTokens, model, updatedAt, groupActivation, ttsAuto
- Session lanes (`lanes.ts`) serialize concurrent requests per session to prevent race conditions
- Auto-compaction when context window fills up; session reset on corruption

---

## 2. Tool System

### Tool Definition Pattern
All tools follow `AnyAgentTool` interface (`tools/common.ts`): `name`, `description`, `parameters` (TypeBox schema), `execute(toolCallId, args)`. Each tool is a factory function (e.g., `createBrowserTool()`, `createMessageTool()`).

### Tool Categories (17+ tools)
| Group | Tools |
|-------|-------|
| `group:fs` | read, write, edit, apply_patch |
| `group:runtime` | exec, process |
| `group:messaging` | message |
| `group:web` | web_search, web_fetch |
| `group:memory` | memory_search, memory_get |
| `group:sessions` | sessions_list, sessions_history, sessions_send, sessions_spawn, session_status |
| `group:ui` | browser, canvas |
| `group:automation` | cron, gateway |
| `group:nodes` | nodes |
| Other | image, tts, agents_list |

### Tool Tier Filtering (Cost Optimization)
The `applyRouterToolFilter()` in `pi-tools.ts` uses the router's complexity score to restrict tools per tier:
- **fast** tier: ~3 tools (e.g., session_status only) -- saves ~77% tokens
- **balanced** tier: ~14 tools (coding + messaging + sessions)
- **capable** tier: all tools (no restriction)

### Tool Policy Layers (applied in order)
1. **Global policy** (`config.tools.policy`) -- allow/deny lists
2. **Provider-specific policy** (`config.tools.providers.<provider>.policy`)
3. **Per-agent policy** (`agents.list[].tools.policy`)
4. **Group/channel policy** -- per-channel tool restrictions
5. **Subagent policy** -- inherited from parent with possible overrides
6. **Owner-only tools** (e.g., `whatsapp_login`) -- filtered for non-owners
7. **Tool gating** -- keyword/prefix triggers that conditionally gate specific tools
8. **Router tier filtering** -- complexity-based tool subset

### Plugin Tools
External plugins can register tools via `resolvePluginTools()`. Plugin tool groups are dynamically built and can be referenced as `group:plugins` or by plugin ID in policy rules.

---

## 3. Multi-Agent Orchestration

### Subagent Spawning
- `sessions_spawn` tool lets an agent spawn a background sub-agent in an isolated session
- Parameters: task, label, agentId, model, thinking level, timeout, cleanup policy
- Subagent gets its own session key: `subagent:<parentId>:run:<runId>`
- System prompt is customized for subagent context via `buildSubagentSystemPrompt()`

### Subagent Registry (`subagent-registry.ts`)
- In-memory `Map<runId, SubagentRunRecord>` with disk persistence
- Tracks lifecycle: created -> started -> ended -> announced -> cleaned up
- Periodic sweeper archives old runs (configurable `archiveAfterMinutes`, default 60)
- On gateway restart, pending runs are resumed from disk

### Announce Flow
- When a subagent completes, `runSubagentAnnounceFlow()` delivers results back to the requester
- Return channel is a contract specifying requester session key + delivery context
- Supports cleanup modes: `delete` (remove session after) or `keep` (preserve for inspection)

### Session Lane Serialization
- Global lane + per-session lane prevent concurrent mutations
- `enqueueCommandInLane()` ensures sequential execution within a lane
- Separate lanes for subagents (`AGENT_LANE_SUBAGENT`)

---

## 4. Memory System

### Architecture (`memory/manager.ts`, 2302 lines)
- **MemoryIndexManager**: Singleton per agent (cached by `agentId:workspaceDir:settings` key)
- **Storage**: SQLite database with FTS5 full-text search + sqlite-vec vector extension
- **Sources**: Memory markdown files (`MEMORY.md`, `memory/*.md`) + session transcripts (JSONL)

### Embedding Pipeline
- **Providers**: OpenAI, Voyage, Gemini, Local (llama) -- with auto-fallback between them
- **Chunking**: Markdown-aware chunking (`chunkMarkdown()`) with configurable token limits and overlap
- **Batching**: Supports batch API for OpenAI/Voyage/Gemini with retry, timeout, concurrency control
- **Caching**: Embedding cache table avoids re-embedding unchanged chunks

### Hybrid Search
- **Vector search**: sqlite-vec cosine similarity on embeddings
- **Keyword search**: FTS5 with BM25 ranking
- **Merge**: Weighted combination (`mergeHybridResults()`) with configurable vectorWeight/textWeight
- **Thresholds**: minScore filtering, candidateMultiplier for over-fetching, maxResults limit

### Incremental Sync
- File watcher (chokidar) monitors memory directory for changes
- Session transcript events trigger delta indexing (only new messages since last sync)
- `sync.onSearch` flag can trigger sync before each search for freshness
- Atomic reindex: builds new index in temp file, then swaps to prevent corruption

### Key Constants
- `EMBEDDING_BATCH_MAX_TOKENS = 8000`, `EMBEDDING_INDEX_CONCURRENCY = 4`
- `SNIPPET_MAX_CHARS = 700`, `VECTOR_LOAD_TIMEOUT_MS = 30s`
- Retry: 3 attempts with exponential backoff (500ms base, 8s max)

---

## 5. Auto-Reply Intelligence

### Message Processing Pipeline
1. **Inbound deduplication** -- skip duplicate messages
2. **Command detection** (`command-detection.ts`) -- `/model`, `/think`, `/status`, `/activation`, etc.
3. **Directive parsing** -- inline directives: model override, thinking level, verbose mode, elevated mode
4. **Group activation** -- `mention` (requires @mention) vs `always` (all messages trigger)
5. **Session state resolution** -- load/create session, apply directives, resolve model
6. **Smart routing** -- complexity-based model+tool selection
7. **Agent execution** -- run embedded PI agent with full tool suite
8. **Reply routing** -- route response back via correct channel/thread

### Directive System
Users can control behavior inline:
- `/model <provider/model>` or `/model @profile` -- switch model mid-conversation
- `/think <level>` -- adjust reasoning depth (off/minimal/low/medium/high/xhigh)
- `/verbose` -- toggle tool output visibility
- `/elevated` -- enable elevated permissions (owner-gated)
- Model aliases for fuzzy matching (e.g., "opus" -> "claude-opus-4-6")

### Block Streaming
- Replies can be streamed in chunks for long-form content
- Configurable chunking: minChars, maxChars, breakPreference (paragraph/newline/sentence)
- Block reply pipeline coalesces chunks and sends via dispatcher

### Typing & Heartbeat
- Typing indicators sent at configurable intervals during agent execution
- Heartbeat system for keep-alive in long-running operations
- Separate heartbeat model can be configured (cheaper model for status checks)

---

## 6. Model Routing & Fallbacks

### Query Router (`query-router.ts`)
**Complexity Scoring** (0.0 to 1.0) with weighted signals:
| Signal | Weight | Logic |
|--------|--------|-------|
| Message length | 0.20 | 0-50 chars=0, 50-500 linear, 500+=1.0 |
| Code blocks | 0.25 | Fenced/inline code detection |
| Media presence | 0.15 | Images/audio attached |
| Technical keywords | 0.15 | 70+ keywords (EN+CN): function, API, deploy, etc. |
| Multi-task | 0.10 | Bullet/numbered list detection |
| Conversation depth | 0.15 | Turn count in session |

**Overrides**: media always bumps to capable tier; code always bumps above fast tier.

**Tier Selection**: score <= fast.maxComplexity -> fast; score <= balanced.maxComplexity -> balanced; else -> capable.

### Provider-Aware Model Selection (`pickModel()`)
- Models in each tier are listed with `provider/model` format
- `pickModel()` prefers a model whose provider matches the agent's default provider
- This ensures Leonard's agents use Anthropic models, family agents use OpenAI models

### Token Budget Caps
- Per-session, daily, and per-request token budgets
- `deriveBudgetCap()` calculates budget ratio and can downgrade tier
- `onExceeded` modes: `downgrade` (force cheaper tier) or `warn` (allow but flag)

### Model Fallback Chain (`model-fallback.ts`)
- `runWithModelFallback()`: tries primary model, then each fallback in sequence
- Fallbacks defined globally (`agents.defaults.model.fallbacks[]`) or per-agent (`agents.list[].model.fallbacks[]`)
- Per-agent overrides take precedence over global
- Always falls back to configured primary model as last resort

### Circuit Breaker (`circuit-breaker.ts`)
- Per-model circuit breaker: tracks failures, opens after N consecutive fails
- States: closed (normal) -> open (blocked) -> half-open (probe)
- Defaults: maxFailures=3, cooldownMs=60s, halfOpenAfterMs=30s
- After 3 trips, suggests rollback (logs warning with git revert instructions)

### Auth Profile System
- Multiple API keys per provider, rotated based on cooldown/failure tracking
- `resolveAuthProfileOrder()` determines key priority
- `isProfileInCooldown()` skips exhausted keys during fallback

### Cost Tracking
- `NormalizedUsage`: input, output, cacheRead, cacheWrite, total tokens
- Universal normalizer handles different provider naming conventions
- `estimateUsageCost()` + `resolveModelCostConfig()` for monetary tracking
- Usage persisted per session for budget enforcement

---

## 7. Key Patterns NEXUS Should Adopt

1. **Complexity-Based Routing**: The query router's weighted signal scoring is elegant and saves significant cost. NEXUS should implement similar scoring to route simple tasks to cheaper models.

2. **Tool Tier Filtering**: Sending only 3 tools for simple queries vs 17+ for complex ones saves massive prompt tokens. NEXUS contracts should specify tool profiles per task complexity.

3. **Circuit Breaker + Fallback Chain**: The combination of per-model circuit breakers with ordered fallback candidates is production-grade resilience. NEXUS should adopt this for its LiteLLM gateway.

4. **Session Lane Serialization**: Preventing concurrent mutations per session is critical for correctness. NEXUS's file-based contracts already serialize, but the lane pattern is more elegant.

5. **Hybrid Memory Search**: Vector + BM25 keyword search with weighted merge gives better recall than either alone. NEXUS should use this for cross-session knowledge retrieval.

6. **Incremental Delta Sync**: Only indexing new session content since last sync is far more efficient than full reindex. Critical for long-running agent sessions.

7. **Subagent Registry with Persistence**: Disk-backed run registry that survives restarts ensures no work is lost. NEXUS's marker files are similar but less structured.

8. **Provider-Aware Model Picking**: Matching model provider to agent's default provider prevents accidental cross-provider routing. NEXUS should enforce this in dispatch.

---

## 8. Key Differences from NEXUS

| Aspect | OpenClaw | NEXUS |
|--------|----------|-------|
| **Execution** | Embedded SDK (pi-ai) with streaming | Bash scripts + Claude CLI + file contracts |
| **Model routing** | Dynamic per-message complexity scoring | Static per-dispatch model parameter |
| **Tool system** | 17+ built-in tools with policy layers | Whatever Claude CLI provides (no filtering) |
| **Memory** | SQLite + vector search + FTS5 hybrid | None (file system only) |
| **Fallbacks** | Automatic chain with circuit breakers | Manual retry in dispatch script |
| **Session mgmt** | JSONL transcripts + lane serialization | Marker files + tmux sessions |
| **Cost control** | Token budgets + tier downgrade | None |
| **Multi-agent** | Native spawn tool + announce flow | Contract files + QA round-trip |
| **Resilience** | Auth profile rotation, circuit breakers, auto-compaction | Basic max-rounds limit |
| **Streaming** | Block-streaming with chunked delivery | Full response only |

### What NEXUS Is Missing
1. **No dynamic model routing** -- every task uses the same model regardless of complexity
2. **No token budget tracking** -- no visibility into spend per session or per day
3. **No memory system** -- agents cannot recall past sessions or decisions
4. **No tool filtering** -- agents get full tool access even for trivial tasks
5. **No circuit breakers** -- if a model fails, there is no automatic fallback
6. **No incremental context** -- each contract starts fresh with no session history
7. **No typing/progress indicators** -- users see nothing until the full response arrives
