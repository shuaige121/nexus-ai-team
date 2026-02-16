"""Activate — the core runtime loop that brings an agent to life.

When an agent receives a contract:
1. Load agent files (jd + resume + memory + race)
2. Build prompt via prompt_builder (with context isolation)
3. Call LLM via llm_client
4. Parse response (action, memory_update, choice, choice_payload, tool_calls)
5. Write back memory
6. Execute tool_calls (deterministic, zero LLM)
7. Convert choice → contract via choice_handlers
8. Route the new contract → recursive activation

NOTE: Current implementation is synchronous/sequential. When CEO dispatches
tasks to multiple Managers, they execute one at a time. Async/parallel
activation (e.g. asyncio.gather for independent subtasks) is planned for
a future iteration.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agentoffice.config import (
    AGENTS_DIR,
    LEVEL_CEO,
    LEVEL_MANAGER,
    LEVEL_QA_WORKER,
    LEVEL_WORKER,
    MEMORY_CHAR_LIMIT,
    MEMORY_FILE,
)
from agentoffice.engine.choice_handlers import (
    get_choices_for_agent,
    resolve_choice_target,
)
from agentoffice.engine.contract_manager import complete_contract, create_contract
from agentoffice.engine.llm_client import call_llm
from agentoffice.engine.prompt_builder import build_prompt
from agentoffice.tools.compress_memory import compress_memory

logger = logging.getLogger(__name__)

# Maximum chain depth to prevent infinite loops
MAX_CHAIN_DEPTH = 20


def activate(
    agent_id: str,
    contract: dict,
    depth: int = 0,
) -> dict:
    """Activate an agent with a contract. Core runtime loop.

    Args:
        agent_id: The agent to activate.
        contract: The contract triggering this activation.
        depth: Current chain depth (for loop prevention).

    Returns:
        Result dict with the agent's output and any chain results.
    """
    if depth >= MAX_CHAIN_DEPTH:
        logger.error("Max chain depth (%d) reached at agent '%s'", MAX_CHAIN_DEPTH, agent_id)
        return {
            "status": "error",
            "message": f"Max chain depth ({MAX_CHAIN_DEPTH}) reached",
            "agent_id": agent_id,
        }

    logger.info("=== Activating agent '%s' (depth=%d) ===", agent_id, depth)

    # 0. Determine agent level
    level = _determine_level(agent_id)

    # 1. Build prompt (with context isolation)
    system_prompt, user_message = build_prompt(agent_id, level, contract)

    # 2. Call LLM
    response = call_llm(agent_id, system_prompt, user_message)

    # 3. Validate choice
    choice = response.get("choice")
    contract_type = contract.get("type")
    valid_choices = get_choices_for_agent(agent_id, level, contract_type)

    if not choice or choice not in valid_choices:
        logger.warning(
            "Agent '%s' returned invalid choice '%s'. Forcing re-choice.",
            agent_id, choice,
        )
        response = _force_choice(agent_id, level, contract, response)
        choice = response.get("choice")

        # If still invalid after retry, use first available choice
        if not choice or choice not in valid_choices:
            choice = next(iter(valid_choices))
            logger.warning("Falling back to default choice '%s' for agent '%s'", choice, agent_id)

    choice_def = valid_choices[choice]
    choice_payload = response.get("choice_payload", {})
    action = response.get("action", {})
    token_usage = response.get("_token_usage", {})

    logger.info(
        "Agent '%s' chose '%s': %s",
        agent_id, choice, choice_def.get("label", ""),
    )

    # 4. Write back memory
    memory_update = response.get("memory_update")
    if memory_update:
        _write_memory(agent_id, memory_update)

    # 5. Execute tool_calls (deterministic)
    tool_results = []
    for tool_call in response.get("tool_calls", []):
        result = _execute_tool_call(tool_call)
        tool_results.append(result)

    # 6. Mark current contract as completed
    if contract.get("contract_id"):
        complete_contract(contract["contract_id"])

    # 7. Convert choice → new contract and route
    chain_result = None
    target = resolve_choice_target(agent_id, choice, choice_def, choice_payload, contract)

    if target and choice_def.get("contract_type"):
        # Build payload for the new contract
        new_payload = _build_contract_payload(action, choice_payload, contract)

        new_contract = create_contract(
            from_agent=agent_id,
            to_agent=target,
            contract_type=choice_def["contract_type"],
            priority=contract.get("priority", "medium"),
            payload=new_payload,
        )

        # Route (recursive activation)
        if target != "board":
            from agentoffice.engine.router import route_contract
            def _chain_activate(aid, c):
                return activate(aid, c, depth + 1)
            chain_result = route_contract(new_contract, activate_fn=_chain_activate)
        else:
            chain_result = {
                "status": "delivered_to_board",
                "contract_id": new_contract["contract_id"],
                "payload": new_payload,
            }

    return {
        "status": "ok",
        "agent_id": agent_id,
        "choice": choice,
        "action": action,
        "tool_results": tool_results,
        "token_usage": token_usage,
        "chain_result": chain_result,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _determine_level(agent_id: str) -> str:
    """Determine an agent's level from org.yaml or jd.md."""
    from agentoffice.tools.org_utils import load_org

    # Special cases
    if agent_id == "ceo":
        return LEVEL_CEO

    org = load_org()
    chain = org.get("chain_of_command", {}).get(agent_id, {})

    # If it can command others, it's a manager
    if chain.get("can_command"):
        return LEVEL_MANAGER

    # Check jd.md for level field
    jd_path = AGENTS_DIR / agent_id / "jd.md"
    if jd_path.exists():
        content = jd_path.read_text(encoding="utf-8")
        if "qa_worker" in content.lower():
            return LEVEL_QA_WORKER
        for line in content.split("\n"):
            if "**级别**" in line:
                val = line.split(":", 1)[-1].strip().lower()
                if val in (LEVEL_CEO, LEVEL_MANAGER, LEVEL_WORKER, LEVEL_QA_WORKER):
                    return val

    return LEVEL_WORKER


