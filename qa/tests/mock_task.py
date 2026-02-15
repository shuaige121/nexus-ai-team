#!/usr/bin/env python3
"""Mock task used by QA specs for smoke testing the validator."""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail", action="store_true", help="Return a non-zero exit code.")
    parser.add_argument("--bad-json", action="store_true", help="Emit invalid JSON.")
    args = parser.parse_args()

    if args.bad_json:
        print("{status:ok")
    else:
        result = {
            "status": "ok", "result": "mock-complete",
            "checks": ["run", "complete", "format"],
        }
        print(json.dumps(result))

    if args.fail:
        print("forced failure", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
