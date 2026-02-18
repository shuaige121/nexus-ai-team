#!/usr/bin/env python3
"""Simple gateway startup test without external dependencies."""

import subprocess
import sys
import time

import httpx


def test_gateway_startup():
    """Test that gateway can start and respond to basic health check."""
    print("=== Testing Gateway Startup ===\n")

    # Start server with minimal config (no Redis/PostgreSQL required)
    print("Starting FastAPI server...")
    proc = subprocess.Popen(
        ["uvicorn", "gateway.main:app", "--host", "127.0.0.1", "--port", "8766"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd="/home/leonard/Desktop/nexus-ai-team",
    )

    # Wait for startup
    time.sleep(4)

    try:
        # Check if process is still running
        if proc.poll() is not None:
            print("❌ Server failed to start")
            stdout, _ = proc.communicate()
            print("Server output:")
            print(stdout)
            return False

        # Try to connect
        print("Testing connection...")
        try:
            response = httpx.get("http://127.0.0.1:8766/health", timeout=5.0)
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.json()}")

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    print("\n✅ Gateway started successfully and health check passed")
                    return True
                else:
                    print(f"\n❌ Unexpected health response: {data}")
                    return False
            else:
                print(f"\n❌ Health check failed with status {response.status_code}")
                return False

        except httpx.ConnectError:
            print("\n❌ Could not connect to server")
            return False
        except Exception as exc:
            print(f"\n❌ Error during health check: {exc}")
            return False

    finally:
        # Cleanup
        print("\nStopping server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    success = test_gateway_startup()
    sys.exit(0 if success else 1)
