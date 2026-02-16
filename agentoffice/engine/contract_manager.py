"""Contract management — create, load, save, and archive contracts."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from agentoffice.config import ARCHIVED_DIR, COMPLETED_DIR, PENDING_DIR

logger = logging.getLogger(__name__)


def generate_contract_id() -> str:
    """Generate a unique contract ID."""
    ts = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    return f"c_{ts}_{short_uuid}"


def create_contract(
    from_agent: str,
    to_agent: str,
    contract_type: str,
    priority: str = "medium",
    payload: dict[str, Any] | None = None,
    chain: dict[str, Any] | None = None,
) -> dict:
    """Create a new contract and save to pending directory.

    Returns the full contract dict.
    """
    contract_id = generate_contract_id()
    now = datetime.now(UTC).isoformat()

    contract: dict[str, Any] = {
        "contract_id": contract_id,
        "from": from_agent,
        "to": to_agent,
        "type": contract_type,
        "priority": priority,
        "created_at": now,
        "payload": payload or {},
        "chain": chain or {
            "on_complete": {
                "action": "send_contract",
                "to": from_agent,
                "type": "report",
            },
            "on_fail": {
                "action": "send_contract",
                "to": from_agent,
                "type": "escalation",
            },
            "on_revision": {
                "action": "send_contract",
                "to": to_agent,
                "type": "revision",
            },
        },
    }

    # Save to pending
    save_contract(contract, PENDING_DIR)
    logger.info(
        "Created contract %s: %s → %s (type=%s)",
        contract_id, from_agent, to_agent, contract_type,
    )
    return contract


def save_contract(contract: dict, directory: Path) -> Path:
    """Save a contract YAML to the specified directory."""
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / f"{contract['contract_id']}.yaml"
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(contract, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return file_path


def load_contract(contract_id: str) -> dict | None:
    """Load a contract by ID, searching pending, completed, archived."""
    for directory in [PENDING_DIR, COMPLETED_DIR, ARCHIVED_DIR]:
        file_path = directory / f"{contract_id}.yaml"
        if file_path.exists():
            with open(file_path, encoding="utf-8") as f:
                return yaml.safe_load(f)
    return None


def load_pending_contracts(agent_id: str | None = None) -> list[dict]:
    """Load all pending contracts, optionally filtered by target agent."""
    contracts = []
    if not PENDING_DIR.exists():
        return contracts

    for file_path in sorted(PENDING_DIR.glob("*.yaml")):
        with open(file_path, encoding="utf-8") as f:
            contract = yaml.safe_load(f)
            if contract and (agent_id is None or contract.get("to") == agent_id):
                contracts.append(contract)
    return contracts


def complete_contract(contract_id: str) -> bool:
    """Move a contract from pending to completed."""
    return _move_contract(contract_id, PENDING_DIR, COMPLETED_DIR)


def archive_contract(contract_id: str) -> bool:
    """Move a contract from completed to archived."""
    return _move_contract(contract_id, COMPLETED_DIR, ARCHIVED_DIR)


def _move_contract(contract_id: str, from_dir: Path, to_dir: Path) -> bool:
    """Move a contract file between directories."""
    source = from_dir / f"{contract_id}.yaml"
    if not source.exists():
        logger.warning("Contract file not found: %s", source)
        return False

    to_dir.mkdir(parents=True, exist_ok=True)
    dest = to_dir / f"{contract_id}.yaml"
    source.rename(dest)
    logger.info("Moved contract %s: %s → %s", contract_id, from_dir.name, to_dir.name)
    return True
