"""Tests for ExecutionAgent."""

import unittest
from unittest.mock import MagicMock, Mock

from agents.execution.executor import ExecutionAgent, ExecutionResult
from nexus_v1.admin import WorkOrder
from nexus_v1.model_router import ModelRouter, RouterResponse


class TestExecutionAgent(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.mock_router = Mock(spec=ModelRouter)
        self.agent = ExecutionAgent(router=self.mock_router)

    def test_execute_success(self):
        """Test successful execution with passing self-test."""
        work_order = WorkOrder(
            id="WO-TEST-001",
            intent="build_feature",
            difficulty="normal",
            owner="director",
            compressed_context="Build a simple calculator function",
            relevant_files=["calc.py"],
            qa_requirements="Function must accept two numbers and return their sum",
        )

        # Mock execution response
        execution_response = RouterResponse(
            provider="anthropic",
            model="claude-sonnet-4-5",
            content="Here's a calculator function:\n\ndef add(a, b):\n    return a + b",
            raw=MagicMock(),
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

        # Mock self-test response
        self_test_response = RouterResponse(
            provider="anthropic",
            model="claude-sonnet-4-5",
            content="PASS",
            raw=MagicMock(),
        )

        self.mock_router.chat.side_effect = [execution_response, self_test_response]

        result = self.agent.execute(work_order)

        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.work_order_id, "WO-TEST-001")
        self.assertEqual(result.agent_role, "director")
        self.assertTrue(result.success)
        self.assertTrue(result.self_test_passed)
        self.assertIn("calculator", result.output)
        self.assertEqual(result.model_used, "claude-sonnet-4-5")

    def test_execute_self_test_failure(self):
        """Test execution where self-test fails."""
        work_order = WorkOrder(
            id="WO-TEST-002",
            intent="build_feature",
            difficulty="trivial",
            owner="intern",
            compressed_context="Write hello world",
            relevant_files=[],
            qa_requirements="Must print 'Hello, World!'",
        )

        execution_response = RouterResponse(
            provider="anthropic",
            model="claude-haiku-3-5",
            content="Incomplete output",
            raw=MagicMock(),
        )

        self_test_response = RouterResponse(
            provider="anthropic",
            model="claude-haiku-3-5",
            content="FAIL - output does not meet requirements",
            raw=MagicMock(),
        )

        self.mock_router.chat.side_effect = [execution_response, self_test_response]

        result = self.agent.execute(work_order)

        self.assertFalse(result.success)
        self.assertFalse(result.self_test_passed)

    def test_execute_unclear_difficulty(self):
        """Test execution with unclear difficulty returns error."""
        work_order = WorkOrder(
            id="WO-TEST-003",
            intent="general_request",
            difficulty="unclear",
            owner="admin",
            compressed_context="Do something",
            relevant_files=[],
            qa_requirements="Must be clear",
            clarification_question="What exactly do you want?",
        )

        result = self.agent.execute(work_order)

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIn("Clarification needed", result.error)

    def test_execute_with_override_role(self):
        """Test execution with role override (for escalation)."""
        work_order = WorkOrder(
            id="WO-TEST-004",
            intent="build_feature",
            difficulty="trivial",
            owner="intern",
            compressed_context="Simple task",
            relevant_files=[],
            qa_requirements="Must work",
        )

        execution_response = RouterResponse(
            provider="anthropic",
            model="claude-opus-4-6",
            content="Done correctly",
            raw=MagicMock(),
        )

        self_test_response = RouterResponse(
            provider="anthropic",
            model="claude-opus-4-6",
            content="PASS",
            raw=MagicMock(),
        )

        self.mock_router.chat.side_effect = [execution_response, self_test_response]

        result = self.agent.execute(work_order, override_role="ceo")

        self.assertEqual(result.agent_role, "ceo")
        self.assertTrue(result.success)

    def test_execute_exception_handling(self):
        """Test that exceptions are caught and returned as errors."""
        work_order = WorkOrder(
            id="WO-TEST-005",
            intent="build_feature",
            difficulty="normal",
            owner="director",
            compressed_context="Test exception",
            relevant_files=[],
            qa_requirements="Must handle errors",
        )

        self.mock_router.chat.side_effect = RuntimeError("API error")

        result = self.agent.execute(work_order)

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIn("Execution error", result.error)
        self.assertIn("API error", result.error)


if __name__ == "__main__":
    unittest.main()
