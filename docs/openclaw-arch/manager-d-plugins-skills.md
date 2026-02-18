# OpenClaw Architecture: Plugin & Skill System

> Manager D report -- consolidated from 3 research agents
> Generated: 2026-02-19

---

## 1. Plugin Architecture

### Overview
The plugin system (`src/plugins/`, ~38 source files) provides a full extensibility framework. Plugins can register tools, hooks, commands, HTTP handlers, CLI subcommands, background services, chat channel adapters, and LLM provider integrations -- all through a single unified API.

### Discovery (discovery.ts)
Plugins are discovered from **four origin tiers** (in priority order):
1. **config** -- explicit paths in `plugins.load` config array
2. **workspace** -- `.openclaw/extensions/` inside the workspace directory
3. **global** -- `~/.config/openclaw/extensions/` (user-level)
4. **bundled** -- shipped with the OpenClaw distribution

Each directory is scanned for `.ts/.js` files or subdirectories with `index.ts`/`package.json`. The `package.json` field `openclaw.extensions[]` declares entry points for multi-extension packages.

### Loading (loader.ts)
`loadOpenClawPlugins()` orchestrates the full lifecycle:
1. Normalize plugin config (enable/disable states, memory slot selection)
2. Run discovery to find all `PluginCandidate` entries
3. Load manifest registry (config schemas, metadata from package.json)
4. For each candidate: validate config schema (JSON Schema), load module via **jiti** (TypeScript-aware runtime loader), resolve `register`/`activate` export, create API handle, call `register(api)`
5. Build `PluginRegistry` with all registrations; cache by workspace+config key
6. Initialize the global hook runner

### Plugin Definition Contract
A plugin exports either:
- An `OpenClawPluginDefinition` object with `{ id, name, version, configSchema, register(api) }`
- Or a plain function `(api: OpenClawPluginApi) => void`

### Plugin API (`OpenClawPluginApi`)
The `api` object passed to `register()` exposes these registration methods:
- `registerTool(tool | factory, opts?)` -- LLM-callable tools
- `registerHook(events, handler, opts?)` -- internal event hooks
- `registerCommand(def)` -- slash commands that bypass the LLM
- `registerHttpHandler(handler)` -- catch-all HTTP handler
- `registerHttpRoute({ path, handler })` -- path-specific HTTP route
- `registerChannel(registration)` -- chat channel adapter (Telegram, Slack, etc.)
- `registerGatewayMethod(name, handler)` -- gateway RPC method
- `registerCli(registrar)` -- CLI subcommand via Commander.js
- `registerService(service)` -- background service with start/stop lifecycle
- `registerProvider(provider)` -- LLM provider (auth methods, model catalog)
- `on(hookName, handler)` -- typed lifecycle hooks (13 events, see below)

### Registry (registry.ts)
`PluginRegistry` is the central data structure containing arrays of all registered items: tools, hooks, channels, providers, gateway handlers, HTTP handlers/routes, CLI registrars, services, commands, and diagnostics. Each `PluginRecord` tracks status (`loaded`/`disabled`/`error`), registered item counts, and origin.

### Plugin Commands (commands.ts)
Plugins can register slash commands (e.g., `/tts`) that execute deterministically without LLM involvement. Commands are validated against a reserved name set (help, stop, config, etc.), matched at message processing time, and executed with authorization checks and argument sanitization.

### Memory Slot System
Only one plugin of `kind: "memory"` can be active at a time. The `slots.memory` config field selects which memory plugin wins.

---

## 2. Skill Contract

### Overview
Skills (`src/agents/skills/`) are Markdown-described capabilities that get injected into the LLM system prompt. They are NOT plugins -- they are lighter-weight prompt extensions loaded from directories containing `SKILL.md` files.

### Skill Interface
From `@mariozechner/pi-coding-agent`, a `Skill` has:
- `name`, `description`, `filePath`, `baseDir`, `source`
- The SKILL.md content becomes part of the system prompt via `formatSkillsForPrompt()`

### Skill Entry Enrichment
Each skill is wrapped in a `SkillEntry` with:
- `frontmatter` -- parsed from SKILL.md YAML front matter
- `metadata` (OpenClawSkillMetadata) -- `requires` (bins, env, config), `os`, `install` specs, `primaryEnv`
- `invocation` policy -- `userInvocable` (creates `/skillname` slash command), `disableModelInvocation` (excludes from prompt)

### Skill Sources (precedence low-to-high)
1. **extra** -- config `skills.load.extraDirs[]` + plugin-contributed skill dirs
2. **bundled** -- shipped with OpenClaw (bundled-dir.ts)
3. **managed** -- `~/.config/openclaw/skills/`
4. **workspace** -- `{workspaceDir}/skills/`

Later sources override earlier ones by name.

