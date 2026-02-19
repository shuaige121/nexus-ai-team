"""
Manager 工具集

Manager 负责任务分解和 Worker 分配。
不能直接执行代码，只能通过 Worker 间接执行。
"""
from __future__ import annotations

import logging

from nexus.orchestrator.permissions import check_tool_permission
from nexus.orchestrator.tools._llm_helper import llm_call

logger = logging.getLogger(__name__)

_BREAK_DOWN_SYSTEM = (
    "You are a technical project manager. "
    "Break the given task into 3-5 atomic subtasks that a developer can execute "
    "independently. Return each subtask on a new line, prefixed with '- '. "
    "Do not include any introduction, conclusion, or extra commentary — "
    "output only the bullet list."
)


def break_down_task(role: str, task_description: str) -> list[str]:
    """
    将高层任务分解为可执行的子任务列表（调用 LLM 进行智能分解）。

    Args:
        role: 调用方角色（必须是 "manager"）
        task_description: 来自 CEO 合同的任务描述

    Returns:
        子任务列表，每项是 Worker 可独立执行的原子任务

    Raises:
        PermissionError: 非 manager 角色调用时抛出
    """
    check_tool_permission(role, "break_down_task")
    logger.info(
        "[MANAGER_TOOL] break_down_task for: %s...", task_description[:60]
    )

    raw = llm_call(role, _BREAK_DOWN_SYSTEM, task_description, max_tokens=512)

    # Parse lines beginning with "- " into a clean list.
    subtasks: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            subtasks.append(stripped[2:].strip())
        elif stripped.startswith("-"):
            subtasks.append(stripped[1:].strip())

    # Fallback: if LLM deviated from format, use non-empty lines as subtasks.
    if not subtasks:
        subtasks = [line.strip() for line in raw.splitlines() if line.strip()]

    logger.info("[MANAGER_TOOL] break_down_task: parsed %d subtasks", len(subtasks))
    return subtasks


def assign_worker(role: str, worker_id: str, subtasks: list[str]) -> str:
    """
    将子任务分配给指定 Worker。

    Args:
        role: 调用方角色
        worker_id: Worker 标识符
        subtasks: 需要执行的子任务列表

    Returns:
        分配指令字符串（会作为 manager_instruction 写入 state）
    """
    check_tool_permission(role, "assign_worker")
    logger.info(
        "[MANAGER_TOOL] assign_worker: worker=%s, tasks=%d", worker_id, len(subtasks)
    )

    # TODO: integrate with a real worker registry / task queue
    # (e.g., lookup worker capacity, assign via message broker)
    task_list = "\n".join(f"  {i + 1}. {t}" for i, t in enumerate(subtasks))
    instruction = (
        f"Worker {worker_id}，请按顺序执行以下任务：\n"
        f"{task_list}\n"
        "完成后提交报告给 Manager。"
    )
    return instruction


def review_report(role: str, worker_output: str, qa_report: str) -> str:
    """
    Manager 审阅 Worker 输出和 QA 报告后生成决策摘要。

    Args:
        role: 调用方角色
        worker_output: Worker 的执行输出
        qa_report: QA 的审查报告

    Returns:
        Manager 决策摘要字符串
    """
    check_tool_permission(role, "review_report")
    logger.info("[MANAGER_TOOL] review_report")
    return (
        f"Manager 审阅完毕。Worker 输出长度: {len(worker_output)} 字符，"
        f"QA 报告: {qa_report[:100]}..."
    )


def escalate(role: str, reason: str, contract_id: str) -> str:
    """
    Manager 向 CEO 发起上报（超出 Manager 处理能力时）。

    Args:
        role: 调用方角色
        reason: 上报原因
        contract_id: 合同编号

    Returns:
        上报摘要字符串
    """
    check_tool_permission(role, "escalate")
    logger.info(
        "[MANAGER_TOOL] escalate: contract=%s reason=%s", contract_id, reason[:50]
    )
    return f"[ESCALATION] contract={contract_id} reason={reason}"
