"""Tests for EscalationManager."""

import unittest
from unittest.mock import Mock

from agents.execution.escalation import EscalationManager
from agents.execution.executor import ExecutionAgent, ExecutionResult
from nexus_v1.admin import WorkOrder


class TestEscalationManager(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.mock_executor = Mock(spec=ExecutionAgent)
        self.manager = EscalationManager(executor=self.mock_executor)

    def test_success_on_first_attempt(self):
        """Test successful execution on first attempt (no escalation)."""
        work_order = WorkOrder(
            id="WO-ESC-001",
            intent="build_feature",
            difficulty="trivial",
            owner="intern",
            compressed_context="Simple task",
            relevant_files=[],
            qa_requirements="Must work",
        )

        # Mock successful execution
        self.mock_executor.execute.return_value = ExecutionResult(
            work_order_id="WO-ESC-001",
            agent_role="intern",
            success=True,
            output="Task completed successfully",
            self_test_passed=True,
        )

        result = self.manager.execute_with_escalation(work_order)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.attempt_count, 1)
        self.assertEqual(result.escalation_chain, ["intern"])
        self.assertIsNotNone(result.final_result)
        self.assertTrue(result.final_result.success)

    def test_escalation_intern_to_director(self):
        """Test escalation from Intern to Director."""
        work_order = WorkOrder(
            id="WO-ESC-002",
            intent="build_feature",
            difficulty="trivial",
            owner="intern",
            compressed_context="Moderately complex task",
            relevant_files=[],
            qa_requirements="Must be correct",
        )

        # First attempt (Intern) fails
        intern_result = ExecutionResult(
            work_order_id="WO-ESC-002",
            agent_role="intern",
            success=False,
            output="Incomplete",
            self_test_passed=False,
            error="Failed self-test",
        )

        # Second attempt (Director) succeeds
        director_result = ExecutionResult(
            work_order_id="WO-ESC-002",
            agent_role="director",
            success=True,
            output="Complete and correct solution",
            self_test_passed=True,
        )

        self.mock_executor.execute.side_effect = [intern_result, director_result]

        result = self.manager.execute_with_escalation(work_order)

        self.assertEqual(result.status, "escalated")
        self.assertEqual(result.attempt_count, 2)
        self.assertEqual(result.escalation_chain, ["intern", "director"])
        self.assertTrue(result.final_result.success)
        self.assertEqual(result.final_result.agent_role, "director")

    def test_full_escalation_chain(self):
        """Test full escalation: Intern → Director → CEO."""
        work_order = WorkOrder(
            id="WO-ESC-003",
            intent="build_feature",
            difficulty="normal",
            owner="director",
            compressed_context="Complex task",
            relevant_files=[],
            qa_requirements="Must be perfect",
        )

        # Director fails
        director_result = ExecutionResult(
            work_order_id="WO-ESC-003",
            agent_role="director",
            success=False,
            output="Attempted but failed",
            self_test_passed=False,
        )

        # CEO succeeds
        ceo_result = ExecutionResult(
            work_order_id="WO-ESC-003",
            agent_role="ceo",
            success=True,
            output="Perfect solution from CEO",
            self_test_passed=True,
        )

        self.mock_executor.execute.side_effect = [director_result, ceo_result]

        result = self.manager.execute_with_escalation(work_order)

        self.assertEqual(result.status, "escalated")
        self.assertEqual(result.attempt_count, 2)
        self.assertEqual(result.escalation_chain, ["director", "ceo"])
        self.assertTrue(result.final_result.success)
        self.assertEqual(result.final_result.agent_role, "ceo")

    def test_escalation_to_board(self):
        """Test escalation to Board after 3 failures."""
        work_order = WorkOrder(
            id="WO-ESC-004",
            intent="build_feature",
            difficulty="trivial",
            owner="intern",
            compressed_context="Impossible task",
            relevant_files=[],
            qa_requirements="Cannot be done",
        )

        # All attempts fail
        failed_result = ExecutionResult(
            work_order_id="WO-ESC-004",
            agent_role="intern",
            success=False,
            output="Failed",
            self_test_passed=False,
            error="Task cannot be completed",
        )

        self.mock_executor.execute.return_value = failed_result

        result = self.manager.execute_with_escalation(work_order)

        self.assertEqual(result.status, "needs_board")
        self.assertEqual(result.attempt_count, 3)
        self.assertEqual(len(result.escalation_chain), 3)
        self.assertIn("intern", result.escalation_chain)
        self.assertIn("director", result.escalation_chain)
        self.assertIn("ceo", result.escalation_chain)
        self.assertIsNotNone(result.board_notification)
        self.assertIn("BOARD ESCALATION", result.board_notification)

    def test_unclear_difficulty_skips_execution(self):
        """Test that unclear difficulty requests skip execution."""
        work_order = WorkOrder(
            id="WO-ESC-005",
            intent="general_request",
            difficulty="unclear",
            owner="admin",
            compressed_context="Vague request",
            relevant_files=[],
            qa_requirements="Needs clarification",
            clarification_question="What do you want me to do?",
        )

        result = self.manager.execute_with_escalation(work_order)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.escalation_chain, ["admin"])
        self.assertIsNotNone(result.board_notification)
        self.assertIn("clarification", result.board_notification.lower())
        # Should not call executor for unclear requests
        self.mock_executor.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
