"""Work order database operations — create, update, query via PostgreSQL.

This is the **async** database client used by the FastAPI gateway and pipeline.
It uses psycopg3 (async) with connection pooling via psycopg_pool.

For the legacy **sync** client used by CLI scripts, see ``db/client.py``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)


class WorkOrderDB:
    """PostgreSQL work order manager with async connection pooling."""

    def __init__(self, db_url: str, *, min_size: int = 2, max_size: int = 10) -> None:
        self.db_url = db_url
        self._min_size = min_size
        self._max_size = max_size
        self._pool: AsyncConnectionPool | None = None

    async def connect(self) -> None:
        """Create and open the async connection pool."""
        self._pool = AsyncConnectionPool(
            conninfo=self.db_url,
            min_size=self._min_size,
            max_size=self._max_size,
            open=False,
            kwargs={"autocommit": False, "row_factory": dict_row},
        )
        await self._pool.open()
        logger.info(
            "WorkOrderDB pool opened (min=%d, max=%d)", self._min_size, self._max_size
        )

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("WorkOrderDB pool closed")

    @asynccontextmanager
    async def get_connection(self) -> AsyncIterator[psycopg.AsyncConnection]:
        """Acquire a connection from the pool as an async context manager."""
        if not self._pool:
            raise RuntimeError("Database pool not initialised. Call connect() first.")
        async with self._pool.connection() as conn:
            yield conn

    # ------------------------------------------------------------------
    # Work-order CRUD
    # ------------------------------------------------------------------

    async def create_work_order(
        self,
        *,
        wo_id: str,
        intent: str,
        difficulty: str,
        owner: str,
        compressed_context: str,
        relevant_files: list[str],
        qa_requirements: str,
        deadline: str | None = None,
    ) -> dict[str, Any]:
        """Insert a new work order into the database."""
        query = """
            INSERT INTO work_orders (
                id, intent, difficulty, owner, compressed_context,
                relevant_files, qa_requirements, deadline, status, retry_count
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, 'queued', 0
            )
            RETURNING id, intent, difficulty, owner, status, created_at
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    (
                        wo_id,
                        intent,
                        difficulty,
                        owner,
                        compressed_context,
                        relevant_files,
                        qa_requirements,
                        deadline,
                    ),
                )
                result = await cur.fetchone()
                await conn.commit()

        logger.info("Created work order: %s (owner=%s, difficulty=%s)", wo_id, owner, difficulty)
        return result or {}

    async def get_work_order(self, wo_id: str) -> dict[str, Any] | None:
        """Retrieve a work order by ID."""
        query = "SELECT * FROM work_orders WHERE id = %s"
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (wo_id,))
                return await cur.fetchone()

    async def update_status(
        self,
        wo_id: str,
        status: str,
        *,
        error: str | None = None,
        increment_retry: bool = False,
    ) -> None:
        """Update work order status."""
        if status == "completed":
            query = """
                UPDATE work_orders
                SET status = %s, completed_at = NOW(), last_error = NULL
                WHERE id = %s
            """
            params = (status, wo_id)
        elif increment_retry:
            query = """
                UPDATE work_orders
                SET status = %s, retry_count = retry_count + 1, last_error = %s
                WHERE id = %s
            """
            params = (status, error, wo_id)
        else:
            query = """
                UPDATE work_orders
                SET status = %s, last_error = %s
                WHERE id = %s
            """
            params = (status, error, wo_id)

        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                await conn.commit()

        logger.info("Updated work order %s -> %s", wo_id, status)

    async def insert_audit_log(
        self,
        *,
        work_order_id: str | None,
        session_id: str | None,
        actor: str,
        action: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Insert an audit log entry."""
        query = """
            INSERT INTO audit_logs (work_order_id, session_id, actor, action, status, details)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    (work_order_id, session_id, actor, action, status, Jsonb(details or {})),
                )
                await conn.commit()

        logger.debug("Audit log: %s %s -> %s", actor, action, status)

    async def insert_agent_metric(
        self,
        *,
        work_order_id: str | None,
        session_id: str | None,
        agent_name: str,
        role: str,
        model: str,
        provider: str | None,
        success: bool,
        latency_ms: int,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert an agent performance metric."""
        query = """
            INSERT INTO agent_metrics (
                work_order_id, session_id, agent_name, role, model, provider,
                success, latency_ms, prompt_tokens, completion_tokens, cost_usd, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    (
                        work_order_id,
                        session_id,
                        agent_name,
                        role,
                        model,
                        provider,
                        success,
                        latency_ms,
                        prompt_tokens,
                        completion_tokens,
                        cost_usd,
                        Jsonb(metadata or {}),
                    ),
                )
                await conn.commit()

        logger.debug("Agent metric: %s (role=%s, model=%s)", agent_name, role, model)

    async def get_cost_summary(
        self, period: str = "today"
    ) -> dict[str, int | float]:
        """Get token usage and cost summary for a period."""
        if period == "today":
            where_clause = "created_at >= CURRENT_DATE"
        elif period == "week":
            where_clause = "created_at >= CURRENT_DATE - INTERVAL '7 days'"
        elif period == "month":
            where_clause = "created_at >= CURRENT_DATE - INTERVAL '30 days'"
        else:
            where_clause = "TRUE"

        query = f"""
            SELECT
                SUM(prompt_tokens) as prompt_tokens,
                SUM(completion_tokens) as completion_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(cost_usd) as total_cost
            FROM agent_metrics
            WHERE {where_clause}
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                row = await cur.fetchone()
                return {
                    "prompt_tokens": int(row["prompt_tokens"] or 0),
                    "completion_tokens": int(row["completion_tokens"] or 0),
                    "total_tokens": int(row["total_tokens"] or 0),
                    "total_cost": float(row["total_cost"] or 0.0),
                }

    async def get_recent_audit_logs(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent audit log entries."""
        query = """
            SELECT id, work_order_id, actor, action, status, created_at
            FROM audit_logs
            ORDER BY created_at DESC
            LIMIT %s
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (limit,))
                return await cur.fetchall()

    async def get_system_status(self) -> dict[str, Any]:
        """Get system health metrics."""
        query_wo = """
            SELECT
                COUNT(*) FILTER (WHERE status = 'queued') as queued,
                COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed
            FROM work_orders
            WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query_wo)
                wo_stats = await cur.fetchone()

        return {
            "work_orders": {
                "queued": int(wo_stats["queued"] or 0),
                "in_progress": int(wo_stats["in_progress"] or 0),
                "completed": int(wo_stats["completed"] or 0),
                "failed": int(wo_stats["failed"] or 0),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
