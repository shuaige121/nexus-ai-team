"""Agent Router — Routes tasks to the correct agent based on department and task type.

Reads agents/registry.yaml to build a routing table, then matches incoming
tasks to the most appropriate agent.  Supports fallback to other members
in the same department when the primary agent is unavailable.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project root (two levels up from gateway/)
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Task-type -> department mapping (extensible)
# ---------------------------------------------------------------------------

TASK_DEPARTMENT_MAP: dict[str, str] = {
    # Engineering
    "code": "engineering",
    "implement": "engineering",
    "refactor": "engineering",
    "build": "engineering",
    "deploy": "engineering",
    "frontend": "engineering",
    "backend": "engineering",
    "devops": "engineering",
    "infra": "engineering",
    "ci": "engineering",
    "cd": "engineering",
    # QA
    "test": "qa",
    "qa": "qa",
    "bug": "qa",
    "regression": "qa",
    "uat": "qa",
    # Product
    "design": "product",
    "ui": "product",
    "ux": "product",
    "feature": "product",
    "roadmap": "product",
    "spec": "product",
    # IT
    "security": "it",
    "audit": "it",
    "network": "it",
    "firewall": "it",
    "monitoring": "it",
    # HR
    "hire": "hr",
    "recruit": "hr",
    "onboard": "hr",
    "interview": "hr",
    # Executive
    "strategy": "executive",
    "report": "executive",
    "brief": "executive",
    "planning": "executive",
}

# Preferred role within each department (first match wins)
DEPARTMENT_ROLE_PRIORITY: dict[str, list[str]] = {
    "engineering": ["eng_manager", "backend_dev", "frontend_dev", "devops"],
    "qa": ["qa_lead", "qa_tester"],
    "product": ["pm", "designer"],
    "it": ["it_admin", "sec_analyst"],
    "hr": ["hr", "recruiter"],
    "executive": ["ceo", "exec_assistant"],
    "dept-gateway": ["dept-gw-manager", "dept-gw-dev-01", "dept-gw-qa"],
}


# ---------------------------------------------------------------------------
# AgentRouter
# ---------------------------------------------------------------------------


class AgentRouter:
    """Routes tasks to agents based on registry.yaml configuration."""

    def __init__(self, registry_path: str | Path | None = None) -> None:
        self.registry_path: Path = (
            Path(registry_path) if registry_path else PROJECT_ROOT / "agents" / "registry.yaml"
        )
        self.agents: dict[str, dict[str, Any]] = {}
        self.departments: dict[str, list[str]] = {}
        self._load_registry()

    # ── Loading ───────────────────────────────────────────────────────────

    def _load_registry(self) -> None:
        """Load and index agents/registry.yaml."""
        if not self.registry_path.exists():
            logger.warning("Agent registry not found: %s", self.registry_path)
            return

        try:
            with open(self.registry_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            logger.exception("Failed to parse agent registry")
            return

        raw_agents: dict[str, dict[str, Any]] = data.get("agents", {})
        self.agents = raw_agents

        # Build department -> [agent_id, ...] index
        dept_map: dict[str, list[str]] = {}
        for agent_id, info in raw_agents.items():
            dept = info.get("department", "unknown")
            dept_map.setdefault(dept, []).append(agent_id)
        self.departments = dept_map

        logger.info(
            "AgentRouter loaded %d agents across %d departments",
            len(self.agents),
            len(self.departments),
        )

    def reload(self) -> None:
        """Re-read the registry from disk."""
        self.agents.clear()
        self.departments.clear()
        self._load_registry()

    # ── Queries ───────────────────────────────────────────────────────────

    def get_active_agents(self) -> dict[str, dict[str, Any]]:
        """Return only agents with status == active."""
        return {
            aid: info
            for aid, info in self.agents.items()
            if info.get("status") == "active"
        }

    def get_department_members(self, department: str) -> list[str]:
        """Return agent IDs belonging to *department*."""
        return [
            aid
            for aid in self.departments.get(department, [])
            if self.agents.get(aid, {}).get("status") == "active"
        ]

    # ── Routing ───────────────────────────────────────────────────────────

    def infer_department(self, task_type: str) -> str | None:
        """Map a task-type keyword to a department name."""
        return TASK_DEPARTMENT_MAP.get(task_type.lower())

    def route(
        self,
        task_type: str,
        *,
        preferred_agent: str | None = None,
        exclude: set[str] | None = None,
    ) -> str | None:
        """Pick the best agent for a task.

        Resolution order:
        1. *preferred_agent* if it is active and not excluded.
        2. Highest-priority active agent in the target department.
        3. Fallback: any other active member in the same department.
        4. ``None`` if no candidate is found.

        Args:
            task_type: A keyword such as "code", "test", "deploy", etc.
            preferred_agent: Explicit agent ID the caller wants.
            exclude: Agent IDs to skip (e.g. already tried and failed).

        Returns:
            Agent ID or ``None``.
        """
        exclude = exclude or set()

        # If a specific agent is requested and available, use it.
        if preferred_agent and preferred_agent not in exclude:
            agent_info = self.agents.get(preferred_agent, {})
            if agent_info.get("status") == "active":
                return preferred_agent

        department = self.infer_department(task_type)
        if department is None:
            # Fall back to CEO for unrecognized task types
            if "ceo" not in exclude and self.agents.get("ceo", {}).get("status") == "active":
                return "ceo"
            return None

        # Try priority order
        for agent_id in DEPARTMENT_ROLE_PRIORITY.get(department, []):
            if agent_id in exclude:
                continue
            agent_info = self.agents.get(agent_id, {})
            if agent_info.get("status") == "active":
                return agent_id

        # Fallback: any active member in the department
        for agent_id in self.departments.get(department, []):
            if agent_id in exclude:
                continue
            if self.agents.get(agent_id, {}).get("status") == "active":
                return agent_id

        return None

    def route_to_department(self, department: str, *, exclude: set[str] | None = None) -> str | None:
        """Route directly to a department (skip task-type inference)."""
        exclude = exclude or set()
        for agent_id in DEPARTMENT_ROLE_PRIORITY.get(department, []):
            if agent_id in exclude:
                continue
            if self.agents.get(agent_id, {}).get("status") == "active":
                return agent_id

        for agent_id in self.departments.get(department, []):
            if agent_id in exclude:
                continue
            if self.agents.get(agent_id, {}).get("status") == "active":
                return agent_id

        return None
