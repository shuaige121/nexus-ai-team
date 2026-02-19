"""
NEXUS LangGraph 主 Graph 定义

Graph 结构（含 Ownership + DoubleCheck 功能）：

    CEO Dispatch
        ↓
    Manager Plan
        ↓
    Worker Accept  ←──────────────────────────────────────┐
        ↓ (accept)              ↓ (reject / no_response)  │
    Worker Execute          Manager Reassign ──────────────┘
        ↓                       ↓ (max_attempts)
    QA Review           CEO Handle Escalation
        ↓
    Manager Review After QA
        ↓ (PASS)              ↓ (FAIL + retry)         ↓ (FAIL + max_attempts)
    CEO Approve          Worker Execute            CEO Handle Escalation
        ↓
       END

    另：Progress Check 节点（DoubleCheck 功能）：
    Progress Check
        ↓ (on_track)      ↓ (stuck / escalated)
    Worker Execute    CEO Handle Escalation
"""
from __future__ import annotations

import logging
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from nexus.orchestrator.nodes.ceo import (
    ceo_approve,
    ceo_dispatch,
    ceo_handle_escalation,
)
from nexus.orchestrator.nodes.manager import manager_plan, manager_review_after_qa
from nexus.orchestrator.nodes.manager_reassign import manager_reassign
from nexus.orchestrator.nodes.progress_check import (
    check_progress,
    route_after_progress_check,
)
from nexus.orchestrator.nodes.qa import qa_review
import nexus.orchestrator.nodes.worker as _worker_node_mod
from nexus.orchestrator.nodes.worker_accept import (
    route_after_worker_accept,
    worker_accept,
)
from nexus.orchestrator.state import NexusContractState

logger = logging.getLogger(__name__)


def _worker_execute_proxy(state: "NexusContractState") -> dict:
    """
    Thin proxy for worker_execute that resolves the function through the module
    at call time rather than at import time.

    This indirection ensures that test patches applied via
    unittest.mock.patch.object(nexus.orchestrator.nodes.worker, 'worker_execute', ...)
    are picked up correctly, because the graph node holds a reference to this
    proxy rather than a direct reference to the original function.
    """
    return _worker_node_mod.worker_execute(state)



# --------------------------------------------------------------------------
# 路由函数（conditional edge）
# --------------------------------------------------------------------------


def route_after_qa_review(
    state: NexusContractState,
) -> Literal["ceo_approve", "worker_execute", "ceo_handle_escalation"]:
    """
    Manager Review 节点之后的路由决策。

    决策逻辑：
    - PASS → CEO 最终审批
    - FAIL + attempt < max → Worker 重试
    - FAIL + attempt >= max → CEO 上报处理
    """
    verdict = state["qa_verdict"]
    attempt = state["attempt_count"]
    max_att = state["max_attempts"]

    logger.info(
        "[ROUTER] route_after_qa_review: verdict=%s, attempt=%d/%d",
        verdict,
        attempt,
        max_att,
    )

    if verdict == "PASS":
        return "ceo_approve"
    elif attempt < max_att:
        # 还有重试机会，返回 worker 重新执行
        return "worker_execute"
    else:
        # 超出上限，上报 CEO
        return "ceo_handle_escalation"


def route_after_manager_reassign(
    state: NexusContractState,
) -> Literal["worker_accept", "ceo_handle_escalation"]:
    """
    Manager Reassign 节点之后的路由决策。

    决策逻辑：
    - escalated == True → CEO 处理上报（无可用 Worker）
    - escalated == False → 重新进入 worker_accept（等待新 Worker 回应）
    """
    if state.get("escalated", False):
        logger.warning("[ROUTER] route_after_manager_reassign: escalated → ceo_handle_escalation")
        return "ceo_handle_escalation"
    else:
        logger.info("[ROUTER] route_after_manager_reassign: retry → worker_accept")
        return "worker_accept"


