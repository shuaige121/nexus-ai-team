"""Agent management API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dashboard.backend.mock_data import MOCK_AGENTS, MOCK_ORG

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentUpdate(BaseModel):
    content: str


class AgentCreate(BaseModel):
    id: str
    name: str
    display_name: str
    department: str
    level: str
    reports_to: str | None = None
    model: str = "claude-haiku-3-5-20241022"
    model_short: str = "Haiku"
    provider: str = "anthropic"
    temperature: float = 0.3
    max_tokens: int = 4096


@router.get("")
async def list_agents():
    """获取所有agent列表。"""
    return list(MOCK_AGENTS.values())


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """获取单个agent详情。"""
    agent = MOCK_AGENTS.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


@router.put("/{agent_id}/jd")
async def update_jd(agent_id: str, body: AgentUpdate):
    """更新Agent的JD。"""
    if agent_id not in MOCK_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    MOCK_AGENTS[agent_id]["jd"] = body.content
    return {"ok": True, "message": f"{agent_id} JD已更新"}


@router.put("/{agent_id}/resume")
async def update_resume(agent_id: str, body: AgentUpdate):
    """更新Agent的Resume。"""
    if agent_id not in MOCK_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    MOCK_AGENTS[agent_id]["resume"] = body.content
    return {"ok": True, "message": f"{agent_id} Resume已更新"}


@router.put("/{agent_id}/memory")
async def update_memory(agent_id: str, body: AgentUpdate):
    """更新Agent的Memory。"""
    if agent_id not in MOCK_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    MOCK_AGENTS[agent_id]["memory"] = body.content
    return {"ok": True, "message": f"{agent_id} Memory已更新"}


@router.put("/{agent_id}/race")
async def update_race(agent_id: str, body: AgentUpdate):
    """更新Agent的Race配置（换模型）。"""
    if agent_id not in MOCK_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    MOCK_AGENTS[agent_id]["race"] = body.content
    return {"ok": True, "message": f"{agent_id} Race配置已更新"}


@router.post("")
async def create_agent(body: AgentCreate):
    """创建新Agent。"""
    if body.id in MOCK_AGENTS:
        raise HTTPException(status_code=409, detail=f"Agent '{body.id}' already exists")
    MOCK_AGENTS[body.id] = {
        **body.model_dump(),
        "status": "idle",
        "jd": f"# {body.display_name}\n\n## 核心职责\n- 待定义",
        "resume": f"# {body.display_name} 人格档案\n\n## 性格特征\n- 待定义",
        "memory": "## 近期记忆\n- 刚刚入职",
        "race": f"model: {body.model}\nprovider: {body.provider}\ntemperature: {body.temperature}\nmax_tokens: {body.max_tokens}"
    }
    # Add to department
    for dept in MOCK_ORG["departments"]:
        if dept["name"] == body.department:
            if body.id not in dept["agents"]:
                dept["agents"].append(body.id)
            break
    return {"ok": True, "message": f"Agent '{body.id}' 创建成功", "agent": MOCK_AGENTS[body.id]}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    """删除Agent。"""
    if agent_id not in MOCK_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    if agent_id in ("ceo", "hr_lead"):
        raise HTTPException(status_code=403, detail="不能删除核心Agent")
    agent = MOCK_AGENTS.pop(agent_id)
    for dept in MOCK_ORG["departments"]:
        if agent_id in dept["agents"]:
            dept["agents"].remove(agent_id)
    return {"ok": True, "message": f"Agent '{agent_id}' 已删除"}
