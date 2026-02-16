"""Activate (trigger execution) API routes."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/activate", tags=["activate"])

# In-memory execution state
_execution_state = {
    "running": False,
    "current_agent": None,
    "current_contract": None,
    "progress": 0,
}


class ActivateRequest(BaseModel):
    instruction: str
    priority: str = "medium"


@router.post("")
async def activate(body: ActivateRequest):
    """发送指令给CEO（触发activate）。"""
    # In a real implementation, this would call the activate engine
    _execution_state["running"] = True
    _execution_state["current_agent"] = "ceo"
    _execution_state["progress"] = 10
    return {
        "ok": True,
        "message": "指令已发送给CEO",
        "instruction": body.instruction,
        "status": "processing"
    }


@router.get("/status")
async def get_status():
    """获取当前执行状态。"""
    return _execution_state
