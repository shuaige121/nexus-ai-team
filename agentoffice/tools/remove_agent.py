"""Tool: Remove an agent and clean up all references."""

from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime

from agentoffice.config import AGENTS_DIR, ARCHIVED_DIR
from agentoffice.tools.org_utils import load_org, save_org

logger = logging.getLogger(__name__)


def remove_agent(agent_id: str) -> dict:
    """Remove an agent: archive memory, delete folder, clean org.yaml.

    Steps:
        1. Archive memory.md to /archived/
        2. Delete /agents/{agent_id}/ folder
        3. Remove from org.yaml departments.positions
        4. Remove from chain_of_command
        5. Remove from all superiors' can_command lists

    Returns dict with status and details.
    """
    # Prevent removing core agents
    if agent_id in ("ceo", "hr_lead"):
        msg = f"Cannot remove core agent '{agent_id}'"
        logger.warning(msg)
        return {"status": "error", "message": msg}

    agent_dir = AGENTS_DIR / agent_id
    if not agent_dir.exists():
        msg = f"Agent '{agent_id}' not found at {agent_dir}"
        logger.warning(msg)
        return {"status": "error", "message": msg}

    # 1. Archive memory.md
    memory_file = agent_dir / "memory.md"
    if memory_file.exists():
        ARCHIVED_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        archive_name = f"{agent_id}_memory_{timestamp}.md"
        shutil.copy2(memory_file, ARCHIVED_DIR / archive_name)
        logger.info("Archived memory for '%s' to '%s'", agent_id, archive_name)

    # 2. Delete agent folder
    shutil.rmtree(agent_dir)
    logger.info("Deleted agent folder '%s'", agent_dir)

    # 3-5. Clean org.yaml
    org = load_org()

    # Remove from departments
    for dept in org["departments"]:
        positions = dept.get("positions", [])
        if agent_id in positions:
            positions.remove(agent_id)

    # Remove from chain_of_command
    org["chain_of_command"].pop(agent_id, None)

    # Remove from all can_command lists
    for _aid, chain in org["chain_of_command"].items():
        if agent_id in chain.get("can_command", []):
            chain["can_command"].remove(agent_id)

    save_org(org)
    logger.info("Cleaned org.yaml references for '%s'", agent_id)
    return {"status": "ok", "agent_id": agent_id}
