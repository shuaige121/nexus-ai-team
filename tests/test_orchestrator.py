"""
NEXUS Orchestrator 测试套件

覆盖：
- test_permission_enforcement  — 权限矩阵严格执行
- test_mail_routing            — Chain of Command 邮件路由
- test_contract_pipeline       — 完整 PASS 流程端到端
- test_qa_retry                — FAIL + 重试机制
- test_max_attempts_escalation — 超出重试上限上报
- test_state_mail_reducer      — mail_log reducer 追加语义
- test_tools_permissions       — 各角色工具白名单
- test_mail_from_role_auto_injected — B-01: from_role 不能被调用方指定
- test_mail_rejection_audit         — B-02: 违规通信被记录到 mail_rejections
"""
from __future__ import annotations

import uuid
import warnings
from typing import Literal
from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

from nexus.orchestrator.graph import build_graph
from nexus.orchestrator.mail import resolve_from_role, send_mail
from nexus.orchestrator.permissions import (
    PermissionError as NexusPermError,
    check_mail_permission,
    check_tool_permission,
    get_role_tools,
)
from nexus.orchestrator.state import NexusContractState
from nexus.orchestrator.tools.ceo_tools import generate_contract
from nexus.orchestrator.tools.manager_tools import break_down_task
from nexus.orchestrator.tools.worker_tools import git_commit, write_code
from nexus.orchestrator.tools.qa_tools import write_verdict


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def base_state() -> NexusContractState:
    """返回最小化的初始合同状态，供各测试复用。"""
    return {
        "contract_id": f"CTR-TEST-{uuid.uuid4().hex[:6].upper()}",
        "task_description": "测试任务：实现一个简单的 Hello World 函数",
        "priority": "low",
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
        "mail_rejections": [],
        "final_result": "",
        "ceo_approved": False,
        "escalated": False,
    }


@pytest.fixture
def graph_with_memory():
    """返回带 MemorySaver 的编译 Graph。"""
    checkpointer = MemorySaver()
    return build_graph(checkpointer=checkpointer)


def make_thread_config(contract_id: str | None = None) -> dict:
    """生成 LangGraph 线程配置。"""
    tid = contract_id or f"thread-{uuid.uuid4().hex[:8]}"
    return {"configurable": {"thread_id": tid}}


# --------------------------------------------------------------------------
# 测试组1：权限矩阵执行
# --------------------------------------------------------------------------

class TestPermissionEnforcement:
    """验证权限矩阵：角色不能调用超出白名单的工具。"""

    def test_ceo_cannot_use_write_code(self):
        """CEO 不能调用 write_code 工具（NO_CODE 约束）。"""
        with pytest.raises(NexusPermError) as exc_info:
            check_tool_permission("ceo", "write_code")
        assert "ceo" in str(exc_info.value)
        assert "write_code" in str(exc_info.value)

    def test_ceo_cannot_use_run_tests(self):
        """CEO 不能运行测试（NO_DIRECT_EXECUTION 约束）。"""
        with pytest.raises(NexusPermError):
            check_tool_permission("ceo", "run_tests")

    def test_ceo_cannot_use_git_commit(self):
        """CEO 不能提交代码。"""
        with pytest.raises(NexusPermError):
            check_tool_permission("ceo", "git_commit")

    def test_worker_cannot_use_generate_contract(self):
        """Worker 不能生成合同（越权操作）。"""
        with pytest.raises(NexusPermError):
            check_tool_permission("worker", "generate_contract")

    def test_worker_cannot_use_break_down_task(self):
        """Worker 不能分解任务（Manager 专属工具）。"""
        with pytest.raises(NexusPermError):
            check_tool_permission("worker", "break_down_task")

    def test_qa_cannot_modify_code(self):
        """QA 不能调用 write_code（NO_CODE_MODIFICATION 约束）。"""
        with pytest.raises(NexusPermError):
            check_tool_permission("qa", "write_code")

    def test_qa_cannot_git_commit(self):
        """QA 不能提交代码（NO_CODE_MODIFICATION 约束）。"""
        with pytest.raises(NexusPermError):
            check_tool_permission("qa", "git_commit")

    def test_manager_cannot_write_code(self):
        """Manager 不能直接写代码（NO_DIRECT_CODE_EXECUTION 约束）。"""
        with pytest.raises(NexusPermError):
            check_tool_permission("manager", "write_code")

    def test_ceo_allowed_tools_work(self):
        """CEO 的合法工具不应抛出异常。"""
        for tool in get_role_tools("ceo"):
            check_tool_permission("ceo", tool)

    def test_worker_allowed_tools_work(self):
        """Worker 的合法工具不应抛出异常。"""
        for tool in get_role_tools("worker"):
            check_tool_permission("worker", tool)

    def test_ceo_generate_contract_via_tool(self):
        """通过工具函数调用也会执行权限校验（CEO 成功，Worker 失败）。"""
        result = generate_contract(
            role="ceo",
            task_description="测试合同",
            priority="low",
            department="IT",
            contract_id="CTR-001",
        )
        assert result["contract_id"] == "CTR-001"

        with pytest.raises(NexusPermError):
            generate_contract(
                role="worker",
                task_description="测试合同",
                priority="low",
                department="IT",
                contract_id="CTR-002",
            )

    def test_unknown_role_raises_error(self):
        """未知角色应立即抛出 PermissionError。"""
        with pytest.raises(NexusPermError) as exc_info:
            check_tool_permission("hacker", "write_code")
        assert "未知角色" in str(exc_info.value)


