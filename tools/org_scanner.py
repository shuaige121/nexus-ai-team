#!/usr/bin/env python3
"""
Department Capability Scanner for Nexus AI-Team.

Scans all data sources (registry, JDs, race configs, skills, tools)
and produces a unified org snapshot at ~/.nexus/org-snapshot.json.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path.home() / "Desktop" / "nexus-ai-team"
AGENTS_REGISTRY = PROJECT_ROOT / "agents" / "registry.yaml"
COMPANY_AGENTS_DIR = PROJECT_ROOT / "company" / "agents"
AGENTS_DIR = PROJECT_ROOT / "agents"
NEXUS_DIR = Path.home() / ".nexus"
SKILLS_REGISTRY = NEXUS_DIR / "skills" / "registry.json"
SNAPSHOT_PATH = NEXUS_DIR / "org-snapshot.json"
PREV_SNAPSHOT_PATH = NEXUS_DIR / "org-snapshot-prev.json"


# ---------------------------------------------------------------------------
# Model cost table (per 1K tokens)
# ---------------------------------------------------------------------------

DEFAULT_COSTS: dict[str, dict[str, float]] = {
    "claude-opus-4-0-20250514": {"input": 0.015, "output": 0.075},
    "claude-sonnet-4-5-20250514": {"input": 0.003, "output": 0.015},
    "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5": {"input": 0.0008, "output": 0.004},
}

# Rough monthly token budget estimate per agent (input + output combined)
MONTHLY_TOKEN_ESTIMATE_K = 5000  # 5M tokens/month assumed


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AgentInfo:
    id: str
    role: str
    department: str
    reports_to: str
    model: str = ""
    model_full: str = ""
    species: str = ""
    name: str = ""
    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    jd_summary: str = ""
    status: str = "active"
    created: str = ""
    capabilities_from_race: dict[str, Any] = field(default_factory=dict)
    cost_input_per_1k: float = 0.0
    cost_output_per_1k: float = 0.0

    @property
    def monthly_cost_estimate(self) -> float:
        """Rough monthly cost estimate in USD."""
        input_cost = self.cost_input_per_1k * MONTHLY_TOKEN_ESTIMATE_K * 0.6
        output_cost = self.cost_output_per_1k * MONTHLY_TOKEN_ESTIMATE_K * 0.4
        return round(input_cost + output_cost, 2)


@dataclass
class DepartmentInfo:
    id: str
    manager: str = ""
    manager_model: str = ""
    members: list[AgentInfo] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    installed_skills: list[str] = field(default_factory=list)

    @property
    def headcount(self) -> int:
        return len(self.members)

    @property
    def total_monthly_cost_estimate(self) -> float:
        return round(sum(m.monthly_cost_estimate for m in self.members), 2)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict[str, Any]:
    """Safely load a YAML file, returning empty dict on failure."""
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _load_json(path: Path) -> Any:
    """Safely load a JSON file."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _extract_jd_summary(jd_path: Path) -> str:
    """Extract first few responsibility lines from a JD markdown."""
    try:
        text = jd_path.read_text(encoding="utf-8")
        lines: list[str] = []
        in_responsibilities = False
        for line in text.splitlines():
            if "职责描述" in line or "Responsibilities" in line.title():
                in_responsibilities = True
                continue
            if in_responsibilities:
                if line.startswith("##"):
                    break
                stripped = line.strip().lstrip("- ").strip()
                if stripped:
                    lines.append(stripped)
        return "; ".join(lines[:3])
    except Exception:
        return ""


def _extract_skills_from_jd(jd_path: Path) -> list[str]:
    """Heuristically extract skill keywords from JD text."""
    keywords_map = {
        "前端": "frontend", "后端": "backend", "devops": "devops",
        "docker": "docker", "kubernetes": "kubernetes", "k8s": "kubernetes",
        "react": "react", "vue": "vue", "typescript": "typescript",
        "python": "python", "node": "nodejs", "api": "api_design",
        "测试": "testing", "qa": "qa", "安全": "security",
        "ui": "ui_design", "ux": "ux_design", "figma": "figma",
        "css": "css", "html": "html", "git": "git",
        "ci/cd": "cicd", "数据库": "database", "sql": "sql",
        "项目管理": "project_management", "产品": "product_management",
        "招聘": "recruiting", "人事": "hr_management",
        "code review": "code_review", "代码审查": "code_review",
        "性能": "performance_optimization",
        "架构": "architecture", "设计": "design",
    }
    try:
        text = jd_path.read_text(encoding="utf-8").lower()
        found: list[str] = []
        for keyword, skill in keywords_map.items():
            if keyword in text and skill not in found:
                found.append(skill)
        return found
    except Exception:
        return []


