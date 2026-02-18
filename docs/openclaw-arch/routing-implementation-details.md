# OpenClaw Routing Implementation Details

> **Purpose**: Technical reference for porting the OpenClaw query router, model fallback, circuit breaker, and tool tier filtering system to Python for the NEXUS AI-Team project.
>
> **Source files** (on `192.168.7.13:/home/leonard/openclaw/src/`):
> - `agents/query-router.ts` - Complexity scoring and tier selection
> - `agents/model-fallback.ts` - Fallback chain with circuit breaker integration
> - `agents/circuit-breaker.ts` - Per-model circuit breaker state machine
> - `agents/failover-error.ts` - Error classification for failover decisions
> - `agents/tool-policy.ts` - Tool groups and policy filtering
> - `agents/pi-tools.ts` - Tool pipeline with router-based filtering
> - `config/types.router.ts` - Config schema for the router
>
> **Generated**: 2026-02-19

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Config Schema](#2-config-schema)
3. [Query Router: Complexity Scoring](#3-query-router-complexity-scoring)
4. [Query Router: Tier Selection](#4-query-router-tier-selection)
5. [Query Router: Budget Caps](#5-query-router-budget-caps)
6. [Query Router: Provider-Aware Model Picking](#6-query-router-provider-aware-model-picking)
7. [Query Router: Override Rules](#7-query-router-override-rules)
8. [Tool Policy: Groups and Filtering](#8-tool-policy-groups-and-filtering)
9. [Tool Tier Filtering (Router + Tools Integration)](#9-tool-tier-filtering-router--tools-integration)
10. [Circuit Breaker](#10-circuit-breaker)
11. [Model Fallback Chain](#11-model-fallback-chain)
12. [Failover Error Classification](#12-failover-error-classification)
13. [Production Config (Live)](#13-production-config-live)
14. [Python Porting Notes](#14-python-porting-notes)

---

## 1. System Overview

The routing system has four layers that execute in sequence for each incoming message:

```
User Message
    |
    v
[1. Query Router] -- classifyQueryComplexity() --> score in [0, 1]
    |                                              + signal labels
    v
[2. Tier Selection] -- selectModelTier(score) --> fast | balanced | capable
    |                  + budget cap override
    v
[3. Model Picking] -- pickModel(tierModels, currentProvider) --> provider/model
    |                  provider-aware: prefers matching provider
    v
[4. Tool Filtering] -- applyRouterToolFilter(tools, tier) --> filtered tool list
    |                  tier.tools.allow / tier.tools.deny
    v
[Model Call with Fallback] -- runWithModelFallback() --> try candidates in order
    |                          circuit breaker per model
    v
[Response]
```

**Key design principle**: The router runs TWICE per request -- once for model selection (in the main routing path) and once for tool filtering (in the tool pipeline). Both use the same `classifyQueryComplexity()` + `selectModelTier()` functions, ensuring consistent tier decisions.

---

## 2. Config Schema

```typescript
// types.router.ts

type QueryRouterTierConfig = {
  models: string[];           // Model candidates in "provider/model" format
  maxComplexity?: number;     // Route here if score <= this (0..1). Last tier doesn't need it.
  tools?: {
    allow?: string[];         // Tool allowlist (names or "group:xxx" refs)
    deny?: string[];          // Tool denylist (names or "group:xxx" refs)
  };
};

type QueryRouterConfig = {
  enabled?: boolean;          // Master switch (default: false)
  tiers?: {
    fast?: QueryRouterTierConfig;
    balanced?: QueryRouterTierConfig;
    capable?: QueryRouterTierConfig;
  };
  tokenBudget?: {
    daily?: number;           // Daily token cap
    perSession?: number;      // Per-session token cap
    perRequest?: number;      // Per-request cap (approx, based on input length * 4)
    warningThreshold?: number; // 0-1 ratio (default: 0.8)
    onExceeded?: "downgrade" | "block" | "warn";
  };
  overrides?: {
    mediaAlwaysCapable?: boolean;   // default: true
    codeAlwaysBalanced?: boolean;   // default: true
  };
};
```

**Python equivalent** (Pydantic):

```python
from pydantic import BaseModel, Field
from typing import Optional

class TierToolsConfig(BaseModel):
    allow: Optional[list[str]] = None
    deny: Optional[list[str]] = None

class TierConfig(BaseModel):
    models: list[str]
    max_complexity: Optional[float] = Field(None, ge=0, le=1)
    tools: Optional[TierToolsConfig] = None

class TokenBudgetConfig(BaseModel):
    daily: Optional[int] = None
    per_session: Optional[int] = None
    per_request: Optional[int] = None
    warning_threshold: float = 0.8
    on_exceeded: str = "downgrade"  # "downgrade" | "block" | "warn"

class OverridesConfig(BaseModel):
    media_always_capable: bool = True
    code_always_balanced: bool = True

class RouterConfig(BaseModel):
    enabled: bool = False
    tiers: Optional[dict[str, TierConfig]] = None  # keys: "fast", "balanced", "capable"
    token_budget: Optional[TokenBudgetConfig] = None
    overrides: Optional[OverridesConfig] = None
```

---

## 3. Query Router: Complexity Scoring

### Function Signature

```typescript
function classifyQueryComplexity(
  message: string,
  options?: { hasMedia?: boolean; conversationDepth?: number }
): { score: number; signals: string[] }
```

### The 6 Signals and Their Weights

| # | Signal | Weight | Score Function | Range |
|---|--------|--------|----------------|-------|
| 1 | `messageLength` | **0.20** | Linear ramp 50-500 chars | 0 if <50, linear to 1 at 500, 1 if >500 |
| 2 | `codeBlocks` | **0.25** | Fenced + inline code detection | 0/0.3/0.5/0.6/1.0 (discrete) |
| 3 | `media` | **0.15** | Boolean: has image/attachment | 0 or 1 |
| 4 | `technicalKeywords` | **0.15** | Keyword count from a 60+ term set | 0/0.4/0.7/1.0 (by hit count) |
| 5 | `multiTask` | **0.10** | Numbered/bulleted list detection | 0/0.5/1.0 (by item count) |
| 6 | `conversationDepth` | **0.15** | Turn count in current session | 0 if <=1, linear 2-10, 1 if >10 |

**Total**: weights sum to 1.0. Final score = `clamp(sum(signal_i * weight_i), 0, 1)`.

### Signal Scoring Detail

#### Signal 1: Message Length

```python
def score_message_length(message: str) -> float:
    length = len(message)
    if length < 50:
        return 0.0
    if length <= 500:
        return (length - 50) / 450
    return 1.0
```

#### Signal 2: Code Blocks

Detection patterns:
- **Fenced**: `` ```...``` `` (regex: `/```[\s\S]*?```/g`)
- **Inline**: `` `...` `` (regex: `/`[^`]+`/g`)

Scoring matrix:

| Fenced | Inline | Score |
|--------|--------|-------|
| 0 | 0 | 0.0 |
| 0 | 1-2 | 0.3 |
| 0 | 3+ | 0.6 |
| 1 | 0-2 | 0.5 |
| 1 | 3+ | 1.0 |
| 2+ | any | 1.0 |

```python
import re

CODE_BLOCK_RE = re.compile(r'```[\s\S]*?```')
INLINE_CODE_RE = re.compile(r'`[^`]+`')

def score_code_blocks(message: str) -> tuple[float, int]:
    fenced = len(CODE_BLOCK_RE.findall(message))
    inline = len(INLINE_CODE_RE.findall(message))
    if fenced == 0 and inline == 0:
        return 0.0, 0
    if fenced == 1 and inline <= 2:
        return 0.5, fenced
    if fenced >= 2 or (fenced == 1 and inline > 2):
        return 1.0, fenced + inline
    # Only inline code
    if inline <= 2:
        return 0.3, inline
    return 0.6, inline
```

#### Signal 3: Media

```python
def score_media(has_media: bool) -> float:
    return 1.0 if has_media else 0.0
```

#### Signal 4: Technical Keywords

The keyword set contains ~60+ terms in English and Chinese:

**English keywords** (matched as whole words, case-insensitive):
```
function, class, interface, module, import, export, async, await, promise,
callback, api, endpoint, database, query, schema, migration, deploy, docker,
kubernetes, debug, refactor, optimize, algorithm, regex, typescript, javascript,
python, rust, golang, component, hook, middleware, architecture, implement,
compile, runtime, generic, template, inheritance, polymorphism, concurrency,
mutex, thread, websocket, graphql, grpc, oauth, jwt, encryption, hash
```

**Chinese keywords** (matched as substrings -- no word boundaries in CJK):
```
函数, 接口, 组件, 模块, 部署, 数据库, 算法, 重构, 优化, 调试,
架构, 实现, 编译, 泛型, 继承, 并发, 线程, 加密
```

Scoring:

| Keyword Hits | Score |
|-------------|-------|
| 0 | 0.0 |
| 1-2 | 0.4 |
| 3-5 | 0.7 |
| 6+ | 1.0 |

```python
CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')

def score_technical_keywords(message: str) -> float:
    lower = message.lower()
    hits = 0
    for kw in TECHNICAL_KEYWORDS:
        if CJK_RE.search(kw):
            # CJK: substring match
            if kw in lower:
                hits += 1
        else:
            # Latin: whole-word match
            if re.search(rf'\b{re.escape(kw)}\b', lower, re.IGNORECASE):
                hits += 1
    if hits == 0: return 0.0
    if hits <= 2: return 0.4
    if hits <= 5: return 0.7
    return 1.0
```

#### Signal 5: Multi-Task

Detects numbered or bulleted lists:

```python
MULTI_TASK_RE = re.compile(r'(?:^|\n)\s*(?:\d+[.)、]|[-*•])\s+\S')

def score_multi_task(message: str) -> tuple[float, int]:
    count = len(MULTI_TASK_RE.findall(message))
    if count <= 1:
        return 0.0, count
    if count <= 3:
        return 0.5, count
    return 1.0, count
```

#### Signal 6: Conversation Depth

```python
def score_conversation_depth(depth: int) -> float:
    if depth <= 1:
        return 0.0
    if depth <= 10:
        return (depth - 1) / 9
    return 1.0
```

### Full Classifier Implementation

```python
SIGNAL_WEIGHTS = {
    "messageLength": 0.20,
    "codeBlocks": 0.25,
    "media": 0.15,
    "technicalKeywords": 0.15,
    "multiTask": 0.10,
    "conversationDepth": 0.15,
}

def classify_query_complexity(
    message: str,
    has_media: bool = False,
    conversation_depth: int = 1
) -> tuple[float, list[str]]:
    """Returns (score, signals) where score is in [0, 1]."""
    signals = []
    weighted_sum = 0.0

    # 1. Message length
    len_score = score_message_length(message)
    weighted_sum += len_score * SIGNAL_WEIGHTS["messageLength"]
    if len_score > 0:
        signals.append(f"length:{len(message)}")

    # 2. Code blocks
    code_score, code_count = score_code_blocks(message)
    weighted_sum += code_score * SIGNAL_WEIGHTS["codeBlocks"]
    if code_score > 0:
        signals.append(f"code:{code_count}")

    # 3. Media
    media_score = score_media(has_media)
    weighted_sum += media_score * SIGNAL_WEIGHTS["media"]
    if media_score > 0:
        signals.append("media")

    # 4. Technical keywords
    tech_score = score_technical_keywords(message)
    weighted_sum += tech_score * SIGNAL_WEIGHTS["technicalKeywords"]
    if tech_score > 0:
        signals.append("technical")

    # 5. Multi-task
    multi_score, multi_count = score_multi_task(message)
    weighted_sum += multi_score * SIGNAL_WEIGHTS["multiTask"]
    if multi_score > 0:
        signals.append(f"tasks:{multi_count}")

    # 6. Conversation depth
    depth_score = score_conversation_depth(conversation_depth)
    weighted_sum += depth_score * SIGNAL_WEIGHTS["conversationDepth"]
    if depth_score > 0:
        signals.append(f"depth:{conversation_depth}")

    return max(0.0, min(1.0, weighted_sum)), signals
```

---

## 4. Query Router: Tier Selection

### Tier Boundaries (configurable)

The tier check is a simple waterfall:

```
score <= fast.maxComplexity      --> fast
score <= balanced.maxComplexity  --> balanced
otherwise                        --> capable
```

Default thresholds in production config:
- **fast**: score <= 0.30
- **balanced**: score <= 0.65
- **capable**: score > 0.65

```python
TierName = Literal["fast", "balanced", "capable"]
TIER_ORDER = ["fast", "balanced", "capable"]

def select_model_tier(
    score: float,
    tiers: dict  # {fast: TierConfig, balanced: TierConfig, capable: TierConfig}
) -> tuple[TierName, TierConfig] | None:
    """Select tier based on complexity score. Returns (tier_name, tier_config) or None."""
    for tier_name in TIER_ORDER:
        tier_cfg = tiers.get(tier_name)
        if not tier_cfg or not tier_cfg.models:
            continue
        if tier_name == "capable":
            # Last tier: catch-all (no maxComplexity needed)
            return tier_name, tier_cfg
        if tier_cfg.max_complexity is not None and score <= tier_cfg.max_complexity:
            return tier_name, tier_cfg
    return None
```

**Key behaviors**:
- Boundary values are **inclusive** (`<=`), so score=0.30 maps to fast, not balanced.
- If a tier has no models configured (empty list), it's skipped.
- If no tiers match, returns `None` (router is effectively disabled).

---

## 5. Query Router: Budget Caps

After tier selection, a budget cap may force a downgrade. The budget system tracks three dimensions:

1. **perSession** -- cumulative tokens in the current session
2. **daily** -- cumulative tokens today across all sessions
3. **perRequest** -- estimated input tokens for this single message (= `len(message) * 4`)

### Algorithm

```python
def derive_budget_cap(
    router_cfg: RouterConfig,
    message: str,
    session_total_tokens: int | None = None,
    daily_total_tokens: int | None = None,
) -> tuple[TierName | None, list[str]]:
    """Returns (cap_tier, budget_signals). cap_tier=None means no cap."""
    budget = router_cfg.token_budget
    if not budget:
        return None, []

    signals = []
    warning_threshold = budget.warning_threshold  # default 0.8

    # Per-request check (approximation: message chars * 4)
    per_request_exceeded = (
        budget.per_request is not None
        and len(message) * 4 > budget.per_request
    )
    if per_request_exceeded:
        signals.append("budget:perRequest:exceeded")

    # Compute ratios
    session_ratio = (
        session_total_tokens / budget.per_session
        if budget.per_session and session_total_tokens
        else None
    )
    daily_ratio = (
        daily_total_tokens / budget.daily
        if budget.daily and daily_total_tokens
        else None
    )
    ratios = [r for r in [session_ratio, daily_ratio] if r is not None]

    if session_ratio is not None:
        signals.append(f"budget:session:{session_ratio:.2f}")
    if daily_ratio is not None:
        signals.append(f"budget:daily:{daily_ratio:.2f}")

    if per_request_exceeded:
        return "fast", signals  # Always cap to fast on per-request overflow

    if not ratios:
        return None, signals

    highest_ratio = max(ratios)
    on_exceeded = budget.on_exceeded  # "downgrade" | "block" | "warn"

    if highest_ratio >= 1.0:
        if on_exceeded == "warn":
            return None, signals + ["budget:exceeded:warn"]
        return "fast", signals + [f"budget:exceeded:{on_exceeded}"]

    if highest_ratio >= warning_threshold:
        if on_exceeded != "warn":
            return "balanced", signals + ["budget:warning"]
        return None, signals + ["budget:warning:warn"]

    return None, signals
```

### Budget-Tier Interaction

When `cap_tier` is returned and the selected tier is more expensive:

```python
if cap_tier and tier_index(selected_tier) > tier_index(cap_tier):
    # Downgrade: find the best available tier at or below the cap
    selected = pick_tier_at_or_below_cap(tiers, cap_tier)
```

`pick_tier_at_or_below_cap` walks from the cap tier downward (balanced -> fast) looking for one with configured models.

---

## 6. Query Router: Provider-Aware Model Picking

Each tier lists multiple model candidates in `"provider/model"` format. The router prefers a model whose provider matches the agent's current provider.

```python
def pick_model(models: list[str], current_provider: str) -> tuple[str, str] | None:
    """Returns (provider, model) or None. Prefers models matching current_provider."""
    if not models:
        return None

    # Try to find a model whose provider matches
    for m in models:
        if "/" in m:
            provider = m.split("/", 1)[0].strip()
            if provider == current_provider:
                return parse_model_ref(m, current_provider)

    # Fall back to first model in the list
    return parse_model_ref(models[0], current_provider)

def parse_model_ref(raw: str, default_provider: str) -> tuple[str, str] | None:
    """Parse 'provider/model' string. If no slash, use default_provider."""
    trimmed = raw.strip()
    if not trimmed:
        return None
    if "/" in trimmed:
        provider, model = trimmed.split("/", 1)
        return provider.strip(), model.strip()
    return default_provider, trimmed
```

**Example**: Agent config says `currentProvider = "anthropic"`. Tier models = `["openai-codex/gpt-5.2", "anthropic/claude-sonnet-4-5"]`. The router picks `anthropic/claude-sonnet-4-5` because the provider matches.

This is critical for the multi-provider agent setup where Leonard uses Claude (Anthropic) but family agents use OpenAI.

---

## 7. Query Router: Override Rules

Two hardcoded overrides run after scoring but before tier selection:

### Override 1: `mediaAlwaysCapable` (default: true)

If the message has media (images/attachments), force score to at least 0.71 (above balanced threshold of 0.65):

```python
if media_always_capable and has_media:
    score = max(score, 0.71)
    signals.append("override:media->capable")
```

### Override 2: `codeAlwaysBalanced` (default: true)

If the message contains fenced code blocks AND score < 0.31, push score to 0.31 (above fast threshold of 0.30):

```python
if code_always_balanced:
    has_code = bool(CODE_BLOCK_RE.search(message))
    if has_code and score < 0.31:
        score = 0.31
        signals.append("override:code->balanced")
```

---

## 8. Tool Policy: Groups and Filtering

### Tool Group Definitions

```python
TOOL_GROUPS = {
    "group:memory":     ["memory_search", "memory_get"],
    "group:web":        ["web_search", "web_fetch"],
    "group:fs":         ["read", "write", "edit", "apply_patch"],
    "group:runtime":    ["exec", "process"],
    "group:sessions":   ["sessions_list", "sessions_history", "sessions_send",
                         "sessions_spawn", "session_status"],
    "group:ui":         ["browser", "canvas"],
    "group:automation": ["cron", "gateway"],
    "group:messaging":  ["message"],
    "group:nodes":      ["nodes"],
    "group:openclaw":   [  # All native tools (excludes provider plugins)
        "browser", "canvas", "nodes", "cron", "message", "gateway",
        "agents_list", "sessions_list", "sessions_history", "sessions_send",
        "sessions_spawn", "session_status", "memory_search", "memory_get",
        "web_search", "web_fetch", "image",
    ],
}
```

### Tool Name Normalization

```python
TOOL_NAME_ALIASES = {
    "bash": "exec",
    "apply-patch": "apply_patch",
}

def normalize_tool_name(name: str) -> str:
    normalized = name.strip().lower()
    return TOOL_NAME_ALIASES.get(normalized, normalized)
```

### Group Expansion

```python
def expand_tool_groups(tool_list: list[str]) -> list[str]:
    """Expand group references to individual tool names."""
    expanded = []
    for entry in tool_list:
        normalized = normalize_tool_name(entry)
        if normalized in TOOL_GROUPS:
            expanded.extend(TOOL_GROUPS[normalized])
        else:
            expanded.append(normalized)
    return list(set(expanded))
```

### Tool Profiles

Predefined sets for common agent roles:

```python
TOOL_PROFILES = {
    "minimal":   {"allow": ["session_status"]},
    "coding":    {"allow": ["group:fs", "group:runtime", "group:sessions", "group:memory", "image"]},
    "messaging": {"allow": ["group:messaging", "sessions_list", "sessions_history",
                             "sessions_send", "session_status"]},
    "full":      {},  # No restriction -- all tools allowed
}
```

---

## 9. Tool Tier Filtering (Router + Tools Integration)

The function `applyRouterToolFilter` in `pi-tools.ts` applies the router's tier-level tool restrictions to the tool pipeline:

```python
def apply_router_tool_filter(
    tools: list[Tool],
    current_message: str | None,
    config: dict | None,
    agent_tool_profile: str | None = None,
) -> list[Tool]:
    """Filter tools based on the router's tier for the current message."""

    # Bypass: agents with profile="full" skip router filtering entirely
    if agent_tool_profile == "full":
        return tools

    router_cfg = config.get("agents", {}).get("defaults", {}).get("router", {})
    if not router_cfg.get("enabled") or not current_message:
        return tools

    # Re-run the classifier (same logic as model routing)
    score, _ = classify_query_complexity(current_message)
    tier_name, tier_cfg = select_model_tier(score, router_cfg["tiers"])
    if not tier_cfg or not tier_cfg.tools:
        return tools

    tier_tools = tier_cfg.tools
    filtered = tools

    # Apply allowlist
    if tier_tools.allow:
        allowed = set(normalize_tool_name(n) for n in expand_tool_groups(tier_tools.allow))
        filtered = [t for t in filtered if normalize_tool_name(t.name) in allowed]

    # Apply denylist
    if tier_tools.deny:
        denied = set(normalize_tool_name(n) for n in expand_tool_groups(tier_tools.deny))
        filtered = [t for t in filtered if normalize_tool_name(t.name) not in denied]

    return filtered
```

### Production Tool Tier Assignment

From the live config:

| Tier | Max Tools | Allowed Tools |
|------|-----------|---------------|
| **fast** (score <= 0.30) | 3 | `message`, `tts`, `session_status` |
| **balanced** (score <= 0.65) | ~14 | `group:messaging`, `group:web`, `group:memory`, `group:fs`, `image`, `tts`, `sessions_list`, `sessions_history`, `sessions_send`, `session_status` |
| **capable** (score > 0.65) | ALL | No restriction (no `tools` config) |

**Token savings**: Fast tier with 3 tools vs capable with all tools saves ~77% of tool-description tokens in the system prompt.

---

## 10. Circuit Breaker

### State Machine

```
         recordSuccess()
    +----------------------+
    |                      |
    v                      |
 CLOSED ---[failures >= maxFailures]--> OPEN
    ^                                     |
    |                                     | [after halfOpenAfterMs]
    |                                     v
    +----[recordSuccess()]---- HALF-OPEN
    |                              |
    |   [recordFailure()]          |
    +--------- OPEN <-------------+
```

### State Type

```python
@dataclass
class CircuitBreakerState:
    failures: int = 0
    last_failure: float | None = None  # timestamp (epoch ms)
    state: str = "closed"  # "closed" | "open" | "half-open"
    trip_count: int = 0
```

### Configuration

```python
DEFAULT_CIRCUIT_BREAKER_CONFIG = {
    "max_failures": 3,          # Failures before tripping to OPEN
    "cooldown_ms": 60_000,      # Failure counter reset after this idle period
    "half_open_after_ms": 30_000, # OPEN -> HALF-OPEN transition delay
    "max_trips_before_rollback": 3,  # Warn after this many trips
}
```

### Key Methods

```python
class CircuitBreaker:
    def __init__(self, max_failures=3, cooldown_ms=60000, half_open_after_ms=30000,
                 max_trips_before_rollback=3):
        self.state = CircuitBreakerState()
        self.max_failures = max_failures
        self.cooldown_ms = cooldown_ms
        self.half_open_after_ms = half_open_after_ms
        self.max_trips_before_rollback = max_trips_before_rollback
        self._rollback_suggested = False

    def can_attempt(self) -> bool:
        """Check if a request can be attempted."""
        if self.state.state in ("closed", "half-open"):
            return True
        if self.state.state == "open":
            if self.state.last_failure is None:
                return False
            if time_ms() - self.state.last_failure >= self.half_open_after_ms:
                self.state.state = "half-open"
                return True
            return False
        return False

    def record_success(self):
        """Reset on success."""
        self.state.failures = 0
        self.state.last_failure = None
        self.state.state = "closed"

    def record_failure(self):
        """Record a failure. May trip the breaker."""
        now = time_ms()

        # Reset failure count if enough time has passed (cooldown)
        if (self.state.last_failure is not None
                and now - self.state.last_failure > self.cooldown_ms):
            self.state.failures = 0

        self.state.last_failure = now

        if self.state.state == "half-open":
            self._trip()
            return

        self.state.failures += 1
        if self.state.failures >= self.max_failures:
            self._trip()

    def _trip(self):
        """Transition to OPEN state."""
        self.state.state = "open"
        self.state.failures = 0
        self.state.trip_count += 1
        if (not self._rollback_suggested
                and self.state.trip_count >= self.max_trips_before_rollback):
            logger.warning(
                f"Circuit tripped {self.state.trip_count} times "
                f"(threshold={self.max_trips_before_rollback}). Consider rollback."
            )
            self._rollback_suggested = True
```

### Registry (Singleton per model key)

```python
_circuit_breaker_registry: dict[str, CircuitBreaker] = {}

def get_circuit_breaker(key: str, **opts) -> CircuitBreaker:
    """Get or create a circuit breaker for a model key like 'openai/gpt-5.2'."""
    normalized = key.strip() or "default"
    if normalized in _circuit_breaker_registry:
        breaker = _circuit_breaker_registry[normalized]
        breaker.configure(**opts)  # Update config if changed
        return breaker
    breaker = CircuitBreaker(**opts)
    _circuit_breaker_registry[normalized] = breaker
    return breaker
```

---

## 11. Model Fallback Chain

### Candidate Resolution

The fallback chain builds an ordered list of model candidates:

```
1. Primary model (the one selected by the router or agent config)
2. Configured fallbacks (from agents.defaults.model.fallbacks or agent-level override)
3. The global default model (if not already in the list)
```

Each candidate is deduplicated by `provider/model` key.

### Execution Flow

```python
async def run_with_model_fallback(
    cfg: dict,
    provider: str,
    model: str,
    fallbacks_override: list[str] | None = None,
    run: Callable[[str, str], Awaitable[T]],
    on_error: Callable | None = None,
) -> tuple[T, str, str, list[dict]]:
    """
    Try models in order. Returns (result, provider, model, attempts).
    """
    candidates = resolve_fallback_candidates(cfg, provider, model, fallbacks_override)
    attempts = []

    for i, candidate in enumerate(candidates):
        # 1. Check auth profile cooldown (skip if all profiles exhausted)
        if all_profiles_in_cooldown(candidate.provider):
            attempts.append({
                "provider": candidate.provider,
                "model": candidate.model,
                "error": f"Provider {candidate.provider} in cooldown",
                "reason": "rate_limit",
            })
            continue

        # 2. Check circuit breaker (skip if open)
        breaker = get_circuit_breaker(f"{candidate.provider}/{candidate.model}")
        if not breaker.can_attempt():
            attempts.append({
                "provider": candidate.provider,
                "model": candidate.model,
                "error": f"Circuit breaker open",
                "reason": "circuit_open",
            })
            continue

        # 3. Try the model
        try:
            result = await run(candidate.provider, candidate.model)
            breaker.record_success()
            return result, candidate.provider, candidate.model, attempts
        except Exception as err:
            # 3a. User abort (not timeout) -> rethrow immediately, no fallback
            if is_abort_error(err) and not is_timeout_error(err):
                raise

            # 3b. Classify the error
            failover_err = coerce_to_failover_error(err, candidate)
            if failover_err is None:
                # Unrecognized error type -> record failure but don't try fallback
                breaker.record_failure()
                raise

            # 3c. Recognized failover error -> record failure, try next
            breaker.record_failure()
            attempts.append(describe_error(failover_err))
            if on_error:
                await on_error(candidate, err, i + 1, len(candidates))

    # All candidates exhausted
    if len(attempts) <= 1:
        raise last_error
    raise AllModelsFailedError(attempts)
```

### Failover vs Non-Failover Errors

Only certain error types trigger fallback to the next model. Unrecognized errors are rethrown immediately.

---

## 12. Failover Error Classification

### FailoverReason Enum

```python
FailoverReason = Literal["auth", "format", "rate_limit", "billing", "timeout", "unknown"]
```

### Classification Logic

```python
def resolve_failover_reason(err: Exception) -> FailoverReason | None:
    """Classify an error into a failover reason. Returns None if not a failover error."""
    status = get_status_code(err)

    # Status-code based classification
    STATUS_MAP = {
        402: "billing",
        429: "rate_limit",
        401: "auth",
        403: "auth",
        408: "timeout",
        400: "format",
    }
    if status in STATUS_MAP:
        return STATUS_MAP[status]

    # Error code based classification
    code = get_error_code(err)
    if code and code.upper() in ("ETIMEDOUT", "ESOCKETTIMEDOUT", "ECONNRESET", "ECONNABORTED"):
        return "timeout"

    # Timeout heuristics (message/name matching)
    if is_timeout_error(err):
        return "timeout"

    # Message-based classification (via classifyFailoverReason helper)
    message = str(err)
    return classify_failover_reason_from_message(message)
```

### Timeout Detection

Multiple heuristics for detecting timeouts:

```python
TIMEOUT_HINT_RE = re.compile(
    r'timeout|timed out|deadline exceeded|context deadline exceeded', re.I
)
ABORT_TIMEOUT_RE = re.compile(r'request was aborted|request aborted', re.I)

def is_timeout_error(err: Exception) -> bool:
    # Check error name
    if getattr(err, 'name', '') == 'TimeoutError':
        return True
    # Check message
    if TIMEOUT_HINT_RE.search(str(err)):
        return True
    # Check AbortError + abort message
    if getattr(err, 'name', '') == 'AbortError':
        if ABORT_TIMEOUT_RE.search(str(err)):
            return True
        # Check cause chain
        cause = getattr(err, '__cause__', None)
        if cause and TIMEOUT_HINT_RE.search(str(cause)):
            return True
    return False
```

### Abort vs Timeout Distinction

This is a critical design decision:

```python
def should_rethrow_abort(err: Exception) -> bool:
    """True = user-initiated abort, don't try fallback. False = timeout, try fallback."""
    return is_abort_error(err) and not is_timeout_error(err)
```

An `AbortError` caused by a timeout IS a failover candidate. An `AbortError` from a user cancel is NOT.

---

## 13. Production Config (Live)

This is the actual config from `/home/leonard/.openclaw/openclaw.json`:

```json
{
  "enabled": true,
  "tiers": {
    "fast": {
      "models": ["openai-codex/gpt-5.2", "anthropic/claude-sonnet-4-5"],
      "maxComplexity": 0.3,
      "tools": {
        "allow": ["message", "tts", "session_status"]
      }
    },
    "balanced": {
      "models": ["openai-codex/gpt-5.3-codex", "anthropic/claude-sonnet-4-5"],
      "maxComplexity": 0.65,
      "tools": {
        "allow": [
          "group:messaging", "group:web", "group:memory", "group:fs",
          "image", "tts", "sessions_list", "sessions_history",
          "sessions_send", "session_status"
        ]
      }
    },
    "capable": {
      "models": ["openai-codex/gpt-5.3-codex", "anthropic/claude-opus-4-6"]
    }
  },
  "tokenBudget": {
    "daily": 500000,
    "perSession": 100000,
    "perRequest": 30000,
    "warningThreshold": 0.8,
    "onExceeded": "downgrade"
  },
  "overrides": {
    "mediaAlwaysCapable": true,
    "codeAlwaysBalanced": true
  }
}
```

### Provider-Aware Model Selection in Practice

- **Leonard (owner)**: `currentProvider = "anthropic"` -> picks `anthropic/claude-sonnet-4-5` for fast, `anthropic/claude-sonnet-4-5` for balanced, `anthropic/claude-opus-4-6` for capable
- **Family agents**: `currentProvider = "openai-codex"` -> picks `openai-codex/gpt-5.2` for fast, `openai-codex/gpt-5.3-codex` for balanced/capable

---

## 14. Python Porting Notes

### Architecture Mapping

| OpenClaw (TypeScript) | NEXUS (Python) Suggested |
|----------------------|--------------------------|
| `query-router.ts` | `nexus/routing/query_router.py` |
| `model-fallback.ts` | `nexus/routing/model_fallback.py` |
| `circuit-breaker.ts` | `nexus/routing/circuit_breaker.py` |
| `failover-error.ts` | `nexus/routing/failover_error.py` |
| `tool-policy.ts` | `nexus/tools/tool_policy.py` |
| `types.router.ts` | Pydantic models in `nexus/routing/schemas.py` |

### Key Differences to Handle

1. **Async model**: OpenClaw uses Node.js async/await. NEXUS uses Python asyncio with FastAPI. Direct mapping works.

2. **Circuit breaker registry**: OpenClaw uses a module-level `Map`. In Python, use a module-level dict (thread-safe for asyncio since it's single-threaded per event loop). For multi-worker setups, consider Redis-backed state.

3. **Regex**: JavaScript regex `/g` flag with `.match()` returns all matches (like Python `re.findall()`). The `CODE_BLOCK_RE.lastIndex` reset issue in JS doesn't exist in Python.

4. **Model reference parsing**: The `provider/model` format is already used by LiteLLM in the NEXUS gateway. Leverage LiteLLM's model name parsing instead of reimplementing `parseModelRef`.

5. **Tool groups**: Map directly to NEXUS tool registry. The group definitions should be in config, not hardcoded.

6. **Token estimation**: The `perRequest` budget uses `len(message) * 4` as a rough token estimate. Consider using `tiktoken` for more accurate counting.

7. **CJK keyword matching**: Python's `re` module handles Unicode well. The substring-match approach for CJK keywords is straightforward.

### Minimal Viable Port

For Phase 2 of NEXUS, the minimal port needs:

1. **`classify_query_complexity()`** -- pure function, no dependencies
2. **`select_model_tier()`** -- pure function
3. **`pick_model()`** with provider awareness -- pure function
4. **`CircuitBreaker` class** -- stateful, in-memory
5. **Fallback loop** -- integrate with LiteLLM's model calling

The tool filtering can come later since NEXUS's tool system is different (bash scripts + file system vs structured tool objects).

### Test Data from OpenClaw

From the test suite, known expected behaviors:

| Input | Expected Tier |
|-------|--------------|
| "你好" (hello) | fast |
| "几点了" (what time) | fast |
| Short msg + image | capable (media override) |
| Any fenced code block | balanced+ (code override) |
| 6-task list + 2 code blocks + 5+ tech keywords | capable |
| Simple msg + budget exceeded | fast (downgraded) |
| Simple msg + budget at 80% warning | balanced (capped) |