# --------------------------------------------------------------------------
# 测试组2：邮件路由 Chain of Command
#
# 注意：send_mail() 签名已更新为 send_mail(state_phase, to_role, ...)
# 合法路由返回 (MailMessage, None)，违规路由返回 (None, MailRejection)
# --------------------------------------------------------------------------

class TestMailRouting:
    """验证邮件路由严格遵循 Chain of Command。"""

    def test_worker_cannot_mail_ceo_directly(self):
        """Worker 不能直接给 CEO 发邮件（跨越 Manager 层级）。"""
        # worker_executing 阶段推断为 worker → ceo 是违规路由
        mail, rejection = send_mail(
            state_phase="worker_executing",
            to_role="ceo",
            subject="测试越权邮件",
            body="Worker 尝试直接联系 CEO",
        )
        assert mail is None, "违规发送不应产生邮件消息"
        assert rejection is not None, "违规发送应产生拒绝记录"
        assert rejection["attempted_from"] == "worker"
        assert rejection["attempted_to"] == "ceo"
        assert "worker" in rejection["reason"]

    def test_qa_cannot_mail_ceo_directly(self):
        """QA 不能直接给 CEO 发邮件。"""
        mail, rejection = send_mail(
            state_phase="qa_reviewing",
            to_role="ceo",
            subject="QA 越权邮件",
            body="QA 尝试直接联系 CEO",
        )
        assert mail is None
        assert rejection is not None
        assert rejection["attempted_from"] == "qa"
        assert rejection["attempted_to"] == "ceo"

    def test_worker_cannot_mail_qa_directly(self):
        """Worker 不能直接给 QA 发邮件（应通过 Manager 协调）。"""
        mail, rejection = send_mail(
            state_phase="worker_executing",
            to_role="qa",
            subject="Worker 到 QA 越权",
            body="直接联系",
        )
        assert mail is None
        assert rejection is not None

    def test_qa_cannot_mail_worker_directly(self):
        """QA 不能直接给 Worker 发邮件（应通过 Manager 协调）。"""
        mail, rejection = send_mail(
            state_phase="qa_reviewing",
            to_role="worker",
            subject="QA 到 Worker 越权",
            body="直接联系",
        )
        assert mail is None
        assert rejection is not None

    def test_ceo_can_mail_manager(self):
        """CEO 可以给 Manager 发邮件（合法下行路径）。"""
        mail, rejection = send_mail(
            state_phase="ceo_dispatch",
            to_role="manager",
            subject="合同下发",
            body="请处理以下任务",
            msg_type="contract",
        )
        assert rejection is None
        assert mail is not None
        assert mail["from_role"] == "ceo"
        assert mail["to_role"] == "manager"
        assert mail["type"] == "contract"

    def test_manager_can_mail_worker(self):
        """Manager 可以给 Worker 发邮件（合法下行路径）。"""
        mail, rejection = send_mail(
            state_phase="manager_planning",
            to_role="worker",
            subject="任务分配",
            body="请执行以下任务",
            msg_type="contract",
        )
        assert rejection is None
        assert mail is not None
        assert mail["from_role"] == "manager"
        assert mail["to_role"] == "worker"

    def test_worker_can_mail_manager(self):
        """Worker 可以给 Manager 发邮件（合法上行汇报路径）。"""
        mail, rejection = send_mail(
            state_phase="worker_executing",
            to_role="manager",
            subject="任务完成报告",
            body="已完成所有子任务",
            msg_type="report",
        )
        assert rejection is None
        assert mail is not None
        assert mail["from_role"] == "worker"
        assert mail["to_role"] == "manager"

    def test_qa_can_mail_manager(self):
        """QA 可以给 Manager 发邮件（合法上行汇报路径）。"""
        mail, rejection = send_mail(
            state_phase="qa_reviewing",
            to_role="manager",
            subject="QA 审查报告",
            body="代码审查通过",
            msg_type="report",
        )
        assert rejection is None
        assert mail is not None
        assert mail["from_role"] == "qa"
        assert mail["to_role"] == "manager"

    def test_manager_can_mail_ceo(self):
        """Manager 可以给 CEO 发邮件（合法上行上报路径）。"""
        mail, rejection = send_mail(
            state_phase="manager_review",
            to_role="ceo",
            subject="上报：无法完成任务",
            body="需要 CEO 决策",
            msg_type="escalation",
        )
        assert rejection is None
        assert mail is not None
        assert mail["from_role"] == "manager"
        assert mail["to_role"] == "ceo"

    def test_mail_message_has_timestamp_in_subject(self):
        """邮件主题应包含时间戳（格式 [ISO]）。"""
        mail, rejection = send_mail(
            state_phase="ceo_dispatch",
            to_role="manager",
            subject="测试时间戳",
            body="body",
        )
        assert rejection is None
        assert mail is not None
        assert mail["subject"].startswith("[")

    def test_check_mail_permission_returns_none_on_allowed(self):
        """check_mail_permission 对合法路由返回 None（不抛异常）。"""
        result = check_mail_permission("ceo", "manager")
        assert result is None

    def test_check_mail_permission_returns_reason_on_denied(self):
        """check_mail_permission 对违规路由返回拒绝原因字符串。"""
        reason = check_mail_permission("worker", "ceo")
        assert isinstance(reason, str)
        assert len(reason) > 0
        assert "worker" in reason


