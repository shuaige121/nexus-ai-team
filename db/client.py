#!/usr/bin/env python3
"""Database client for NEXUS with PostgreSQL and SQLite fallback support.

.. deprecated::
    This is the **legacy synchronous** database client, used only by CLI scripts
    and offline tooling (e.g. db/ CLI helpers).  It uses psycopg2 (sync).

    For the **async** database client used by the FastAPI gateway and the
    execution pipeline, see :mod:`pipeline.work_order.WorkOrderDB` which uses
    ``psycopg3`` with ``psycopg_pool.AsyncConnectionPool``.

    Do **not** add new features here.  New database access should go through
    ``WorkOrderDB`` (async) whenever possible.  This module will be retired
    once all CLI scripts are migrated to async.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

logger = logging.getLogger(__name__)


@dataclass
class WorkOrderLog:
    """Work order creation/completion log."""
    id: str
    intent: str
    difficulty: str
    owner: str
    compressed_context: str
    relevant_files: list[str]
    qa_requirements: str
    status: str = "queued"
    retry_count: int = 0
    deadline: datetime | None = None
    completed_at: datetime | None = None
    last_error: str | None = None


@dataclass
class AgentMetric:
    """Agent execution metrics."""
    work_order_id: str | None
    session_id: str | None
    agent_name: str
    role: str
    model: str
    provider: str | None
    success: bool
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    metadata: dict[str, Any] | None = None


@dataclass
class AuditLog:
    """Audit log entry."""
    actor: str
    action: str
    status: str
    work_order_id: str | None = None
    session_id: str | None = None
    details: dict[str, Any] | None = None


@dataclass
class SessionLog:
    """Session tracking entry."""
    id: str
    user_id: str
    channel: str
    status: str = "active"
    title: str | None = None
    context: dict[str, Any] | None = None


class DatabaseClient:
    """Database client supporting PostgreSQL with SQLite fallback."""

    def __init__(
        self,
        postgres_url: str | None = None,
        sqlite_path: str | Path | None = None,
        pool_size: int = 5,
    ):
        self.postgres_url = postgres_url or os.getenv("DATABASE_URL")
        self.sqlite_path = Path(sqlite_path or os.getenv("SQLITE_DB_PATH", "nexus.db"))
        self.pool_size = pool_size
        self._pool: psycopg2.pool.SimpleConnectionPool | None = None
        self._use_postgres = False

        self._initialize()

    def _initialize(self) -> None:
        """Initialize database connection (PostgreSQL or SQLite fallback)."""
        if HAS_POSTGRES and self.postgres_url:
            try:
                self._pool = psycopg2.pool.SimpleConnectionPool(
                    1,
                    self.pool_size,
                    self.postgres_url,
                )
                # Test connection
                with self._get_postgres_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                self._use_postgres = True
                logger.info("Connected to PostgreSQL database")
                return
            except Exception as exc:
                logger.warning(f"Failed to connect to PostgreSQL: {exc}")
                logger.info("Falling back to SQLite")

        # Fallback to SQLite
        self._use_postgres = False
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_sqlite_schema()
        logger.info(f"Using SQLite database at {self.sqlite_path}")

    @contextmanager
    def _get_postgres_conn(self) -> Iterator[Any]:
        """Get PostgreSQL connection from pool."""
        if not self._pool:
            raise RuntimeError("PostgreSQL pool not initialized")
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    @contextmanager
    def _get_sqlite_conn(self) -> Iterator[sqlite3.Connection]:
        """Get SQLite connection."""
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_sqlite_schema(self) -> None:
        """Initialize SQLite schema (simplified version of PostgreSQL schema)."""
        schema = """
        CREATE TABLE IF NOT EXISTS work_orders (
            id TEXT PRIMARY KEY,
            intent TEXT NOT NULL,
            difficulty TEXT NOT NULL CHECK (difficulty IN ('trivial', 'normal', 'complex', 'unclear')),
            owner TEXT NOT NULL CHECK (owner IN ('admin', 'intern', 'director', 'ceo')),
            compressed_context TEXT NOT NULL,
            relevant_files TEXT NOT NULL,
            qa_requirements TEXT NOT NULL,
            deadline TEXT,
            status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'in_progress', 'blocked', 'completed', 'failed', 'cancelled')),
            retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT,
            last_error TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            channel TEXT NOT NULL CHECK (channel IN ('telegram', 'webgui', 'api', 'internal')),
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'closed', 'expired')),
            title TEXT,
            context TEXT NOT NULL DEFAULT '{}',
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_activity_at TEXT NOT NULL DEFAULT (datetime('now')),
            ended_at TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_order_id TEXT,
            session_id TEXT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('success', 'failure', 'warning', 'info')),
            details TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (work_order_id) REFERENCES work_orders(id) ON DELETE SET NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS agent_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_order_id TEXT,
            session_id TEXT,
            agent_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'intern', 'director', 'ceo', 'equipment')),
            model TEXT NOT NULL,
            provider TEXT,
            success INTEGER NOT NULL,
            latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
            prompt_tokens INTEGER NOT NULL DEFAULT 0 CHECK (prompt_tokens >= 0),
            completion_tokens INTEGER NOT NULL DEFAULT 0 CHECK (completion_tokens >= 0),
            cost_usd REAL NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (work_order_id) REFERENCES work_orders(id) ON DELETE CASCADE,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_work_orders_owner_status ON work_orders(owner, status);
        CREATE INDEX IF NOT EXISTS idx_work_orders_deadline ON work_orders(deadline);
        CREATE INDEX IF NOT EXISTS idx_work_orders_created_at ON work_orders(created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_sessions_user_status ON sessions(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity_at DESC);

        CREATE INDEX IF NOT EXISTS idx_audit_logs_work_order ON audit_logs(work_order_id);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_session ON audit_logs(session_id);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_agent_metrics_work_order ON agent_metrics(work_order_id);
        CREATE INDEX IF NOT EXISTS idx_agent_metrics_agent_created ON agent_metrics(agent_name, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_agent_metrics_success_created ON agent_metrics(success, created_at DESC);
        """

        with self._get_sqlite_conn() as conn:
            conn.executescript(schema)

    def log_work_order(self, work_order: WorkOrderLog) -> None:
        """Log work order creation/update."""
        if self._use_postgres:
            self._log_work_order_postgres(work_order)
        else:
            self._log_work_order_sqlite(work_order)

    def _log_work_order_postgres(self, work_order: WorkOrderLog) -> None:
        """Log work order to PostgreSQL."""
        with self._get_postgres_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO work_orders (
                        id, intent, difficulty, owner, compressed_context,
                        relevant_files, qa_requirements, status, retry_count,
                        deadline, completed_at, last_error
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        retry_count = EXCLUDED.retry_count,
                        completed_at = EXCLUDED.completed_at,
                        last_error = EXCLUDED.last_error,
                        updated_at = NOW()
                    """,
                    (
                        work_order.id,
                        work_order.intent,
                        work_order.difficulty,
                        work_order.owner,
                        work_order.compressed_context,
                        work_order.relevant_files,
                        work_order.qa_requirements,
                        work_order.status,
                        work_order.retry_count,
                        work_order.deadline,
                        work_order.completed_at,
                        work_order.last_error,
                    ),
                )

    def _log_work_order_sqlite(self, work_order: WorkOrderLog) -> None:
        """Log work order to SQLite."""
        with self._get_sqlite_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO work_orders (
                    id, intent, difficulty, owner, compressed_context,
                    relevant_files, qa_requirements, status, retry_count,
                    deadline, completed_at, last_error, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    work_order.id,
                    work_order.intent,
                    work_order.difficulty,
                    work_order.owner,
                    work_order.compressed_context,
                    json.dumps(work_order.relevant_files),
                    work_order.qa_requirements,
                    work_order.status,
                    work_order.retry_count,
                    work_order.deadline.isoformat() if work_order.deadline else None,
                    work_order.completed_at.isoformat() if work_order.completed_at else None,
                    work_order.last_error,
                ),
            )

    def log_agent_metric(self, metric: AgentMetric) -> None:
        """Log agent execution metrics."""
        if self._use_postgres:
            self._log_agent_metric_postgres(metric)
        else:
            self._log_agent_metric_sqlite(metric)

    def _log_agent_metric_postgres(self, metric: AgentMetric) -> None:
        """Log agent metric to PostgreSQL."""
        with self._get_postgres_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_metrics (
                        work_order_id, session_id, agent_name, role, model,
                        provider, success, latency_ms, prompt_tokens,
                        completion_tokens, cost_usd, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        metric.work_order_id,
                        metric.session_id,
                        metric.agent_name,
                        metric.role,
                        metric.model,
                        metric.provider,
                        metric.success,
                        metric.latency_ms,
                        metric.prompt_tokens,
                        metric.completion_tokens,
                        metric.cost_usd,
                        json.dumps(metric.metadata or {}),
                    ),
                )

    def _log_agent_metric_sqlite(self, metric: AgentMetric) -> None:
        """Log agent metric to SQLite."""
        with self._get_sqlite_conn() as conn:
            conn.execute(
                """
                INSERT INTO agent_metrics (
                    work_order_id, session_id, agent_name, role, model,
                    provider, success, latency_ms, prompt_tokens,
                    completion_tokens, cost_usd, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metric.work_order_id,
                    metric.session_id,
                    metric.agent_name,
                    metric.role,
                    metric.model,
                    metric.provider,
                    1 if metric.success else 0,
                    metric.latency_ms,
                    metric.prompt_tokens,
                    metric.completion_tokens,
                    metric.cost_usd,
                    json.dumps(metric.metadata or {}),
                ),
            )

    def log_audit(self, audit: AuditLog) -> None:
        """Log audit entry."""
        if self._use_postgres:
            self._log_audit_postgres(audit)
        else:
            self._log_audit_sqlite(audit)

    def _log_audit_postgres(self, audit: AuditLog) -> None:
        """Log audit entry to PostgreSQL."""
        with self._get_postgres_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs (
                        work_order_id, session_id, actor, action, status, details
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        audit.work_order_id,
                        audit.session_id,
                        audit.actor,
                        audit.action,
                        audit.status,
                        json.dumps(audit.details or {}),
                    ),
                )

    def _log_audit_sqlite(self, audit: AuditLog) -> None:
        """Log audit entry to SQLite."""
        with self._get_sqlite_conn() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (
                    work_order_id, session_id, actor, action, status, details
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    audit.work_order_id,
                    audit.session_id,
                    audit.actor,
                    audit.action,
                    audit.status,
                    json.dumps(audit.details or {}),
                ),
            )

    def log_session(self, session: SessionLog) -> None:
        """Log session creation/update."""
        if self._use_postgres:
            self._log_session_postgres(session)
        else:
            self._log_session_sqlite(session)

    def _log_session_postgres(self, session: SessionLog) -> None:
        """Log session to PostgreSQL."""
        with self._get_postgres_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sessions (
                        id, user_id, channel, status, title, context
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        title = EXCLUDED.title,
                        context = EXCLUDED.context,
                        last_activity_at = NOW(),
                        updated_at = NOW()
                    """,
                    (
                        session.id,
                        session.user_id,
                        session.channel,
                        session.status,
                        session.title,
                        json.dumps(session.context or {}),
                    ),
                )

    def _log_session_sqlite(self, session: SessionLog) -> None:
        """Log session to SQLite."""
        with self._get_sqlite_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (
                    id, user_id, channel, status, title, context,
                    last_activity_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    session.id,
                    session.user_id,
                    session.channel,
                    session.status,
                    session.title,
                    json.dumps(session.context or {}),
                ),
            )

    def query_metrics(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        agent_name: str | None = None,
        work_order_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query agent metrics with filters."""
        if self._use_postgres:
            return self._query_metrics_postgres(start_time, end_time, agent_name, work_order_id, limit)
        return self._query_metrics_sqlite(start_time, end_time, agent_name, work_order_id, limit)

    def _query_metrics_postgres(
        self,
        start_time: datetime | None,
        end_time: datetime | None,
        agent_name: str | None,
        work_order_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Query metrics from PostgreSQL."""
        conditions = []
        params: list[Any] = []

        if start_time:
            conditions.append("created_at >= %s")
            params.append(start_time)
        if end_time:
            conditions.append("created_at <= %s")
            params.append(end_time)
        if agent_name:
            conditions.append("agent_name = %s")
            params.append(agent_name)
        if work_order_id:
            conditions.append("work_order_id = %s")
            params.append(work_order_id)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        params.append(limit)

        with self._get_postgres_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT * FROM agent_metrics
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    params,
                )
                return [dict(row) for row in cur.fetchall()]

    def _query_metrics_sqlite(
        self,
        start_time: datetime | None,
        end_time: datetime | None,
        agent_name: str | None,
        work_order_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Query metrics from SQLite."""
        conditions = []
        params: list[Any] = []

        if start_time:
            conditions.append("created_at >= ?")
            params.append(start_time.isoformat())
        if end_time:
            conditions.append("created_at <= ?")
            params.append(end_time.isoformat())
        if agent_name:
            conditions.append("agent_name = ?")
            params.append(agent_name)
        if work_order_id:
            conditions.append("work_order_id = ?")
            params.append(work_order_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        with self._get_sqlite_conn() as conn:
            cursor = conn.execute(
                f"""
                SELECT * FROM agent_metrics
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
            )
            return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close database connections."""
        if self._pool:
            self._pool.closeall()
            logger.info("PostgreSQL connection pool closed")


# Singleton instance
_db_client: DatabaseClient | None = None


def get_db_client() -> DatabaseClient:
    """Get or create singleton database client."""
    global _db_client
    if _db_client is None:
        _db_client = DatabaseClient()
    return _db_client
