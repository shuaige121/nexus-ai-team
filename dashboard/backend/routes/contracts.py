"""Contract management API routes."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from dashboard.backend.mock_data import MOCK_CONTRACTS

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


class ContractCreate(BaseModel):
    type: str = "task"
    from_agent: str
    to_agent: str
    priority: str = "medium"
    objective: str = ""
    payload: dict | None = None
    parent_id: str | None = None


@router.get("")
async def list_contracts(
    status: str | None = Query(None),
    type: str | None = Query(None),
):
    """获取所有contract（支持状态和类型筛选）。"""
    result = MOCK_CONTRACTS
    if status:
        result = [c for c in result if c["status"] == status]
    if type:
        result = [c for c in result if c["type"] == type]
    return result


@router.get("/{contract_id}")
async def get_contract(contract_id: str):
    """获取单个contract详情。"""
    for c in MOCK_CONTRACTS:
        if c["id"] == contract_id:
            return c
    raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found")


@router.get("/{contract_id}/chain")
async def get_contract_chain(contract_id: str):
    """获取任务血缘链。"""
    contract = None
    for c in MOCK_CONTRACTS:
        if c["id"] == contract_id:
            contract = c
            break
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found")

    # Find root
    root = contract
    visited = {root["id"]}
    while root["parent_id"]:
        parent = None
        for c in MOCK_CONTRACTS:
            if c["id"] == root["parent_id"] and c["id"] not in visited:
                parent = c
                visited.add(c["id"])
                break
        if not parent:
            break
        root = parent

    # Build chain from root
    def build_tree(node_id: str) -> dict:
        node = None
        for c in MOCK_CONTRACTS:
            if c["id"] == node_id:
                node = c
                break
        if not node:
            return {}
        children = [c for c in MOCK_CONTRACTS if c["parent_id"] == node_id]
        return {
            **node,
            "children": [build_tree(ch["id"]) for ch in children]
        }

    return build_tree(root["id"])


@router.post("")
async def create_contract(body: ContractCreate):
    """手动创建contract（调试用）。"""
    import uuid
    from datetime import datetime, timezone
    new_id = f"CTR-{str(uuid.uuid4())[:6].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    contract = {
        "id": new_id,
        "type": body.type,
        "from_agent": body.from_agent,
        "to_agent": body.to_agent,
        "priority": body.priority,
        "status": "pending",
        "objective": body.objective,
        "payload": body.payload or {"objective": body.objective},
        "parent_id": body.parent_id,
        "created_at": now,
        "updated_at": now
    }
    MOCK_CONTRACTS.append(contract)
    return {"ok": True, "contract": contract}