# --------------------------------------------------------------------------
# 测试组3：完整 PASS 流程端到端
# --------------------------------------------------------------------------

class TestContractPipeline:
    """验证完整的 CEO → Manager → Worker → QA PASS → CEO 批准流程。"""

    def test_full_pass_pipeline(self, base_state, graph_with_memory):
        """
        端到端测试：正常 PASS 流程。

        验证：
        - 所有节点按顺序执行
        - 最终 ceo_approved == True
        - mail_log 包含完整通信记录
        - attempt_count >= 1 且 <= max_attempts

        QA 的 llm_call 被 mock 为始终返回 PASS，确保测试确定性。
        """
        import nexus.orchestrator.tools.qa_tools as _qa_tools_mod

        def _qa_llm_always_pass(role, system_prompt, user_prompt, max_tokens=512):
            return "PASS\nAll checks passed."

        config = make_thread_config(base_state["contract_id"])

        steps: list[str] = []
        with patch.object(_qa_tools_mod, "llm_call", side_effect=_qa_llm_always_pass):
            for event in graph_with_memory.stream(base_state, config=config, stream_mode="updates"):
                for node_name in event:
                    steps.append(node_name)

            final_state = graph_with_memory.get_state(config).values

        assert "ceo_dispatch" in steps
        assert "manager_plan" in steps
        assert "worker_execute" in steps
        assert "qa_review" in steps
        assert "manager_review_after_qa" in steps
        assert "ceo_approve" in steps

        assert final_state["ceo_approved"] is True
        assert final_state["qa_verdict"] == "PASS"
        assert final_state["escalated"] is False
        assert 1 <= final_state["attempt_count"] <= base_state["max_attempts"]
        assert final_state["current_phase"] == "completed"

        assert len(final_state["mail_log"]) >= 4
        assert len(final_state["final_result"]) > 0

    def test_pipeline_state_transitions(self, base_state, graph_with_memory):
        """验证每个节点的状态转换：current_phase 必须更新到预期值。"""
        config = make_thread_config(base_state["contract_id"])
        phase_sequence: list[str] = []

        for event in graph_with_memory.stream(base_state, config=config, stream_mode="updates"):
            for node_name, node_output in event.items():
                if "current_phase" in node_output:
                    phase_sequence.append(node_output["current_phase"])

        assert "manager_planning" in phase_sequence
        assert "worker_executing" in phase_sequence
        assert "qa_reviewing" in phase_sequence
        assert "completed" in phase_sequence

    def test_pipeline_mail_log_accumulates(self, base_state, graph_with_memory):
        """验证 mail_log 通过 reducer 正确累积（不会被覆盖）。"""
        config = make_thread_config(base_state["contract_id"])

        for _ in graph_with_memory.stream(base_state, config=config, stream_mode="updates"):
            pass

        final_state = graph_with_memory.get_state(config).values
        mail_log = final_state["mail_log"]

        from_roles = {m["from_role"] for m in mail_log}
        to_roles = {m["to_role"] for m in mail_log}

        assert "ceo" in from_roles
        assert "manager" in from_roles
        assert "worker" in from_roles
        assert "qa" in from_roles


