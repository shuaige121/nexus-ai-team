"""Integration test for Phase 2A - Complete execution flow."""

import unittest
from unittest.mock import Mock

from agents.execution.escalation import EscalationManager
from agents.execution.executor import ExecutionAgent, ExecutionResult
from agents.execution.pipeline import ExecutionPipeline
from nexus_v1.admin import AdminAgent, WorkOrder


class TestPhase2AIntegration(unittest.TestCase):
    """
    Integration test covering the complete Phase 2A flow:
    User message → Admin → Route → Execute → Escalate → QA → Return
    """

    def test_complete_flow_success_no_escalation(self):
        """Test complete flow with successful execution (no escalation needed)."""
        # Create mocks
        mock_admin = Mock(spec=AdminAgent)
        mock_executor = Mock(spec=ExecutionAgent)
        mock_escalation = EscalationManager(executor=mock_executor)

        # Mock work order
        work_order = WorkOrder(
            id="WO-INT-001",
            intent="build_feature",
            difficulty="normal",
            owner="director",
            compressed_context="Build a function that adds two numbers",
            relevant_files=[],
            qa_requirements="Must return correct sum",
        )
        mock_admin.create_work_order.return_value = work_order

        # Mock successful execution
        mock_executor.execute.return_value = ExecutionResult(
            work_order_id="WO-INT-001",
            agent_role="director",
            success=True,
            output="def add(a, b):\n    return a + b",
            self_test_passed=True,
            model_used="claude-sonnet-4-5",
        )

        import asyncio

        pipeline = ExecutionPipeline(admin=mock_admin, escalation_mgr=mock_escalation)
        result = asyncio.run(pipeline.process("Write a function to add two numbers"))

        self.assertTrue(result.success)
        self.assertTrue(result.qa_passed)
        self.assertIn("add", result.output)
        self.assertEqual(result.escalation_info["status"], "success")
        self.assertEqual(result.escalation_info["attempts"], 1)

    def test_complete_flow_with_escalation(self):
        """Test complete flow with escalation from Intern to Director."""
        mock_admin = Mock(spec=AdminAgent)
        mock_executor = Mock(spec=ExecutionAgent)
        mock_escalation = EscalationManager(executor=mock_executor)

        # Mock work order (trivial difficulty)
        work_order = WorkOrder(
            id="WO-INT-002",
            intent="build_feature",
            difficulty="trivial",
            owner="intern",
            compressed_context="Simple greeting function",
            relevant_files=[],
            qa_requirements="Must print greeting",
        )
        mock_admin.create_work_order.return_value = work_order

        # Intern fails, then Director succeeds
        intern_fail = ExecutionResult(
            work_order_id="WO-INT-002",
            agent_role="intern",
            success=False,
            output="print hello",
            self_test_passed=False,
            error="Failed self-test",
        )

        director_success = ExecutionResult(
            work_order_id="WO-INT-002",
            agent_role="director",
            success=True,
            output='def greet(name):\n    print(f"Hello, {name}!")',
            self_test_passed=True,
        )

        mock_executor.execute.side_effect = [intern_fail, director_success]

        import asyncio

        pipeline = ExecutionPipeline(admin=mock_admin, escalation_mgr=mock_escalation)
        result = asyncio.run(pipeline.process("Create a greeting function"))

        self.assertTrue(result.success)
        self.assertTrue(result.qa_passed)
        self.assertEqual(result.escalation_info["status"], "escalated")
        self.assertEqual(result.escalation_info["attempts"], 2)
        self.assertIn("intern", result.escalation_info["chain"])
        self.assertIn("director", result.escalation_info["chain"])

    def test_complete_flow_board_escalation(self):
        """Test complete flow ending in Board escalation after all failures."""
        mock_admin = Mock(spec=AdminAgent)
        mock_executor = Mock(spec=ExecutionAgent)
        mock_escalation = EscalationManager(executor=mock_executor)

        # Mock work order - start with TRIVIAL so it goes through full chain
        work_order = WorkOrder(
            id="WO-INT-003",
            intent="build_feature",
            difficulty="trivial",
            owner="intern",
            compressed_context="Difficult task misclassified as trivial",
            relevant_files=[],
            qa_requirements="Must be correct",
        )
        mock_admin.create_work_order.return_value = work_order

        # All attempts fail (intern, director, ceo)
        fail_result = ExecutionResult(
            work_order_id="WO-INT-003",
            agent_role="intern",
            success=False,
            output="Attempted but cannot complete",
            self_test_passed=False,
            error="Task too complex",
        )

        # Return same failure for all 3 attempts
        mock_executor.execute.return_value = fail_result

        import asyncio

        pipeline = ExecutionPipeline(admin=mock_admin, escalation_mgr=mock_escalation)
        result = asyncio.run(
            pipeline.process("Implement a quantum entanglement algorithm")
        )

        self.assertFalse(result.success)
        self.assertFalse(result.qa_passed)
        self.assertEqual(result.escalation_info["status"], "needs_board")
        self.assertEqual(result.escalation_info["attempts"], 3)
        self.assertIsNotNone(result.board_notification)
        self.assertIn("BOARD ESCALATION", result.board_notification)


if __name__ == "__main__":
    unittest.main()
