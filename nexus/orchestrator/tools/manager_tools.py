"""
Manager 工具集

Manager 负责任务分解和 Worker 分配。
不能直接执行代码，只能通过 Worker 间接执行。
"""
from __future__ import annotations

import logging

from nexus.orchestrator.permissions import check_tool_permission

logger = logging.getLogger(__name__)


def break_down_task(role: str, task_description: str) -> list[str]:
    """
    将高层任务分解为可执行的子任务列表。

    Args:
        role: 调用方角色（必须是 "manager"）
        task_description: 来自 CEO 合同的任务描述

    Returns:
        子任务列表，每项是 Worker 可独立执行的原子任务

    Raises:
        PermissionError: 非 manager 角色调用时抛出
    """
    check_tool_permission(role, "break_down_task")
    logger.info("[MANAGER_TOOL] break_down_task for: %s...", task_description[:60])

    # PoC 阶段：根据任务描述生成固定子任务结构
    # 真实场景中此处调用 LLM 进行智能分解
    subtasks = [
        f"[子任务1] 分析需求并设计方案: {task_description[:40]}",
        "[子任务2] 编写核心实现代码",
        "[子任务3] 编写单元测试并确保覆盖率 >80%",
        "[子任务4] 提交 git commit 并生成执行报告",
    ]
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
    logger.info("[MANAGER_TOOL] assign_worker: worker=%s, tasks=%d", worker_id, len(subtasks))

    task_list = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(subtasks))
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
    logger.info("[MANAGER_TOOL] escalate: contract=%s reason=%s", contract_id, reason[:50])
    return f"[ESCALATION] contract={contract_id} reason={reason}"
