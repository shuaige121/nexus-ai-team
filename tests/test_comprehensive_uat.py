#!/usr/bin/env python3
"""Comprehensive UAT for Phase 3B: QA Pipeline + PostgreSQL Logging."""

import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def run_test(name: str, command: list[str], expected_exit_code: int = 0) -> tuple[bool, str]:
    """Run a test command and return success status."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/home/leonard/Desktop/nexus-ai-team",
        )

        print(f"Exit code: {result.returncode}")
        if result.stdout:
            print("STDOUT:")
            print(result.stdout[:500])
        if result.stderr:
            print("STDERR:")
            print(result.stderr[:500])

        success = result.returncode == expected_exit_code
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"\n{status}")

        return success, result.stdout + result.stderr

    except subprocess.TimeoutExpired:
        print("\n❌ FAIL: Test timed out")
        return False, "Timeout"
    except Exception as exc:
        print(f"\n❌ FAIL: {exc}")
        return False, str(exc)


def main():
    """Run comprehensive UAT tests."""
    print("="*60)
    print("NEXUS Phase 3B — Comprehensive UAT")
    print("="*60)
    print(f"Start time: {datetime.now().isoformat()}")
    print()

    results = {}
    failures = []

    # Test 1: QA Pipeline - Valid Work Order
    success, output = run_test(
        "QA Pipeline: Valid Work Order (PASS Expected)",
        ["python3", "qa/runner.py", "--spec", "qa/specs/sample_success.json"],
        expected_exit_code=0,
    )
    results["qa_valid"] = success
    if not success:
        failures.append("QA Pipeline failed for valid work order")

    # Test 2: QA Pipeline - Defective Work Order
    success, output = run_test(
        "QA Pipeline: Defective Work Order (FAIL Expected)",
        ["python3", "qa/runner.py", "--spec", "qa/specs/test_failure.json"],
        expected_exit_code=1,
    )
    results["qa_defective"] = success
    if not success:
        failures.append("QA Pipeline did not correctly detect failure")

    # Test 3: QA Pipeline - Security Validation
    success, output = run_test(
        "QA Pipeline: Security Validation",
        ["python3", "qa/runner.py", "--spec", "qa/specs/security_check.json"],
        expected_exit_code=0,
    )
    results["qa_security"] = success
    if not success:
        failures.append("QA security validation failed")

    # Test 4: QA Pipeline - Work Order Response Format
    success, output = run_test(
        "QA Pipeline: Work Order Response Format Validation",
        ["python3", "qa/runner.py", "--spec", "qa/specs/work_order_response.json"],
        expected_exit_code=0,
    )
    results["qa_format"] = success
    if not success:
        failures.append("QA format validation failed")

    # Test 5: Database Graceful Degradation
    success, output = run_test(
        "Database: Graceful Degradation to SQLite",
        ["python3", "test_db_degradation.py"],
        expected_exit_code=0,
    )
    results["db_degradation"] = success
    if not success:
        failures.append("Database degradation to SQLite failed")

    # Test 6: QA with Database Logging
    success, output = run_test(
        "QA Pipeline: Database Logging Integration",
        ["python3", "qa/runner.py", "--spec", "qa/specs/sample_success.json",
         "--log-to-db", "--work-order-id", "uat-final-test"],
        expected_exit_code=0,
    )
    results["qa_db_logging"] = success
    if not success:
        failures.append("QA database logging integration failed")
    elif "logged to database" not in output:
        failures.append("QA database logging did not confirm write")
        results["qa_db_logging"] = False

    # Test 7: Security Audit - SQL Injection Check
    success, output = run_test(
        "Security: SQL Injection & Validation Bypass Check",
        ["python3", "test_security_audit.py"],
        expected_exit_code=0,
    )
    results["security_audit"] = success
    if not success:
        failures.append("Security audit detected vulnerabilities")

    # Test 8: Gateway Startup
    success, output = run_test(
        "Gateway: Service Startup & Health Check",
        ["python3", "test_gateway_simple.py"],
        expected_exit_code=0,
    )
    results["gateway_startup"] = success
    if not success:
        failures.append("Gateway failed to start or health check failed")

    # Final Report
    print("\n" + "="*60)
    print("FINAL UAT REPORT")
    print("="*60)

    total_tests = len(results)
    passed_tests = sum(results.values())

    print(f"\nTotal tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")

    print("\nDetailed Results:")
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} {test_name}")

    print(f"\nEnd time: {datetime.now().isoformat()}")

    # Determine final result
    if not failures:
        print("\n" + "="*60)
        print("UAT_RESULT:PASS")
        print("="*60)
        return 0
    else:
        print("\n" + "="*60)
        print("UAT_RESULT:FAIL:" + ";".join(failures))
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
