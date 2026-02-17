"""Tests for ExecutionPipeline."""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from agents.execution.escalation import EscalationManager, EscalationResult
from agents.execution.executor import ExecutionResult
from agents.execution.pipeline import ExecutionPipeline, PipelineResult
from nexus_v1.admin import AdminAgent, WorkOrder


class TestExecutionPipeline(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.mock_admin = Mock(spec=AdminAgent)
        self.mock_escalation = Mock(spec=EscalationManager)
        self.pipeline = ExecutionPipeline(
            admin=self.mock_admin,
            escalation_mgr=self.mock_escalation,
        )

    def test_successful_pipeline(self):
        """Test complete successful pipeline execution."""
        # Mock work order creation
        work_order = WorkOrder(
            id="WO-PIPE-001",
            intent="build_feature",
            difficulty="normal",
            owner="director",
            compressed_context="Build calculator",
            relevant_files=["calc.py"],
            qa_requirements="Must work correctly",
        )
        self.mock_admin.create_work_order.return_value = work_order

        # Mock successful escalation
        escalation_result = EscalationResult(
            work_order_id="WO-PIPE-001",
            status="success",
            final_result=ExecutionResult(
                work_order_id="WO-PIPE-001",
                agent_role="director",
                success=True,
                output="Calculator implemented successfully",
                self_test_passed=True,
            ),
            escalation_chain=["director"],
            attempt_count=1,
        )
        self.mock_escalation.execute_with_escalation.return_value = escalation_result

        # Run pipeline
        result = asyncio.run(self.pipeline.process("Build a calculator"))

        self.assertIsInstance(result, PipelineResult)
        self.assertEqual(result.work_order_id, "WO-PIPE-001")
        self.assertTrue(result.success)
        self.assertTrue(result.qa_passed)
        self.assertIn("Calculator", result.output)
        self.assertEqual(result.escalation_info["status"], "success")
        self.assertEqual(result.escalation_info["attempts"], 1)

    def test_pipeline_with_escalation(self):
        """Test pipeline with escalation from Intern to Director."""
        work_order = WorkOrder(
            id="WO-PIPE-002",
            intent="build_feature",
            difficulty="trivial",
            owner="intern",
            compressed_context="Simple task",
            relevant_files=[],
            qa_requirements="Must be correct",
        )
        self.mock_admin.create_work_order.return_value = work_order

        # Mock escalation (2 attempts)
        escalation_result = EscalationResult(
            work_order_id="WO-PIPE-002",
            status="escalated",
            final_result=ExecutionResult(
                work_order_id="WO-PIPE-002",
                agent_role="director",
                success=True,
                output="Task completed after escalation",
                self_test_passed=True,
            ),
            escalation_chain=["intern", "director"],
            attempt_count=2,
        )
        self.mock_escalation.execute_with_escalation.return_value = escalation_result

        result = asyncio.run(self.pipeline.process("Do simple task"))

        self.assertTrue(result.success)
        self.assertEqual(result.escalation_info["status"], "escalated")
        self.assertEqual(result.escalation_info["attempts"], 2)

    def test_pipeline_board_escalation(self):
        """Test pipeline when all attempts fail and Board intervention needed."""
        work_order = WorkOrder(
            id="WO-PIPE-003",
            intent="build_feature",
            difficulty="complex",
            owner="ceo",
            compressed_context="Very hard task",
            relevant_files=[],
            qa_requirements="Impossible",
        )
        self.mock_admin.create_work_order.return_value = work_order

        # Mock all failures
        escalation_result = EscalationResult(
            work_order_id="WO-PIPE-003",
            status="needs_board",
            final_result=ExecutionResult(
                work_order_id="WO-PIPE-003",
                agent_role="ceo",
                success=False,
                output="Failed attempt",
                self_test_passed=False,
                error="Task too complex",
            ),
            escalation_chain=["ceo"],
            attempt_count=3,
            board_notification="Board intervention required for WO-PIPE-003",
        )
        self.mock_escalation.execute_with_escalation.return_value = escalation_result

        result = asyncio.run(self.pipeline.process("Do impossible task"))

        self.assertFalse(result.success)
        self.assertFalse(result.qa_passed)
        self.assertEqual(result.escalation_info["status"], "needs_board")
        self.assertIsNotNone(result.board_notification)
        self.assertIn("Board intervention", result.board_notification)

    def test_pipeline_with_conversation_history(self):
        """Test pipeline with conversation history passed to admin."""
        conversation = [
            {"role": "user", "content": "I need help"},
            {"role": "assistant", "content": "Sure, what do you need?"},
        ]

        work_order = WorkOrder(
            id="WO-PIPE-004",
            intent="general_request",
            difficulty="normal",
            owner="director",
            compressed_context="User needs help with context",
            relevant_files=[],
            qa_requirements="Must be helpful",
        )
        self.mock_admin.create_work_order.return_value = work_order

        escalation_result = EscalationResult(
            work_order_id="WO-PIPE-004",
            status="success",
            final_result=ExecutionResult(
                work_order_id="WO-PIPE-004",
                agent_role="director",
                success=True,
                output="Help provided",
                self_test_passed=True,
            ),
            escalation_chain=["director"],
            attempt_count=1,
        )
        self.mock_escalation.execute_with_escalation.return_value = escalation_result

        result = asyncio.run(
            self.pipeline.process("Build something", conversation=conversation)
        )

        # Verify admin was called with conversation
        self.mock_admin.create_work_order.assert_called_once()
        call_args = self.mock_admin.create_work_order.call_args
        self.assertEqual(call_args[0][1], conversation)


if __name__ == "__main__":
    unittest.main()
