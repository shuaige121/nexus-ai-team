"""Dispatcher — consume work orders from queue, route to agents, update status."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from nexus_v1.model_router import ModelRouter

from .queue import QueueManager
from .work_order import WorkOrderDB

# Optional: Import database logging integration
try:
    from db.integration import log_agent_execution, log_audit_event
    DB_LOGGING_AVAILABLE = True
except ImportError:
    DB_LOGGING_AVAILABLE = False

logger = logging.getLogger(__name__)

# Cost estimation (USD per 1M tokens) based on PROJECT_PLAN.md
COST_PER_1M_TOKENS = {
    "ceo": {"input": 5.0, "output": 25.0},
    "director": {"input": 3.0, "output": 15.0},
    "intern": {"input": 0.8, "output": 4.0},
    "admin": {"input": 0.0, "output": 0.0},  # local model
}


class Dispatcher:
    """
    Main dispatcher loop:
    1. Consume work orders from Redis Streams queue
    2. Route to appropriate agent via ModelRouter
    3. Update work order status in PostgreSQL
    4. Publish progress events for WebSocket
    """

    def __init__(
        self,
        db: WorkOrderDB,
        queue: QueueManager,
        router: ModelRouter | None = None,
    ) -> None:
        self.db = db
        self.queue = queue
        self.router = router or ModelRouter()
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(
        self,
        consumer_group: str = "nexus-dispatcher",
        consumer_name: str = "worker-1",
    ) -> None:
        """Start the dispatcher loop in the background."""
        if self._running:
            logger.warning("Dispatcher already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop(consumer_group, consumer_name))
        logger.info("Dispatcher started (group=%s, name=%s)", consumer_group, consumer_name)

    async def stop(self) -> None:
        """Stop the dispatcher loop."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Dispatcher stopped")

    async def _run_loop(self, consumer_group: str, consumer_name: str) -> None:
        """Main dispatcher loop — consume and process work orders."""
        while self._running:
            try:
                messages = await self.queue.consume(
                    consumer_group=consumer_group,
                    consumer_name=consumer_name,
                    count=1,
                    block_ms=5000,
                )

                for msg in messages:
                    await self._process_message(msg, consumer_group)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Dispatcher loop error")
                await asyncio.sleep(5)

    async def _process_message(self, msg: dict[str, Any], consumer_group: str) -> None:
        """Process a single work order message."""
        work_order_id = msg["work_order_id"]
        entry_id = msg["entry_id"]
        payload = msg["payload"]

        logger.info("Processing work order: %s", work_order_id)

        try:
            # Fetch full work order from DB
            wo = await self.db.get_work_order(work_order_id)
            if not wo:
                logger.warning("Work order %s not found in DB", work_order_id)
                await self.queue.ack(entry_id, consumer_group)
                return

            # Update status to in_progress
            await self.db.update_status(work_order_id, "in_progress")
            await self._publish_progress(work_order_id, "in_progress", {"started": True})

            # Audit log
            await self.db.insert_audit_log(
                work_order_id=work_order_id,
                session_id=payload.get("session_id"),
                actor="dispatcher",
                action="process_start",
                status="info",
                details={"owner": wo["owner"]},
            )

            # Additional logging to Phase 3B database (if available)
            if DB_LOGGING_AVAILABLE:
                log_audit_event(
                    actor="dispatcher",
                    action="process_start",
                    status="info",
                    work_order_id=work_order_id,
                    session_id=payload.get("session_id"),
                    details={"owner": wo["owner"]},
                )

            # Execute work order via ModelRouter
            result = await self._execute_work_order(wo, payload)

            # Update status to completed
            await self.db.update_status(work_order_id, "completed")
            await self._publish_progress(work_order_id, "completed", result)

            # Audit log
            await self.db.insert_audit_log(
                work_order_id=work_order_id,
                session_id=payload.get("session_id"),
                actor=wo["owner"],
                action="process_complete",
                status="success",
                details=result,
            )

            # ACK the message
            await self.queue.ack(entry_id, consumer_group)
            logger.info("Completed work order: %s", work_order_id)

        except Exception as e:
            logger.exception("Failed to process work order %s", work_order_id)

            # Update status to failed, increment retry
            await self.db.update_status(
                work_order_id,
                "failed",
                error=str(e),
                increment_retry=True,
            )
            await self._publish_progress(
                work_order_id,
                "failed",
                {"error": str(e)},
            )

            # Audit log
            await self.db.insert_audit_log(
                work_order_id=work_order_id,
                session_id=payload.get("session_id"),
                actor="dispatcher",
                action="process_failed",
                status="failure",
                details={"error": str(e)},
            )

            # ACK the message even on failure (manual retry handled elsewhere)
            await self.queue.ack(entry_id, consumer_group)

    async def _execute_work_order(
        self, wo: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a work order using ModelRouter."""
        owner = wo["owner"]
        user_message = payload.get("user_message", "")
        conversation = payload.get("conversation", [])

        # Build messages for LLM
        messages = []
        if conversation:
            messages.extend(conversation[-5:])  # Last 5 messages for context
        messages.append({"role": "user", "content": user_message})

        # Track time
        start_time = time.time()

        # Route to agent
        response = self.router.chat(messages, role=owner)

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Extract metrics
        usage = response.usage or {}
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        cost_usd = self._calculate_cost(owner, prompt_tokens, completion_tokens)

        # Insert agent metric
        await self.db.insert_agent_metric(
            work_order_id=wo["id"],
            session_id=payload.get("session_id"),
            agent_name=f"{owner}_agent",
            role=owner,
            model=response.model,
            provider=response.provider,
            success=True,
            latency_ms=elapsed_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            metadata={"difficulty": wo["difficulty"]},
        )

        # Additional logging to Phase 3B database (if available)
        if DB_LOGGING_AVAILABLE:
            log_agent_execution(
                work_order_id=wo["id"],
                session_id=payload.get("session_id"),
                agent_name=f"{owner}_agent",
                role=owner,
                model=response.model,
                provider=response.provider,
                success=True,
                latency_ms=elapsed_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
                metadata={"difficulty": wo["difficulty"]},
            )

        return {
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "latency_ms": elapsed_ms,
            "tokens": usage,
            "cost_usd": cost_usd,
        }

    @staticmethod
    def _calculate_cost(role: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost in USD based on token usage."""
        cost_config = COST_PER_1M_TOKENS.get(role, {"input": 0.0, "output": 0.0})
        input_cost = (prompt_tokens / 1_000_000) * cost_config["input"]
        output_cost = (completion_tokens / 1_000_000) * cost_config["output"]
        return round(input_cost + output_cost, 6)

    async def _publish_progress(
        self, work_order_id: str, status: str, data: dict[str, Any]
    ) -> None:
        """Publish progress event to Redis pub/sub for WebSocket broadcasting."""
        event = {
            "work_order_id": work_order_id,
            "status": status,
            "data": data,
        }
        await self.queue.publish_event(f"nexus:progress:{work_order_id}", event)
        logger.debug("Published progress: %s -> %s", work_order_id, status)
