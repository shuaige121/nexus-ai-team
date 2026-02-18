"""
NEXUS LangGraph PoC 演示脚本

演示完整的 CEO → Manager → Worker → QA → PASS → CEO 批准 生命周期。

运行方式：
    cd ~/Desktop/nexus-ai-team
    source .venv/bin/activate
    python -m nexus.orchestrator.demo

可选参数（通过环境变量控制演示场景）：
    NEXUS_DEMO_SCENARIO=fail_retry   演示 QA FAIL + 重试流程
    NEXUS_DEMO_SCENARIO=escalate     演示超出重试上限上报流程
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from nexus.orchestrator.graph import build_graph
from nexus.orchestrator.mail import format_mail_log
from nexus.orchestrator.state import NexusContractState

# --------------------------------------------------------------------------
# 日志配置
# --------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# 抑制 LangGraph 内部的冗余日志，只保留 NEXUS 自己的日志
logging.getLogger("langgraph").setLevel(logging.WARNING)
logging.getLogger("langchain_core").setLevel(logging.WARNING)


def print_separator(title: str = "", width: int = 70) -> None:
    """打印分隔线，可选标题居中。"""
    if title:
        pad = (width - len(title) - 2) // 2
        print(f"\n{'=' * pad} {title} {'=' * pad}")
    else:
        print("=" * width)


def print_state_summary(state: dict[str, Any], phase_label: str = "") -> None:
    """打印当前 state 的关键字段摘要。"""
    if phase_label:
        print_separator(phase_label)
    print(f"  contract_id   : {state.get('contract_id', 'N/A')}")
    print(f"  current_phase : {state.get('current_phase', 'N/A')}")
    print(f"  attempt_count : {state.get('attempt_count', 0)}")
    print(f"  qa_verdict    : {state.get('qa_verdict', '(尚未出具)')}")
    print(f"  ceo_approved  : {state.get('ceo_approved', False)}")
    print(f"  escalated     : {state.get('escalated', False)}")
    mail_count = len(state.get("mail_log", []))
    print(f"  mail_log 条数 : {mail_count}")


def run_demo_pass_scenario() -> None:
    """
    场景1：正常 PASS 流程

    CEO 发起 → Manager 分解 → Worker 执行 → QA PASS → CEO 批准
    """
    print_separator("NEXUS LangGraph PoC — 场景1: 正常 PASS 流程")

    contract_id = f"CTR-{uuid.uuid4().hex[:8].upper()}"

    # 初始状态（由调用方填入合同元信息）
    initial_state: NexusContractState = {
        "contract_id": contract_id,
        "task_description": "开发一个 RESTful API 端点，支持用户认证和 JWT token 生成",
        "priority": "high",
        "department": "IT",
        "current_phase": "ceo_dispatch",
        "worker_output": "",
        "qa_verdict": "",
        "qa_report": "",
        "attempt_count": 0,
        "max_attempts": 3,
        "subtasks": [],
        "manager_instruction": "",
        "mail_log": [],
        "final_result": "",
        "ceo_approved": False,
        "escalated": False,
    }

    print(f"\n合同 ID: {contract_id}")
    print(f"任务描述: {initial_state['task_description']}")
    print(f"优先级: {initial_state['priority']}")
    print(f"目标部门: {initial_state['department']}")

    # 构建 Graph（使用 MemorySaver，PoC 阶段不需要 PostgreSQL）
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer=checkpointer)

    # thread_id 对应一个独立的合同执行线程
    config = {"configurable": {"thread_id": contract_id}}

    print_separator("开始执行 Graph")

    # 执行 Graph，流式输出每个节点的状态变化
    step_count = 0
    for event in graph.stream(initial_state, config=config, stream_mode="updates"):
        step_count += 1
        for node_name, node_output in event.items():
            print(f"\n[Step {step_count}] 节点: {node_name}")
            # 打印本节点产生的状态更新
            for key, value in node_output.items():
                if key == "mail_log":
                    # 只显示本次新增邮件数量，详细邮件在最后打印
                    print(f"  + mail_log: +{len(value)} 条邮件")
                elif key in ("worker_output", "qa_report", "final_result"):
                    # 长文本截断显示
                    preview = str(value)[:120].replace("\n", " | ")
                    print(f"  + {key}: {preview}...")
                elif key == "subtasks" and isinstance(value, list):
                    print(f"  + subtasks: {len(value)} 个子任务")
                else:
                    print(f"  + {key}: {value}")

    # 读取最终状态
    final_state = graph.get_state(config).values

    print_separator("最终状态")
    print_state_summary(final_state, "")

    print_separator("邮件日志")
    print(format_mail_log(final_state.get("mail_log", [])))

    if final_state.get("final_result"):
        print_separator("最终交付结果")
        print(final_state["final_result"])

    # 结论
    print_separator("结论")
    if final_state.get("ceo_approved"):
        print("合同执行成功！CEO 已批准交付结果。")
    elif final_state.get("escalated"):
        print("合同执行失败，已上报 CEO。")
    else:
        print("合同执行状态未知，请检查 Graph 配置。")


def run_demo_fail_retry_scenario() -> None:
    """
    场景2：QA FAIL + 重试流程

    通过 monkey-patch QA 工具模拟第一次 FAIL，第二次 PASS。
    演示 Worker 重试机制。
    """
    print_separator("NEXUS LangGraph PoC — 场景2: QA FAIL + 重试")

    import nexus.orchestrator.nodes.qa as qa_node_mod
    from typing import Literal

    original_write_verdict = qa_node_mod.write_verdict
    call_count = {"n": 0}

    def patched_write_verdict(role, review_result, linter_result, test_result):
        """第一次调用返回 FAIL，第二次及之后返回 PASS。"""
        call_count["n"] += 1
        if call_count["n"] == 1:
            # 强制第一次 FAIL
            from nexus.orchestrator.permissions import check_tool_permission
            check_tool_permission(role, "write_verdict")
            verdict: Literal["PASS", "FAIL"] = "FAIL"
            report = "QA 裁决: FAIL\n失败原因:\n  - 模拟第一次失败（用于演示重试机制）\n代码质量分: 55/100"
            return verdict, report
        else:
            return original_write_verdict(role, review_result, linter_result, test_result)

    qa_node_mod.write_verdict = patched_write_verdict  # type: ignore[assignment]

    try:
        contract_id = f"CTR-{uuid.uuid4().hex[:8].upper()}-RETRY"
        initial_state: NexusContractState = {
            "contract_id": contract_id,
            "task_description": "实现数据库连接池管理模块，支持自动重连和健康检查",
            "priority": "medium",
            "department": "IT",
            "current_phase": "ceo_dispatch",
            "worker_output": "",
            "qa_verdict": "",
            "qa_report": "",
            "attempt_count": 0,
            "max_attempts": 3,
            "subtasks": [],
            "manager_instruction": "",
            "mail_log": [],
            "final_result": "",
            "ceo_approved": False,
            "escalated": False,
        }

        checkpointer = MemorySaver()
        graph = build_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": contract_id}}

        step_count = 0
        for event in graph.stream(initial_state, config=config, stream_mode="updates"):
            step_count += 1
            for node_name, node_output in event.items():
                phase = node_output.get("current_phase", "")
                verdict = node_output.get("qa_verdict", "")
                attempt = node_output.get("attempt_count", "")
                print(
                    f"[Step {step_count:02d}] {node_name:<30} "
                    f"phase={phase or '—':<20} "
                    f"verdict={verdict or '—':<6} "
                    f"attempt={attempt or '—'}"
                )

        final_state = graph.get_state(config).values
        print_separator("结论（场景2）")
        print(f"总重试次数: {final_state.get('attempt_count', 0)}")
        print(f"QA 裁决: {final_state.get('qa_verdict', 'N/A')}")
        print(f"CEO 批准: {final_state.get('ceo_approved', False)}")
        print(f"总邮件数: {len(final_state.get('mail_log', []))}")
    finally:
        qa_node_mod.write_verdict = original_write_verdict  # type: ignore[assignment]


def run_demo_escalation_scenario() -> None:
    """
    场景3：超出最大重试次数，上报 CEO

    强制所有 QA 审查都返回 FAIL，演示上报机制。
    """
    print_separator("NEXUS LangGraph PoC — 场景3: 超出上限，上报 CEO")

    import nexus.orchestrator.nodes.qa as qa_node_mod
    from typing import Literal

    original_write_verdict = qa_node_mod.write_verdict

    def always_fail_verdict(role, review_result, linter_result, test_result):
        """永远返回 FAIL，模拟无法修复的问题。"""
        from nexus.orchestrator.permissions import check_tool_permission
        check_tool_permission(role, "write_verdict")
        verdict: Literal["PASS", "FAIL"] = "FAIL"
        report = "QA 裁决: FAIL\n失败原因:\n  - 模拟永久失败（演示上报机制）\n代码质量分: 30/100"
        return verdict, report

    qa_node_mod.write_verdict = always_fail_verdict  # type: ignore[assignment]

    try:
        contract_id = f"CTR-{uuid.uuid4().hex[:8].upper()}-ESC"
        initial_state: NexusContractState = {
            "contract_id": contract_id,
            "task_description": "修复严重的并发安全漏洞（演示上报场景）",
            "priority": "critical",
            "department": "IT",
            "current_phase": "ceo_dispatch",
            "worker_output": "",
            "qa_verdict": "",
            "qa_report": "",
            "attempt_count": 0,
            "max_attempts": 2,   # 设为 2 次，快速触发上报
            "subtasks": [],
            "manager_instruction": "",
            "mail_log": [],
            "final_result": "",
            "ceo_approved": False,
            "escalated": False,
        }

        checkpointer = MemorySaver()
        graph = build_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": contract_id}}

        step_count = 0
        for event in graph.stream(initial_state, config=config, stream_mode="updates"):
            step_count += 1
            for node_name, node_output in event.items():
                phase = node_output.get("current_phase", "")
                verdict = node_output.get("qa_verdict", "")
                attempt = node_output.get("attempt_count", "")
                escalated = node_output.get("escalated", "")
                print(
                    f"[Step {step_count:02d}] {node_name:<30} "
                    f"phase={phase or '—':<22} "
                    f"verdict={verdict or '—':<6} "
                    f"attempt={attempt or '—':<4} "
                    f"escalated={escalated or '—'}"
                )

        final_state = graph.get_state(config).values
        print_separator("结论（场景3）")
        print(f"总重试次数: {final_state.get('attempt_count', 0)}")
        print(f"是否上报: {final_state.get('escalated', False)}")
        print(f"CEO 批准: {final_state.get('ceo_approved', False)}")
        if final_state.get("final_result"):
            print(f"最终结果:\n{final_state['final_result']}")
    finally:
        qa_node_mod.write_verdict = original_write_verdict  # type: ignore[assignment]


def main() -> None:
    """主入口：根据环境变量选择演示场景。"""
    scenario = os.getenv("NEXUS_DEMO_SCENARIO", "pass")

    print_separator("NEXUS AI-Team LangGraph PoC", width=70)
    print("  Graph 架构: CEO → Manager → Worker → QA → CEO")
    print("  Checkpointer: MemorySaver (内存，PoC 阶段)")
    print(f"  演示场景: {scenario}")
    print_separator(width=70)

    if scenario == "fail_retry":
        run_demo_fail_retry_scenario()
    elif scenario == "escalate":
        run_demo_escalation_scenario()
    else:
        # 默认运行所有三个场景
        run_demo_pass_scenario()
        print("\n")
        run_demo_fail_retry_scenario()
        print("\n")
        run_demo_escalation_scenario()

    print_separator("Demo 完成", width=70)


if __name__ == "__main__":
    main()
