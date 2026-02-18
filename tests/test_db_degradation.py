#!/usr/bin/env python3
"""Test database graceful degradation."""

import os
import sys
from datetime import datetime
from pathlib import Path

# Remove DATABASE_URL to test fallback
if "DATABASE_URL" in os.environ:
    del os.environ["DATABASE_URL"]

# Import after removing env var
from db.client import DatabaseClient, WorkOrderLog, AgentMetric, AuditLog

def test_sqlite_fallback():
    """Test that database client falls back to SQLite when PostgreSQL is unavailable."""
    print("Testing database graceful degradation...")

    # Use a test database file
    test_db = Path("/tmp/nexus_test.db")
    if test_db.exists():
        test_db.unlink()

    # Create client without PostgreSQL
    db = DatabaseClient(postgres_url=None, sqlite_path=test_db)

    # Verify SQLite is being used
    if db._use_postgres:
        print("FAIL: Expected SQLite fallback, but using PostgreSQL")
        return False

    print(f"SUCCESS: Using SQLite at {test_db}")

    # Test work order logging
    work_order = WorkOrderLog(
        id="test-wo-001",
        intent="Test work order",
        difficulty="trivial",
        owner="admin",
        compressed_context="Test context",
        relevant_files=["test.py"],
        qa_requirements="Basic validation",
        status="queued",
    )

    try:
        db.log_work_order(work_order)
        print("SUCCESS: Work order logged to SQLite")
    except Exception as exc:
        print(f"FAIL: Failed to log work order: {exc}")
        return False

    # Test agent metrics logging
    metric = AgentMetric(
        work_order_id="test-wo-001",
        session_id="test-session-001",
        agent_name="test-agent",
        role="admin",
        model="gpt-4",
        provider="openai",
        success=True,
        latency_ms=250,
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.01,
    )

    try:
        db.log_agent_metric(metric)
        print("SUCCESS: Agent metric logged to SQLite")
    except Exception as exc:
        print(f"FAIL: Failed to log metric: {exc}")
        return False

    # Test audit logging
    audit = AuditLog(
        work_order_id="test-wo-001",
        session_id="test-session-001",
        actor="qa_tester",
        action="test_db_degradation",
        status="success",
        details={"test": "degradation"},
    )

    try:
        db.log_audit(audit)
        print("SUCCESS: Audit log entry created")
    except Exception as exc:
        print(f"FAIL: Failed to log audit: {exc}")
        return False

    # Test query metrics
    try:
        metrics = db.query_metrics(limit=10)
        if len(metrics) == 0:
            print("FAIL: Expected to find metrics in database")
            return False
        print(f"SUCCESS: Retrieved {len(metrics)} metrics from SQLite")
    except Exception as exc:
        print(f"FAIL: Failed to query metrics: {exc}")
        return False

    # Verify database file was created
    if not test_db.exists():
        print("FAIL: SQLite database file was not created")
        return False

    print(f"SUCCESS: SQLite database file created at {test_db}")

    db.close()

    # Cleanup
    if test_db.exists():
        test_db.unlink()

    return True

if __name__ == "__main__":
    success = test_sqlite_fallback()
    sys.exit(0 if success else 1)
