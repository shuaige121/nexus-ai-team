# NEXUS AI-Team: Production Readiness Audit

> Date: 2026-02-19 | Auditor: Ops Engineer (automated)
> Repo: shuaige121/nexus-ai-team | Commits: 42 | Age: 3 days
> Tests: 22 files, 69 passing | Stack: Python 3.12 + FastAPI + PostgreSQL + Redis

## Executive Summary

NEXUS AI-Team is a multi-agent AI company simulation built with FastAPI, Bash scripts, React, PostgreSQL, and Redis. For a 3-day-old prototype, the architecture is surprisingly well-structured: multi-stage Docker builds, health checks, a proper heartbeat/recovery system, parameterized SQL queries, and a reasonable test suite. The engineering fundamentals are solid.

However, the project is **NOT production-ready**. The overall readiness score is **YELLOW (Staging-Ready, Not Production-Ready)**. There are no show-stopping security breaches (secrets are loaded from env vars, SQL is parameterized, auth exists), but there are significant gaps in reliability, security hardening, and operational maturity. The most critical issues are: (1) a single async PostgreSQL connection shared across all requests with no connection pooling, (2) CORS set to wildcard `*` in the live `.env`, (3) the JWT secret is a weak static string, (4) no CI/CD pipeline exists, (5) no resource limits on Docker containers, and (6) the in-memory rate limiter resets on restart and does not work across multiple workers.

With 2-3 focused sprints addressing the issues below, this project could reach production-grade status. The architecture does not need a fundamental redesign -- it needs hardening, pooling, proper secrets management, and operational tooling.

---

## Critical Issues (Must Fix Before Production)

### C1. Single PostgreSQL connection, no connection pooling
- **File**: `pipeline/work_order.py:27-33`
- **Severity**: CRITICAL
- **Issue**: `WorkOrderDB` uses a single `psycopg.AsyncConnection` for all operations. Under concurrent load, this will cause connection serialization, deadlocks, or connection-closed errors. There is no connection pool.
```python
async def connect(self) -> None:
    self._conn = await psycopg.AsyncConnection.connect(
        self.db_url,
        autocommit=False,
        row_factory=dict_row,
    )
```
- **Also affected**: `gateway/main.py` -- the global `db` object is shared across all request handlers and the health broadcast loop.
- **Fix**: Replace with `psycopg_pool.AsyncConnectionPool` (min_size=2, max_size=10). Use `async with pool.connection() as conn:` for each operation. This is a ~30-line refactor.

### C2. JWT secret is a hardcoded weak static string
- **File**: `.env:12`
- **Severity**: CRITICAL
- **Issue**: The JWT secret is `dev-jwt-secret-please-change-in-production-min-32-chars`. While this is clearly marked as a dev value, it is the actual value being used. Anyone who reads the source code can forge JWTs.
```
JWT_SECRET=dev-jwt-secret-please-change-in-production-min-32-chars
```
- **Fix**: Generate a cryptographically random secret: `openssl rand -hex 32`. Store in a secrets manager (not in `.env` file committed to the repo). Ensure `.env` is in `.gitignore` (it already is, confirmed).

### C3. CORS wildcard allows any origin
- **File**: `.env:18`, `gateway/main.py:119-126`
- **Severity**: CRITICAL
- **Issue**: `CORS_ORIGINS=*` allows any website to make authenticated API requests to the gateway. Combined with `allow_credentials=True`, this is a credential-theft vector.
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # ["*"]
    allow_credentials=True,      # This + wildcard = dangerous
    allow_methods=["*"],
    allow_headers=["*"],
)
```
- **Fix**: Set `CORS_ORIGINS=http://localhost:3000,https://your-domain.com` with explicit allowed origins. Never combine `*` with `allow_credentials=True`.

### C4. No resource limits on Docker containers
- **File**: `docker-compose.yml`
- **Severity**: CRITICAL
- **Issue**: No `mem_limit`, `cpus`, `deploy.resources` on any service. A runaway LLM call or memory leak in the gateway will consume all host memory and crash everything.
- **Fix**: Add resource limits to each service:
```yaml
gateway:
  deploy:
    resources:
      limits:
        memory: 1G
        cpus: '2.0'
      reservations:
        memory: 256M
postgres:
  deploy:
    resources:
      limits:
        memory: 512M
redis:
  deploy:
    resources:
      limits:
        memory: 256M
```

