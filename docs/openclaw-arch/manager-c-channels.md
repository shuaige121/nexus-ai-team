# OpenClaw Architecture: Channel & Integration System

> Manager C Report -- Channel & Integration Architecture
> Generated: 2026-02-19

---

## 1. Channel Abstraction

OpenClaw supports 8+ built-in channels (Telegram, WhatsApp, Discord, IRC, Google Chat, Slack,
Signal, iMessage) plus unlimited external channels via the plugin system. The abstraction is
split into three conceptual layers:

### 1.1 Registry (`src/channels/registry.ts`)
- `CHAT_CHANNEL_ORDER` -- ordered list of built-in channel IDs
- `CHAT_CHANNEL_META` -- per-channel metadata (label, docs path, blurb, system image)
- `CHAT_CHANNEL_ALIASES` -- alias map (e.g., "imsg" -> "imessage", "gchat" -> "googlechat")
- `normalizeAnyChannelId()` -- resolves both built-in and plugin-registered channel IDs
  through the active plugin registry

### 1.2 Dock (`src/channels/dock.ts`)
The "dock" is a lightweight per-channel behavior descriptor. Each channel gets a `ChannelDock`:
```
ChannelDock {
  id, capabilities, commands?, outbound?, streaming?,
  elevated?, config?, groups?, mentions?, threading?, agentPrompt?
}
```
Key properties:
- **capabilities**: chatTypes (direct/group/channel/thread), polls, reactions, media, etc.
- **outbound.textChunkLimit**: per-channel max message length (e.g., Discord=2000, IRC=350)
- **streaming**: block-streaming coalesce defaults (minChars, idleMs)
- **config.resolveAllowFrom / formatAllowFrom**: per-channel allowlist resolution
- **groups**: mention-require policies and tool policies per group
- **threading**: reply-to mode and tool context builders
- **mentions.stripPatterns**: regex to strip @-mentions per platform

Shared code imports from `dock.ts` (lightweight), NOT from the plugin index (heavy).

### 1.3 ChannelPlugin (`src/channels/plugins/types.plugin.ts`)
The full plugin contract -- approximately 20 adapter interfaces:
- **config**: listAccountIds, resolveAccount, setAccountEnabled, deleteAccount
- **setup**: applyAccountConfig, validateInput (CLI onboarding)
- **gateway**: startAccount, stopAccount, loginWithQrStart/Wait, logoutAccount
- **outbound**: deliveryMode (direct/gateway/hybrid), sendText, sendMedia, sendPoll
- **status**: probeAccount, auditAccount, buildAccountSnapshot, collectStatusIssues
- **security**: resolveDmPolicy, collectWarnings
- **pairing**: normalizeAllowEntry, notifyApproval
- **directory**: self, listPeers, listGroups, listGroupMembers
- **actions**: handleAction (send, edit, react, pin, etc.)
- **heartbeat**: checkReady, resolveRecipients
- **auth**: login flow adapter
- **agentTools**: channel-owned tools exposed to the AI agent

## 2. Message Flow

### Inbound (Receive)
```
Platform API (webhook/polling/socket)
  -> Channel-specific handler (e.g., grammy bot, discord.js client, Slack socket)
  -> Build platform context (TelegramContext, etc.)
  -> Download media if present
  -> buildMessageContext() -- normalizes to MsgContext:
       { Channel, From, To, Body, ChatType, SenderId, SenderName,
         SenderUsername, MediaUrl, ReplyToId, GroupSubject, ... }
  -> Allowlist check (sender identity validation)
  -> Mention gating (group: require @mention or bypass via command)
  -> Command gating (access group authorization)
  -> Session resolution (session key from channel+chat+thread)
  -> Record inbound session + route to agent
  -> Agent processes -> generates reply
```

### Outbound (Send)
```
Agent reply (text, media, tool results)
  -> Reply prefix (model name, identity)
  -> Text chunking (per-channel limits)
  -> Channel outbound adapter:
       deliveryMode: "direct" (call API), "gateway" (HTTP to gateway), "hybrid"
  -> Platform-specific send (Telegram API, Discord REST, Slack Web API, etc.)
  -> Ack reaction cleanup (remove thinking emoji)
  -> Record outbound session metadata
```

### Normalize Layer (`src/channels/plugins/normalize/`)
Per-channel normalizers: `telegram.ts`, `discord.ts`, `slack.ts`, `signal.ts`,
`whatsapp.ts`, `imessage.ts` -- transform platform-specific payloads into the
unified `MsgContext` shape.

