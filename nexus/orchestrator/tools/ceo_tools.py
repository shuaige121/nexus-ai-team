"""
CEO 工具集

CEO 只有有限的工具：生成合同和发邮件。
CEO 不能直接执行代码、CLI 命令或操作文件系统。
所有工具函数在调用前通过 check_tool_permission() 校验。
"""
from __future__ import annotations

import logging

from nexus.orchestrator.permissions import check_tool_permission

logger = logging.getLogger(__name__)


def generate_contract(
    role: str,
    task_description: str,
    priority: str,
    department: str,
    contract_id: str,
) -> dict:
    """
    生成标准化合同文档。

    CEO 专属工具，格式化任务需求为可下发的合同结构。

    Args:
        role: 调用方角色（必须是 "ceo"）
        task_description: 任务描述
        priority: 优先级 (low/medium/high/critical)
        department: 目标部门
        contract_id: 合同编号

    Returns:
        合同字典，包含所有元数据

    Raises:
        PermissionError: 非 CEO 角色调用时抛出
    """
    # 工具权限校验
    check_tool_permission(role, "generate_contract")

    logger.info("[CEO_TOOL] generate_contract: contract_id=%s", contract_id)

    return {
        "contract_id": contract_id,
        "task_description": task_description,
        "priority": priority,
        "department": department,
        "status": "issued",
        "issued_by": role,
    }


def write_note(role: str, note: str) -> str:
    """
    CEO 写备忘录（内部记录，不对外发送）。

    Args:
        role: 调用方角色
        note: 备忘录内容

    Returns:
        带时间戳的备忘录字符串
    """
    check_tool_permission(role, "write_note")
    logger.info("[CEO_TOOL] write_note: %s...", note[:50])
    return f"[NOTE] {note}"


def read_reports(role: str, report_content: str) -> str:
    """
    CEO 阅读报告（只读操作）。

    Args:
        role: 调用方角色
        report_content: 报告内容（由系统注入）

    Returns:
        经 CEO 确认的报告摘要
    """
    check_tool_permission(role, "read_reports")
    logger.info("[CEO_TOOL] read_reports: %d chars", len(report_content))
    return f"[CEO READ] {report_content[:200]}..."
