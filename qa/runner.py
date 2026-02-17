#!/usr/bin/env python3
"""Enhanced QA validation runner for NEXUS work outputs with security and code execution checks."""

from __future__ import annotations

import argparse
import ast
import json
import re
import shlex
import subprocess
import sys
import tempfile
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
    qa_result_logged: bool = False

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


def _check_security(spec: dict[str, Any], stdout: str, stderr: str) -> CheckResult:
    """Check for security issues like sensitive information leakage."""
    config = spec.get("security", {})
    if not config.get("enabled", False):
        return CheckResult(name="security", passed=True, details="Security checks disabled.")

    source = config.get("source", "combined")
    content = _read_source(source, stdout, stderr)

    # Patterns to detect sensitive information
    sensitive_patterns = [
        (r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[\w@#$%^&*]+", "password"),
        (r"(?i)(api[_-]?key|apikey|access[_-]?token)\s*[:=]\s*['\"]?[\w-]+", "API key"),
        (r"(?i)(secret|private[_-]?key)\s*[:=]\s*['\"]?[\w-]+", "secret/private key"),
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "email address"),
        (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "IP address"),
        (r"(?i)(bearer|authorization)\s+[\w-]+", "authorization token"),
    ]

    # Additional custom patterns from spec
    custom_patterns = config.get("forbidden_patterns", [])
    for pattern in custom_patterns:
        sensitive_patterns.append((pattern, "custom pattern"))

    findings: list[str] = []
    for pattern, description in sensitive_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            findings.append(f"{description} detected: {match.group()[:50]}...")

    # Check for empty/placeholder values if configured
    if config.get("check_placeholders", True):
        placeholder_patterns = [
            r"(?i)(TODO|FIXME|XXX|PLACEHOLDER|CHANGEME)",
            r"<[^>]+>",  # HTML-like placeholders
            r"\{\{[^}]+\}\}",  # Template placeholders
        ]
        for pattern in placeholder_patterns:
            if re.search(pattern, content):
                findings.append(f"Placeholder or TODO marker found: {pattern}")

    if findings:
        return CheckResult(
            name="security",
            passed=False,
            details=f"Security issues detected: {'; '.join(findings[:5])}",  # Limit to first 5
        )

    return CheckResult(name="security", passed=True, details="No security issues detected.")


def _check_code_execution(spec: dict[str, Any], stdout: str, stderr: str) -> CheckResult:
    """Validate code snippets by attempting to parse/execute them."""
    config = spec.get("code_execution", {})
    if not config.get("enabled", False):
        return CheckResult(name="code_execution", passed=True, details="Code execution checks disabled.")

    source = config.get("source", "stdout")
    content = _read_source(source, stdout, stderr).strip()
    language = config.get("language", "python")

    if language == "python":
        # Try to extract Python code blocks
        code_blocks = re.findall(r"```python\n(.*?)```", content, re.DOTALL)
        if not code_blocks:
            # Try to parse entire content as Python
            code_blocks = [content]

        errors: list[str] = []
        for i, code in enumerate(code_blocks):
            try:
                ast.parse(code)
            except SyntaxError as exc:
                errors.append(f"Block {i+1}: Syntax error at line {exc.lineno}: {exc.msg}")
            except Exception as exc:
                errors.append(f"Block {i+1}: Parse error: {exc}")

        if errors:
            return CheckResult(
                name="code_execution",
                passed=False,
                details=f"Python code validation failed: {'; '.join(errors)}",
            )

        # Optional: try to execute in sandbox if configured
        if config.get("execute_in_sandbox", False):
            for i, code in enumerate(code_blocks):
                try:
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                        f.write(code)
                        temp_path = f.name

                    result = subprocess.run(
                        ["python3", temp_path],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )

                    if result.returncode != 0:
                        errors.append(f"Block {i+1}: Execution failed with code {result.returncode}")

                    Path(temp_path).unlink()
                except subprocess.TimeoutExpired:
                    errors.append(f"Block {i+1}: Execution timed out")
                except Exception as exc:
                    errors.append(f"Block {i+1}: Execution error: {exc}")

            if errors:
                return CheckResult(
                    name="code_execution",
                    passed=False,
                    details=f"Code execution failed: {'; '.join(errors)}",
                )

        return CheckResult(name="code_execution", passed=True, details="Python code validation passed.")

    elif language == "json":
        try:
            json.loads(content)
            return CheckResult(name="code_execution", passed=True, details="JSON validation passed.")
        except json.JSONDecodeError as exc:
            return CheckResult(
                name="code_execution",
                passed=False,
                details=f"JSON validation failed: {exc}",
            )

    return CheckResult(
        name="code_execution",
        passed=True,
        details=f"Code execution checks for {language} not implemented.",
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
        _check_security(spec, stdout, stderr),
        _check_code_execution(spec, stdout, stderr),
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
    parser.add_argument(
        "--work-order-id",
        help="Work order ID to associate with this QA run (for database logging).",
    )
    parser.add_argument(
        "--log-to-db",
        action="store_true",
        help="Log QA results to database.",
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

    # Log to database if requested
    if args.log_to_db:
        try:
            # Import here to avoid dependency if not using database
            from db.client import AuditLog, get_db_client

            db = get_db_client()
            audit = AuditLog(
                work_order_id=args.work_order_id,
                session_id=None,
                actor="qa_runner",
                action="qa_validation",
                status="success" if report.passed else "failure",
                details={
                    "spec_name": report.spec_name,
                    "command": report.command,
                    "duration_ms": report.duration_ms,
                    "checks": [asdict(check) for check in report.checks],
                },
            )
            db.log_audit(audit)
            report.qa_result_logged = True
            print(f"QA results logged to database (work_order_id={args.work_order_id})")
        except Exception as exc:
            print(f"Warning: Failed to log QA results to database: {exc}", file=sys.stderr)

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
