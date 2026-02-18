"""Execution agent - handles work orders and executes tasks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from nexus_v1.admin import WorkOrder
from nexus_v1.config import AgentRole
from nexus_v1.model_router import ModelRouter

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing a work order."""

    work_order_id: str
    agent_role: AgentRole
    success: bool
    output: str
    error: str | None = None
    self_test_passed: bool = False
    model_used: str | None = None
    usage: dict[str, int] | None = None


class ExecutionAgent:
    """
    Execution agent that takes a work order and executes it.

    Each agent (CEO/Director/Intern) uses a different model based on difficulty:
    - CEO: Claude Opus 4.6 (complex tasks)
    - Director: Claude Sonnet 4.5 (normal tasks)
    - Intern: Claude Haiku 3.5 (trivial tasks)
    """

    def __init__(self, router: ModelRouter | None = None) -> None:
        self.router = router or ModelRouter()

    def execute(
        self,
        work_order: WorkOrder,
        *,
        override_role: AgentRole | None = None,
    ) -> ExecutionResult:
        """
        Execute a work order using the appropriate model.

        Args:
            work_order: The work order to execute
            override_role: Optional role override for escalation

        Returns:
            ExecutionResult with output and self-test results
        """
        role = override_role or work_order.owner
        logger.info(
            f"Executing work order {work_order.id} as {role} (difficulty: {work_order.difficulty})"
        )

        # If unclear, return error immediately
        if work_order.difficulty == "unclear" and work_order.clarification_question:
            return ExecutionResult(
                work_order_id=work_order.id,
                agent_role=role,
                success=False,
                output="",
                error=f"Clarification needed: {work_order.clarification_question}",
            )

        try:
            # Execute the task
            execution_output = self._execute_task(work_order, role)

            # Self-test
            self_test_passed = self._self_test(work_order, execution_output, role)

            return ExecutionResult(
                work_order_id=work_order.id,
                agent_role=role,
                success=self_test_passed,
                output=execution_output["output"],
                self_test_passed=self_test_passed,
                model_used=execution_output["model"],
                usage=execution_output.get("usage"),
            )

        except Exception as exc:
            logger.exception(f"Execution failed for {work_order.id}")
            return ExecutionResult(
                work_order_id=work_order.id,
                agent_role=role,
                success=False,
                output="",
                error=f"Execution error: {str(exc)}",
            )

    def _execute_task(
        self,
        work_order: WorkOrder,
        role: AgentRole,
    ) -> dict[str, Any]:
        """Execute the actual task using the LLM."""
        system_prompt = self._build_system_prompt(role, work_order)
        user_prompt = self._build_user_prompt(work_order)

        response = self.router.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            role=role,
            temperature=0.2,
            max_tokens=4096,
        )

        return {
            "output": response.content.strip(),
            "model": response.model,
            "usage": response.usage,
        }

    def _self_test(
        self,
        work_order: WorkOrder,
        execution_output: dict[str, Any],
        role: AgentRole,
    ) -> bool:
        """
        Self-test: ask the agent to verify its own output.

        Returns True if self-test passes, False otherwise.
        """
        output = execution_output["output"]

        # Quick sanity checks
        if not output or len(output.strip()) < 10:
            logger.warning(f"Self-test failed: output too short for {work_order.id}")
            return False

        # LLM-based self-verification
        verification_prompt = f"""You are a quality assurance agent reviewing work output.

Work Order ID: {work_order.id}
Intent: {work_order.intent}
QA Requirements: {work_order.qa_requirements}

Output to verify:
{output}

Does this output meet the QA requirements? Answer with EXACTLY one of:
- PASS: if the output clearly meets all requirements
- FAIL: if the output is incomplete, incorrect, or does not meet requirements

Your answer (PASS or FAIL only):"""

        try:
            response = self.router.chat(
                [{"role": "user", "content": verification_prompt}],
                role=role,
                temperature=0.0,
                max_tokens=50,
            )

            result = response.content.strip().upper()
            passed = "PASS" in result and "FAIL" not in result

            if not passed:
                logger.warning(
                    f"Self-test failed for {work_order.id}: QA verification returned {result}"
                )

            return passed

        except Exception:
            logger.exception(f"Self-test error for {work_order.id}")
            # On error, be conservative and fail the test
            return False

    def _build_system_prompt(self, role: AgentRole, work_order: WorkOrder) -> str:
        """Build system prompt based on role."""
        role_descriptions = {
            "ceo": "You are the CEO of NEXUS, handling complex and critical tasks. You have extensive experience and deep expertise.",
            "director": "You are a Director at NEXUS, handling normal-complexity tasks efficiently and professionally.",
            "intern": "You are an Intern at NEXUS, handling straightforward tasks quickly and correctly.",
        }

        base_prompt = role_descriptions.get(
            role,
            "You are an agent at NEXUS, executing tasks professionally.",
        )

        return f"""{base_prompt}

Your task is classified as: {work_order.difficulty}
Intent: {work_order.intent}

Execute the task according to the requirements. Be concise, accurate, and complete.
If files are referenced, assume they exist in the project context.
"""

    def _build_user_prompt(self, work_order: WorkOrder) -> str:
        """Build user prompt from work order."""
        parts = [
            f"Work Order ID: {work_order.id}",
            f"\n{work_order.compressed_context}",
        ]

        if work_order.relevant_files:
            files_list = ", ".join(work_order.relevant_files)
            parts.append(f"\nRelevant files: {files_list}")

        parts.append(f"\nQA Requirements: {work_order.qa_requirements}")

        if work_order.deadline:
            parts.append(f"\nDeadline: {work_order.deadline}")

        parts.append("\nPlease execute this task:")

        return "\n".join(parts)
