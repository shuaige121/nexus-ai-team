"""Tool: Update chain of command for an agent in org.yaml."""

from __future__ import annotations

import logging

from agentoffice.tools.org_utils import load_org, save_org

logger = logging.getLogger(__name__)


def update_chain(
    agent_id: str,
    reports_to: str | None = None,
    can_command: list[str] | None = None,
    authority: list[str] | None = None,
) -> dict:
    """Update chain_of_command entry for an agent.

    Only updates fields that are provided (non-None).
    Also updates the superior's can_command list if reports_to changes.

    Returns dict with status and details.
    """
    org = load_org()

    if agent_id not in org["chain_of_command"]:
        msg = f"Agent '{agent_id}' not found in chain_of_command"
        logger.warning(msg)
        return {"status": "error", "message": msg}

    chain_entry = org["chain_of_command"][agent_id]
    old_reports_to = chain_entry.get("reports_to")

    if reports_to is not None:
        # Remove from old superior's can_command
        if old_reports_to and old_reports_to in org["chain_of_command"]:
            old_superior = org["chain_of_command"][old_reports_to]
            if agent_id in old_superior.get("can_command", []):
                old_superior["can_command"].remove(agent_id)

        chain_entry["reports_to"] = reports_to

        # Add to new superior's can_command
        if reports_to in org["chain_of_command"]:
            new_superior = org["chain_of_command"][reports_to]
            if agent_id not in new_superior.get("can_command", []):
                new_superior.setdefault("can_command", []).append(agent_id)

    if can_command is not None:
        chain_entry["can_command"] = can_command

    if authority is not None:
        chain_entry["authority"] = authority

    save_org(org)
    logger.info("Updated chain_of_command for '%s'", agent_id)
    return {
        "status": "ok",
        "agent_id": agent_id,
        "chain": chain_entry,
    }
