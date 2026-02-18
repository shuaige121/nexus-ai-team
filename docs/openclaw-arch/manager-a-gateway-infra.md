# OpenClaw Architecture: Gateway & Infrastructure

> Manager A Report -- Generated 2026-02-19
> Domain: src/gateway/, src/config/, src/infra/, src/security/, src/cli/

---

## 1. Gateway Architecture

### Entry Point & Server Lifecycle

The gateway is a **single-process Node.js server** started via `startGatewayServer(port, opts)` in `server.impl.ts`. The startup sequence is:

1. **Config load & validation** -- Reads `openclaw.json` via JSON5, applies legacy migrations, validates via Zod schemas, applies defaults chain (message -> logging -> session -> agent -> context-pruning -> compaction -> model -> router).
2. **Plugin auto-enable** -- Detects installed plugins and auto-enables them in config.
3. **Runtime state creation** -- Builds the HTTP/WS server, canvas host, hook handlers, and all in-memory state maps.
4. **Sidecar launch** -- Starts browser control, Gmail watcher, internal hooks, channels (Telegram/Discord/Slack/etc.), plugin services, memory backend.
5. **Discovery & networking** -- Bonjour/mDNS, Tailscale exposure, wide-area DNS.
6. **Cron, heartbeat, maintenance timers** -- Scheduled jobs, health snapshots, update checks.

### Transport Layer (Dual: WebSocket + HTTP)

- **WebSocket (primary)**: JSON-RPC style protocol. Clients connect, authenticate, then send `{ method, params }` messages. ~25 handler groups registered via `coreGatewayHandlers` (chat, agent, config, models, sessions, channels, cron, health, etc.).
- **HTTP endpoints**: Layered onto the same `http.Server`:
  - `/v1/chat/completions` -- OpenAI-compatible chat API
  - `/v1/responses` -- OpenResponses API
  - `/hooks/<path>` -- Webhook ingress (wake, agent, custom mappings)
  - `/api/tools/invoke` -- Direct tool invocation
  - Control UI static files (SPA)
  - Canvas host paths
  - Slack HTTP callbacks

### Request Flow (WebSocket)

```
Client WS connect -> auth check (token/password/tailscale/device) 
  -> role assignment (operator/node) -> scope resolution
  -> method dispatch -> authorizeGatewayMethod(method, client)
  -> handler lookup from coreGatewayHandlers + plugin handlers
  -> handler execution -> respond(ok, result, error)
```

### Key Abstractions

- **GatewayServer**: The top-level facade with `close()` method.
- **GatewayRequestHandlers**: A `Record<method, handler>` map for all WS methods.
- **ChatRunState**: Registry + buffers + delta timing for streaming chat to clients.
- **ToolEventRecipientRegistry**: Tracks which WS connections want tool events per run.
- **NodeRegistry**: Manages connected remote nodes (Raspberry Pi, mobile, etc.).
- **ChannelManager**: Per-channel lifecycle (start/stop/logout) for Telegram, Discord, etc.
- **Broadcast**: Fan-out events to all connected WS clients with backpressure (`dropIfSlow`).

### Boot System

`BOOT.md` is read from the workspace on gateway start. If present, it runs as an agent prompt -- useful for automated startup tasks like sending notifications.

---

## 2. Configuration System

### Config Loading Pipeline

```
openclaw.json (JSON5)
  -> resolveConfigIncludes($include directives)
  -> applyConfigEnv (config.env -> process.env)  
  -> resolveConfigEnvVars (${VAR} substitution)
  -> validateConfigObjectWithPlugins (Zod schema)
  -> applyDefaults chain (8 layers)
  -> normalizeConfigPaths
  -> applyConfigOverrides (runtime env overrides)
```

Key design: Config is a **pure function** -- `loadConfig()` reads from disk every time (no in-memory cache of the config object itself). The gateway has a config reloader (`config-reload.ts`) that watches for file changes.

### Config File Features

- **JSON5 format** -- Comments allowed, trailing commas, unquoted keys.
- **$include directives** -- Compose config from multiple files.
- **${VAR} env substitution** -- Reference environment variables in config values.
- **Legacy migration** -- Auto-detects old config schemas and migrates (3 migration generations).
- **Backup rotation** -- Keeps 5 config backups on write.
- **Version stamping** -- Records `lastTouchedVersion` and warns if config is from a newer version.
- **Shell env fallback** -- Can source API keys from shell profile if not in env.

### Config Type System

The config is deeply typed via TypeScript interfaces in `types.*.ts` files:

- `types.base.ts`: Gateway settings (bind, port, auth, TLS, trusted proxies, control UI)
- `types.agents.ts`: Multi-agent config, agent list, per-agent overrides
- `types.models.ts`: Model aliases, allowlists, fallbacks
- `types.router.ts`: Query router config (complexity scoring, tier thresholds)
- `types.tools.ts`: Tool policies, groups, tier filtering
- `types.channels.ts`: Per-channel config (Telegram, Discord, Slack, IRC, etc.)
- `types.hooks.ts`: Webhook ingress config, hook mappings
- Plus: sessions, approvals, sandbox, memory, cron, TTS, browser, etc.

