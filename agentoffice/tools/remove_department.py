"""Tool: Remove a department and all its agents from org.yaml."""

from __future__ import annotations

import logging

from agentoffice.tools.org_utils import load_org, save_org
from agentoffice.tools.remove_agent import remove_agent

logger = logging.getLogger(__name__)


def remove_department(department_id: str) -> dict:
    """Remove a department and all agents within it.

    Steps:
        1. Find all positions in the department
        2. Remove each agent via remove_agent
        3. Remove department from departments list
        4. Clean up chain_of_command references

    Returns dict with status and details.
    """
    org = load_org()

    # Find the department
    target_dept = None
    for dept in org["departments"]:
        if dept["id"] == department_id:
            target_dept = dept
            break

    if target_dept is None:
        msg = f"Department '{department_id}' not found"
        logger.warning(msg)
        return {"status": "error", "message": msg}

    # Prevent removing core departments
    if department_id in ("executive", "hr"):
        msg = f"Cannot remove core department '{department_id}'"
        logger.warning(msg)
        return {"status": "error", "message": msg}

    # 1. Remove all agents in the department
    positions = list(target_dept.get("positions", []))
    removed_agents = []
    for position_id in positions:
        result = remove_agent(position_id)
        removed_agents.append({"agent_id": position_id, "result": result})

    # 2. Reload org (remove_agent may have modified it)
    org = load_org()

    # 3. Remove department entry
    org["departments"] = [d for d in org["departments"] if d["id"] != department_id]

    # 4. Remove from CEO's can_command
    ceo_chain = org["chain_of_command"].get("ceo", {})
    for position_id in positions:
        if position_id in ceo_chain.get("can_command", []):
            ceo_chain["can_command"].remove(position_id)

    save_org(org)
    logger.info("Removed department '%s' with %d agents", department_id, len(removed_agents))
    return {
        "status": "ok",
        "department_id": department_id,
        "removed_agents": removed_agents,
    }