## 3. Core Channel Patterns

### Telegram (`src/telegram/`, ~21K lines)
- **Transport**: grammy Bot framework; webhook OR long-polling
- **Entry**: `createTelegramBot()` sets up grammy Bot with middleware pipeline
- **Sequentialization**: `sequentialize()` by chat+thread key prevents race conditions
- **Throttling**: `apiThrottler()` from `@grammyjs/transformer-throttler`
- **Message context**: `buildTelegramMessageContext()` normalizes grammy ctx -> MsgContext
- **Media**: downloads via Telegram File API, sticker cache, voice transcription
- **Outbound** (`send.ts`, 31K): caption splitting, video-note support, proxy support
- **Native commands**: `/model`, `/help`, etc. via `registerTelegramNativeCommands()`
- **Multi-account**: `resolveTelegramAccount()` resolves config per accountId

### Discord (`src/discord/`, ~14K lines)
- **Transport**: discord.js client via gateway WebSocket
- **Structure**: `monitor/` subdir with modular handlers (listeners, message-handler, threading)
- **Rich features**: slash commands, threads, embeds, stickers/emoji upload, guild management
- **Outbound**: split across `send.channels.ts`, `send.guild.ts`, `send.messages.ts`,
  `send.outbound.ts`, `send.reactions.ts` -- very granular action decomposition
- **PluralKit**: integration for multi-user systems
- **Threading**: thread creation, reply targets, sanitized thread names

### Slack (`src/slack/`, ~10K lines)
- **Transport**: Socket Mode (no webhook needed)
- **Structure**: `monitor/` subdir (commands, policy, provider, replies)
- **Threading**: Slack thread_ts based, dedicated `threading-tool-context.ts`
- **Actions**: edit, react, pin, read messages, list reactions -- all via Slack Web API

### LINE (`src/line/`, ~9K lines)
- **Transport**: Webhook-based with LINE Messaging API
- **Rich output**: Flex Messages, Rich Menus, Quick Replies, Carousels
- **Markdown conversion**: `markdown-to-line.ts` converts markdown to Flex Bubble containers
- **Templates**: info cards, list cards, image cards, receipt cards, device control cards

### Common Patterns Across Channels
1. **Account resolution**: each channel has `resolveXxxAccount()` reading from `openclaw.json`
2. **Monitor pattern**: `monitorXxxProvider()` starts the listener and wires handlers
3. **Allowlist gating**: sender checked against `allowFrom` list before processing
4. **Group mention policy**: configurable require-mention per group/channel
5. **Session key derivation**: `channel:accountId:chatId[:threadId]`
6. **Ack reactions**: thinking emoji on receive, remove after reply
7. **Typing indicators**: `createTypingCallbacks()` shared abstraction

## 4. Media Handling

### Inbound Media
- Each channel extracts media references during context building
- Telegram: File API download with `download.ts`, sticker metadata cache
- WhatsApp: decrypted media from baileys, JPEG optimization
- Discord: attachment URLs from message objects
- Signal: attachments from signal-cli REST API
- All channels normalize to `{ path, contentType, stickerMetadata? }`

### Outbound Media
- `mediaUrl` field in outbound context
- Per-channel limits: `media-limits.ts` in channel plugins
- Caption splitting: long captions split across messages
- GIF playback flag for animated content
- Voice/video note special handling (Telegram)

### Vision Support
- `resolveStickerVisionSupport()` checks if current model supports image input
- Used to decide whether to send sticker images to the LLM or describe them textually

## 5. Plugin / Extension System

### Discovery (`src/plugins/discovery.ts`)
Four-tier plugin discovery with priority ordering:
1. **config** (priority 0): explicit paths in `openclaw.json` `plugins.load`
2. **workspace** (priority 1): `.openclaw/extensions/` in workspace root
3. **global** (priority 2): `~/.config/openclaw/extensions/`
4. **bundled** (priority 3): built-in plugins shipped with OpenClaw

Discovery scans for:
- Direct `.ts`/`.js` files
- Directories with `package.json` containing `openclaw.extensions` array
- Directories with `index.ts`/`index.js`

### Manifest (`openclaw.plugin.json`)
Each plugin requires a JSON manifest with:
- `id`: unique plugin identifier
- `configSchema`: JSON Schema for validation
- Optional: `kind`, `channels`, `providers`, `skills`, `name`, `version`

