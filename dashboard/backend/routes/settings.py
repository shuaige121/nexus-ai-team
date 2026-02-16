"""Settings API routes (tools, models, state machine, contract format)."""

from fastapi import APIRouter
from dashboard.backend.mock_data import MOCK_TOOLS, MOCK_MODELS

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/tools")
async def list_tools():
    """获取所有可用工具。"""
    return MOCK_TOOLS


@router.get("/models")
async def list_models():
    """获取所有接入的模型。"""
    return MOCK_MODELS


@router.get("/state-machine")
async def get_state_machine():
    """获取强制选择状态机定义。"""
    return {
        "states": [
            {
                "role": "worker",
                "name": "Worker完成任务",
                "choices": [
                    {"id": "submit", "label": "提交结果", "next": "manager_review"},
                    {"id": "need_help", "label": "请求协助", "next": "escalation"},
                    {"id": "blocked", "label": "任务受阻", "next": "escalation"},
                    {"id": "partial", "label": "部分完成", "next": "manager_review"},
                    {"id": "reject", "label": "无法完成", "next": "escalation"}
                ]
            },
            {
                "role": "manager",
                "name": "Manager审核",
                "choices": [
                    {"id": "approve", "label": "审核通过", "next": "qa_check"},
                    {"id": "revision", "label": "打回修改", "next": "worker_redo"},
                    {"id": "reassign", "label": "重新分配", "next": "worker_start"},
                    {"id": "escalate", "label": "升级处理", "next": "ceo_decision"}
                ]
            },
            {
                "role": "qa",
                "name": "QA质检",
                "choices": [
                    {"id": "pass", "label": "质检通过", "next": "report"},
                    {"id": "fail", "label": "质检不通过", "next": "worker_redo"},
                    {"id": "conditional", "label": "有条件通过", "next": "report"}
                ]
            },
            {
                "role": "ceo",
                "name": "CEO决策",
                "choices": [
                    {"id": "approve", "label": "批准", "next": "complete"},
                    {"id": "modify", "label": "要求修改", "next": "manager_review"},
                    {"id": "cancel", "label": "取消任务", "next": "archive"},
                    {"id": "reprioritize", "label": "调整优先级", "next": "manager_review"}
                ]
            }
        ]
    }


@router.get("/contract-format")
async def get_contract_format():
    """获取Contract格式说明和示例。"""
    return {
        "template": {
            "id": "CTR-XXXXXX",
            "type": "task | report | revision | escalation | assistance",
            "from_agent": "发送者agent_id",
            "to_agent": "接收者agent_id",
            "priority": "high | medium | low",
            "status": "pending | executing | completed | failed | archived",
            "payload": {
                "objective": "任务目标描述",
                "constraints": ["约束条件列表"],
                "deadline": "截止日期(可选)",
                "context": "上下文信息(可选)"
            },
            "parent_id": "父Contract ID(可选)",
            "created_at": "ISO 8601时间戳",
            "updated_at": "ISO 8601时间戳"
        },
        "examples": [
            {
                "type": "task",
                "description": "任务分配",
                "example": {
                    "id": "CTR-001",
                    "type": "task",
                    "from_agent": "ceo",
                    "to_agent": "eng_director",
                    "priority": "high",
                    "payload": {"objective": "重构后端API", "deadline": "2026-02-20"}
                }
            },
            {
                "type": "report",
                "description": "工作汇报",
                "example": {
                    "id": "CTR-002",
                    "type": "report",
                    "from_agent": "eng_director",
                    "to_agent": "ceo",
                    "priority": "medium",
                    "payload": {"objective": "周进度汇报", "result": "完成60%"}
                }
            },
            {
                "type": "revision",
                "description": "打回修改",
                "example": {
                    "id": "CTR-003",
                    "type": "revision",
                    "from_agent": "qa_engineer",
                    "to_agent": "backend_dev",
                    "priority": "high",
                    "payload": {"objective": "代码质检不通过", "issues": ["缺少单元测试"]}
                }
            },
            {
                "type": "escalation",
                "description": "问题升级",
                "example": {
                    "id": "CTR-004",
                    "type": "escalation",
                    "from_agent": "backend_dev",
                    "to_agent": "eng_director",
                    "priority": "high",
                    "payload": {"objective": "需要架构决策", "reason": "超出Worker权限"}
                }
            }
        ]
    }