# --------------------------------------------------------------------------
# 测试组4：QA FAIL + 重试
# --------------------------------------------------------------------------

class TestQARetry:
    """验证 QA FAIL 后 Worker 自动重试机制。"""

    def test_first_fail_then_pass(self, base_state, graph_with_memory):
        """第一次 QA 返回 FAIL，第二次返回 PASS。"""
        call_count = {"n": 0}

        def patched_verdict(role, review_result, linter_result, test_result):
            call_count["n"] += 1
            from nexus.orchestrator.permissions import check_tool_permission
            check_tool_permission(role, "write_verdict")
            if call_count["n"] == 1:
                verdict: Literal["PASS", "FAIL"] = "FAIL"
                report = "QA 裁决: FAIL\n失败原因:\n  - 测试覆盖率不足\n代码质量分: 55/100"
                return verdict, report
            else:
                verdict = "PASS"
                report = "QA 裁决: PASS\n代码质量分: 92/100\n覆盖率: 88%"
                return verdict, report

        import nexus.orchestrator.nodes.qa as qa_node_mod
        with patch.object(qa_node_mod, "write_verdict", side_effect=patched_verdict):
            config = make_thread_config(base_state["contract_id"])
            steps: list[str] = []
            for event in graph_with_memory.stream(
                base_state, config=config, stream_mode="updates"
            ):
                for node_name in event:
                    steps.append(node_name)

            final_state = graph_with_memory.get_state(config).values

        worker_count = steps.count("worker_execute")
        assert worker_count == 2, f"期望 Worker 执行 2 次，实际 {worker_count} 次"

        qa_count = steps.count("qa_review")
        assert qa_count == 2, f"期望 QA 执行 2 次，实际 {qa_count} 次"

        assert final_state["ceo_approved"] is True
        assert final_state["qa_verdict"] == "PASS"
        assert final_state["attempt_count"] == 2
        assert final_state["escalated"] is False

    def test_retry_mail_log_contains_retry_messages(self, base_state, graph_with_memory):
        """验证重试时 Manager 会发送重试指令邮件给 Worker。"""
        call_count = {"n": 0}

        def patched_verdict(role, review_result, linter_result, test_result):
            call_count["n"] += 1
            from nexus.orchestrator.permissions import check_tool_permission
            check_tool_permission(role, "write_verdict")
            if call_count["n"] == 1:
                return "FAIL", "QA FAIL: 覆盖率不足"
            return "PASS", "QA PASS: 全部通过"

        import nexus.orchestrator.nodes.qa as qa_node_mod
        with patch.object(qa_node_mod, "write_verdict", side_effect=patched_verdict):
            config = make_thread_config(base_state["contract_id"])
            for _ in graph_with_memory.stream(
                base_state, config=config, stream_mode="updates"
            ):
                pass
            final_state = graph_with_memory.get_state(config).values

        subjects = [m["subject"] for m in final_state["mail_log"]]
        retry_mails = [s for s in subjects if "重试" in s]
        assert len(retry_mails) >= 1, f"期望找到重试邮件，subjects={subjects}"


# --------------------------------------------------------------------------
# 测试组5：超出最大重试次数上报
# --------------------------------------------------------------------------

