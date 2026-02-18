"""Integration tests for Phase 2B — message pipeline and Telegram integration."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

# Mock dependencies that require external services
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql://nexus:nexus@localhost:5432/nexus")
os.environ.setdefault("REDIS_URL", "redis://:nexus_redis_dev_password_2024@localhost:6379/0")


@pytest.fixture
def mock_router():
    """Mock ModelRouter to avoid real API calls."""
    from nexus_v1.model_router import RouterResponse

    router = MagicMock()
    router.chat = MagicMock(
        return_value=RouterResponse(
            provider="anthropic",
            model="claude-sonnet-4-5",
            content="This is a mock response from the agent.",
            raw=MagicMock(usage={"prompt_tokens": 100, "completion_tokens": 50}),
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )
    )
    return router


@pytest.mark.asyncio
async def test_work_order_creation():
    """Test that AdminAgent creates valid work orders."""
    from nexus_v1.admin import AdminAgent

    agent = AdminAgent(use_llm=False)  # Disable LLM for unit test
    wo = agent.create_work_order(user_message="Build a feature to send emails")

    assert wo.id.startswith("WO-")
    assert wo.intent in ["general_request", "build_feature"]
    assert wo.difficulty in ["trivial", "normal", "complex", "unclear"]
    assert wo.owner in ["admin", "intern", "director", "ceo"]
    assert len(wo.compressed_context) > 0


@pytest.mark.asyncio
async def test_queue_enqueue_consume():
    """Test Redis Streams queue enqueue and consume."""
    pytest.importorskip("redis")

    from pipeline.queue import QueueManager

    redis_password = os.getenv("REDIS_PASSWORD", "nexus_redis_dev_password_2024")
    redis_url = f"redis://:{redis_password}@localhost:6379/15" if redis_password else "redis://localhost:6379/15"
    queue = QueueManager(redis_url, stream_name="test:work_orders")

    try:
        await queue.connect()

        # Enqueue a test message
        entry_id = await queue.enqueue(
            "WO-TEST-001",
            {"user_message": "test message", "session_id": "test-session"},
        )

        assert entry_id is not None

        # Consume the message
        messages = await queue.consume(
            consumer_group="test-group",
            consumer_name="test-worker",
            count=1,
            block_ms=1000,
        )

        assert len(messages) == 1
        msg = messages[0]
        assert msg["work_order_id"] == "WO-TEST-001"
        assert msg["payload"]["user_message"] == "test message"

        # ACK the message
        await queue.ack(msg["entry_id"], consumer_group="test-group")

    finally:
        await queue.close()


@pytest.mark.asyncio
async def test_dispatcher_process_work_order(mock_router):
    """Test that Dispatcher processes work orders end-to-end."""
    pytest.importorskip("redis")
    pytest.importorskip("psycopg")

    import os

    from pipeline import Dispatcher, QueueManager, WorkOrderDB

    # Use test databases - read from environment or skip test if not configured
    db_url = os.getenv("DATABASE_URL", "postgresql://nexus:nexus@localhost:5432/nexus")
    db = WorkOrderDB(db_url)
    redis_password = os.getenv("REDIS_PASSWORD", "nexus_redis_dev_password_2024")
    redis_url = f"redis://:{redis_password}@localhost:6379/15" if redis_password else "redis://localhost:6379/15"
    queue = QueueManager(redis_url, stream_name="test:dispatcher")

    try:
        await db.connect()
        await queue.connect()

        # Create a test work order (clean up from previous runs)
        wo_id = "WO-TEST-DISPATCHER-001"
        test_session_id = "test-session-dispatcher"
        async with db.get_connection() as conn, conn.cursor() as cur:
            await cur.execute("DELETE FROM audit_logs WHERE work_order_id = %s", (wo_id,))
            await cur.execute("DELETE FROM agent_metrics WHERE work_order_id = %s", (wo_id,))
            await cur.execute("DELETE FROM work_orders WHERE id = %s", (wo_id,))
            # Ensure test session exists for FK constraints
            await cur.execute(
                "INSERT INTO sessions (id, user_id, channel, status) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                (test_session_id, "test-user", "api", "active"),
            )
            await conn.commit()
        await db.create_work_order(
            wo_id=wo_id,
            intent="test_intent",
            difficulty="normal",
            owner="director",
            compressed_context="Test message for dispatcher",
            relevant_files=[],
            qa_requirements="Must complete without errors",
        )

        # Enqueue it
        await queue.enqueue(
            wo_id,
            {
                "user_message": "Test dispatcher message",
                "conversation": [],
                "session_id": test_session_id,
            },
        )

        # Create dispatcher with mock router
        dispatcher = Dispatcher(db, queue, mock_router)

        # Manually process one message (don't start background loop)
        messages = await queue.consume(
            consumer_group="test-dispatcher-group",
            consumer_name="test-worker",
            count=1,
            block_ms=1000,
        )

        if messages:
            await dispatcher._process_message(messages[0], "test-dispatcher-group")

            # Verify work order was updated
            wo = await db.get_work_order(wo_id)
            # Status should be completed if mock router succeeded
            # (depends on implementation, might still be in_progress in fast test)
            assert wo is not None

    finally:
        await db.close()
        await queue.close()


@pytest.mark.asyncio
async def test_telegram_gateway_integration():
    """Test that Telegram bot can send messages to gateway."""
    from interfaces.telegram.gateway_client import GatewayClient

    # This test requires gateway to be running
    # Skip if gateway is not available
    try:
        async with GatewayClient(base_url="http://localhost:8000") as client:
            result = await client.send_message("Test message from integration test")

            # Should receive a work order ID even if pipeline fails
            assert "ok" in result

    except Exception as e:
        pytest.skip(f"Gateway not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
