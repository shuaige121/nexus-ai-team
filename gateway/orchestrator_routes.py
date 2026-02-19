"""Orchestrator API routes for NEXUS Gateway.

Provides REST endpoints for creating and querying LangGraph contracts.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


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
# Routes
# ---------------------------------------------------------------------------


@router.post("/", response_model=ContractResponse)
async def create_contract(req: ContractRequest):
    """CEO creates a new contract and kicks off the graph."""
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

    # Run synchronously for MVP (async streaming later)
    final_state = None
    for event in graph.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, node_output in event.items():
            logger.debug("[CONTRACT] %s node %s completed", contract_id, node_name)
            final_state = node_output

    result = graph.get_state(config).values

    status = "in_progress"
    if result.get("ceo_approved"):
        status = "completed"
    elif result.get("escalated"):
        status = "escalated"

    logger.info("[CONTRACT] %s finished with status=%s", contract_id, status)

    return ContractResponse(
        contract_id=contract_id,
        status=status,
        current_phase=result.get("current_phase", "unknown"),
    )


@router.get("/{contract_id}", response_model=dict)
async def get_contract_status(contract_id: str):
    """Get the current state of a contract."""
    from nexus.orchestrator.checkpoint import get_checkpointer
    from nexus.orchestrator.graph import build_graph

    checkpointer = get_checkpointer()
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": contract_id}}

    state = graph.get_state(config)
    if not state or not state.values:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")

    return state.values
