"""Department management API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dashboard.backend.mock_data import MOCK_ORG, MOCK_AGENTS

router = APIRouter(prefix="/api/departments", tags=["departments"])


class DepartmentCreate(BaseModel):
    name: str
    display_name: str


@router.post("")
async def create_department(body: DepartmentCreate):
    """创建新部门。"""
    for dept in MOCK_ORG["departments"]:
        if dept["name"] == body.name:
            raise HTTPException(status_code=409, detail=f"部门 '{body.name}' 已存在")
    new_dept = {
        "name": body.name,
        "display_name": body.display_name,
        "agents": []
    }
    MOCK_ORG["departments"].append(new_dept)
    return {"ok": True, "message": f"部门 '{body.display_name}' 创建成功", "department": new_dept}


@router.delete("/{dept_name}")
async def delete_department(dept_name: str):
    """删除部门。"""
    target = None
    for dept in MOCK_ORG["departments"]:
        if dept["name"] == dept_name:
            target = dept
            break
    if not target:
        raise HTTPException(status_code=404, detail=f"部门 '{dept_name}' 不存在")
    if target["agents"]:
        raise HTTPException(
            status_code=400,
            detail=f"部门 '{dept_name}' 仍有 {len(target['agents'])} 名员工，请先转移或删除"
        )
    MOCK_ORG["departments"].remove(target)
    return {"ok": True, "message": f"部门 '{dept_name}' 已删除"}
