#!/usr/bin/env python3
"""
Auto-Update Hook for Nexus AI-Team Org Chart.

Monitors key files for changes and triggers org re-scan + brief update.
Supports two modes:
  1. watchdog (real-time): Uses filesystem events (requires `pip install watchdog`)
  2. poll (cron-friendly): One-shot check via file modification times

Usage:
  python org_hook.py watch       # Real-time file watcher (daemon mode)
  python org_hook.py poll        # One-shot poll (for cron)
  python org_hook.py install     # Install cron job for every 5 minutes
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure tools/ is on sys.path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))

from ceo_brief import generate_brief, save_brief
from org_scanner import (
    AGENTS_DIR,
    AGENTS_REGISTRY,
    COMPANY_AGENTS_DIR,
    NEXUS_DIR,
    PROJECT_ROOT,
    OrgScanner,
    _load_json,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WATCH_PATHS: list[Path] = [
    AGENTS_REGISTRY,                    # agents/registry.yaml
    COMPANY_AGENTS_DIR,                 # company/agents/ (JDs + race)
    AGENTS_DIR,                         # agents/ (TOOL.md files)
    NEXUS_DIR / "skills",               # ~/.nexus/skills/
]

STATE_FILE = NEXUS_DIR / "org-hook-state.json"
CHANGE_LOG = NEXUS_DIR / "org-changes.log"
ORG_SUMMARY_PATH = PROJECT_ROOT / "company" / "org_summary.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    """Log with timestamp."""
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        NEXUS_DIR.mkdir(parents=True, exist_ok=True)
        with open(CHANGE_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _get_watched_mtimes() -> dict[str, float]:
    """Get modification times of all watched files."""
    mtimes: dict[str, float] = {}
    for path in WATCH_PATHS:
        if path.is_file():
            mtimes[str(path)] = path.stat().st_mtime
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    mtimes[str(child)] = child.stat().st_mtime
    return mtimes


def _load_state() -> dict[str, Any]:
    """Load previous hook state."""
    if STATE_FILE.exists():
        return _load_json(STATE_FILE)
    return {}


def _save_state(state: dict[str, Any]) -> None:
    """Save hook state."""
    NEXUS_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _detect_changes() -> list[str]:
    """Compare current mtimes with saved state, return list of changed files."""
    current = _get_watched_mtimes()
    state = _load_state()
    prev_mtimes: dict[str, float] = state.get("mtimes", {})

    changed: list[str] = []

    # New or modified files
    for fpath, mtime in current.items():
        if fpath not in prev_mtimes or prev_mtimes[fpath] < mtime:
            changed.append(fpath)

    # Deleted files
    for fpath in prev_mtimes:
        if fpath not in current:
            changed.append(f"DELETED:{fpath}")

    # Save new state
    state["mtimes"] = current
    state["last_poll"] = datetime.now(UTC).isoformat()
    _save_state(state)

    return changed


def _on_change(changed_files: list[str]) -> None:
    """Handle detected changes: rescan, diff, update summary, notify."""
    _log(f"Detected {len(changed_files)} changed file(s)")
    for f in changed_files[:10]:
        _log(f"  - {f}")

    # 1. Run scanner
    scanner = OrgScanner()
    snapshot = scanner.scan()
    diff = scanner.compute_diff(snapshot)
    scanner.save_snapshot(snapshot)
    _log(f"Org snapshot updated: {snapshot.get('total_agents', 0)} agents, "
         f"{snapshot.get('total_departments', 0)} departments")

    # 2. Log diff
    total_changes = diff.get("total_changes", 0)
    if total_changes > 0:
        _log(f"Changes since last scan: {total_changes}")
        for c in diff.get("changes", []):
            _log(f"  [{c.get('type')}] {json.dumps(c, ensure_ascii=False)}")
    else:
        _log("No structural changes detected in org data.")

    # 3. Update company/org_summary.md
    brief_content = generate_brief(force_scan=False)
    # For the company-internal summary, we reuse the CEO brief format
    _update_org_summary(snapshot)
    save_brief(brief_content)
    _log("CEO brief updated at ~/.nexus/ceo-brief.md")

    # 4. Notify on major changes
    if diff.get("is_major_change"):
        _notify_major_change(diff)


def _update_org_summary(snapshot: dict[str, Any]) -> None:
    """Update company/org_summary.md with current org overview."""
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = [
        "# Nexus AI-Team 组织架构概况",
        "",
        f"> 最后更新: {now}",
        f"> 总员工: {snapshot.get('total_agents', 0)} | "
        f"总部门: {snapshot.get('total_departments', 0)}",
        "",
        "## 部门列表",
        "",
    ]

    for dept_id, dept in sorted(snapshot.get("departments", {}).items()):
        manager = dept.get("manager", "N/A")
        headcount = dept.get("headcount", 0)
        cost = dept.get("total_monthly_cost_estimate", "$0")
        members = [m["id"] for m in dept.get("members", [])]
        caps = dept.get("capabilities", [])

        lines.append(f"### {dept_id}")
        lines.append(f"- **负责人**: {manager}")
        lines.append(f"- **人数**: {headcount}")
        lines.append(f"- **成员**: {', '.join(members)}")
        lines.append(f"- **能力**: {', '.join(caps)}")
        lines.append(f"- **月估算成本**: {cost}")
        lines.append("")

    lines.append("---")
    lines.append("_此文件由 org_hook 自动维护，请勿手动编辑。_")

    content = "\n".join(lines) + "\n"
    ORG_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    ORG_SUMMARY_PATH.write_text(content, encoding="utf-8")
    _log(f"Org summary updated at {ORG_SUMMARY_PATH}")


def _notify_major_change(diff: dict[str, Any]) -> None:
    """Log a prominent notification for major changes."""
    changes = diff.get("changes", [])
    major = [c for c in changes if c["type"] in
             ("dept_added", "dept_removed", "agent_added", "agent_removed")]
    _log("=" * 60)
    _log("MAJOR ORG CHANGE DETECTED")
    for c in major:
        _log(f"  >> {c['type'].upper()}: {json.dumps(c, ensure_ascii=False)}")
    _log("=" * 60)

    # Write notification file for other systems to pick up
    notif_path = NEXUS_DIR / "org-notification.json"
    notif = {
        "timestamp": datetime.now(UTC).isoformat(),
        "type": "major_org_change",
        "changes": major,
    }
    with open(notif_path, "w", encoding="utf-8") as f:
        json.dump(notif, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_poll() -> None:
    """One-shot poll for changes."""
    _log("Running poll check...")
    changed = _detect_changes()
    if changed:
        _on_change(changed)
    else:
        _log("No file changes detected.")


def cmd_watch() -> None:
    """Real-time file watcher using watchdog (or fallback to polling)."""
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        class OrgChangeHandler(FileSystemEventHandler):
            def __init__(self) -> None:
                self._last_trigger = 0.0
                self._debounce_seconds = 3.0

            def on_any_event(self, event: Any) -> None:
                # Debounce: don't trigger more than once per N seconds
                now = time.time()
                if now - self._last_trigger < self._debounce_seconds:
                    return
                self._last_trigger = now

                # Skip temporary/swap files
                src = getattr(event, "src_path", "")
                if src.endswith((".swp", ".tmp", "~", ".pyc")):
                    return

                _log(f"File event: {event.event_type} on {src}")
                try:
                    _on_change([src])
                except Exception as e:
                    _log(f"Error processing change: {e}")

        handler = OrgChangeHandler()
        observer = Observer()

        for path in WATCH_PATHS:
            if path.exists():
                if path.is_dir():
                    observer.schedule(handler, str(path), recursive=True)
                    _log(f"Watching directory: {path}")
                elif path.is_file():
                    observer.schedule(handler, str(path.parent), recursive=False)
                    _log(f"Watching file: {path}")

        _log("Starting watchdog observer (Ctrl+C to stop)...")
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            _log("Watcher stopped.")
        observer.join()

    except ImportError:
        _log("watchdog not installed, falling back to polling mode (10s interval)")
        _log("Install watchdog for real-time monitoring: pip install watchdog")
        # Initialize state
        _detect_changes()
        _log("Polling watcher started (Ctrl+C to stop)...")
        try:
            while True:
                time.sleep(10)
                changed = _detect_changes()
                if changed:
                    _on_change(changed)
        except KeyboardInterrupt:
            _log("Watcher stopped.")


def cmd_install_cron() -> None:
    """Install a cron job to poll every 5 minutes."""
    script_path = Path(__file__).resolve()
    python_path = sys.executable
    cron_line = f"*/5 * * * * cd {script_path.parent} && {python_path} {script_path} poll >> {CHANGE_LOG} 2>&1"

    # Check if already installed
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current_cron = result.stdout if result.returncode == 0 else ""

    if str(script_path) in current_cron:
        print("Cron job already installed.")
        print(f"Log: {CHANGE_LOG}")
        return

    new_cron = current_cron.rstrip("\n") + "\n" + cron_line + "\n"
    proc = subprocess.run(
        ["crontab", "-"],
        input=new_cron,
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        print("Cron job installed: poll every 5 minutes")
        print(f"Log: {CHANGE_LOG}")
    else:
        print(f"Failed to install cron: {proc.stderr}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python org_hook.py <watch|poll|install>")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "watch":
        cmd_watch()
    elif cmd == "poll":
        cmd_poll()
    elif cmd == "install":
        cmd_install_cron()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python org_hook.py <watch|poll|install>")
        sys.exit(1)


if __name__ == "__main__":
    main()