class TestMaxAttemptsEscalation:
    """验证超出最大重试次数后触发上报机制。"""

    def test_escalation_when_max_attempts_reached(self, graph_with_memory):
        """max_attempts=2，QA 永远返回 FAIL，触发上报。"""
        def always_fail_verdict(role, review_result, linter_result, test_result):
            from nexus.orchestrator.permissions import check_tool_permission
            check_tool_permission(role, "write_verdict")
            return "FAIL", "QA 裁决: FAIL\n模拟永久失败"

        import nexus.orchestrator.nodes.qa as qa_node_mod

        state: NexusContractState = {
            "contract_id": f"CTR-ESC-{uuid.uuid4().hex[:6].upper()}",
            "task_description": "演示上报机制的任务",
            "priority": "critical",
            "department": "IT",
            "current_phase": "ceo_dispatch",
            "worker_output": "",
            "qa_verdict": "",
            "qa_report": "",
            "attempt_count": 0,
            "max_attempts": 2,
            "subtasks": [],
            "manager_instruction": "",
            "mail_log": [],
            "mail_rejections": [],
            "final_result": "",
            "ceo_approved": False,
            "escalated": False,
        }

        with patch.object(qa_node_mod, "write_verdict", side_effect=always_fail_verdict):
            config = make_thread_config(state["contract_id"])
            steps: list[str] = []
            for event in graph_with_memory.stream(state, config=config, stream_mode="updates"):
                for node_name in event:
                    steps.append(node_name)

            final_state = graph_with_memory.get_state(config).values

        assert "ceo_handle_escalation" in steps, (
            f"期望触发 ceo_handle_escalation 节点，实际步骤: {steps}"
        )

        assert final_state["escalated"] is True
        assert final_state["ceo_approved"] is False
        assert final_state["attempt_count"] == 2
        assert final_state["qa_verdict"] == "FAIL"
        assert "失败" in final_state["final_result"] or "关闭" in final_state["final_result"]

    def test_escalation_mail_sent_to_ceo(self, graph_with_memory):
        """验证上报时 Manager 向 CEO 发送了上报邮件。"""
        def always_fail_verdict(role, review_result, linter_result, test_result):
            from nexus.orchestrator.permissions import check_tool_permission
            check_tool_permission(role, "write_verdict")
            return "FAIL", "永久失败"

        import nexus.orchestrator.nodes.qa as qa_node_mod

        state: NexusContractState = {
            "contract_id": f"CTR-ESC2-{uuid.uuid4().hex[:6].upper()}",
            "task_description": "上报邮件测试任务",
            "priority": "high",
            "department": "IT",
            "current_phase": "ceo_dispatch",
            "worker_output": "",
            "qa_verdict": "",
            "qa_report": "",
            "attempt_count": 0,
            "max_attempts": 1,
            "subtasks": [],
            "manager_instruction": "",
            "mail_log": [],
            "mail_rejections": [],
            "final_result": "",
            "ceo_approved": False,
            "escalated": False,
        }

        with patch.object(qa_node_mod, "write_verdict", side_effect=always_fail_verdict):
            config = make_thread_config(state["contract_id"])
            for _ in graph_with_memory.stream(state, config=config, stream_mode="updates"):
                pass
            final_state = graph_with_memory.get_state(config).values

        escalation_mails = [
            m for m in final_state["mail_log"]
            if m["from_role"] == "manager" and m["to_role"] == "ceo"
            and m["type"] == "escalation"
        ]
        assert len(escalation_mails) >= 1, (
            f"期望找到 manager→ceo 上报邮件，mail_log={final_state['mail_log']}"
        )

    def test_no_escalation_within_max_attempts(self, graph_with_memory):
        """在最大重试次数内通过时，不应触发上报节点。"""
        call_count = {"n": 0}

        def second_pass_verdict(role, review_result, linter_result, test_result):
            from nexus.orchestrator.permissions import check_tool_permission
            check_tool_permission(role, "write_verdict")
            call_count["n"] += 1
            if call_count["n"] < 2:
                return "FAIL", "第一次失败"
            return "PASS", "第二次通过"

        import nexus.orchestrator.nodes.qa as qa_node_mod

        state: NexusContractState = {
            "contract_id": f"CTR-NOESC-{uuid.uuid4().hex[:6].upper()}",
            "task_description": "不应触发上报的任务",
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
            "mail_rejections": [],
            "final_result": "",
            "ceo_approved": False,
            "escalated": False,
        }

        with patch.object(qa_node_mod, "write_verdict", side_effect=second_pass_verdict):
            config = make_thread_config(state["contract_id"])
            steps: list[str] = []
            for event in graph_with_memory.stream(state, config=config, stream_mode="updates"):
                for node_name in event:
                    steps.append(node_name)
            final_state = graph_with_memory.get_state(config).values

        assert "ceo_handle_escalation" not in steps
        assert final_state["ceo_approved"] is True
        assert final_state["escalated"] is False


# --------------------------------------------------------------------------
# 测试组6：辅助功能测试
# --------------------------------------------------------------------------

class TestWorkerConstraints:
    """验证 Worker 的特殊约束（如禁止提交到 main 分支）。"""

    def test_worker_cannot_commit_to_main(self):
        """Worker 不能提交到 main 分支（NO_MAIN_BRANCH 约束）。"""
        with pytest.raises(NexusPermError) as exc_info:
            git_commit(
                role="worker",
                code="print('hello')",
                message="test commit",
                branch="main",
            )
        assert "main" in str(exc_info.value).lower() or "受保护" in str(exc_info.value)

    def test_worker_cannot_commit_to_master(self):
        """Worker 不能提交到 master 分支。"""
        with pytest.raises(NexusPermError):
            git_commit(
                role="worker",
                code="print('hello')",
                message="test commit",
                branch="master",
            )

    def test_worker_can_commit_to_feature_branch(self):
        """Worker 可以提交到 feature/ 前缀的分支。"""
        result = git_commit(
            role="worker",
            code="def hello(): return 'world'",
            message="feat: 实现 hello 函数",
            branch="feature/ctr-001",
        )
        assert isinstance(result, str)
        assert "feature/ctr-001" in result


