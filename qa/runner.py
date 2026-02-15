#!/usr/bin/env python3
"""Simple QA validation runner for NEXUS work outputs."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


@dataclass
class RunReport:
    spec_name: str
    command: str
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    checks: list[CheckResult]
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["passed"] = self.passed
        return payload


def _load_spec(spec_path: Path) -> dict[str, Any]:
    try:
        return json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in spec: {spec_path} ({exc})") from exc


def _read_source(source: str, stdout: str, stderr: str) -> str:
    if source == "stdout":
        return stdout
    if source == "stderr":
        return stderr
    return f"{stdout}\n{stderr}".strip()


def _check_runnable(spec: dict[str, Any], exit_code: int | None, timed_out: bool) -> CheckResult:
    expected_exit_code = int(spec.get("expected_exit_code", 0))

    if timed_out:
        return CheckResult(
            name="runnable",
            passed=False,
            details="Command timed out before completion.",
        )

    if exit_code != expected_exit_code:
        return CheckResult(
            name="runnable",
            passed=False,
            details=f"Exit code {exit_code} does not match expected {expected_exit_code}.",
        )

    return CheckResult(name="runnable", passed=True, details="Command exited as expected.")


def _check_completeness(spec: dict[str, Any], stdout: str, stderr: str) -> CheckResult:
    config = spec.get("completeness", {})
    source = config.get("source", "combined")
    content = _read_source(source, stdout, stderr)

    required_substrings = config.get("required_substrings", [])
    forbidden_substrings = config.get("forbidden_substrings", [])
    required_regex = config.get("required_regex", [])

    missing = [item for item in required_substrings if item not in content]
    forbidden_hits = [item for item in forbidden_substrings if item in content]

    missing_regex = []
    for pattern in required_regex:
        if not re.search(pattern, content, flags=re.MULTILINE):
            missing_regex.append(pattern)

    details: list[str] = []

    if missing:
        details.append(f"Missing required substrings: {missing}")
    if forbidden_hits:
        details.append(f"Found forbidden substrings: {forbidden_hits}")
    if missing_regex:
        details.append(f"Missing required regex patterns: {missing_regex}")

    if details:
        return CheckResult(name="completeness", passed=False, details="; ".join(details))

    return CheckResult(
        name="completeness", passed=True,
        details="Output completeness checks passed.",
    )


def _walk_json_path(payload: Any, dotted_path: str) -> bool:
    current = payload
    for part in dotted_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return False
    return True


def _check_format(spec: dict[str, Any], stdout: str, stderr: str) -> CheckResult:
    config = spec.get("format", {})
    if not config:
        return CheckResult(name="format", passed=True, details="No format checks configured.")

    fmt_type = config.get("type", "none")
    source = config.get("source", "stdout")
    content = _read_source(source, stdout, stderr).strip()

    if fmt_type == "none":
        return CheckResult(name="format", passed=True, details="Format checks skipped.")

    if fmt_type == "regex":
        pattern = config.get("pattern")
        if not pattern:
            return CheckResult(name="format", passed=False, details="Regex pattern is required.")
        if not re.search(pattern, content, flags=re.MULTILINE):
            return CheckResult(
                name="format",
                passed=False,
                details=f"Output does not match regex pattern: {pattern}",
            )
        return CheckResult(name="format", passed=True, details="Regex format check passed.")

    if fmt_type == "json":
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            return CheckResult(
                name="format", passed=False,
                details=f"Output is not valid JSON: {exc}",
            )

        required_keys = config.get("required_keys", [])
        missing_keys = [
            key for key in required_keys
            if not isinstance(payload, dict) or key not in payload
        ]

        required_paths = config.get("required_paths", [])
        missing_paths = [path for path in required_paths if not _walk_json_path(payload, path)]

        problems: list[str] = []
        if missing_keys:
            problems.append(f"Missing required keys: {missing_keys}")
        if missing_paths:
            problems.append(f"Missing required paths: {missing_paths}")

        if problems:
            return CheckResult(name="format", passed=False, details="; ".join(problems))

        return CheckResult(name="format", passed=True, details="JSON format check passed.")

    return CheckResult(
        name="format",
        passed=False,
        details=f"Unsupported format type: {fmt_type}.",
    )


def run_spec(spec_path: Path) -> RunReport:
    spec = _load_spec(spec_path)
    spec_name = spec.get("name", spec_path.stem)
    command = spec["command"]
    timeout_seconds = int(spec.get("timeout_seconds", 60))
    use_shell = bool(spec.get("use_shell", False))

    start = time.perf_counter()

    try:
        process = subprocess.run(
            command if use_shell else shlex.split(command),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=use_shell,
        )
        stdout = process.stdout
        stderr = process.stderr
        exit_code = process.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        exit_code = None
        timed_out = True

    duration_ms = int((time.perf_counter() - start) * 1000)

    checks = [
        _check_runnable(spec, exit_code, timed_out),
        _check_completeness(spec, stdout, stderr),
        _check_format(spec, stdout, stderr),
    ]

    return RunReport(
        spec_name=spec_name,
        command=command,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_ms=duration_ms,
        checks=checks,
        stdout=stdout,
        stderr=stderr,
    )


def _print_report(report: RunReport, show_output: bool) -> None:
    print(f"Spec: {report.spec_name}")
    print(f"Command: {report.command}")
    print(f"Duration: {report.duration_ms}ms")
    print(f"Exit code: {report.exit_code}")
    print(f"Timed out: {report.timed_out}")

    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"[{status}] {check.name}: {check.details}")

    print(f"Overall: {'PASS' if report.passed else 'FAIL'}")

    if show_output or not report.passed:
        print("\n--- stdout ---")
        print(report.stdout.strip())
        print("--- stderr ---")
        print(report.stderr.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NEXUS QA checks from a JSON spec.")
    parser.add_argument("--spec", required=True, help="Path to the QA spec JSON file.")
    parser.add_argument(
        "--report-json",
        help="Optional output path for machine-readable JSON report.",
    )
    parser.add_argument(
        "--show-output",
        action="store_true",
        help="Always print captured stdout/stderr.",
    )

    args = parser.parse_args()
    spec_path = Path(args.spec)

    if not spec_path.exists():
        print(f"Spec file not found: {spec_path}", file=sys.stderr)
        return 2

    try:
        report = run_spec(spec_path)
    except (ValueError, KeyError) as exc:
        print(f"Spec error: {exc}", file=sys.stderr)
        return 2

    _print_report(report, show_output=args.show_output)

    if args.report_json:
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
