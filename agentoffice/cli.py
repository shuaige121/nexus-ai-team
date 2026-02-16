"""AgentOffice CLI — entry point for interacting with the AI company.

The user (board/董事会) sends instructions to the CEO, triggering the
chain of agent activations.

Usage:
    python -m agentoffice.cli "调研新加坡私人司机市场"
    python -m agentoffice.cli --interactive
    python -m agentoffice.cli --status
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

from agentoffice.config import (
    AGENTS_DIR,
    CONTRACT_TASK,
    PRIORITY_HIGH,
)
from agentoffice.engine.activate import activate
from agentoffice.engine.contract_manager import create_contract, load_pending_contracts
from agentoffice.tools.org_utils import load_org


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)


def send_to_ceo(instruction: str, priority: str = PRIORITY_HIGH) -> dict[str, Any]:
    """Send a user instruction to the CEO as a task contract.

    This is the main entry point: user → CEO → chain of agents.
    """
    contract = create_contract(
        from_agent="board",
        to_agent="ceo",
        contract_type=CONTRACT_TASK,
        priority=priority,
        payload={
            "objective": instruction,
            "acceptance_criteria": ["按用户要求完成"],
            "deadline": "",
            "attachments": [],
        },
    )

    print(f"\n📋 Contract {contract['contract_id']} created: board → ceo")
    print(f"   Objective: {instruction}\n")

    result = activate("ceo", contract)
    return result


def show_status() -> None:
    """Display current company status: org structure, pending contracts, agents."""
    org = load_org()

    print("\n=== NEXUS Corp Status ===\n")
    print(f"Company: {org['company']['name']}")
    print(f"Board: {org['company']['board']}")

    print("\n--- Departments ---")
    for dept in org.get("departments", []):
        positions = dept.get("positions", [])
        print(f"  {dept['name']} ({dept['id']}): {', '.join(positions)}")

    print("\n--- Chain of Command ---")
    for agent_id, chain in org.get("chain_of_command", {}).items():
        reports_to = chain.get("reports_to", "?")
        commands = chain.get("can_command", [])
        cmd_str = f" → commands: {', '.join(commands)}" if commands else ""
        print(f"  {agent_id} → reports to: {reports_to}{cmd_str}")

    print("\n--- Active Agents ---")
    if AGENTS_DIR.exists():
        for agent_dir in sorted(AGENTS_DIR.iterdir()):
            if agent_dir.is_dir():
                race_file = agent_dir / "race.yaml"
                if race_file.exists():
                    import yaml
                    with open(race_file, encoding="utf-8") as f:
                        race = yaml.safe_load(f)
                    mdl = race.get("model", "?")
                    prv = race.get("provider", "?")
                    print(f"  {agent_dir.name}: {mdl} ({prv})")
                else:
                    print(f"  {agent_dir.name}: (no race.yaml)")

    pending = load_pending_contracts()
    print(f"\n--- Pending Contracts: {len(pending)} ---")
    for c in pending[:10]:
        print(f"  {c.get('contract_id')}: {c.get('from')} → {c.get('to')} ({c.get('type')})")


def print_result(result: dict, indent: int = 0) -> None:
    """Pretty-print an activation result."""
    prefix = "  " * indent

    status = result.get("status", "unknown")
    agent_id = result.get("agent_id", "?")

    if status == "delivered_to_board":
        print(f"\n{'=' * 60}")
        print("📬 FINAL REPORT TO BOARD (USER)")
        print(f"{'=' * 60}")
        payload = result.get("payload", {})
        if isinstance(payload, dict):
            fallback = json.dumps(payload, ensure_ascii=False, indent=2)
            output = payload.get("output", payload.get("summary", fallback))
            print(output)
        else:
            print(payload)
        print(f"{'=' * 60}\n")
        return

    if status == "error":
        print(f"{prefix}❌ Error at {agent_id}: {result.get('message', 'unknown error')}")
        return

    choice = result.get("choice", "?")
    action = result.get("action", {})
    summary = action.get("summary", "")
    token_usage = result.get("token_usage", {})

    print(f"{prefix}✅ {agent_id} → choice: {choice}")
    if summary:
        print(f"{prefix}   Summary: {summary}")
    if token_usage:
        in_tok = token_usage.get("input_tokens", 0)
        out_tok = token_usage.get("output_tokens", 0)
        print(f"{prefix}   Tokens: {in_tok} in / {out_tok} out")

    # Tool results
    for tr in result.get("tool_results", []):
        tool_status = "✅" if tr.get("status") == "ok" else "❌"
        print(f"{prefix}   {tool_status} Tool: {tr.get('tool', '?')}")

    # Chain result
    chain_result = result.get("chain_result")
    if chain_result:
        print_result(chain_result, indent + 1)


def interactive_mode() -> None:
    """Run in interactive mode: user types instructions, CEO processes them."""
    print("\n🏢 NEXUS Corp — AgentOffice Interactive Mode")
    print("Type your instructions (Ctrl+C to exit)\n")

    while True:
        try:
            instruction = input("董事会> ").strip()
            if not instruction:
                continue
            if instruction.lower() in ("exit", "quit", "q"):
                break
            if instruction.lower() == "status":
                show_status()
                continue

            result = send_to_ceo(instruction)
            print_result(result)

        except KeyboardInterrupt:
            print("\n\n👋 Session ended.")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            logging.getLogger(__name__).exception("Unhandled error in interactive mode")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AgentOffice — AI Virtual Company Operating System",
    )
    parser.add_argument(
        "instruction",
        nargs="?",
        help="Instruction to send to the CEO",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode",
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show current company status",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--priority", "-p",
        choices=["high", "medium", "low"],
        default="high",
        help="Priority for the task (default: high)",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.status:
        show_status()
        return

    if args.interactive:
        interactive_mode()
        return

    if args.instruction:
        result = send_to_ceo(args.instruction, args.priority)
        print_result(result)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
