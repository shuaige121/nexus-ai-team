#!/usr/bin/env python3
"""Hello World MCP Server — minimal skill example for Nexus."""

import json
import sys
from typing import Any


def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "hello_greet",
                    "description": "Greet someone by name",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Name to greet"}
                        },
                        "required": ["name"],
                    },
                },
                {
                    "name": "hello_echo",
                    "description": "Echo back the input message",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "Message to echo"}
                        },
                        "required": ["message"],
                    },
                },
            ]
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name == "hello_greet":
            name = arguments.get("name", "World")
            return {"content": [{"type": "text", "text": f"Hello, {name}! Welcome to Nexus."}]}

        if tool_name == "hello_echo":
            message = arguments.get("message", "")
            return {"content": [{"type": "text", "text": f"Echo: {message}"}]}

        return {"error": {"code": -1, "message": f"Unknown tool: {tool_name}"}}

    return {"error": {"code": -1, "message": f"Unknown method: {method}"}}


def main() -> None:
    """Run as stdio MCP server — read JSON-RPC from stdin, write to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            response["id"] = request.get("id")
            response["jsonrpc"] = "2.0"
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            error_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
            sys.stdout.write(json.dumps(error_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