### C5. In-memory rate limiter is not production-viable
- **File**: `gateway/rate_limiter.py:17-29`
- **Severity**: CRITICAL
- **Issue**: The rate limiter uses an in-memory `defaultdict` that resets on every restart and is not shared across workers. If you run multiple uvicorn workers (which you must for production), each worker has its own counter.
```python
class _SlidingWindow:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)
```
- **Also**: No memory cleanup -- `_hits` grows unboundedly as new client IPs are seen. This is a slow memory leak.
- **Fix**: Use Redis-based rate limiting with a sorted set or the `redis-py` `INCR`/`EXPIRE` pattern. The Redis connection already exists in the pipeline.

### C6. No CI/CD pipeline
- **Severity**: CRITICAL
- **Issue**: No `.github/workflows/` directory exists. No automated testing, linting, security scanning, or deployment automation. Every deployment is manual.
- **Fix**: Create `.github/workflows/ci.yml` with at minimum: `ruff check .`, `pytest tests/`, Docker image build. Add branch protection requiring CI pass before merge to main.

---

## High Priority (Fix Within Sprint 1)

### H1. Auth is effectively disabled in development mode
- **File**: `gateway/auth.py:29-33`
- **Severity**: HIGH
- **Issue**: When `API_SECRET` is empty (which it is in `.env`), `_verify_token()` returns `True` for any input, including empty tokens. This means all API endpoints are currently unauthenticated.
```python
def _verify_token(token: str) -> bool:
    if not settings.api_secret:
        return True  # Auth disabled
```
- **Fix**: For production, always require `API_SECRET` to be set. Add a startup check that refuses to start without it (unless `DEBUG=true`).

