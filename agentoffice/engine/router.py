"""Contract router — delivers contracts to target agents and triggers activation.

The router reads the 'to' field of a contract, verifies the target agent exists,
and calls activate(). It also handles the special 'board' target (return to user).
"""

from __future__ import annotations

import logging

from agentoffice.config import AGENTS_DIR
from agentoffice.engine.contract_manager import load_pending_contracts

logger = logging.getLogger(__name__)


def route_contract(contract: dict, activate_fn: object = None) -> dict:
    """Route a contract to its target agent.

    Args:
        contract: The contract dict to route.
        activate_fn: The activate function to call (injected to avoid circular imports).

    Returns:
        Result dict with status and any output.
    """
    target = contract.get("to")

    if not target:
        logger.error("Contract %s has no 'to' field", contract.get("contract_id"))
        return {"status": "error", "message": "Contract missing 'to' field"}

    # Terminal: contract goes to the board (user)
    if target == "board":
        logger.info(
            "Contract %s delivered to board (user). Payload: %s",
            contract.get("contract_id"),
            contract.get("payload", {}),
        )
        return {
            "status": "delivered_to_board",
            "contract_id": contract.get("contract_id"),
            "payload": contract.get("payload", {}),
        }

    # Verify target agent exists
    agent_dir = AGENTS_DIR / target
    if not agent_dir.exists():
        logger.error(
            "Target agent '%s' not found for contract %s",
            target, contract.get("contract_id"),
        )
        return {
            "status": "error",
            "message": f"Target agent '{target}' does not exist",
            "contract_id": contract.get("contract_id"),
        }

    # Activate the target agent
    if activate_fn is None:
        # Lazy import to avoid circular dependency
        from agentoffice.engine.activate import activate
        activate_fn = activate

    logger.info("Routing contract %s to agent '%s'", contract.get("contract_id"), target)
    return activate_fn(target, contract)


def process_pending_contracts(agent_id: str | None = None) -> list[dict]:
    """Process all pending contracts for an agent (or all agents).

    Returns list of results.
    """
    contracts = load_pending_contracts(agent_id)
    results = []

    for contract in contracts:
        result = route_contract(contract)
        results.append(result)

    return results
