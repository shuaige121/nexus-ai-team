-- ══════════════════════════════════════════════════════════════════════════════
-- NEXUS PostgreSQL Initialization Script
-- ══════════════════════════════════════════════════════════════════════════════
--
-- This script is automatically executed when the PostgreSQL container starts
-- for the first time. It creates the database schema with all required tables,
-- indexes, and constraints.
--
-- Tables:
--   - work_orders     : Task assignments and execution tracking
--   - sessions        : User session management (WebSocket, Telegram, API)
--   - audit_logs      : Complete audit trail of all system actions
--   - agent_metrics   : Performance metrics, token usage, and costs
--

BEGIN;

-- ── Utility Functions ─────────────────────────────────────────────────────────

-- Automatically update the updated_at timestamp on any UPDATE
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ── Core Tables ───────────────────────────────────────────────────────────────

-- Work Orders: Tasks assigned to AI agents
CREATE TABLE IF NOT EXISTS work_orders (
  id TEXT PRIMARY KEY,
  intent TEXT NOT NULL,
  difficulty TEXT NOT NULL CHECK (difficulty IN ('trivial', 'normal', 'complex', 'unclear')),
  owner TEXT NOT NULL CHECK (owner IN ('admin', 'intern', 'director', 'ceo')),
  compressed_context TEXT NOT NULL,
  relevant_files TEXT[] NOT NULL DEFAULT '{}',
  qa_requirements TEXT NOT NULL,
  deadline TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'in_progress', 'blocked', 'completed', 'failed', 'cancelled')),
  retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  last_error TEXT
);

DROP TRIGGER IF EXISTS trg_work_orders_updated_at ON work_orders;
CREATE TRIGGER trg_work_orders_updated_at
BEFORE UPDATE ON work_orders
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Sessions: Multi-channel user sessions (WebSocket, Telegram, API)
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('telegram', 'webgui', 'api', 'internal')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'closed', 'expired')),
  title TEXT,
  context JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ended_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_sessions_updated_at ON sessions;
CREATE TRIGGER trg_sessions_updated_at
BEFORE UPDATE ON sessions
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Audit Logs: Complete system activity trail
CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGSERIAL PRIMARY KEY,
  work_order_id TEXT REFERENCES work_orders(id) ON DELETE SET NULL,
  session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('success', 'failure', 'warning', 'info')),
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Agent Metrics: Performance tracking, token usage, and cost analysis
CREATE TABLE IF NOT EXISTS agent_metrics (
  id BIGSERIAL PRIMARY KEY,
  work_order_id TEXT REFERENCES work_orders(id) ON DELETE CASCADE,
  session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
  agent_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin', 'intern', 'director', 'ceo', 'equipment')),
  model TEXT NOT NULL,
  provider TEXT,
  success BOOLEAN NOT NULL,
  latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
  prompt_tokens INTEGER NOT NULL DEFAULT 0 CHECK (prompt_tokens >= 0),
  completion_tokens INTEGER NOT NULL DEFAULT 0 CHECK (completion_tokens >= 0),
  total_tokens INTEGER GENERATED ALWAYS AS (prompt_tokens + completion_tokens) STORED,
  cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Indexes for Performance ───────────────────────────────────────────────────

-- Work Orders
CREATE INDEX IF NOT EXISTS idx_work_orders_owner_status ON work_orders(owner, status);
CREATE INDEX IF NOT EXISTS idx_work_orders_deadline ON work_orders(deadline);
CREATE INDEX IF NOT EXISTS idx_work_orders_created_at ON work_orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_work_orders_status ON work_orders(status);

-- Sessions
CREATE INDEX IF NOT EXISTS idx_sessions_user_status ON sessions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_channel ON sessions(channel);

-- Audit Logs
CREATE INDEX IF NOT EXISTS idx_audit_logs_work_order ON audit_logs(work_order_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_session ON audit_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_action ON audit_logs(actor, action);

-- Agent Metrics
CREATE INDEX IF NOT EXISTS idx_agent_metrics_work_order ON agent_metrics(work_order_id);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_agent_created ON agent_metrics(agent_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_success_created ON agent_metrics(success, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_role ON agent_metrics(role);

COMMIT;

-- ── Completion Notice ─────────────────────────────────────────────────────────
-- This message will appear in the PostgreSQL logs
DO $$
BEGIN
  RAISE NOTICE '✅ NEXUS database schema initialized successfully';
END
$$;
