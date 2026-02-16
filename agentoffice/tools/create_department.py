"""Tool: Create a new department in org.yaml."""

from __future__ import annotations

import logging

from agentoffice.tools.org_utils import load_org, save_org

logger = logging.getLogger(__name__)


def create_department(
    department_id: str,
    department_name: str,
    head_position: str,
) -> dict:
    """Add a new department to org.yaml.

    Steps:
        1. Add department entry to departments list
        2. Add head_position to chain_of_command (reports_to ceo)
        3. Add head_position to CEO's can_command list

    Returns dict with status and details.
    """
    org = load_org()

    # Check if department already exists
    for dept in org["departments"]:
        if dept["id"] == department_id:
            msg = f"Department '{department_id}' already exists"
            logger.warning(msg)
            return {"status": "error", "message": msg}

    # 1. Add department
    org["departments"].append({
        "id": department_id,
        "name": department_name,
        "positions": [head_position],
    })

    # 2. Add head to chain_of_command
    if head_position not in org["chain_of_command"]:
        org["chain_of_command"][head_position] = {
            "reports_to": "ceo",
            "can_command": [],
            "authority": [],
        }

    # 3. Add to CEO's can_command
    ceo_chain = org["chain_of_command"].get("ceo", {})
    if head_position not in ceo_chain.get("can_command", []):
        ceo_chain.setdefault("can_command", []).append(head_position)

    save_org(org)
    logger.info("Created department '%s' with head '%s'", department_id, head_position)
    return {
        "status": "ok",
        "department_id": department_id,
        "head_position": head_position,
    }
