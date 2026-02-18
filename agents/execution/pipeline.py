"""Complete execution pipeline: Admin → Route → Execute → QA → Return."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from nexus_v1.admin import AdminAgent

from .escalation import EscalationManager, EscalationResult

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of the complete execution pipeline."""

    work_order_id: str
    success: bool
    output: str
    qa_passed: bool
    escalation_info: dict[str, Any]
    board_notification: str | None = None


class ExecutionPipeline:
    """
    Complete execution pipeline orchestrating:
    1. Admin agent (compress + classify)
    2. Routing (by difficulty)
    3. Execution (with escalation)
    4. QA validation
    5. Return result
    """

    def __init__(
        self,
        admin: AdminAgent | None = None,
        escalation_mgr: EscalationManager | None = None,
    ) -> None:
        self.admin = admin or AdminAgent()
        self.escalation_mgr = escalation_mgr or EscalationManager()

    async def process(
        self,
        user_message: str,
        conversation: list[dict[str, Any]] | None = None,
    ) -> PipelineResult:
        """
        Process a user message through the complete pipeline.

        Args:
            user_message: The user's request
            conversation: Optional conversation history

        Returns:
            PipelineResult with execution outcome
        """
        # Step 1: Admin creates work order
        logger.info(f"Pipeline: Creating work order for message: {user_message[:100]}...")
        work_order = self.admin.create_work_order(user_message, conversation)

        logger.info(
            f"Pipeline: Work order {work_order.id} created "
            f"(difficulty: {work_order.difficulty}, owner: {work_order.owner})"
        )

        # Step 2: Execute with escalation
        logger.info(f"Pipeline: Starting execution for {work_order.id}")
        escalation_result = self.escalation_mgr.execute_with_escalation(work_order)

        # Step 3: QA validation (using qa/runner.py)
        qa_passed = self._validate_with_qa(escalation_result)

        # Step 4: Build result
        success = escalation_result.status in ("success", "escalated") and qa_passed

        output = ""
        if escalation_result.final_result:
            output = escalation_result.final_result.output

        escalation_info = {
            "status": escalation_result.status,
            "chain": escalation_result.escalation_chain,
            "attempts": escalation_result.attempt_count,
        }

        logger.info(
            f"Pipeline: Completed {work_order.id} - "
            f"success={success}, qa_passed={qa_passed}, "
            f"status={escalation_result.status}"
        )

        return PipelineResult(
            work_order_id=work_order.id,
            success=success,
            output=output,
            qa_passed=qa_passed,
            escalation_info=escalation_info,
            board_notification=escalation_result.board_notification,
        )

    def _validate_with_qa(self, escalation_result: EscalationResult) -> bool:
        """
        Validate result with QA framework.

        For now, this uses the self-test result from the execution agent.
        In the future, this could invoke qa/runner.py with a spec.
        """
        if not escalation_result.final_result:
            return False

        # Use self-test result
        qa_passed = escalation_result.final_result.self_test_passed

        logger.info(
            f"QA validation for {escalation_result.work_order_id}: "
            f"{'PASS' if qa_passed else 'FAIL'}"
        )

        return qa_passed