### H2. WebSocket has no rate limiting
- **File**: `gateway/ws.py`, `gateway/main.py:237-247`
- **Severity**: HIGH
- **Issue**: The WebSocket endpoint (`/ws`) is not covered by the rate limiter middleware (Starlette's `BaseHTTPMiddleware` does not intercept WebSocket connections). A malicious client can flood the server with messages.
- **Fix**: Add per-connection rate limiting inside `ConnectionManager.handle_message()` -- track messages per second per connection and disconnect abusive clients.

### H3. Two separate database client implementations with divergent behavior
- **File**: `db/client.py` (sync, psycopg2), `pipeline/work_order.py` (async, psycopg3)
- **Severity**: HIGH
- **Issue**: There are two completely different database layers:
  1. `db/client.py` -- Synchronous, uses `psycopg2`, has connection pooling via `SimpleConnectionPool`, supports SQLite fallback
  2. `pipeline/work_order.py` -- Async, uses `psycopg` (v3), single connection, no pooling

  The gateway uses `pipeline/work_order.py` (async). The `db/client.py` module appears to be used by some offline scripts. Having two DB clients is a maintenance risk and a source of schema drift bugs.
- **Fix**: Consolidate on one async DB client using `psycopg` v3 with `AsyncConnectionPool`. Provide a sync wrapper for CLI scripts.

### H4. No input validation on API endpoints
- **File**: `gateway/main.py:219-225`
- **Severity**: HIGH
- **Issue**: The `/api/chat` endpoint accepts a raw `dict` with no Pydantic validation:
```python
@app.post("/api/chat", tags=["chat"])
async def chat(message: dict):
    content = message.get("content", "")
```
  Similarly, `/api/work-orders` accepts `status` and `owner` as raw strings with no validation or enum enforcement.
- **Fix**: Define Pydantic request models for all POST endpoints. Use path/query parameter validation for GET endpoints.

### H5. No TLS termination configured
- **Severity**: HIGH
- **Issue**: Neither the gateway nor the dashboard nginx has TLS configured. All traffic (including auth tokens, WebSocket frames, and LLM responses) travels in plaintext.
- **Fix**: Add a reverse proxy (Caddy, Traefik, or nginx with certbot) in front of the gateway and dashboard for automatic TLS certificate management.

### H6. SQLite database file (`nexus.db`) exists in project root and is not git-ignored
- **File**: `nexus.db` (86KB), `.gitignore`
- **Severity**: HIGH
- **Issue**: `nexus.db` is present in the project root and shows up as an untracked file in `git status`. While it is not currently tracked, the `.gitignore` does not explicitly exclude it. If someone runs `git add .`, it will be committed.
- **Fix**: Add `*.db` or `nexus.db` to `.gitignore`.

### H7. Dockerfile `pip install -e .` in builder stage copies no source
- **File**: `Dockerfile:38-40`
- **Severity**: HIGH
- **Issue**: The builder stage runs `pip install -e .` but only copies `pyproject.toml` -- no source code. An editable install (`-e .`) creates a `.egg-link` pointing to `/app`, which has no code at that point. The production stage then copies the site-packages which contain broken symlinks.
```dockerfile
COPY pyproject.toml ./
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e .
```
- **Fix**: Either (a) use `pip install .` (non-editable) instead of `-e .`, or (b) copy the full source before installing. Option (a) is preferred for production builds.

---

## Medium Priority (Fix Within Sprint 2-3)

### M1. No database migration strategy
- **File**: `docker/init.sql`
- **Severity**: MEDIUM
- **Issue**: Schema is applied via `docker-entrypoint-initdb.d/` which only runs on first container creation. There is no migration tool (Alembic, Flyway) for schema evolution. Adding a column requires either dropping the database or manual SQL.
- **Fix**: Adopt Alembic for schema migrations. Add a `make migrate` command and run migrations in the startup script.

### M2. No backup strategy beyond the equipment script
- **File**: `equipment/registry.yaml`
- **Severity**: MEDIUM
- **Issue**: There is a `backup` equipment entry configured but `last_run: null` -- it has never been executed. No `pg_dump` cron job, no volume backup, no point-in-time recovery setup.
- **Fix**: Implement automated PostgreSQL backups via `pg_dump` cron (daily), configure WAL archiving for PITR, and test restore procedures.

### M3. QA runner uses `shell=True` from spec files
- **File**: `qa/runner.py:259-266`
- **Severity**: MEDIUM
- **Issue**: The QA runner executes commands from JSON spec files with `shell=True` when `use_shell` is set in the spec. If spec files can be influenced by agent output, this is a command injection vector.
```python
process = subprocess.run(
    command if use_shell else shlex.split(command),
    shell=use_shell,
    ...
)
```
- **Fix**: Disable `shell=True` entirely, or validate/sanitize commands before execution. Add an allowlist of permitted commands.

### M4. Health broadcast loop accesses internal DB connection directly
- **File**: `gateway/main.py:56-68`
- **Severity**: MEDIUM
- **Issue**: The background health broadcast loop accesses `db._conn` directly (a private attribute) and creates cursors on the same shared connection that request handlers use, without locking.
```python
async with db._conn.cursor() as cur:
    await cur.execute("SELECT 1")
```
- **Fix**: Use a dedicated health-check connection, or move to a connection pool (see C1).

### M5. No graceful shutdown for the startup script process
- **File**: `scripts/nexus-start.sh:67-73`
- **Severity**: MEDIUM
- **Issue**: The gateway is started with `nohup ... &` and there is no PID file, no process group management, and no signal handling for graceful shutdown. `pkill -f` is used which could kill unrelated processes.
- **Fix**: Write PID to a file. Use `trap` for cleanup. Consider systemd service files (a template already exists at `heartbeat/nexus-heartbeat.service`). Create a matching `nexus-gateway.service`.

### M6. No request ID / correlation ID in logs
- **File**: `gateway/main.py:30-32`
- **Severity**: MEDIUM
- **Issue**: Logging uses a basic format with no request correlation. When debugging concurrent requests, there is no way to trace a single request through the system.
```python
logging.basicConfig(
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
```
- **Fix**: Add middleware to generate a UUID request ID, attach it to the request state, and include it in all log messages. Use `structlog` for structured JSON logging in production.

### M7. WebSocket connection cleanup is incomplete
- **File**: `gateway/ws.py:42-44`
- **Severity**: MEDIUM
- **Issue**: Dead connections are only detected and cleaned during `broadcast()`. If no broadcast happens for a while, dead connections accumulate in `_connections`. There is no periodic cleanup or heartbeat ping.
- **Fix**: Implement WebSocket ping/pong (every 30s). Remove connections that fail to pong within 10s. Add periodic cleanup independent of broadcast.

### M8. Dashboard backend has no auth at all
- **File**: `dashboard/backend/main.py`
- **Severity**: MEDIUM
- **Issue**: The dashboard FastAPI app (`dashboard/backend/main.py`) has zero authentication. No middleware, no token check. Any client on the network can access all routes including agent activation and settings.
```python
app = FastAPI(title="AgentOffice Dashboard", ...)
# No auth middleware added anywhere
```
- **Fix**: Add the same bearer-token auth middleware used in the gateway, or proxy dashboard API calls through the gateway.

### M9. LLM client has no timeout, retry, or cost controls
- **File**: `agentoffice/engine/llm_client.py:67-85`
- **Severity**: MEDIUM
- **Issue**: The `call_llm()` function calls `litellm.completion()` with no timeout, no retry logic, and no cost/token budget enforcement. A stuck LLM API call will block the agent activation chain indefinitely.
```python
response = litellm.completion(**kwargs)
```
- **Fix**: Add `timeout=60` to litellm calls. Implement retry with exponential backoff (max 3 attempts). Add a per-agent daily token budget check before calling.

### M10. Recovery manager can restart services but has no guard against cascading restarts
- **File**: `heartbeat/recovery.py:86-104`
- **Severity**: MEDIUM
- **Issue**: The recovery manager limits to 3 attempts per component, but the counter is never persisted. On service restart, the counter resets to 0, enabling infinite restart loops across process lifetimes.
- **Fix**: Persist recovery attempt counts in Redis with a TTL (e.g., 1 hour). This prevents restart storms.

---

## Low Priority (Nice to Have)

### L1. No API versioning
- **File**: `gateway/main.py`
- **Issue**: All routes are under `/api/` with no version prefix. Adding breaking changes later will be difficult.
- **Fix**: Prefix routes with `/api/v1/`. Use FastAPI's `APIRouter(prefix="/api/v1")`.

### L2. `node_modules` committed in dashboard/frontend
- **File**: `dashboard/frontend/node_modules/`
- **Issue**: The `node_modules/` directory appears to be present on disk (visible in the file listing). While `.gitignore` includes `node_modules/`, the dashboard has its own `.gitignore` that may not be consistent.
- **Fix**: Verify `node_modules/` is not tracked. Run `git rm -r --cached dashboard/frontend/node_modules/` if it is.

### L3. Heartbeat service has no systemd unit for the gateway
- **File**: `heartbeat/nexus-heartbeat.service`
- **Issue**: A systemd service file exists for heartbeat but not for the gateway itself. The gateway is managed by `nohup` in the startup script.
- **Fix**: Create `nexus-gateway.service` systemd unit for proper process management with auto-restart.

### L4. Agent activation is synchronous and blocking
- **File**: `agentoffice/engine/activate.py:1-12`
- **Issue**: As documented in the file header, agent activation is sequential. When the CEO dispatches tasks to multiple managers, they execute one at a time.
- **Fix**: Implement `asyncio.gather()` for independent subtasks in the activation chain.

### L5. `datetime.utcnow()` is deprecated in Python 3.12+
- **File**: `gateway/schemas.py:17`, `pipeline/work_order.py` (multiple)
- **Issue**: `datetime.utcnow()` is deprecated since Python 3.12 in favor of `datetime.now(UTC)`.
- **Fix**: Replace all occurrences with `datetime.now(datetime.UTC)`.

### L6. The `_SlidingWindow` rate limiter leaks memory
- **File**: `gateway/rate_limiter.py:22`
- **Issue**: The `_hits` dictionary grows without bound. Old entries are only cleaned when `is_allowed()` is called for the same key. Entries for IPs that never return are never cleaned.
- **Fix**: Add periodic cleanup or use Redis (see C5).

### L7. Equipment registry `last_run` is tracked in YAML file
- **File**: `equipment/registry.yaml`
- **Issue**: Runtime state (`last_run`, `run_count`, `last_status`) is stored in the same YAML file as configuration. This means every equipment run modifies a config file, causing unnecessary git diffs.
- **Fix**: Separate configuration from runtime state. Store runtime state in the database or a separate untracked state file.

---

## Missing Components

### Missing 1: CI/CD Pipeline (CRITICAL)
No GitHub Actions, no automated testing on push, no automated deployments. This is the single most impactful missing piece.

### Missing 2: Secrets Management
No integration with any secrets manager (Vault, AWS Secrets Manager, SOPS). All secrets live in `.env` on disk. For production, secrets should be injected at runtime from an external vault.

### Missing 3: Database Migration Tool
No Alembic, no Flyway, no schema versioning. The init.sql approach only works for fresh deployments.

### Missing 4: Log Aggregation & Rotation
Logs go to `logs/` directory with basic file rotation (via equipment cron). No centralized log aggregation (ELK, Loki). No structured JSON logging for machine parsing.

### Missing 5: Prometheus/Grafana Metrics
No `/metrics` endpoint for Prometheus scraping. The `/api/metrics` endpoint returns business metrics but not system metrics (request latency histograms, error rates, connection pool stats).

### Missing 6: Automated Database Backups
The backup equipment is registered but has never run. No tested restore procedure exists.

### Missing 7: Load Testing / Performance Baseline
No load test scripts, no performance benchmarks, no baseline metrics to compare against.

### Missing 8: Runbooks / Incident Response Procedures
No documented procedures for common incidents (database down, LLM API quota exceeded, disk full, etc.).

### Missing 9: Network Policies / Firewall Rules
The Docker network is a flat bridge network. Redis and PostgreSQL ports are exposed to the host. No network segmentation.

### Missing 10: Container Image Scanning
No Trivy, Snyk, or similar tool scanning Docker images for vulnerabilities.

---

## Detailed Findings by Area

### 1. Infrastructure & Deployment

**Dockerfile** (`Dockerfile`):
- GOOD: Multi-stage build (base, builder, production, development)
- GOOD: Non-root user (`nexus`, uid 1000) in production
- GOOD: Health check with proper intervals
- GOOD: `PYTHONUNBUFFERED=1`, `PIP_NO_CACHE_DIR=1`
- GOOD: `apt-get` cleanup with `rm -rf /var/lib/apt/lists/*`
- BAD: `pip install -e .` (editable install) in builder stage -- will create broken symlinks in production (see H7)
- BAD: No `.dockerignore` file found -- build context may include `.git/`, `node_modules/`, `.venv/`, test data

**docker-compose.yml**:
- GOOD: Health checks on all services with proper `depends_on: condition: service_healthy`
- GOOD: Named volumes for data persistence
- GOOD: All config via environment variables (no hardcoded values)
- GOOD: Separate network for service isolation
- BAD: No resource limits (mem_limit, cpus) on any service (see C4)
- BAD: No logging driver configured -- defaults to json-file with no rotation
- BAD: Redis and PostgreSQL ports exposed to host (should be internal-only in production)
- NOTE: Volume mount `${APP_SOURCE_PATH}:${APP_WORKDIR}:${VOLUME_MODE:-ro}` mounts entire project into container in production -- should only mount in dev mode

**Dashboard Frontend Dockerfile** (`dashboard/frontend/Dockerfile`):
- GOOD: Multi-stage with separate dev and production targets
- GOOD: Nginx for production with proper SPA routing
- GOOD: Health check endpoint
- BAD: References `nginx.conf` which is in the frontend directory but could be missing from Docker context

**Startup Script** (`scripts/nexus-start.sh`):
- GOOD: Proper error handling (`set -euo pipefail`)
- GOOD: Waits for PostgreSQL readiness
- GOOD: Color-coded output, good UX
- BAD: Uses `nohup ... &` for process management (no PID file, no systemd)
- BAD: `pkill -f "uvicorn gateway.main:app"` is overly broad

**Makefile**:
- GOOD: Comprehensive targets (up, down, dev, test, health, clean, etc.)
- GOOD: `clean` has confirmation prompt
- GOOD: Organized with clear sections

### 2. Gateway & API

**Authentication** (`gateway/auth.py`):
- GOOD: Timing-safe comparison via `hmac.compare_digest()`
- GOOD: Public paths excluded from auth
- GOOD: WebSocket auth function exists
- BAD: Auth is disabled when `API_SECRET` is empty (current state)
- BAD: No JWT token validation (only bearer token comparison). Despite having `jwt_secret` in config, no JWT decoding occurs
- BAD: WebSocket auth accepts token via query parameter (visible in server logs, browser history)

**Rate Limiting** (`gateway/rate_limiter.py`):
- GOOD: Sliding window algorithm is correct
- GOOD: Returns proper 429 with Retry-After header
- BAD: In-memory only -- resets on restart, not shared across workers (see C5)
- BAD: Memory leak in `_hits` dict (see L6)
- BAD: Does not apply to WebSocket connections

**WebSocket** (`gateway/ws.py`):
- GOOD: Clean connection lifecycle (connect, auth, disconnect)
- GOOD: Pydantic models for frames (WSRequest, WSResponse, WSEvent)
- GOOD: Dead connection cleanup during broadcast
- BAD: No message rate limiting per connection
- BAD: No maximum payload size enforcement
- BAD: Global sequence counter (`_seq`) is not atomic -- potential race condition under concurrent broadcasts

**API Design** (`gateway/main.py`):
- GOOD: OpenAPI docs auto-generated via FastAPI
- GOOD: Proper lifespan context manager for startup/shutdown
- GOOD: Health endpoints (basic + detailed)
- GOOD: Graceful pipeline cleanup on shutdown
- BAD: No API versioning
- BAD: No input validation on `/api/chat` (accepts raw dict)
- BAD: `/api/work-orders` builds SQL query with string interpolation for WHERE clause (though parameters are properly parameterized, the clause structure is dynamic)
- BAD: Error responses expose internal exception messages (`str(e)`)

### 3. Database

**Schema** (`docker/init.sql`):
- GOOD: Proper constraints (CHECK, NOT NULL, FOREIGN KEY)
- GOOD: `updated_at` trigger function
- GOOD: Comprehensive indexes
- GOOD: JSONB for flexible metadata
- GOOD: Generated column (`total_tokens`)
- GOOD: Wrapped in BEGIN/COMMIT transaction

**Pipeline DB** (`pipeline/work_order.py`):
- GOOD: All queries use parameterized placeholders (`%s`)
- GOOD: Proper async/await
- BAD: Single connection, no pooling (see C1)
- BAD: Manual commit after every operation -- should use autocommit or a proper transaction manager
- BAD: No connection health check / reconnection logic

**Legacy DB Client** (`db/client.py`):
- GOOD: Connection pooling via `SimpleConnectionPool` (sync only)
- GOOD: SQLite fallback for development
- GOOD: Parameterized queries throughout
- BAD: Completely separate from the async pipeline client (see H3)
- BAD: Singleton pattern is not thread-safe

### 4. Security

**Secrets Scanning Results**:
- `.env` file is properly in `.gitignore` and NOT tracked by git
- No API keys found hardcoded in source files
- `JWT_SECRET` in `.env` is a weak development value (see C2)
- Password `strong_dev_password_2024` in `.env` is descriptive but weak
- Previous commits show security improvements (commit `42aab82`: "remove hardcoded development password", commit `e3336a1`: "remove weak default credentials")

**Security Headers** (nginx.conf):
- GOOD: `X-Frame-Options: SAMEORIGIN`
- GOOD: `X-Content-Type-Options: nosniff`
- GOOD: `X-XSS-Protection: 1; mode=block`
- BAD: Missing `Content-Security-Policy`
- BAD: Missing `Strict-Transport-Security` (HSTS)
- BAD: Missing `Referrer-Policy`

**File Permissions**:
- `.env` file is 0644 (world-readable) -- should be 0600

### 5. Observability

**Logging**:
- GOOD: Consistent logger per module (`logging.getLogger(__name__)`)
- GOOD: Structured format with timestamp, level, module
- BAD: Not JSON-structured -- difficult to parse with log aggregation tools
- BAD: No request correlation ID
- BAD: No log rotation in gateway (only via equipment cron)

**Health Checks**:
- GOOD: `/health` basic endpoint
- GOOD: `/api/health/detailed` with Redis, PostgreSQL, agent status checks
- GOOD: WebSocket health broadcasting every 60s
- GOOD: Heartbeat monitor checks 7 components (gateway, redis, postgres, agents, GPU, budget, disk)

**Alerting**:
- GOOD: Telegram integration for critical/warning alerts
- GOOD: Rate-limited alerts (5-minute cooldown)
- BAD: No PagerDuty/Slack/email integration
- BAD: Alert history not persisted (in-memory only)

### 6. Testing

**Test Suite** (22 files, 69 tests):
- Test files cover: gateway startup, admin routing, equipment API/UAT, heartbeat (alerts, API, monitor, security), integration (Phase 2A, system), pipeline integration, security audit, comprehensive UAT, DB degradation
- GOOD: Decent coverage across modules
- BAD: No unit tests for `pipeline/work_order.py`, `pipeline/queue.py`, `pipeline/dispatcher.py`
- BAD: No unit tests for `agentoffice/engine/` (activate, llm_client, contract_manager)
- BAD: No WebSocket tests
- BAD: Some tests rely on live server startup (`test_gateway_simple.py` starts uvicorn via subprocess)
- BAD: No test for auth middleware behavior
- BAD: No mocking of LLM calls -- tests that hit LLM are expensive and non-deterministic

**CI/CD**:
- No `.github/workflows/` directory
- No pre-commit hooks
- No automated linting enforcement

### 7. Reliability

**Heartbeat Monitor** (`heartbeat/monitor.py`):
- GOOD: Comprehensive health checks (gateway, redis, postgres, agents, GPU, budget, disk)
- GOOD: Concurrent health checks via `asyncio.gather()`
- GOOD: Configurable intervals and thresholds
- GOOD: Stale work order detection for stuck agents

**Recovery Manager** (`heartbeat/recovery.py`):
- GOOD: Automatic recovery attempts with rate limiting (max 3 per component)
- GOOD: Disk cleanup (old logs, pycache)
- GOOD: Token budget enforcement
- BAD: Recovery attempt counter resets on restart (see M10)
- BAD: Gateway restart via systemd is disabled by default
- BAD: No circuit breaker pattern for LLM API calls

**Graceful Shutdown**:
- GOOD: FastAPI lifespan cleanup (dispatcher stop, queue close, DB close)
- BAD: No SIGTERM handler in startup script
- BAD: No drain period for in-flight requests

### 8. Performance

**Async Patterns**:
- GOOD: FastAPI with async routes
- GOOD: Async Redis client (`redis.asyncio`)
- GOOD: Async PostgreSQL (`psycopg` v3 async)
- BAD: Single DB connection is a performance bottleneck (see C1)
- BAD: `agentoffice/engine/activate.py` is fully synchronous -- blocks the event loop if called from async context

**Caching**:
- BAD: No caching layer for repeated queries (e.g., agent registry, model config)
- BAD: No Redis caching for API responses

**WebSocket**:
- GOOD: Connection tracking with O(1) lookup
- BAD: Broadcast iterates all connections sequentially
- BAD: No message queue/buffer for offline clients

**Database**:
- GOOD: Proper indexes on frequently queried columns
- BAD: `get_cost_summary()` does a full table scan with `SUM()` on every `/api/metrics` call
- BAD: No query result caching
- BAD: Audit log queries have no pagination

### 9. AgentOffice Engine

**Activation** (`agentoffice/engine/activate.py`):
- GOOD: Chain depth limit (MAX_CHAIN_DEPTH=20) prevents infinite loops
- GOOD: Choice validation with retry mechanism
- GOOD: Memory compression when exceeding limit
- BAD: Entirely synchronous -- will block async event loop
- BAD: No timeout on individual activation steps
- BAD: Tool execution has no sandboxing

**LLM Client** (`agentoffice/engine/llm_client.py`):
- GOOD: Unified interface via litellm
- GOOD: Robust JSON extraction from LLM responses (tries multiple strategies)
- BAD: No timeout (see M9)
- BAD: No retry logic
- BAD: No cost tracking or budget enforcement before calling
- BAD: `api_key` passed in kwargs -- could appear in logs if litellm has verbose mode

**Contract Manager** (`agentoffice/engine/contract_manager.py`):
- GOOD: Clean YAML-based contract lifecycle (pending -> completed -> archived)
- GOOD: Unique contract IDs with timestamp
- BAD: File-system based -- not suitable for high concurrency (race conditions on file moves)
- BAD: No locking mechanism on contract state transitions

---

## Recommended Implementation Order

| # | Task | Priority | Effort | Impact |
|---|------|----------|--------|--------|
| 1 | Create GitHub Actions CI pipeline (lint + test + build) | CRITICAL | M | Prevents regressions on every push |
| 2 | Add PostgreSQL connection pooling (`psycopg_pool.AsyncConnectionPool`) | CRITICAL | M | Fixes concurrency bottleneck |
| 3 | Move rate limiting to Redis | CRITICAL | S | Works across restarts and workers |
| 4 | Set proper CORS origins, require API_SECRET in production | CRITICAL | S | Closes credential-theft vectors |
| 5 | Generate strong JWT secret, add startup validation | CRITICAL | S | Prevents token forgery |
| 6 | Add Docker resource limits | CRITICAL | S | Prevents host OOM |
| 7 | Fix Dockerfile `pip install -e .` to non-editable install | HIGH | S | Fixes broken production image |
| 8 | Add Pydantic request validation to all endpoints | HIGH | M | Input sanitization |
| 9 | Add `.dockerignore` file | HIGH | S | Smaller build context, faster builds |
| 10 | Add TLS termination (Caddy or Traefik) | HIGH | M | Encrypted traffic |
| 11 | Implement request correlation IDs | MEDIUM | S | Debugging in production |
| 12 | Adopt Alembic for database migrations | MEDIUM | M | Schema evolution support |
| 13 | Add LLM call timeouts and retries | MEDIUM | S | Prevents stuck agents |
| 14 | Set up automated PostgreSQL backups | MEDIUM | M | Data safety |
| 15 | Add Prometheus metrics endpoint | MEDIUM | L | Production observability |
| 16 | Create systemd service files for gateway | LOW | S | Proper process management |
| 17 | Add WebSocket ping/pong and rate limiting | LOW | M | Connection reliability |
| 18 | Implement structured JSON logging | LOW | M | Log aggregation readiness |
| 19 | Consolidate database clients | LOW | L | Reduce maintenance burden |
| 20 | Add load testing scripts (locust/k6) | LOW | M | Performance baseline |

Effort key: S = < 1 day, M = 1-3 days, L = 3-5 days, XL = 1+ week

---

## Architecture Recommendations

### 1. Add a Reverse Proxy Layer
Place Caddy or Traefik in front of both the gateway and dashboard. This handles TLS termination, HTTP/2, rate limiting at the edge, and load balancing. Add it as a service in docker-compose.yml.

### 2. Consolidate Database Access
Merge `db/client.py` and `pipeline/work_order.py` into a single async database module using `psycopg_pool.AsyncConnectionPool`. Expose both sync and async interfaces. This eliminates the dual-client confusion and the single-connection bottleneck.

### 3. Externalize Configuration
Move from `.env` file to a proper configuration system. For sensitive values (API keys, passwords), use Docker secrets or an external vault. For non-sensitive config, keep environment variables.

### 4. Add a Message Bus
The current Redis Streams usage is solid. Consider adding Redis pub/sub subscription in the WebSocket manager so that work order progress updates are automatically pushed to connected clients without polling.

### 5. Separate AgentOffice into Its Own Service
The AgentOffice engine is synchronous and CPU/IO intensive (LLM calls). Running it in the same process as the async FastAPI gateway blocks the event loop. Consider running AgentOffice as a separate worker process that consumes contracts from Redis and reports results back.

### 6. Implement Proper Secret Rotation
The current setup has static secrets. Design a secret rotation strategy: JWT secrets should be rotatable (support multiple valid secrets during rotation window), database passwords should be rotatable via connection pool refresh, and API keys should have separate staging/production values.