### Eligibility Filtering
`shouldIncludeSkill()` checks: explicit enable/disable config, bundled allowlist, OS compatibility, `always` flag, required binaries (local + remote), required env vars (with `apiKey`/`primaryEnv` fallback), required config paths.

### Skill Commands
User-invocable skills automatically get slash commands (e.g., `/weather`). Some skills declare `command-dispatch: tool` in frontmatter to route directly to a named tool, bypassing the LLM.

### Plugin-Skill Bridge
Plugins can contribute skill directories via their manifest's `skills[]` array. `resolvePluginSkillDirs()` resolves these, respecting enable state and memory slot decisions.

---

## 3. Command Pipeline

### Overview
The `src/commands/` directory (~44K lines, 150+ files) is NOT a command dispatch pipeline in the traditional middleware sense. It is a collection of **CLI commands and configuration wizards** organized by feature area.

### Structure
Commands are organized by feature domain:
- **agent.ts / agents.*.ts** -- agent management (add, delete, list, config, identity, providers)
- **auth-choice.*.ts** -- authentication flow for multiple providers (Anthropic, OpenAI, GitHub Copilot, xAI, MiniMax, etc.)
- **onboard-*.ts** -- interactive and non-interactive onboarding wizards (auth, channels, skills, custom config)
- **configure.*.ts** -- configuration commands (gateway, channels, daemon, wizard)
- **doctor*.ts** -- diagnostic/health check commands (auth, security, sandbox, state migrations, gateway)
- **status*.ts / health.ts** -- system status and health reporting
- **model-picker.ts / models.ts** -- model selection and management
- **sessions.ts** -- session management
- **sandbox.ts** -- sandbox configuration

### Plugin Command Integration
Plugin-registered commands are checked BEFORE built-in commands. The flow is:
1. `matchPluginCommand(commandBody)` checks the plugin command registry
2. If matched, `executePluginCommand()` runs the handler with auth checks
3. If not matched, falls through to built-in command handling and then to agent/LLM

---

## 4. Hook System

### Internal Hooks (`src/hooks/internal-hooks.ts`)
A lightweight pub-sub event system using a global `Map<string, InternalHookHandler[]>`:
- **Event structure**: `{ type, action, sessionKey, context, timestamp, messages[] }`
- **Event types**: `command`, `session`, `agent`, `gateway`
- **Registration**: `registerInternalHook(eventKey, handler)` where `eventKey` is `"type"` (all actions) or `"type:action"` (specific)
- **Triggering**: `triggerInternalHook(event)` calls type-level then action-level handlers sequentially; errors are caught per-handler

### Hook Discovery (`workspace.ts`)
Hooks live in directories containing `HOOK.md` + `handler.ts`. Discovered from:
1. **bundled** -- 4 built-in hooks (boot-md, command-logger, session-memory, soul-evil)
2. **managed** -- `~/.config/openclaw/hooks/`
3. **workspace** -- `{workspaceDir}/hooks/`

### Hook Metadata
HOOK.md frontmatter declares: `events[]`, `os[]`, `requires` (bins, env, config), `always`, `export` name, `install[]` specs.

### Plugin Lifecycle Hooks (typed)
Plugins get 13 strongly-typed lifecycle hooks via `api.on(hookName, handler)`:
- **Agent**: `before_agent_start`, `agent_end`
- **Compaction**: `before_compaction`, `after_compaction`
- **Message**: `message_received`, `message_sending` (can modify/cancel), `message_sent`
- **Tool**: `before_tool_call` (can block/modify params), `after_tool_call`, `tool_result_persist`
- **Session**: `session_start`, `session_end`
- **Gateway**: `gateway_start`, `gateway_stop`

Some hooks return results (e.g., `before_tool_call` can return `{ block: true, blockReason }`; `message_sending` can return `{ cancel: true }`).

### Bundled Hook Examples
- **session-memory**: On `/new` command, reads recent session messages, generates an LLM-powered slug, saves session context to a dated memory file
- **boot-md**: Runs gateway boot checklist on `gateway:startup`
- **command-logger**: Logs command events
- **soul-evil**: Personality/behavior modifier hook

---

## 5. Cron & Scheduling

### CronService (`src/cron/service.ts`)
A class wrapping an ops-based architecture:
- `start()` -- load store, clear stale markers, run missed jobs, arm timer
- `stop()` -- stop timer
- `add/update/remove(job)` -- CRUD operations
- `run(id, mode?)` -- manual trigger (`due` or `force`)
- `wake({ mode, text })` -- immediate or next-heartbeat wake

### Schedule Types (`types.ts`)
Three schedule kinds:
- **at** -- one-shot absolute time (ISO string), auto-deletes after run
- **every** -- interval in milliseconds with optional anchor
- **cron** -- standard cron expression with timezone support (via `croner` library)