def _force_choice(
    agent_id: str,
    level: str,
    contract: dict,
    previous_response: dict,
) -> dict:
    """Re-call LLM with only the choice question, no full context."""
    from agentoffice.engine.choice_handlers import format_choices_prompt

    contract_type = contract.get("type")
    choices = get_choices_for_agent(agent_id, level, contract_type)
    choices_prompt = format_choices_prompt(choices, agent_id)

    action_summary = previous_response.get("action", {}).get("summary", "（已完成工作）")

    force_prompt = (
        f"你已完成工作：{action_summary}\n\n"
        f"但你没有做出有效选择。请现在从以下选项中选择一个，只返回JSON：\n"
        f'{{"choice": "选项ID", "choice_payload": {{}}}}\n\n'
        f"{choices_prompt}"
    )

    response = call_llm(
        agent_id,
        "你必须从选择题中选一个选项。只返回JSON。",
        force_prompt,
    )

    # Merge with previous response (keep action, update choice)
    previous_response["choice"] = response.get("choice")
    previous_response["choice_payload"] = response.get("choice_payload", {})
    return previous_response


def _write_memory(agent_id: str, memory_content: str) -> None:
    """Write updated memory and compress if needed."""
    memory_path = AGENTS_DIR / agent_id / MEMORY_FILE

    # Ensure content starts with the expected header
    if not memory_content.strip().startswith("# 工作记忆"):
        memory_content = "# 工作记忆 (Working Memory)\n\n" + memory_content

    memory_path.write_text(memory_content, encoding="utf-8")

    # Compress if over limit
    if len(memory_content) > MEMORY_CHAR_LIMIT:
        compress_memory(agent_id)


def _execute_tool_call(tool_call: dict) -> dict:
    """Execute a single tool call deterministically.

    Maps tool names to actual functions. Zero LLM involvement.
    """
    tool_name = tool_call.get("tool", "")
    params = tool_call.get("params", {})

    logger.info("Executing tool: %s(%s)", tool_name, json.dumps(params, ensure_ascii=False)[:200])

    tool_map = _get_tool_map()

    if tool_name not in tool_map:
        logger.error("Unknown tool: %s", tool_name)
        return {"status": "error", "tool": tool_name, "message": f"Unknown tool: {tool_name}"}

    try:
        result = tool_map[tool_name](**params)
        return {"status": "ok", "tool": tool_name, "result": result}
    except Exception as e:
        logger.exception("Tool '%s' failed", tool_name)
        return {"status": "error", "tool": tool_name, "message": str(e)}


def _get_tool_map() -> dict:
    """Lazy-load the tool function mapping."""
    from agentoffice.tools.create_agent import create_agent
    from agentoffice.tools.create_department import create_department
    from agentoffice.tools.remove_agent import remove_agent
    from agentoffice.tools.remove_department import remove_department
    from agentoffice.tools.update_chain import update_chain

    return {
        "create_agent": create_agent,
        "remove_agent": remove_agent,
        "create_department": create_department,
        "remove_department": remove_department,
        "update_chain": update_chain,
    }


def _build_contract_payload(
    action: dict,
    choice_payload: dict,
    source_contract: dict,
) -> dict:
    """Build the payload for a new contract from action output and choice payload."""
    payload: dict[str, Any] = {}

    # Include summary from choice_payload or action
    payload["summary"] = choice_payload.get("summary", action.get("summary", ""))

    # Include output if present
    if action.get("output"):
        payload["output"] = action["output"]

    # Include any additional fields from choice_payload
    for key, value in choice_payload.items():
        if key not in ("to", "summary"):
            payload[key] = value

    # Reference the source contract
    payload["source_contract_id"] = source_contract.get("contract_id")

    return payload
