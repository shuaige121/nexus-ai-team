#!/usr/bin/env python3
"""
CEO Brief Generator for Nexus AI-Team.

Produces a daily executive summary in Markdown format
at ~/.nexus/ceo-brief.md.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from org_scanner import (
    NEXUS_DIR, SNAPSHOT_PATH, PREV_SNAPSHOT_PATH,
    OrgScanner, _load_json, run_scan, get_diff,
)

BRIEF_PATH = NEXUS_DIR / "ceo-brief.md"

# Capabilities that a well-rounded tech company should have
EXPECTED_CAPABILITIES = {
    "frontend", "backend", "devops", "qa", "testing",
    "security", "database", "api_design", "cicd",
    "project_management", "product_management", "ui_design",
    "ux_design", "hr_management", "recruiting",
    "architecture", "performance_optimization", "code_review",
    "documentation", "data_engineering", "ml_ops",
    "monitoring", "incident_response",
}


def _build_org_tree(snapshot: dict[str, Any]) -> str:
    """Build ASCII org chart tree."""
    chain = snapshot.get("chain_of_command", {})
    departments = snapshot.get("departments", {})

    # Build a flat lookup: agent_id -> department + role
    agent_info: dict[str, str] = {}
    for dept_id, dept in departments.items():
        for member in dept.get("members", []):
            mid = member["id"]
            model_short = member.get("model", "")
            # Shorten model names
            for full, short in [
                ("claude-opus-4-0-20250514", "opus"),
                ("claude-sonnet-4-5-20250514", "sonnet"),
                ("claude-sonnet-4-5", "sonnet"),
                ("claude-haiku-4-5", "haiku"),
            ]:
                model_short = model_short.replace(full, short)
            agent_info[mid] = f"[{model_short}] ({dept_id})"

    lines: list[str] = []

    def _render(node_id: str, prefix: str, is_last: bool, depth: int) -> None:
        connector = "└── " if is_last else "├── "
        info = agent_info.get(node_id, "")
        if depth == 0:
            lines.append(f"{node_id} {info}")
        else:
            lines.append(f"{prefix}{connector}{node_id} {info}")

        new_prefix = prefix + ("    " if is_last else "│   ")

        # Find children from chain_of_command
        children = _find_children(chain, node_id)
        for i, child in enumerate(children):
            _render(child, new_prefix, i == len(children) - 1, depth + 1)

    def _find_children(node: dict[str, Any], target: str) -> list[str]:
        """Recursively find direct_reports for a target in the chain tree."""
        if target in node:
            sub = node[target]
            if isinstance(sub, dict):
                return sub.get("direct_reports", [])
        for key, val in node.items():
            if isinstance(val, dict):
                result = _find_children(val, target)
                if result:
                    return result
        return []

    # Start from board
    lines.append("board (董事会/用户)")
    board_reports = chain.get("board", {}).get("direct_reports", [])
    for i, child in enumerate(board_reports):
        _render(child, "", i == len(board_reports) - 1, 1)

    return "\n".join(lines)


def _build_dept_table(snapshot: dict[str, Any]) -> str:
    """Build department summary table."""
    lines: list[str] = []
    lines.append("| 部门 | 负责人 | 人数 | 模型组合 | 月估算成本 |")
    lines.append("|------|--------|------|----------|------------|")

    for dept_id, dept in sorted(snapshot.get("departments", {}).items()):
        manager = dept.get("manager", "N/A")
        headcount = dept.get("headcount", 0)
        cost = dept.get("total_monthly_cost_estimate", "$0")

        # Model mix
        models: dict[str, int] = {}
        for m in dept.get("members", []):
            model = m.get("model", "unknown")
            for full, short in [
                ("claude-opus-4-0-20250514", "opus"),
                ("claude-sonnet-4-5-20250514", "sonnet"),
                ("claude-sonnet-4-5", "sonnet"),
                ("claude-haiku-4-5", "haiku"),
            ]:
                model = model.replace(full, short)
            models[model] = models.get(model, 0) + 1
        model_str = ", ".join(f"{k}x{v}" for k, v in sorted(models.items()))

        lines.append(f"| {dept_id} | {manager} | {headcount} | {model_str} | {cost} |")

    return "\n".join(lines)


def _build_capabilities_matrix(snapshot: dict[str, Any]) -> str:
    """Build capabilities per department."""
    lines: list[str] = []
    for dept_id, dept in sorted(snapshot.get("departments", {}).items()):
        caps = dept.get("capabilities", [])
        skills_list = dept.get("installed_skills", [])
        lines.append(f"### {dept_id}")
        lines.append(f"- **角色能力**: {', '.join(caps) if caps else '无'}")
        lines.append(f"- **已安装技能**: {', '.join(skills_list) if skills_list else '无'}")
        lines.append("")
    return "\n".join(lines)


def _build_gap_analysis(snapshot: dict[str, Any]) -> str:
    """Identify capability gaps."""
    all_caps: set[str] = set()
    for dept in snapshot.get("departments", {}).values():
        for cap in dept.get("capabilities", []):
            all_caps.add(cap)
        for member in dept.get("members", []):
            for skill in member.get("skills", []):
                all_caps.add(skill)

    gaps = sorted(EXPECTED_CAPABILITIES - all_caps)
    covered = sorted(EXPECTED_CAPABILITIES & all_caps)

    lines: list[str] = []
    if gaps:
        lines.append(f"**缺口能力 ({len(gaps)})**: 以下能力目前无 Agent 覆盖:\n")
        for g in gaps:
            lines.append(f"- {g}")
    else:
        lines.append("所有预期能力均已覆盖。")

    lines.append("")
    lines.append(f"**已覆盖能力 ({len(covered)}/{len(EXPECTED_CAPABILITIES)})**: {', '.join(covered)}")

    return "\n".join(lines)


def _build_recent_changes(diff: dict[str, Any] | None) -> str:
    """Format recent changes."""
    if diff is None or diff.get("status") == "no_previous_snapshot":
        return "_首次扫描，无历史变更记录。_"

    changes = diff.get("changes", [])
    if not changes:
        return "_自上次扫描以来无变更。_"

    lines: list[str] = []
    type_labels = {
        "dept_added": "新增部门",
        "dept_removed": "撤销部门",
        "agent_added": "新增人员",
        "agent_removed": "人员离开",
        "headcount_changed": "人数变更",
        "capability_added": "新增能力",
        "capability_removed": "失去能力",
    }

    for c in changes:
        label = type_labels.get(c["type"], c["type"])
        detail_parts = [f"{k}: {v}" for k, v in c.items() if k != "type"]
        detail = ", ".join(detail_parts)
        lines.append(f"- **{label}** — {detail}")

    return "\n".join(lines)


def generate_brief(force_scan: bool = True) -> str:
    """Generate the CEO brief markdown content."""
    if force_scan:
        scanner = OrgScanner()
        snapshot = scanner.scan()
        diff = scanner.compute_diff(snapshot)
        scanner.save_snapshot(snapshot)
    else:
        snapshot = _load_json(SNAPSHOT_PATH)
        diff = None

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_agents = snapshot.get("total_agents", 0)
    total_depts = snapshot.get("total_departments", 0)

    brief = f"""# Nexus AI-Team CEO 每日简报

> 生成时间: {now}
> 总员工数: {total_agents} | 总部门数: {total_depts}

---

## 1. 组织架构树

```
{_build_org_tree(snapshot)}
```

## 2. 部门概览

{_build_dept_table(snapshot)}

## 3. 各部门能力矩阵

{_build_capabilities_matrix(snapshot)}

## 4. 最近变更记录

{_build_recent_changes(diff)}

## 5. 能力缺口分析

{_build_gap_analysis(snapshot)}

---

_此简报由 `nexus-org` 系统自动生成。如需详细数据，请运行 `nexus-org scan` 或 `nexus-org export --format json`。_
"""
    return brief


def save_brief(content: str | None = None) -> Path:
    """Generate and save CEO brief."""
    if content is None:
        content = generate_brief()
    NEXUS_DIR.mkdir(parents=True, exist_ok=True)
    BRIEF_PATH.write_text(content, encoding="utf-8")
    return BRIEF_PATH


if __name__ == "__main__":
    content = generate_brief()
    path = save_brief(content)
    print(content)
    print(f"\n--- Brief saved to: {path} ---")