### Plugin Loading (`src/plugins/loader.ts`)
1. Discover candidates across all tiers
2. Load manifests, validate schemas
3. Use `jiti` (JIT TypeScript loader) to require plugin modules
4. Resolve `register()` or `activate()` export
5. Call `register(api)` with the `OpenClawPluginApi`
6. Plugin calls `api.registerChannel()`, `api.registerTool()`, etc.
7. Store in global `PluginRegistry` singleton

### Plugin Registry (`src/plugins/registry.ts`)
Central registry holding all plugin registrations:
```
PluginRegistry {
  plugins[], tools[], hooks[], typedHooks[],
  channels[], providers[], gatewayHandlers{},
  httpHandlers[], httpRoutes[], cliRegistrars[],
  services[], commands[], diagnostics[]
}
```

### Plugin API (`OpenClawPluginApi`)
What a plugin can register:
- `registerChannel(plugin)` -- add a new messaging channel
- `registerTool(tool)` -- add agent tools
- `registerHook(events, handler)` -- lifecycle hooks
- `registerProvider(provider)` -- LLM provider
- `registerGatewayMethod(method, handler)` -- gateway RPC methods
- `registerHttpHandler/Route` -- HTTP endpoints
- `registerCli(registrar)` -- CLI commands
- `registerService(service)` -- background services
- `registerCommand(command)` -- native chat commands
- `on(hookName, handler)` -- typed lifecycle hooks

### Lifecycle Hooks
14 hook points: `before_agent_start`, `agent_end`, `before/after_compaction`,
`message_received/sending/sent`, `before/after_tool_call`, `tool_result_persist`,
`session_start/end`, `gateway_start/stop`

## 6. Key Patterns NEXUS Should Adopt

### 6.1 Two-Tier Channel Abstraction
- **Dock** (lightweight): capabilities, limits, policies -- used everywhere
- **Plugin** (heavyweight): gateway, outbound, status -- used at execution boundaries
- This prevents eager loading of heavy dependencies across the codebase

### 6.2 Normalized Message Context
- All channels normalize to a single `MsgContext` shape before processing
- This is the key enabler for channel-agnostic agent logic
- NEXUS should define a similar `AgentTaskContext` for cross-agent communication

### 6.3 Plugin Discovery with Priority
- Four-tier discovery (config > workspace > global > bundled) with deduplication
- Manifest-driven metadata (no code execution needed for catalog browsing)
- NEXUS should adopt for agent/tool discovery

### 6.4 Adapter Pattern for Optional Features
- Approximately 20 optional adapter interfaces (groups, threading, directory, actions, etc.)
- Channels implement only what they support; `capabilities` declares what is available
- NEXUS agents should declare capabilities similarly

### 6.5 Account Multi-tenancy
- Each channel supports multiple accounts (e.g., 3 Telegram bots)
- Account resolution, per-account config, per-account status
- NEXUS should support multiple instances of the same agent type

### 6.6 Gateway Hybrid Delivery
- Outbound supports "direct" (in-process), "gateway" (HTTP), or "hybrid"
- Enables both embedded and microservice deployment models

## 7. Relevance to NEXUS

### Agent Communication Layer
NEXUS dispatches work to agents (Claude, Codex) via tmux + CLI. OpenClaw's channel
abstraction provides a proven pattern for normalizing communication across heterogeneous
interfaces. NEXUS could adopt:

1. An `AgentChannel` abstraction to normalize tmux, SSH, HTTP, and future agent interfaces
   behind a common `AgentChannelPlugin` contract
2. Capability declaration so agents declare what they support (code execution, file I/O,
   web search, etc.) similar to `ChannelCapabilities`
3. Message normalization so all agent inputs/outputs go through a normalized envelope
   format before routing, just like `MsgContext`

### Plugin Architecture for Extensibility
NEXUS Phase 2 (execution layer) should adopt the plugin pattern:
- Manifest-based discovery for new agent types
- `register(api)` pattern for adding agents, tools, and pipelines
- Typed hook system for pipeline stages (before_dispatch, after_completion, etc.)

### Configuration Hierarchy
OpenClaw's per-channel, per-account, per-group config cascade is a pattern NEXUS needs
for per-agent, per-task, per-team configuration management.

---

*Report by Manager C (Channel & Integration Architecture)*
*Source: OpenClaw codebase at /home/leonard/openclaw, branch session-recall*
