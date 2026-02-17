"""Work order database operations — create, update, query via PostgreSQL."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class WorkOrderDB:
    """PostgreSQL work order manager."""

    def __init__(self, db_url: str) -> None:
        self.db_url = db_url
        self._conn: psycopg.Connection | None = None

    async def connect(self) -> None:
        """Establish async PostgreSQL connection."""
        self._conn = await psycopg.AsyncConnection.connect(
            self.db_url,
            autocommit=False,
            row_factory=dict_row,
        )
        logger.info("WorkOrderDB connected to PostgreSQL")

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("WorkOrderDB disconnected")

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
        if not self._conn:
            raise RuntimeError("Database not connected. Call connect() first.")

        query = """
            INSERT INTO work_orders (
                id, intent, difficulty, owner, compressed_context,
                relevant_files, qa_requirements, deadline, status, retry_count
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, 'queued', 0
            )
            RETURNING id, intent, difficulty, owner, status, created_at
        """
        async with self._conn.cursor() as cur:
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
            await self._conn.commit()

        logger.info("Created work order: %s (owner=%s, difficulty=%s)", wo_id, owner, difficulty)
        return result or {}

    async def get_work_order(self, wo_id: str) -> dict[str, Any] | None:
        """Retrieve a work order by ID."""
        if not self._conn:
            raise RuntimeError("Database not connected.")

        query = "SELECT * FROM work_orders WHERE id = %s"
        async with self._conn.cursor() as cur:
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
        if not self._conn:
            raise RuntimeError("Database not connected.")

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

        async with self._conn.cursor() as cur:
            await cur.execute(query, params)
            await self._conn.commit()

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
        if not self._conn:
            raise RuntimeError("Database not connected.")

        query = """
            INSERT INTO audit_logs (work_order_id, session_id, actor, action, status, details)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        async with self._conn.cursor() as cur:
            await cur.execute(
                query,
                (work_order_id, session_id, actor, action, status, details or {}),
            )
            await self._conn.commit()

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
        if not self._conn:
            raise RuntimeError("Database not connected.")

        query = """
            INSERT INTO agent_metrics (
                work_order_id, session_id, agent_name, role, model, provider,
                success, latency_ms, prompt_tokens, completion_tokens, cost_usd, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        async with self._conn.cursor() as cur:
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
                    metadata or {},
                ),
            )
            await self._conn.commit()

        logger.debug("Agent metric: %s (role=%s, model=%s)", agent_name, role, model)

    async def get_cost_summary(
        self, period: str = "today"
    ) -> dict[str, int | float]:
        """Get token usage and cost summary for a period."""
        if not self._conn:
            raise RuntimeError("Database not connected.")

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
        async with self._conn.cursor() as cur:
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
        if not self._conn:
            raise RuntimeError("Database not connected.")

        query = """
            SELECT id, work_order_id, actor, action, status, created_at
            FROM audit_logs
            ORDER BY created_at DESC
            LIMIT %s
        """
        async with self._conn.cursor() as cur:
            await cur.execute(query, (limit,))
            return await cur.fetchall()

    async def get_system_status(self) -> dict[str, Any]:
        """Get system health metrics."""
        if not self._conn:
            raise RuntimeError("Database not connected.")

        query_wo = """
            SELECT
                COUNT(*) FILTER (WHERE status = 'queued') as queued,
                COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed
            FROM work_orders
            WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
        """
        async with self._conn.cursor() as cur:
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