### Model Routing

Model selection is config-driven through `agents.defaults.models` and per-agent overrides. The router (`types.router.ts`) supports:

- Complexity scoring with configurable thresholds
- Tier-based model selection (fast/balanced/capable)
- Provider-aware model picking (matches agent's default provider)
- Tool tier filtering (fast=3, balanced=~14, capable=all tools)

### Group Policy

`group-policy.ts` manages who can interact with the agent per-channel. Policies control DM access, group chat behavior, and allowlists.

---

## 3. Infrastructure Layer

### Session Cost & Usage Tracking (`session-cost-usage.ts`)

A comprehensive cost tracking system that:

- Parses JSONL transcript files line-by-line (streaming, memory-efficient)
- Computes per-session totals: input/output/cacheRead/cacheWrite tokens and costs
- Provides daily breakdowns, message counts, latency stats, model usage, tool usage
- Supports cost breakdown by token type from actual API cost data
- Types: `CostUsageSummary`, `SessionCostSummary`, `SessionDailyUsage`

### Heartbeat Runner (`heartbeat-runner.ts`)

A ~35KB file managing the proactive heartbeat system:

- Periodically sends heartbeat prompts to the agent (scheduled)
- Supports model overrides per heartbeat
- Cost guard to prevent runaway spending
- Deduplication to avoid concurrent heartbeats
- Session reset capability
- Visibility control per channel (suppress OK responses on webchat)
- Active hours filtering

### Execution Approvals (`exec-approvals.ts`)

A sophisticated command execution gating system:

- **Security levels**: `deny`, `allowlist`, `full`
- **Ask modes**: `off`, `on-miss` (ask when not in allowlist), `always`
- **Allowlist**: Pattern-based with last-used tracking
- **Per-agent overrides**: Each agent can have its own security policy
- **Socket-based**: Uses a Unix socket + token for approval forwarding
- **Safe bins**: Default safe binaries (jq, grep, cut, sort, etc.)
- Stored in `~/.openclaw/exec-approvals.json`

### Other Infra Components

- **Gateway Lock** (`gateway-lock.ts`): Prevents multiple gateway instances
- **Retry Policy** (`retry-policy.ts`): Configurable retry with backoff
- **Runtime Guard** (`runtime-guard.ts`): Enforces minimum Node.js version
- **Restart Sentinel** (`restart-sentinel.ts`): Graceful restart coordination
- **Provider Usage** (`provider-usage.*.ts`): Per-provider API usage tracking (Anthropic, OpenAI, Gemini, etc.)
- **Bonjour Discovery** (`bonjour-discovery.ts`): LAN service discovery
- **Tailscale Integration** (`tailscale.ts`): VPN mesh networking
- **SSH Tunneling** (`ssh-tunnel.ts`): Remote node connectivity
- **Update Runner** (`update-runner.ts`): Auto-update system

---

## 4. Security Model

### Authentication Architecture

Multi-layered auth in `auth.ts`:

1. **Token auth**: Bearer token in WS connect or HTTP header
2. **Password auth**: Basic auth alternative
3. **Tailscale auth**: Identity from Tailscale mesh (when mode="serve")
4. **Device auth**: Paired device tokens (mobile/desktop clients)
5. **Local direct**: Loopback connections trusted implicitly (unless proxied)

### Authorization (RBAC)

Role-based method authorization in `server-methods.ts`:

- **Roles**: `operator` (human), `node` (remote device)
- **Scopes**: `operator.admin`, `operator.read`, `operator.write`, `operator.approvals`, `operator.pairing`
- Methods are classified into scope groups (READ_METHODS, WRITE_METHODS, ADMIN, PAIRING, APPROVAL)
- Node role can only call node-specific methods (`node.invoke.result`, `node.event`, `skills.bins`)
- Unrecognized methods default to requiring admin scope

### Security Audit System (`audit.ts`)

A comprehensive security scanner with 20+ checks:

- **Gateway config findings**: Bind mode vs auth, trusted proxies, control UI exposure
- **Filesystem findings**: State dir and config file permissions (world/group writable/readable, symlinks)
- **Channel security**: DM policy openness, group policy, allowFrom configuration
- **Extended checks** (in `audit-extra.ts`): Attack surface summary, exposure matrix, hooks hardening, model hygiene, small model risks, secrets in config, plugin trust, skills code safety, synced folders
- Findings are severity-classified: `info`, `warn`, `critical`
- Deep mode can probe the running gateway for live vulnerability checks

### External Content Safety (`external-content.ts`)

Validates and sanitizes external content injected into agent context (from hooks, APIs).

### Skill Scanner (`skill-scanner.ts`)

Scans installed skills for code safety issues before allowing execution.

---

## 5. CLI Architecture

### Program Structure

The CLI uses **Commander.js** with lazy-loaded subcommands:

```
runCli(argv)
  -> loadDotEnv, normalizeEnv, ensureOpenClawCliOnPath
  -> assertSupportedRuntime
  -> tryRouteCli (fast-path for known commands)
  -> buildProgram (Commander program tree)
  -> registerSubCliByName (lazy load the specific subcommand)
  -> registerPluginCliCommands
  -> program.parseAsync(argv)
```

### Command Registration Pattern

Commands are registered in `program/register.*.ts` files:

- `register.agent.ts` -- Agent management
- `register.configure.ts` -- Config editing
- `register.maintenance.ts` -- Doctor, update, security
- `register.message.ts` -- Send messages
- `register.onboard.ts` -- Setup wizard
- `register.setup.ts` -- Initial configuration
- `register.status-health-sessions.ts` -- Status, health, sessions
- `register.subclis.ts` -- Sub-CLI commands (gateway, nodes, daemon, etc.)

### Route-First Pattern

`route.ts` implements a fast-path: Before building the full Commander tree, it checks if the command matches a known "routed command" (from `command-registry.ts`). If yes, it runs directly -- avoiding the overhead of loading all subcommands. This is a performance optimization for the most common commands.

### Notable CLI Subcommands

- `gateway` -- Start the gateway server
- `config` -- Get/set/delete config values (supports dot-path notation like `agents.defaults.model`)
- `models` -- List available models with pricing/status
- `sessions` -- Session management (list, preview, delete, compact)
- `security` -- Run security audit
- `update` -- Self-update
- `plugins` -- Plugin management
- `browser` -- Browser automation control
- `hooks` -- Webhook management

---

## 6. Key Patterns NEXUS Should Adopt

### 1. Config-as-Code with Layered Defaults
OpenClaw's config pipeline (JSON5 -> includes -> env substitution -> validation -> 8 default layers) is extremely robust. NEXUS should adopt:
- Zod schema validation for all config
- Layered defaults (so partial configs "just work")
- `$include` for config composition (e.g., separate model config from channel config)

### 2. Method-Based RPC over WebSocket
The `{ method, params } -> handler` pattern is clean and extensible. Each handler group is a separate file. NEXUS could use this for its gateway API instead of REST-only.

### 3. Execution Approval System
The allowlist + ask-mode + per-agent override pattern for command execution is exactly what NEXUS needs for safe agent tool use. The Unix socket forwarding for interactive approvals is clever.

### 4. Security Audit as a First-Class Feature
Having `openclaw security` as a built-in CLI command that scans for misconfigurations is excellent. NEXUS should build a similar `nexus audit` command.

### 5. Session Cost Tracking
The per-session, per-day, per-model cost tracking with JSONL transcript parsing is production-grade. NEXUS should adopt this for budget management.

### 6. Heartbeat System
Proactive heartbeats with cost guards and active hours are essential for autonomous agents. NEXUS's pipeline model could use this for health monitoring.

### 7. Plugin Architecture
Gateway methods and CLI commands can be extended via plugins. NEXUS should plan for extensibility from the start.

### 8. Route-First CLI Pattern
Lazy loading subcommands and fast-routing common commands is a great UX optimization for CLIs with many commands.

---

## 7. Key Differences from NEXUS

### What OpenClaw Has That NEXUS Lacks

| Capability | OpenClaw | NEXUS |
|---|---|---|
| **Real-time transport** | WebSocket + HTTP dual | HTTP only (FastAPI) |
| **Config validation** | Zod schemas, 8 default layers | Basic Python dicts |
| **Multi-channel** | Telegram, Discord, Slack, IRC, WhatsApp, iMessage | None (CLI only) |
| **Security audit** | 20+ checks, deep probe mode | No security scanning |
| **Cost tracking** | Per-session, per-day, per-model | No cost tracking |
| **Execution gating** | Allowlist + ask-mode + per-agent | `--dangerously-skip-permissions` |
| **Auto-update** | Built-in update runner | Manual git pull |
| **Remote nodes** | Bonjour discovery, Tailscale, SSH tunnel | Single machine |
| **Session management** | JSONL transcripts, compaction, preview | File system only |
| **Heartbeat/cron** | Proactive scheduling with cost guards | No scheduled runs |

### Architectural Gaps in NEXUS

1. **No WebSocket layer** -- NEXUS cannot stream agent output in real-time. OpenClaw's chat delta streaming (buffered, 150ms throttle) is essential for interactive use.
2. **No config schema validation** -- NEXUS config is ad-hoc Python dicts. OpenClaw's Zod-validated, type-safe config prevents entire classes of misconfiguration bugs.
3. **No execution approval system** -- NEXUS runs agents with full permissions. OpenClaw's gating system would prevent agents from running arbitrary commands.
4. **No cost visibility** -- NEXUS has no way to track how much each session/agent/day costs. This is critical for budget management.
5. **No plugin system** -- NEXUS cannot be extended without modifying core code. OpenClaw's plugin architecture allows third-party extensions.
6. **No multi-machine support** -- NEXUS runs on a single machine. OpenClaw's node registry, Bonjour discovery, and SSH tunneling enable distributed operation.

---

*Report generated by Manager A (Gateway & Infrastructure domain)*
*Source: OpenClaw project at /home/leonard/openclaw, branch session-recall*