def route_after_worker_execute(
    state: NexusContractState,
) -> Literal["qa_review", "progress_check"]:
    """
    worker_execute 节点之后的路由决策。

    决策逻辑：
    - check_after_seconds is not None → "progress_check"（需要定时回查）
    - check_after_seconds is None     → "qa_review"（直接进入 QA 审查）
    """
    if state.get("check_after_seconds") is not None:
        logger.info(
            "[ROUTER] route_after_worker_execute: check_after_seconds=%s → progress_check",
            state.get("check_after_seconds"),
        )
        return "progress_check"
    else:
        logger.info("[ROUTER] route_after_worker_execute: no check → qa_review")
        return "qa_review"


# --------------------------------------------------------------------------
# Graph 构建函数
# --------------------------------------------------------------------------


def build_graph(checkpointer=None) -> StateGraph:
    """
    构建并编译 NEXUS LangGraph（含 Ownership + DoubleCheck 节点）。

    新增节点：
    - worker_accept: Worker 回应接受/拒绝合同（Ownership 功能）
    - manager_reassign: 处理 Worker 拒绝的重新分配（Ownership 功能）
    - progress_check: 定期回查 Worker 进度（DoubleCheck 功能）

    Args:
        checkpointer: LangGraph checkpoint 对象，默认 None（无持久化）
                      PoC 阶段传入 MemorySaver，生产阶段可传入 PostgresSaver

    Returns:
        编译后的 CompiledStateGraph 对象
    """
    builder = StateGraph(NexusContractState)

    # ---------- 注册节点（原有）----------
    builder.add_node("ceo_dispatch", ceo_dispatch)
    builder.add_node("manager_plan", manager_plan)
    builder.add_node("worker_execute", _worker_execute_proxy)
    builder.add_node("qa_review", qa_review)
    builder.add_node("manager_review_after_qa", manager_review_after_qa)
    builder.add_node("ceo_approve", ceo_approve)
    builder.add_node("ceo_handle_escalation", ceo_handle_escalation)

    # ---------- 注册节点（新增：Ownership + DoubleCheck）----------
    builder.add_node("worker_accept", worker_accept)
    builder.add_node("manager_reassign", manager_reassign)
    builder.add_node("progress_check", check_progress)

    # ---------- 注册边（固定顺序）----------
    # START → CEO 发起合同
    builder.add_edge(START, "ceo_dispatch")

    # CEO dispatch → Manager 规划
    builder.add_edge("ceo_dispatch", "manager_plan")

    # Manager 规划 → Worker Accept（新增：先确认责任归属）
    builder.add_edge("manager_plan", "worker_accept")

    # ---------- 条件边：Worker Accept 后路由 ----------
    builder.add_conditional_edges(
        "worker_accept",
        route_after_worker_accept,
        {
            "worker_execute": "worker_execute",    # 接受 → 开始执行
            "manager_reassign": "manager_reassign",  # 拒绝/未回应 → Manager 重新分配
        },
    )

    # ---------- 条件边：Manager Reassign 后路由 ----------
    builder.add_conditional_edges(
        "manager_reassign",
        route_after_manager_reassign,
        {
            "worker_accept": "worker_accept",         # 重新发给 Worker 等待接受
            "ceo_handle_escalation": "ceo_handle_escalation",  # 上报 CEO
        },
    )

    # ---------- 条件边：Worker Execute 后路由（DoubleCheck）----------
    builder.add_conditional_edges(
        "worker_execute",
        route_after_worker_execute,
        {
            "qa_review": "qa_review",              # 无回查需求，直接 QA
            "progress_check": "progress_check",    # 需要定时回查，进入 DoubleCheck
        },
    )

    # QA 审查 → Manager 汇总审阅
    builder.add_edge("qa_review", "manager_review_after_qa")

    # ---------- 条件边：Manager 审阅后路由 ----------
    builder.add_conditional_edges(
        "manager_review_after_qa",
        route_after_qa_review,
        {
            "ceo_approve": "ceo_approve",
            "worker_execute": "worker_execute",           # 重试循环
            "ceo_handle_escalation": "ceo_handle_escalation",
        },
    )

    # ---------- Progress Check 节点（DoubleCheck 功能）----------
    # 注：PoC 阶段通过手动调用触发（从 worker_execute 之后插入）
    # 真实场景中由 APScheduler 定时注入，此处提供节点注册和路由
    builder.add_conditional_edges(
        "progress_check",
        route_after_progress_check,
        {
            "worker_execute": "worker_execute",           # 进度正常，继续等
            "ceo_handle_escalation": "ceo_handle_escalation",  # 卡死，上报
        },
    )

    # CEO 审批 → 结束
    builder.add_edge("ceo_approve", END)

    # CEO 处理上报 → 结束
    builder.add_edge("ceo_handle_escalation", END)

    # ---------- 编译 ----------
    compile_kwargs: dict = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    graph = builder.compile(**compile_kwargs)
    logger.info("[GRAPH] NEXUS LangGraph compiled successfully (with Ownership + DoubleCheck)")
    return graph