def _parse_tools_from_toolmd(tool_path: Path) -> list[str]:
    """Extract tool names from a TOOL.md file."""
    tools: list[str] = []
    try:
        text = tool_path.read_text(encoding="utf-8")
        # Match lines like: - `send_mail.sh ...` or - `check_inbox.sh ...`
        for match in re.finditer(r"`(\w[\w\-]*\.sh|\w[\w\-]*)`", text):
            name = match.group(1)
            if name not in tools:
                tools.append(name)
    except Exception:
        pass
    return tools


# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------

class OrgScanner:
    """Scans the Nexus AI-Team organization and produces a snapshot."""

    def __init__(self) -> None:
        self.agents: dict[str, AgentInfo] = {}
        self.departments: dict[str, DepartmentInfo] = {}
        self.skills_assignments: dict[str, list[str]] = {}  # agent_id -> [skill_name]

    def scan(self) -> dict[str, Any]:
        """Run full scan and return snapshot dict."""
        self._scan_registry()
        self._scan_jds_and_race()
        self._scan_skills()
        self._scan_tools()
        self._build_departments()
        return self._build_snapshot()

    def _scan_registry(self) -> None:
        """Parse agents/registry.yaml."""
        data = _load_yaml(AGENTS_REGISTRY)
        agents_data = data.get("agents", {})
        for agent_id, info in agents_data.items():
            self.agents[agent_id] = AgentInfo(
                id=agent_id,
                role=info.get("role", ""),
                department=info.get("department", "unknown"),
                reports_to=info.get("reports_to", ""),
                model=info.get("model", ""),
                status=info.get("status", "active"),
                created=str(info.get("created", "")),
            )

    def _scan_jds_and_race(self) -> None:
        """Enrich agent info from company/agents/<id>/jd.md and race.yaml."""
        if not COMPANY_AGENTS_DIR.exists():
            return
        for agent_dir in COMPANY_AGENTS_DIR.iterdir():
            if not agent_dir.is_dir():
                continue
            agent_id = agent_dir.name
            agent = self.agents.get(agent_id)
            if agent is None:
                # Agent exists in company dir but not in registry - create entry
                agent = AgentInfo(
                    id=agent_id,
                    role=agent_id,
                    department="unknown",
                    reports_to="",
                )
                self.agents[agent_id] = agent

            # Parse race.yaml
            race_path = agent_dir / "race.yaml"
            if race_path.exists():
                race = _load_yaml(race_path)
                agent.model_full = race.get("model", agent.model)
                agent.species = race.get("species", "")
                agent.capabilities_from_race = race.get("capabilities", {})
                cost = race.get("cost", {})
                if cost:
                    agent.cost_input_per_1k = cost.get("input_per_1k", 0.0)
                    agent.cost_output_per_1k = cost.get("output_per_1k", 0.0)
                else:
                    # Use defaults from model name
                    model_name = agent.model_full
                    if model_name in DEFAULT_COSTS:
                        agent.cost_input_per_1k = DEFAULT_COSTS[model_name]["input"]
                        agent.cost_output_per_1k = DEFAULT_COSTS[model_name]["output"]

            # Parse jd.md
            jd_path = agent_dir / "jd.md"
            if jd_path.exists():
                agent.jd_summary = _extract_jd_summary(jd_path)
                agent.skills = _extract_skills_from_jd(jd_path)

            # Generate display name from species or role
            if agent.species:
                agent.name = agent.species.replace("Claude ", "")
                # Add role-based suffix
                role_names = {
                    "ceo": "CEO", "hr": "HR-Lead", "hr_lead": "HR-Lead",
                    "eng_manager": "Eng-Mgr", "frontend_dev": "Pixel",
                    "backend_dev": "Backend", "devops": "DevOps",
                    "qa_lead": "QA-Lead", "qa_tester": "QA-Tester",
                    "it_admin": "IT-Admin", "sec_analyst": "Sec-Analyst",
                    "pm": "PM", "designer": "Designer",
                    "exec_assistant": "EA", "recruiter": "Recruiter",
                    "manager": "Mgr", "worker": "Worker", "qa": "QA",
                }
                suffix = role_names.get(agent.role, agent.role)
                agent.name = f"{agent.species}-{suffix}"

    def _scan_skills(self) -> None:
        """Load installed skills from ~/.nexus/skills/registry.json."""
        if not SKILLS_REGISTRY.exists():
            return
        data = _load_json(SKILLS_REGISTRY)
        if isinstance(data, dict):
            # Expected format: {"skills": [{"name": "...", "assigned_to": [...]}]}
            for skill in data.get("skills", []):
                skill_name = skill.get("name", "")
                for agent_id in skill.get("assigned_to", []):
                    self.skills_assignments.setdefault(agent_id, []).append(skill_name)

    def _scan_tools(self) -> None:
        """Parse TOOL.md files from agents/<id>/TOOL.md."""
        for agent_id, agent in self.agents.items():
            # Check multiple possible TOOL.md locations
            candidates = [
                AGENTS_DIR / agent_id / "TOOL.md",
                AGENTS_DIR / agent.role / "TOOL.md",
            ]
            for tool_path in candidates:
                if tool_path.exists():
                    agent.tools = _parse_tools_from_toolmd(tool_path)
                    break

    def _build_departments(self) -> None:
        """Group agents into departments."""
        dept_agents: dict[str, list[AgentInfo]] = {}
        for agent in self.agents.values():
            dept_id = agent.department
            dept_agents.setdefault(dept_id, []).append(agent)

        for dept_id, members in dept_agents.items():
            dept = DepartmentInfo(id=dept_id)
            # Find manager (by role containing 'manager' or 'lead' or specific roles)
            manager_roles = {"manager", "eng_manager", "qa_lead", "hr", "hr_lead",
                             "it_admin", "pm", "ceo"}
            for m in members:
                if m.role in manager_roles or "manager" in m.role or "lead" in m.role:
                    dept.manager = m.id
                    dept.manager_model = m.model_full or m.model
                    break

            dept.members = sorted(members, key=lambda a: a.id)

            # Aggregate capabilities (unique roles/skills across members)
            caps: list[str] = []
            for m in members:
                if m.role and m.role not in caps:
                    caps.append(m.role)
                for s in m.skills:
                    if s not in caps:
                        caps.append(s)
            dept.capabilities = caps

            # Aggregate installed skills
            skills: list[str] = []
            for m in members:
                for s in self.skills_assignments.get(m.id, []):
                    if s not in skills:
                        skills.append(s)
            dept.installed_skills = skills

            self.departments[dept_id] = dept

    def _build_chain_of_command(self) -> dict[str, Any]:
        """Build hierarchical chain of command."""
        # Find who reports to whom
        children: dict[str, list[str]] = {}
        for agent in self.agents.values():
            parent = agent.reports_to
            if parent:
                children.setdefault(parent, []).append(agent.id)

        def _build_node(agent_id: str) -> dict[str, Any]:
            node: dict[str, Any] = {}
            direct = sorted(children.get(agent_id, []))
            if direct:
                node["direct_reports"] = direct
                for child_id in direct:
                    child_node = _build_node(child_id)
                    if child_node:
                        node[child_id] = child_node
            return node

        # Start from board level
        chain: dict[str, Any] = {"board": _build_node("board")}
        # Also handle agents reporting to specific IDs not in the tree
        for agent in self.agents.values():
            if agent.reports_to and agent.reports_to not in self.agents and agent.reports_to != "board":
                chain.setdefault(agent.reports_to, _build_node(agent.reports_to))

        return chain

    def _build_snapshot(self) -> dict[str, Any]:
        """Build the final snapshot dictionary."""
        now = datetime.now(UTC).isoformat(timespec="seconds")
        departments: dict[str, Any] = {}
        for dept_id, dept in sorted(self.departments.items()):
            departments[dept_id] = {
                "manager": dept.manager,
                "manager_model": dept.manager_model,
                "headcount": dept.headcount,
                "members": [
                    {
                        "id": m.id,
                        "name": m.name or m.id,
                        "role": m.role,
                        "model": m.model_full or m.model,
                        "skills": m.skills,
                        "tools": m.tools,
                        "jd_summary": m.jd_summary,
                        "status": m.status,
                    }
                    for m in dept.members
                ],
                "capabilities": dept.capabilities,
                "installed_skills": dept.installed_skills,
                "total_monthly_cost_estimate": f"${dept.total_monthly_cost_estimate:,.2f}",
            }

        return {
            "snapshot_at": now,
            "total_agents": len(self.agents),
            "total_departments": len(self.departments),
            "departments": departments,
            "chain_of_command": self._build_chain_of_command(),
        }

    def save_snapshot(self, snapshot: dict[str, Any]) -> Path:
        """Save snapshot to disk, archiving previous version."""
        NEXUS_DIR.mkdir(parents=True, exist_ok=True)
        # Archive previous snapshot for diff
        if SNAPSHOT_PATH.exists():
            import shutil
            shutil.copy2(SNAPSHOT_PATH, PREV_SNAPSHOT_PATH)
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        return SNAPSHOT_PATH

    def compute_diff(self, current: dict[str, Any]) -> dict[str, Any]:
        """Compare current snapshot with previous one."""
        if not PREV_SNAPSHOT_PATH.exists():
            return {"status": "no_previous_snapshot", "changes": []}

        prev = _load_json(PREV_SNAPSHOT_PATH)
        changes: list[dict[str, str]] = []

        prev_depts = set(prev.get("departments", {}).keys())
        curr_depts = set(current.get("departments", {}).keys())

        # New departments
        for d in sorted(curr_depts - prev_depts):
            changes.append({"type": "dept_added", "id": d})

        # Removed departments
        for d in sorted(prev_depts - curr_depts):
            changes.append({"type": "dept_removed", "id": d})

        # Check each department for member changes
        for dept_id in sorted(curr_depts & prev_depts):
            prev_members = {m["id"] for m in prev["departments"][dept_id].get("members", [])}
            curr_members = {m["id"] for m in current["departments"][dept_id].get("members", [])}

            for m in sorted(curr_members - prev_members):
                changes.append({"type": "agent_added", "department": dept_id, "agent": m})
            for m in sorted(prev_members - curr_members):
                changes.append({"type": "agent_removed", "department": dept_id, "agent": m})

            # Headcount change
            prev_hc = prev["departments"][dept_id].get("headcount", 0)
            curr_hc = current["departments"][dept_id].get("headcount", 0)
            if prev_hc != curr_hc:
                changes.append({
                    "type": "headcount_changed",
                    "department": dept_id,
                    "from": str(prev_hc),
                    "to": str(curr_hc),
                })

            # Capability changes
            prev_caps = set(prev["departments"][dept_id].get("capabilities", []))
            curr_caps = set(current["departments"][dept_id].get("capabilities", []))
            for c in sorted(curr_caps - prev_caps):
                changes.append({"type": "capability_added", "department": dept_id, "capability": c})
            for c in sorted(prev_caps - curr_caps):
                changes.append({"type": "capability_removed", "department": dept_id, "capability": c})

        prev_total = prev.get("total_agents", 0)
        curr_total = current.get("total_agents", 0)

        return {
            "status": "diff_computed",
            "prev_snapshot_at": prev.get("snapshot_at", "unknown"),
            "curr_snapshot_at": current.get("snapshot_at", "unknown"),
            "prev_total_agents": prev_total,
            "curr_total_agents": curr_total,
            "total_changes": len(changes),
            "is_major_change": any(
                c["type"] in ("dept_added", "dept_removed", "agent_added", "agent_removed")
                for c in changes
            ),
            "changes": changes,
        }


def run_scan() -> dict[str, Any]:
    """Convenience: run scan, save, return snapshot."""
    scanner = OrgScanner()
    snapshot = scanner.scan()
    scanner.save_snapshot(snapshot)
    return snapshot


def get_diff() -> dict[str, Any]:
    """Convenience: run scan and compute diff."""
    scanner = OrgScanner()
    snapshot = scanner.scan()
    diff = scanner.compute_diff(snapshot)
    scanner.save_snapshot(snapshot)
    return diff


if __name__ == "__main__":
    snapshot = run_scan()
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
