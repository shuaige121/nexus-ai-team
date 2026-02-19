"""Orchestrator API routes for NEXUS Gateway.

Provides REST endpoints for creating and querying LangGraph contracts.
Uses asyncio.Semaphore to limit parallel contract execution.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from nexus.orchestrator.llm_config import MAX_PARALLEL_CONTRACTS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contracts", tags=["contracts"])

# ---------------------------------------------------------------------------
# Parallel execution limiter
# ---------------------------------------------------------------------------
# Semaphore limits how many contracts run concurrently.
# Requests exceeding MAX_PARALLEL_CONTRACTS will queue in FIFO order.
_parallel_semaphore = asyncio.Semaphore(MAX_PARALLEL_CONTRACTS)

# ---------------------------------------------------------------------------
# In-memory contract tracking (for async submit + poll)
# ---------------------------------------------------------------------------

_contract_status: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ContractRequest(BaseModel):
    """Request body for creating a new contract."""

    task_description: str = Field(..., min_length=1, max_length=10000)
    priority: str = Field(default="medium", pattern=r"^(low|medium|high|critical)$")
    department: str = Field(default="IT")
    max_attempts: int = Field(default=3, ge=1, le=10)
    # Approval routing fields
    approver_type: str = Field(default="ai", pattern=r"^(ai|human)$")
    approver_id: str = Field(default="ai_ceo")
    cc_list: list[str] = Field(default_factory=list)


class ContractResponse(BaseModel):
    """Response after creating or querying a contract."""

    contract_id: str
    status: str
    current_phase: str


# ---------------------------------------------------------------------------
# Background graph runner (with semaphore-based parallel limit)
# ---------------------------------------------------------------------------


def _run_graph_sync(
    contract_id: str,
    graph,
    initial_state: dict,
    config: dict,
) -> None:
    """Run graph.stream() synchronously, updating _contract_status."""
    try:
        _contract_status[contract_id]["status"] = "running"
        final_state = None

        for event in graph.stream(initial_state, config=config, stream_mode="updates"):
            for node_name, node_output in event.items():
                logger.debug("[CONTRACT] %s node %s completed", contract_id, node_name)
                _contract_status[contract_id]["current_phase"] = node_name
                _contract_status[contract_id]["steps"].append(node_name)
                final_state = node_output

        # Retrieve authoritative final state from checkpointer
        result = graph.get_state(config).values

        status = "in_progress"
        if result.get("ceo_approved"):
            status = "completed"
        elif result.get("escalated"):
            status = "escalated"

        _contract_status[contract_id].update({
            "status": status,
            "current_phase": result.get("current_phase", "unknown"),
            "final_state": result,
        })
        logger.info("[CONTRACT] %s finished with status=%s", contract_id, status)

    except Exception as exc:
        logger.exception("[CONTRACT] %s failed: %s", contract_id, exc)
        _contract_status[contract_id].update({
            "status": "error",
            "error": str(exc),
        })


async def _run_graph_background(
    contract_id: str,
    graph,
    initial_state: dict,
    config: dict,
) -> None:
    """Acquire semaphore slot, then run graph in a thread.

    If all slots are occupied, this coroutine waits (queues) until a
    slot becomes available.  This enforces MAX_PARALLEL_CONTRACTS.
    """
    _contract_status[contract_id]["status"] = "queued"
    logger.info(
        "[CONTRACT] %s waiting for execution slot (max_parallel=%d)",
        contract_id, MAX_PARALLEL_CONTRACTS,
    )

    async with _parallel_semaphore:
        logger.info("[CONTRACT] %s acquired execution slot", contract_id)
        # Run the blocking graph.stream() in a thread so we don't block the event loop
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, _run_graph_sync, contract_id, graph, initial_state, config,
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/", status_code=202)
async def create_contract(req: ContractRequest):
    """CEO creates a new contract and kicks off the graph in the background.

    Execution is limited to MAX_PARALLEL_CONTRACTS concurrent contracts.
    Requests beyond this limit are queued in FIFO order.
    """
    from nexus.orchestrator.checkpoint import get_checkpointer
    from nexus.orchestrator.graph import build_graph

    contract_id = f"CTR-{uuid.uuid4().hex[:8].upper()}"
    initial_state = {
        "contract_id": contract_id,
        "task_description": req.task_description,
        "priority": req.priority,
        "department": req.department,
        "current_phase": "ceo_dispatch",
        "worker_output": "",
        "qa_verdict": "",
        "qa_report": "",
        "attempt_count": 0,
        "max_attempts": req.max_attempts,
        "subtasks": [],
        "manager_instruction": "",
        "mail_log": [],
        "mail_rejections": [],
        "final_result": "",
        "ceo_approved": False,
        "escalated": False,
        # Ownership fields
        "contract_accepted": None,
        "reject_reason": "",
        "acceptance_deadline": "",
        # DoubleCheck fields
        "check_after_seconds": None,
        "check_count": 0,
        "max_checks": 3,
        "last_check_time": "",
        "check_result": "",
        # Approval fields
        "approval_request_id": "",
        "approval_status": "",
        "approval_rejection_notes": "",
        "approver_type": req.approver_type,
        "approver_id": req.approver_id,
        "approval_cc_list": req.cc_list,
    }

    logger.info("[CONTRACT] Creating contract %s: %s", contract_id, req.task_description[:80])

    checkpointer = get_checkpointer()
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": contract_id}}

    # Track contract
    _contract_status[contract_id] = {
        "status": "queued",
        "current_phase": "ceo_dispatch",
        "steps": [],
    }

    # Schedule graph execution with parallel limiting (fire-and-forget)
    asyncio.create_task(
        _run_graph_background(contract_id, graph, initial_state, config)
    )

    return JSONResponse(
        status_code=202,
        content={
            "contract_id": contract_id,
            "status": "queued",
            "current_phase": "ceo_dispatch",
        },
    )


@router.get("/")
async def list_contracts():
    """List all known contracts (in-memory + checkpointed)."""
    from nexus.orchestrator.checkpoint import get_checkpointer
    from nexus.orchestrator.graph import build_graph

    contracts = []

    # 1. In-memory tracked contracts
    for cid, info in _contract_status.items():
        contracts.append({
            "contract_id": cid,
            "status": info.get("status", "unknown"),
            "current_phase": info.get("current_phase", "unknown"),
        })

    # 2. Check checkpointer for persisted contracts not in memory
    try:
        checkpointer = get_checkpointer()
        graph = build_graph(checkpointer=checkpointer)
        if hasattr(checkpointer, "list"):
            in_memory_ids = set(_contract_status.keys())
            for checkpoint_tuple in checkpointer.list(None):
                thread_id = checkpoint_tuple.config.get("configurable", {}).get("thread_id", "")
                if thread_id and thread_id not in in_memory_ids:
                    config = {"configurable": {"thread_id": thread_id}}
                    state = graph.get_state(config)
                    if state and state.values:
                        status = "in_progress"
                        if state.values.get("ceo_approved"):
                            status = "completed"
                        elif state.values.get("escalated"):
                            status = "escalated"
                        contracts.append({
                            "contract_id": thread_id,
                            "status": status,
                            "current_phase": state.values.get("current_phase", "unknown"),
                        })
    except Exception as exc:
        logger.warning("[CONTRACT] Could not list checkpointed contracts: %s", exc)

    return contracts


@router.get("/{contract_id}", response_model=dict)
async def get_contract_status(contract_id: str):
    """Get the current state of a contract (filtered to safe fields)."""
    from nexus.orchestrator.checkpoint import get_checkpointer
    from nexus.orchestrator.graph import build_graph

    safe_fields = [
        "contract_id", "task_description", "current_phase", "qa_verdict",
        "qa_report", "attempt_count", "ceo_approved", "approval_status",
        "final_result", "subtasks", "escalated", "priority", "department",
    ]

    # Check in-memory status first (may not be checkpointed yet)
    in_memory = _contract_status.get(contract_id)

    checkpointer = get_checkpointer()
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": contract_id}}

    state = graph.get_state(config)

    if state and state.values:
        # Checkpointed state exists — filter to safe fields
        result = {k: state.values.get(k) for k in safe_fields if state.values.get(k) is not None}
        # Overlay runtime tracking info
        if in_memory:
            result["status"] = in_memory.get("status", "unknown")
            result["steps"] = in_memory.get("steps", [])
            if in_memory.get("error"):
                result["error"] = in_memory["error"]
        else:
            status = "in_progress"
            if state.values.get("ceo_approved"):
                status = "completed"
            elif state.values.get("escalated"):
                status = "escalated"
            result["status"] = status
        return result

    # Not checkpointed yet — return in-memory tracking if available
    if in_memory:
        return {
            "contract_id": contract_id,
            "status": in_memory.get("status", "unknown"),
            "current_phase": in_memory.get("current_phase", "unknown"),
            "steps": in_memory.get("steps", []),
            **({"error": in_memory["error"]} if in_memory.get("error") else {}),
        }

    raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")


@router.delete("/{contract_id}")
async def cancel_contract(contract_id: str):
    """Cancel a running contract."""
    if contract_id not in _contract_status:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found in active contracts")

    current = _contract_status[contract_id]
    if current.get("status") in ("completed", "error", "cancelled"):
        return {"contract_id": contract_id, "status": current["status"], "message": "Contract already finished"}

    _contract_status[contract_id]["status"] = "cancelled"
    logger.info("[CONTRACT] %s marked as cancelled", contract_id)

    return {"contract_id": contract_id, "status": "cancelled"}


@router.get("/{contract_id}/logs")
async def get_contract_logs(contract_id: str):
    """Return the mail_log for a contract."""
    from nexus.orchestrator.checkpoint import get_checkpointer
    from nexus.orchestrator.graph import build_graph

    checkpointer = get_checkpointer()
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": contract_id}}

    state = graph.get_state(config)
    if not state or not state.values:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")

    return {"contract_id": contract_id, "mail_log": state.values.get("mail_log", [])}
