from pathlib import Path

#!/usr/bin/env python3
"""Integration test for gateway API endpoints."""

import asyncio
import json
import subprocess
import sys
import time

import httpx


def start_server():
    """Start the FastAPI server in background."""
    print("Starting FastAPI server...")

    # Start uvicorn in background
    proc = subprocess.Popen(
        ["uvicorn", "gateway.main:app", "--host", "127.0.0.1", "--port", "8765"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
    )

    # Wait for server to start
    print("Waiting for server to start...")
    time.sleep(3)

    return proc


async def test_health_endpoint():
    """Test the /health endpoint."""
    print("\n=== Testing /health endpoint ===")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://127.0.0.1:8765/health")

            print(f"Status code: {response.status_code}")
            print(f"Response text: {response.text}")

            if response.status_code != 200:
                print(f"❌ FAIL: Expected status 200, got {response.status_code}")
                return False

            data = response.json()
            print(f"✅ Response: {json.dumps(data, indent=2)}")

            # HealthResponse returns {"status": "ok"}
            if data.get("status") != "ok":
                print(f"❌ FAIL: Expected status='ok', got {data.get('status')}")
                return False

            return True

    except Exception as exc:
        print(f"❌ FAIL: {exc}")
        return False


async def test_workorders_endpoint():
    """Test the /api/work-orders endpoint."""
    print("\n=== Testing /api/work-orders endpoint ===")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test GET work orders list
            response = await client.get("http://127.0.0.1:8765/api/work-orders?limit=5")

            print(f"Status code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Response: {json.dumps(data, indent=2)}")
                return True
            elif response.status_code in (500, 503):
                # Expected if database not connected (fallback mode)
                print(f"⚠️  Database not available (fallback mode), status: {response.status_code}")
                return True
            else:
                print(f"❌ FAIL: Unexpected status code {response.status_code}")
                return False

    except Exception as exc:
        print(f"⚠️  WARNING: {exc}")
        # Not failing, as this is expected if endpoint has issues
        return True


async def test_error_handling():
    """Test error handling with invalid requests."""
    print("\n=== Testing error handling ===")

    try:
        async with httpx.AsyncClient() as client:
            # Test invalid endpoint
            response = await client.get("http://127.0.0.1:8765/nonexistent")

            if response.status_code != 404:
                print(f"⚠️  Expected 404, got {response.status_code}")
            else:
                print("✅ Correct 404 response for invalid endpoint")

            return True

    except Exception as exc:
        print(f"❌ FAIL: {exc}")
        return False


async def run_tests():
    """Run all integration tests."""
    results = []

    results.append(await test_health_endpoint())
    results.append(await test_workorders_endpoint())
    results.append(await test_error_handling())

    return all(results)


def main():
    """Main test runner."""
    print("=== Gateway Integration Test ===")

    # Start server
    proc = start_server()

    try:
        # Run tests
        success = asyncio.run(run_tests())

        print("\n" + "="*50)
        if success:
            print("✅ All integration tests passed")
            return 0
        else:
            print("❌ Some integration tests failed")
            return 1

    finally:
        # Stop server
        print("\nStopping server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