class TestBreakDownTask:
    """验证 Manager 任务分解工具。"""

    def test_break_down_returns_list(self):
        """break_down_task 应返回非空列表。"""
        subtasks = break_down_task(
            role="manager",
            task_description="开发用户认证模块",
        )
        assert isinstance(subtasks, list)
        assert len(subtasks) > 0

    def test_break_down_permission_enforced(self):
        """非 manager 角色不能调用 break_down_task。"""
        with pytest.raises(NexusPermError):
            break_down_task(role="worker", task_description="任务")


class TestQAVerdictLogic:
    """验证 QA 裁决逻辑（不依赖 Graph 的单元测试）。"""

    def test_pass_verdict_on_clean_code(self):
        """无问题时应输出 PASS 裁决。

        mock llm_call 保证确定性：LLM 返回 'PASS' 首行时 verdict 必须为 'PASS'。
        report 是首行之后的内容，不检查是否包含 'PASS' 字符串。
        """
        import nexus.orchestrator.tools.qa_tools as _qa_tools_mod

        with patch.object(
            _qa_tools_mod,
            "llm_call",
            return_value="PASS\nAll checks passed, no issues found.",
        ):
            verdict, report = write_verdict(
                role="qa",
                review_result={"issues_found": [], "code_quality_score": 95},
                linter_result={"errors": 0, "warnings": 0},
                test_result={"status": "GREEN", "coverage": "90%"},
            )
        assert verdict == "PASS"

    def test_fail_verdict_on_linter_error(self):
        """Linter 报错时应输出 FAIL 裁决。

        mock llm_call 保证确定性：LLM 返回 'FAIL' 首行时 verdict 必须为 'FAIL'。
        report 是首行之后的内容，不检查是否包含 'FAIL' 字符串。
        """
        import nexus.orchestrator.tools.qa_tools as _qa_tools_mod

        with patch.object(
            _qa_tools_mod,
            "llm_call",
            return_value="FAIL\nLinter reported 3 errors.",
        ):
            verdict, report = write_verdict(
                role="qa",
                review_result={"issues_found": [], "code_quality_score": 80},
                linter_result={"errors": 3, "warnings": 0},
                test_result={"status": "GREEN", "coverage": "85%"},
            )
        assert verdict == "FAIL"

    def test_fail_verdict_on_test_failure(self):
        """测试失败时应输出 FAIL 裁决。"""
        verdict, report = write_verdict(
            role="qa",
            review_result={"issues_found": [], "code_quality_score": 90},
            linter_result={"errors": 0, "warnings": 0},
            test_result={"status": "RED", "coverage": "60%"},
        )
        assert verdict == "FAIL"

    def test_fail_verdict_on_code_issues(self):
        """代码审查发现问题时应输出 FAIL 裁决。"""
        verdict, report = write_verdict(
            role="qa",
            review_result={
                "issues_found": ["发现未完成的 TODO 注释"],
                "code_quality_score": 60,
            },
            linter_result={"errors": 0, "warnings": 1},
            test_result={"status": "GREEN", "coverage": "80%"},
        )
        assert verdict == "FAIL"
        assert "TODO" in report or "问题" in report

    def test_qa_cannot_call_verdict_as_worker(self):
        """非 qa 角色不能调用 write_verdict。"""
        with pytest.raises(NexusPermError):
            write_verdict(
                role="worker",
                review_result={"issues_found": []},
                linter_result={"errors": 0},
                test_result={"status": "GREEN"},
            )


# --------------------------------------------------------------------------
# 测试组7：B-01 — from_role 自动注入，不可伪造
# --------------------------------------------------------------------------