### Payload Types
Three job payload kinds:
- **systemEvent** -- injects text into the main session as a system event
- **agentTurn** -- starts an isolated agent session with a message, optional model/thinking/timeout overrides
- **script** -- executes a shell command with optional cwd, shell, timeout

### Delivery System (`delivery.ts`, `deliver-result.ts`)
For isolated agent turns, results can be delivered:
- **none** -- no delivery
- **announce** -- send output to a channel (Telegram, WhatsApp, etc.)
- **direct** -- send directly to a target
- **process** -- run output through another LLM model before delivery (with customizable prompt)

Delivery targets are resolved from the job config or inferred from the last active channel.

### Execution Architecture
- **Timer** (`service/timer.ts`): Single `setTimeout` armed to the nearest next-run time; re-arms after each execution
- **Concurrency**: Jobs execute with locking (`service/locked.ts`) to prevent overlapping runs; stale `runningAtMs` markers cleared on startup
- **Error handling**: Consecutive error counter with backoff; jobs track `lastStatus`, `lastError`, `lastDurationMs`
- **Session reaper**: Cleans up stale cron sessions (`session-reaper.ts`)
- **Run log**: Records execution history (`run-log.ts`)
- **Store**: JSON file persistence at configurable path (`store.ts`)

### Script Runner (`script-runner.ts`)
Executes shell commands for `script` payload kind with configurable timeout, working directory, and shell.

---

## 6. Key Patterns NEXUS Should Adopt

### 1. Unified Registration API
OpenClaw's `OpenClawPluginApi` is the standout pattern. A single `api` object given to `register(api)` lets plugins declare all their capabilities in one place. NEXUS equipment should follow this: `equipment.register(api)` where `api.registerSkill()`, `api.registerTool()`, `api.registerHook()` are all available.

### 2. Multi-Tier Discovery with Override
The 4-tier discovery (config > workspace > global > bundled) with same-name override is elegant. NEXUS should adopt: project-local equipment overrides global, which overrides built-in.

### 3. Frontmatter-Driven Metadata
Skills and hooks use Markdown files with YAML frontmatter for metadata (requirements, OS filters, invocation policies). This is human-readable, version-controllable, and works without a build step. NEXUS skill definitions could use the same pattern.

### 4. Eligibility Filtering
The `shouldIncludeSkill()` pattern -- checking bins, env vars, OS, config paths, allowlists -- is a production-ready capability gate. NEXUS should gate equipment/skills on similar prerequisite checks.

### 5. Typed Lifecycle Hooks with Result Returns
The 13 plugin lifecycle hooks with typed events AND return values (block, modify, cancel) is a powerful interception pattern. NEXUS pipeline stages should emit typed events that equipment can intercept.

### 6. Cron Delivery Pipeline
The cron system's separation of execution (3 payload kinds) from delivery (4 modes including LLM post-processing) is a clean design. NEXUS scheduled tasks could adopt this execution/delivery split.

### 7. Plugin Command Bypass
The ability for plugins to register deterministic commands that bypass the LLM entirely is important for performance and reliability. NEXUS equipment should support both LLM-mediated and direct-dispatch commands.

---

## 7. Relevance to NEXUS

### Equipment System
NEXUS "equipment" maps directly to OpenClaw's plugin system. Key takeaways:
- Use a registration-based API pattern, not inheritance
- Support JSON Schema config validation per equipment
- Implement memory slot exclusivity (only one memory backend active)
- Cache registries by config key for performance

### Skill Marketplace
NEXUS skills can follow OpenClaw's skill model:
- Markdown-defined skills with frontmatter metadata
- Automatic slash-command generation for user-invocable skills
- Prompt injection via `formatSkillsForPrompt()` pattern
- Eligibility gating based on runtime environment

### Pipeline Hooks
NEXUS contract execution pipeline should expose typed hook points:
- `before_worker_start`, `after_worker_complete`
- `before_qa_review`, `after_qa_verdict`
- `on_pipeline_error`, `on_pipeline_complete`
- Allow equipment to intercept, modify, or block pipeline stages

### Task Scheduling
NEXUS could adopt OpenClaw's cron patterns for:
- Recurring pipeline execution (nightly builds, scheduled reviews)
- One-shot delayed tasks (deferred deployments)
- Script execution with timeout and error tracking
- Result delivery through multiple channels

### Key Metrics from OpenClaw
- Plugins: ~38 source files, ~150K lines including tests
- Hooks: ~6K lines, 4 bundled hooks, 13 typed lifecycle events
- Cron: ~9K lines, 3 schedule types, 3 payload kinds, 4 delivery modes
- Commands: ~44K lines, organized by feature domain (not a pipeline)
- Skills: located at `src/agents/skills/`, loaded from @mariozechner/pi-coding-agent