def build_graph_with_interrupts(checkpointer=None) -> StateGraph:
    """
    构建带 interrupt 的 Graph（用于需要人工审批的生产场景）。

    interrupt_before 指定的节点会在执行前暂停，等待外部输入。
    PoC 阶段使用 build_graph()（无 interrupt）以便自动运行完整流程。

    Args:
        checkpointer: 必须提供 checkpointer 才能使用 interrupt

    Returns:
        编译后的带 interrupt 的 CompiledStateGraph
    """
    builder = StateGraph(NexusContractState)

    # 注册节点（同 build_graph）
    builder.add_node("ceo_dispatch", ceo_dispatch)
    builder.add_node("manager_plan", manager_plan)
    builder.add_node("worker_accept", worker_accept)
    builder.add_node("manager_reassign", manager_reassign)
    builder.add_node("worker_execute", _worker_execute_proxy)
    builder.add_node("qa_review", qa_review)
    builder.add_node("manager_review_after_qa", manager_review_after_qa)
    builder.add_node("ceo_approve", ceo_approve)
    builder.add_node("ceo_handle_escalation", ceo_handle_escalation)
    builder.add_node("progress_check", check_progress)

    # 注册边（同 build_graph）
    builder.add_edge(START, "ceo_dispatch")
    builder.add_edge("ceo_dispatch", "manager_plan")
    builder.add_edge("manager_plan", "worker_accept")
    builder.add_conditional_edges(
        "worker_accept",
        route_after_worker_accept,
        {
            "worker_execute": "worker_execute",
            "manager_reassign": "manager_reassign",
        },
    )
    builder.add_conditional_edges(
        "manager_reassign",
        route_after_manager_reassign,
        {
            "worker_accept": "worker_accept",
            "ceo_handle_escalation": "ceo_handle_escalation",
        },
    )
    builder.add_conditional_edges(
        "worker_execute",
        route_after_worker_execute,
        {
            "qa_review": "qa_review",
            "progress_check": "progress_check",
        },
    )
    builder.add_edge("qa_review", "manager_review_after_qa")
    builder.add_conditional_edges(
        "manager_review_after_qa",
        route_after_qa_review,
        {
            "ceo_approve": "ceo_approve",
            "worker_execute": "worker_execute",
            "ceo_handle_escalation": "ceo_handle_escalation",
        },
    )
    builder.add_conditional_edges(
        "progress_check",
        route_after_progress_check,
        {
            "worker_execute": "worker_execute",
            "ceo_handle_escalation": "ceo_handle_escalation",
        },
    )
    builder.add_edge("ceo_approve", END)
    builder.add_edge("ceo_handle_escalation", END)

    compile_kwargs: dict = {
        # 在 CEO 审批和上报处理前 interrupt，等待人工输入
        "interrupt_before": ["ceo_approve", "ceo_handle_escalation"],
    }
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    graph = builder.compile(**compile_kwargs)
    logger.info("[GRAPH] NEXUS LangGraph (with interrupts) compiled successfully")
    return graph


def get_default_graph() -> StateGraph:
    """
    获取带 MemorySaver checkpointer 的默认 Graph（适用于 PoC 运行）。

    Returns:
        使用内存 checkpoint 的编译 Graph
    """
    checkpointer = MemorySaver()
    return build_graph(checkpointer=checkpointer)