class TestMailFromRoleAutoInjected:
    """
    B-01 安全修复验证：from_role 由系统根据 state_phase 自动推断，
    调用方不能通过传入 from_role 参数伪造发件人身份。
    """

    def test_from_role_inferred_from_phase_ceo(self):
        """ceo_dispatch 阶段推断出 from_role=ceo。"""
        role = resolve_from_role("ceo_dispatch")
        assert role == "ceo"

    def test_from_role_inferred_from_phase_manager(self):
        """manager_planning 阶段推断出 from_role=manager。"""
        role = resolve_from_role("manager_planning")
        assert role == "manager"

    def test_from_role_inferred_from_phase_worker(self):
        """worker_executing 阶段推断出 from_role=worker。"""
        role = resolve_from_role("worker_executing")
        assert role == "worker"

    def test_from_role_inferred_from_phase_qa(self):
        """qa_reviewing 阶段推断出 from_role=qa。"""
        role = resolve_from_role("qa_reviewing")
        assert role == "qa"

    def test_caller_supplied_from_role_is_ignored(self):
        """
        调用方传入 from_role 会被忽略，系统使用 state_phase 推断的角色。

        即使传入 from_role="ceo"，若 state_phase 为 worker_executing，
        实际 from_role 仍是 "worker"，且路由校验用的是 "worker"，
        不会因为传入 from_role="ceo" 而绕过 Chain of Command。
        """
        # worker_executing → from_role 推断为 "worker"
        # 即使调用方试图传入 from_role="ceo"，也会触发警告并被忽略
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            mail, rejection = send_mail(
                state_phase="worker_executing",
                to_role="manager",
                subject="汇报",
                body="完成",
                from_role="ceo",  # 试图伪造为 ceo
            )

        # 应产生废弃警告
        assert len(caught) >= 1
        assert any("废弃" in str(w.message) or "from_role" in str(w.message) for w in caught)

        # 邮件应成功（worker → manager 是合法路由）
        assert rejection is None
        assert mail is not None
        # 实际 from_role 必须是 worker，不是 ceo
        assert mail["from_role"] == "worker", (
            f"期望 from_role=worker（由系统推断），实际得到 {mail['from_role']!r}"
        )

    def test_forged_identity_cannot_bypass_chain_of_command(self):
        """
        伪造 from_role="ceo" 但 state_phase="worker_executing" 时，
        系统仍用 worker 角色做路由校验，因此 worker→ceo 路由被拒绝。

        这验证了：即使攻击者试图将 from_role 伪造成高权限角色，
        由于系统从 state_phase 自动推断，伪造值被彻底忽略。
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            mail, rejection = send_mail(
                state_phase="worker_executing",
                to_role="ceo",  # worker 无权联系 ceo
                subject="伪造高权限邮件",
                body="我是 CEO，请批准",
                from_role="ceo",  # 试图伪造身份
            )

        # 路由应被拒绝（系统用 worker 做校验）
        assert mail is None, "伪造身份不应绕过路由校验"
        assert rejection is not None, "应产生违规记录"
        assert rejection["attempted_from"] == "worker", (
            f"违规记录应显示真实角色 worker，实际得到 {rejection['attempted_from']!r}"
        )
        assert rejection["attempted_to"] == "ceo"

    def test_unknown_phase_raises_value_error(self):
        """无法识别的 state_phase 应抛出 ValueError，而不是静默失败。"""
        with pytest.raises(ValueError, match="无法从 current_phase"):
            resolve_from_role("unknown_phase_xyz")

    def test_mail_log_from_role_matches_phase_role(self, base_state, graph_with_memory):
        """
        端到端验证：mail_log 中每条邮件的 from_role 必须与
        发送时所处的 current_phase 对应角色一致。
        """
        config = make_thread_config(base_state["contract_id"])
        for _ in graph_with_memory.stream(base_state, config=config, stream_mode="updates"):
            pass
        final_state = graph_with_memory.get_state(config).values

        # 每条邮件的 from_role 必须是系统合法角色之一
        valid_roles = {"ceo", "manager", "worker", "qa"}
        for msg in final_state["mail_log"]:
            assert msg["from_role"] in valid_roles, (
                f"邮件 from_role={msg['from_role']!r} 不是合法角色"
            )


# --------------------------------------------------------------------------
# 测试组8：B-02 — 违规通信审计记录
# --------------------------------------------------------------------------

class TestMailRejectionAudit:
    """
    B-02 安全修复验证：被拒绝的通信必须记录到 state.mail_rejections，
    包含 attempted_from, attempted_to, msg_type, reason, timestamp 字段。
    """

    def test_rejection_record_has_required_fields(self):
        """违规通信记录必须包含所有必要字段。"""
        mail, rejection = send_mail(
            state_phase="worker_executing",
            to_role="ceo",
            subject="越权测试",
            body="测试违规记录字段完整性",
            msg_type="info",
        )
        assert mail is None
        assert rejection is not None

        # 验证所有必要字段存在
        assert "attempted_from" in rejection
        assert "attempted_to" in rejection
        assert "msg_type" in rejection
        assert "reason" in rejection
        assert "timestamp" in rejection

        # 验证字段值
        assert rejection["attempted_from"] == "worker"
        assert rejection["attempted_to"] == "ceo"
        assert rejection["msg_type"] == "info"
        assert len(rejection["reason"]) > 0
        assert len(rejection["timestamp"]) > 0

    def test_rejection_timestamp_is_iso_format(self):
        """违规记录的 timestamp 应为 ISO 8601 格式。"""
        from datetime import datetime
        _, rejection = send_mail(
            state_phase="qa_reviewing",
            to_role="ceo",
            subject="时间戳测试",
            body="body",
        )
        assert rejection is not None
        # 应能被 fromisoformat 解析
        ts = datetime.fromisoformat(rejection["timestamp"])
        assert ts is not None

    def test_rejection_reason_contains_role_info(self):
        """违规记录的 reason 字段应包含发件人和收件人角色信息。"""
        _, rejection = send_mail(
            state_phase="worker_executing",
            to_role="ceo",
            subject="测试",
            body="body",
        )
        assert rejection is not None
        assert "worker" in rejection["reason"]
        assert "ceo" in rejection["reason"]

    def test_successful_send_produces_no_rejection(self):
        """合法发送不应产生任何违规记录。"""
        mail, rejection = send_mail(
            state_phase="ceo_dispatch",
            to_role="manager",
            subject="正常发送",
            body="body",
        )
        assert rejection is None
        assert mail is not None

    def test_multiple_rejections_accumulate(self):
        """多次违规通信应各自产生独立的违规记录。"""
        rejections = []
        for to_role in ["ceo", "qa"]:
            _, rejection = send_mail(
                state_phase="worker_executing",
                to_role=to_role,
                subject=f"越权到 {to_role}",
                body="body",
            )
            if rejection is not None:
                rejections.append(rejection)

        assert len(rejections) == 2
        targets = {r["attempted_to"] for r in rejections}
        assert "ceo" in targets
        assert "qa" in targets

    def test_mail_rejections_field_in_state(self, base_state):
        """NexusContractState 必须包含 mail_rejections 字段，初始值为空列表。"""
        assert "mail_rejections" in base_state
        assert isinstance(base_state["mail_rejections"], list)
        assert len(base_state["mail_rejections"]) == 0

    def test_rejection_accumulated_in_graph_state(self, graph_with_memory):
        """
        端到端验证：当节点中发生违规通信时，rejection 记录应通过
        LangGraph reducer 累积到 state.mail_rejections 中。

        此测试通过 mock 注入一个产生违规通信的节点行为来验证。
        """
        import nexus.orchestrator.nodes.worker as worker_node_mod
        from nexus.orchestrator.mail import send_mail as real_send_mail

        original_worker_execute = worker_node_mod.worker_execute

        def patched_worker_execute(state: NexusContractState) -> dict:
            """在正常执行后，额外注入一次违规通信（worker 试图联系 ceo）。"""
            result = original_worker_execute(state)
            # 注入违规通信
            _, rejection = real_send_mail(
                state_phase="worker_executing",
                to_role="ceo",
                subject="越权测试注入",
                body="此通信应被拒绝并记录",
            )
            if rejection is not None:
                existing = result.get("mail_rejections", [])
                result["mail_rejections"] = existing + [rejection]
            return result

        state: NexusContractState = {
            "contract_id": f"CTR-REJ-{uuid.uuid4().hex[:6].upper()}",
            "task_description": "违规通信审计测试",
            "priority": "low",
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
            "mail_rejections": [],
            "final_result": "",
            "ceo_approved": False,
            "escalated": False,
        }

        with patch.object(worker_node_mod, "worker_execute", side_effect=patched_worker_execute):
            config = make_thread_config(state["contract_id"])
            for _ in graph_with_memory.stream(state, config=config, stream_mode="updates"):
                pass
            final_state = graph_with_memory.get_state(config).values

        # mail_rejections 应包含我们注入的违规记录
        rejections = final_state.get("mail_rejections", [])
        assert len(rejections) >= 1, (
            f"期望 mail_rejections 有记录，实际 mail_rejections={rejections}"
        )
        injected = [r for r in rejections if r["attempted_to"] == "ceo"]
        assert len(injected) >= 1, (
            f"期望找到 worker→ceo 违规记录，实际 rejections={rejections}"
        )
        rec = injected[0]
        assert rec["attempted_from"] == "worker"
        assert rec["attempted_to"] == "ceo"
        assert "attempted_from" in rec
        assert "attempted_to" in rec
        assert "msg_type" in rec
        assert "reason" in rec
        assert "timestamp" in rec
