#!/usr/bin/env python3
"""
nexus-org CLI — Dynamic Org Chart Manager for Nexus AI-Team.

Commands:
  scan                      Scan all agents, generate latest org snapshot
  chain                     Display current chain of command
  department <dept-id>      Show department details (members, skills, capabilities)
  capabilities              List capability matrix for all departments
  diff                      Show changes since last scan
  export --format <fmt>     Export org data as json / yaml / markdown
  brief                     Generate CEO daily brief
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure tools/ is on sys.path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))

from org_scanner import (
    OrgScanner, run_scan, get_diff,
    SNAPSHOT_PATH, PREV_SNAPSHOT_PATH, NEXUS_DIR, _load_json,
)
from ceo_brief import generate_brief, save_brief


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def _print_chain_tree(chain: dict[str, Any], indent: int = 0) -> None:
    """Recursively print chain of command as a tree."""
    for key, val in chain.items():
        if key == "direct_reports":
            continue
        prefix = "  " * indent
        direct = []
        if isinstance(val, dict):
            direct = val.get("direct_reports", [])
        print(f"{prefix}{key}")
        if direct:
            for i, child_id in enumerate(direct):
                is_last = (i == len(direct) - 1)
                branch = "└── " if is_last else "├── "
                print(f"{prefix}  {branch}{child_id}")
                # Recurse into child
                child_node = val.get(child_id, {})
                if child_node:
                    _print_subtree(child_node, prefix + ("      " if is_last else "  │   "))


def _print_subtree(node: dict[str, Any], prefix: str) -> None:
    """Print subtree from a chain node."""
    direct = node.get("direct_reports", [])
    for i, child_id in enumerate(direct):
        is_last = (i == len(direct) - 1)
        branch = "└── " if is_last else "├── "
        print(f"{prefix}{branch}{child_id}")
        child_node = node.get(child_id, {})
        if child_node:
            new_prefix = prefix + ("    " if is_last else "│   ")
            _print_subtree(child_node, new_prefix)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> None:
    """Run full org scan."""
    _print_header("Nexus AI-Team Org Scan")
    snapshot = run_scan()
    print(f"Scan completed at: {snapshot['snapshot_at']}")
    print(f"Total agents: {snapshot['total_agents']}")
    print(f"Total departments: {snapshot['total_departments']}")
    print()

    for dept_id, dept in sorted(snapshot["departments"].items()):
        mgr = dept["manager"] or "N/A"
        hc = dept["headcount"]
        cost = dept["total_monthly_cost_estimate"]
        print(f"  [{dept_id}] Manager: {mgr} | Headcount: {hc} | Cost: {cost}")
        for m in dept["members"]:
            model = m["model"]
            for full, short in [
                ("claude-opus-4-0-20250514", "opus"),
                ("claude-sonnet-4-5-20250514", "sonnet"),
                ("claude-sonnet-4-5", "sonnet"),
                ("claude-haiku-4-5", "haiku"),
            ]:
                model = model.replace(full, short)
            skills = ", ".join(m["skills"][:5]) if m["skills"] else "-"
            status_icon = "+" if m["status"] == "active" else "x"
            print(f"    {status_icon} {m['id']:20s} [{model:8s}] skills: {skills}")
        print()

    print(f"Snapshot saved to: {SNAPSHOT_PATH}")


def cmd_chain(args: argparse.Namespace) -> None:
    """Display chain of command."""
    _print_header("Chain of Command")
    snapshot = _load_json(SNAPSHOT_PATH)
    if not snapshot:
        print("No snapshot found. Run 'nexus-org scan' first.")
        return
    chain = snapshot.get("chain_of_command", {})
    _print_chain_tree(chain)


def cmd_department(args: argparse.Namespace) -> None:
    """Show department details."""
    dept_id = args.dept_id
    snapshot = _load_json(SNAPSHOT_PATH)
    if not snapshot:
        print("No snapshot found. Run 'nexus-org scan' first.")
        return

    dept = snapshot.get("departments", {}).get(dept_id)
    if not dept:
        print(f"Department '{dept_id}' not found.")
        print(f"Available departments: {', '.join(snapshot.get('departments', {}).keys())}")
        return

    _print_header(f"Department: {dept_id}")
    print(f"  Manager:    {dept['manager'] or 'N/A'}")
    print(f"  Model:      {dept['manager_model'] or 'N/A'}")
    print(f"  Headcount:  {dept['headcount']}")
    print(f"  Est. Cost:  {dept['total_monthly_cost_estimate']}")
    print()

    print("  Members:")
    for m in dept["members"]:
        model = m["model"]
        for full, short in [
            ("claude-opus-4-0-20250514", "opus"),
            ("claude-sonnet-4-5-20250514", "sonnet"),
            ("claude-sonnet-4-5", "sonnet"),
            ("claude-haiku-4-5", "haiku"),
        ]:
            model = model.replace(full, short)
        print(f"    - {m['id']:20s} role={m['role']:15s} model={model}")
        if m["skills"]:
            print(f"      skills: {', '.join(m['skills'])}")
        if m["tools"]:
            print(f"      tools:  {', '.join(m['tools'])}")
        if m["jd_summary"]:
            print(f"      summary: {m['jd_summary'][:80]}...")
    print()

    print(f"  Capabilities: {', '.join(dept['capabilities'])}")
    if dept["installed_skills"]:
        print(f"  Installed Skills: {', '.join(dept['installed_skills'])}")


def cmd_capabilities(args: argparse.Namespace) -> None:
    """List capability matrix for all departments."""
    _print_header("Organization Capability Matrix")
    snapshot = _load_json(SNAPSHOT_PATH)
    if not snapshot:
        print("No snapshot found. Run 'nexus-org scan' first.")
        return

    # Collect all unique capabilities
    all_caps: set[str] = set()
    for dept in snapshot.get("departments", {}).values():
        all_caps.update(dept.get("capabilities", []))
        for m in dept.get("members", []):
            all_caps.update(m.get("skills", []))

    sorted_caps = sorted(all_caps)
    depts = sorted(snapshot.get("departments", {}).keys())

    # Build matrix
    print(f"{'Capability':<30s}", end="")
    for d in depts:
        print(f" {d[:12]:>12s}", end="")
    print()
    print("-" * (30 + 13 * len(depts)))

    for cap in sorted_caps:
        print(f"{cap:<30s}", end="")
        for d in depts:
            dept = snapshot["departments"][d]
            has_it = (cap in dept.get("capabilities", []) or
                      any(cap in m.get("skills", []) for m in dept.get("members", [])))
            marker = "  *" if has_it else "  -"
            print(f" {marker:>12s}", end="")
        print()

    print()
    print(f"Total unique capabilities: {len(sorted_caps)}")


def cmd_diff(args: argparse.Namespace) -> None:
    """Show changes since last scan."""
    _print_header("Org Changes (Diff)")
    diff = get_diff()

    if diff.get("status") == "no_previous_snapshot":
        print("No previous snapshot found. This is the first scan.")
        print("Run 'nexus-org scan' again to establish a baseline for future diffs.")
        return

    print(f"Previous scan: {diff.get('prev_snapshot_at', 'N/A')}")
    print(f"Current scan:  {diff.get('curr_snapshot_at', 'N/A')}")
    print(f"Agent count:   {diff.get('prev_total_agents', 0)} -> {diff.get('curr_total_agents', 0)}")
    print(f"Total changes: {diff.get('total_changes', 0)}")
    print(f"Major change:  {'YES' if diff.get('is_major_change') else 'No'}")
    print()

    changes = diff.get("changes", [])
    if not changes:
        print("No changes detected.")
    else:
        type_colors = {
            "dept_added": "[+DEPT]",
            "dept_removed": "[-DEPT]",
            "agent_added": "[+AGENT]",
            "agent_removed": "[-AGENT]",
            "headcount_changed": "[COUNT]",
            "capability_added": "[+CAP]",
            "capability_removed": "[-CAP]",
        }
        for c in changes:
            tag = type_colors.get(c["type"], f"[{c['type']}]")
            detail_parts = [f"{k}={v}" for k, v in c.items() if k != "type"]
            print(f"  {tag:12s} {', '.join(detail_parts)}")


def cmd_export(args: argparse.Namespace) -> None:
    """Export org data in specified format."""
    fmt = args.format.lower()
    snapshot = _load_json(SNAPSHOT_PATH)
    if not snapshot:
        print("No snapshot found. Run 'nexus-org scan' first.")
        return

    if fmt == "json":
        output = json.dumps(snapshot, ensure_ascii=False, indent=2)
        ext = "json"
    elif fmt == "yaml":
        try:
            import yaml
            output = yaml.dump(snapshot, allow_unicode=True, default_flow_style=False, sort_keys=False)
            ext = "yaml"
        except ImportError:
            print("PyYAML not installed. Use --format json or install: pip install pyyaml")
            return
    elif fmt in ("md", "markdown"):
        output = _snapshot_to_markdown(snapshot)
        ext = "md"
    else:
        print(f"Unknown format: {fmt}. Supported: json, yaml, markdown")
        return

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output, encoding="utf-8")
        print(f"Exported to: {out_path}")
    else:
        print(output)


def _snapshot_to_markdown(snapshot: dict[str, Any]) -> str:
    """Convert snapshot to readable Markdown."""
    lines: list[str] = [
        f"# Nexus AI-Team Organization Snapshot",
        f"",
        f"**Timestamp**: {snapshot.get('snapshot_at', 'N/A')}",
        f"**Total Agents**: {snapshot.get('total_agents', 0)}",
        f"**Total Departments**: {snapshot.get('total_departments', 0)}",
        f"",
    ]
    for dept_id, dept in sorted(snapshot.get("departments", {}).items()):
        lines.append(f"## {dept_id}")
        lines.append(f"- Manager: {dept.get('manager', 'N/A')}")
        lines.append(f"- Headcount: {dept.get('headcount', 0)}")
        lines.append(f"- Est. Cost: {dept.get('total_monthly_cost_estimate', '$0')}")
        lines.append(f"- Capabilities: {', '.join(dept.get('capabilities', []))}")
        lines.append("")
        lines.append("| Agent | Role | Model | Skills |")
        lines.append("|-------|------|-------|--------|")
        for m in dept.get("members", []):
            skills = ", ".join(m.get("skills", [])[:5])
            lines.append(f"| {m['id']} | {m.get('role', '')} | {m.get('model', '')} | {skills} |")
        lines.append("")

    return "\n".join(lines)


def cmd_brief(args: argparse.Namespace) -> None:
    """Generate and display CEO brief."""
    _print_header("CEO Daily Brief")
    content = generate_brief(force_scan=True)
    path = save_brief(content)
    print(content)
    print(f"Brief saved to: {path}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nexus-org",
        description="Nexus AI-Team Dynamic Org Chart Manager",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # scan
    sub.add_parser("scan", help="Scan all agents, generate latest org snapshot")

    # chain
    sub.add_parser("chain", help="Display current chain of command")

    # department
    dept_parser = sub.add_parser("department", help="Show department details")
    dept_parser.add_argument("dept_id", help="Department ID (e.g. engineering, qa)")

    # capabilities
    sub.add_parser("capabilities", help="List capability matrix for all departments")

    # diff
    sub.add_parser("diff", help="Show changes since last scan")

    # export
    export_parser = sub.add_parser("export", help="Export org data")
    export_parser.add_argument("--format", "-f", default="json",
                               help="Output format: json, yaml, markdown (default: json)")
    export_parser.add_argument("--output", "-o", help="Output file path (default: stdout)")

    # brief
    sub.add_parser("brief", help="Generate CEO daily brief")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "scan": cmd_scan,
        "chain": cmd_chain,
        "department": cmd_department,
        "capabilities": cmd_capabilities,
        "diff": cmd_diff,
        "export": cmd_export,
        "brief": cmd_brief,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
