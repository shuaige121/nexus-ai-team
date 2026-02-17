"""Escalation manager - handles Intern → Director → CEO → Board escalation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from nexus_v1.admin import WorkOrder
from nexus_v1.config import AgentRole

from .executor import ExecutionAgent, ExecutionResult

logger = logging.getLogger(__name__)

EscalationStatus = Literal["success", "escalated", "failed", "needs_board"]


@dataclass
class EscalationResult:
    """Result of escalation process."""

    work_order_id: str
    status: EscalationStatus
    final_result: ExecutionResult | None = None
    escalation_chain: list[AgentRole] = field(default_factory=list)
    attempt_count: int = 0
    board_notification: str | None = None


class EscalationManager:
    """
    Manages the escalation chain: Intern → Director → CEO → Board.

    Flow:
    1. Start with assigned owner (based on difficulty)
    2. If fails, escalate to next level
    3. After 3 total failures (across all levels), escalate to Board
    """

    MAX_ATTEMPTS = 3
    ESCALATION_CHAIN: list[AgentRole] = ["intern", "director", "ceo"]

    def __init__(self, executor: ExecutionAgent | None = None) -> None:
        self.executor = executor or ExecutionAgent()

    def execute_with_escalation(self, work_order: WorkOrder) -> EscalationResult:
        """
        Execute work order with automatic escalation on failure.

        Args:
            work_order: The work order to execute

        Returns:
            EscalationResult with final outcome and escalation history
        """
        logger.info(
            f"Starting execution with escalation for {work_order.id} "
            f"(initial owner: {work_order.owner})"
        )

        # Determine starting point in escalation chain
        start_role = work_order.owner
        if work_order.difficulty == "unclear":
            # For unclear requests, skip execution and ask for clarification
            return EscalationResult(
                work_order_id=work_order.id,
                status="failed",
                final_result=ExecutionResult(
                    work_order_id=work_order.id,
                    agent_role="admin",
                    success=False,
                    output="",
                    error=f"Clarification needed: {work_order.clarification_question}",
                ),
                escalation_chain=["admin"],
                attempt_count=0,
                board_notification="Request unclear - requires user clarification",
            )

        # Find starting position in chain
        try:
            start_idx = self.ESCALATION_CHAIN.index(start_role)
        except ValueError:
            # If role not in chain, start from beginning
            start_idx = 0

        escalation_chain: list[AgentRole] = []
        attempt_count = 0
        last_result: ExecutionResult | None = None

        # Try escalation chain
        for role in self.ESCALATION_CHAIN[start_idx:]:
            if attempt_count >= self.MAX_ATTEMPTS:
                break

            attempt_count += 1
            escalation_chain.append(role)

            logger.info(
                f"Attempt {attempt_count}/{self.MAX_ATTEMPTS}: "
                f"Executing {work_order.id} as {role}"
            )

            result = self.executor.execute(work_order, override_role=role)
            last_result = result

            if result.success:
                logger.info(
                    f"Work order {work_order.id} completed successfully by {role} "
                    f"(attempt {attempt_count})"
                )
                return EscalationResult(
                    work_order_id=work_order.id,
                    status="success" if attempt_count == 1 else "escalated",
                    final_result=result,
                    escalation_chain=escalation_chain,
                    attempt_count=attempt_count,
                )

            logger.warning(
                f"Attempt {attempt_count} failed for {work_order.id} "
                f"(role: {role}, error: {result.error})"
            )

        # All attempts exhausted - escalate to Board
        logger.error(
            f"All {attempt_count} attempts failed for {work_order.id}. "
            "Escalating to Board."
        )

        board_notification = self._create_board_notification(
            work_order,
            escalation_chain,
            last_result,
        )

        return EscalationResult(
            work_order_id=work_order.id,
            status="needs_board",
            final_result=last_result,
            escalation_chain=escalation_chain,
            attempt_count=attempt_count,
            board_notification=board_notification,
        )

    def _create_board_notification(
        self,
        work_order: WorkOrder,
        escalation_chain: list[AgentRole],
        last_result: ExecutionResult | None,
    ) -> str:
        """Create a notification message for the Board."""
        chain_str = " → ".join(escalation_chain)

        error_details = "Unknown error"
        if last_result:
            error_details = last_result.error or "Task failed self-test validation"

        return f"""BOARD ESCALATION REQUIRED

Work Order: {work_order.id}
Intent: {work_order.intent}
Difficulty: {work_order.difficulty}

Escalation Chain: {chain_str}
Total Attempts: {len(escalation_chain)}

Last Error: {error_details}

Request Context:
{work_order.compressed_context[:500]}...

This task requires Board intervention or user clarification.
"""
