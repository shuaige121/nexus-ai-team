"""
Progress Check 节点实现（功能2：DoubleCheck 定时回查）

当合同设置了 check_after_seconds 时，在 Worker 执行期间
系统可定期检查进度状态，防止任务卡死无人知晓。

PoC 阶段：
    不使用真实定时器（APScheduler 是后续集成的事）。
    此节点在 Graph 中存在，通过 demo 调用模拟定时触发。

进度判断逻辑：
    - worker_output 为空       → "stuck"（可能卡死）
    - worker_output 有部分内容  → "on_track"（进行中）
    - check_count >= max_checks → 上报 escalation

路由：
    progress_check → (on_track)  → END（等待下次检查）
                  → (stuck)     → manager_plan（触发 escalation）
                  → (max_checks) → ceo_handle_escalation
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from nexus.orchestrator.mail import send_mail
from nexus.orchestrator.state import NexusContractState

logger = logging.getLogger(__name__)


def check_progress(state: NexusContractState) -> dict:
    """
    Progress Check 节点：检查 Worker 的当前执行进度。

    检查策略（PoC 阶段简化逻辑）：
    1. worker_output 为空且 check_count >= 1 → "stuck"
    2. worker_output 非空 → "on_track"
    3. check_count >= max_checks → 触发上报（即使 on_track）

    Args:
        state: 当前合同状态

    Returns:
        状态更新字典，包含：
        - check_result: "on_track" / "delayed" / "stuck"
        - check_count: 累加后的回查次数
        - last_check_time: 本次回查时间（ISO 格式）
        - escalated: 超过最大回查次数时设为 True
    """
    contract_id = state["contract_id"]
    worker_output = state.get("worker_output", "")
    check_count = state.get("check_count", 0)
    max_checks = state.get("max_checks", 3)

    # 更新回查次数和时间
    new_check_count = check_count + 1
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    logger.info(
        "[PROGRESS_CHECK] 回查 contract=%s, check=%d/%d, output_len=%d",
        contract_id,
        new_check_count,
        max_checks,
        len(worker_output),
    )

    # --- 超过最大回查次数且任务未完成 → 上报 ---
    if new_check_count > max_checks and not worker_output:
        logger.error(
            "[PROGRESS_CHECK] 超过最大回查次数且无产出，触发 escalation: contract=%s",
            contract_id,
        )
        mail, rejection = send_mail(
            state_phase="check_escalation",
            to_role="ceo",
            subject=f"上报: {contract_id} 超过最大回查次数仍无进展",
            body=(
                f"合同 {contract_id} 已回查 {new_check_count} 次，"
                f"超过上限 {max_checks} 次，Worker 仍无任何产出。\n"
                f"建议 CEO 介入处理或重新分配资源。"
            ),
            msg_type="escalation",
        )
        return {
            "current_phase": "check_escalation",
            "check_result": "stuck",
            "check_count": new_check_count,
            "last_check_time": now_iso,
            "escalated": True,
            "mail_log": [mail] if mail else [],
        }

    # --- 判断当前进度状态 ---
    if not worker_output:
        # Worker 尚无任何输出
        check_result = "stuck"
        logger.warning(
            "[PROGRESS_CHECK] Worker 无产出（stuck），contract=%s", contract_id
        )
        # 通知 Manager Worker 可能卡住了
        mail, rejection = send_mail(
            state_phase="check_stuck",
            to_role="ceo",
            subject=f"进度预警: {contract_id} Worker 无响应",
            body=(
                f"合同 {contract_id} 第 {new_check_count} 次回查，"
                f"Worker 仍无任何产出，可能已卡死。\n"
                f"回查上限：{max_checks} 次。"
            ),
            msg_type="escalation",
        )
        return {
            "current_phase": "check_stuck",
            "check_result": "stuck",
            "check_count": new_check_count,
            "last_check_time": now_iso,
            "escalated": True,
            "mail_log": [mail] if mail else [],
        }

    else:
        # Worker 有输出，进度正常
        check_result = "on_track"
        logger.info(
            "[PROGRESS_CHECK] 进度正常（on_track），output_len=%d, contract=%s",
            len(worker_output),
            contract_id,
        )
        return {
            "current_phase": "check_on_track",
            "check_result": "on_track",
            "check_count": new_check_count,
            "last_check_time": now_iso,
        }


def route_after_progress_check(state: NexusContractState) -> str:
    """
    progress_check 节点后的条件路由。

    决策逻辑：
    - on_track  → "worker_execute"（继续等待 Worker 完成）
    - stuck     → "ceo_handle_escalation"（上报，Worker 已无响应）
    - delayed   → "worker_execute"（延迟但仍在进行，继续等）

    Args:
        state: 当前合同状态（check_result 已由 check_progress 填入）

    Returns:
        下一节点名称字符串
    """
    check_result = state.get("check_result", "on_track")
    escalated = state.get("escalated", False)

    if escalated or check_result == "stuck":
        logger.warning(
            "[ROUTER] route_after_progress_check: stuck/escalated → ceo_handle_escalation"
        )
        return "ceo_handle_escalation"
    else:
        logger.info(
            "[ROUTER] route_after_progress_check: %s → worker_execute", check_result
        )
        return "worker_execute"
