"""Forced choice mechanism — state machine transitions for each agent level.

Each level has a fixed set of choices. LLM picks one, the handler creates
the corresponding contract deterministically. No free-form "what next".
"""

from __future__ import annotations

import logging
from typing import Any

from agentoffice.config import (
    CONTRACT_ASSISTANCE,
    CONTRACT_CLARIFICATION,
    CONTRACT_CROSS_DEPARTMENT,
    CONTRACT_ESCALATION,
    CONTRACT_FAILURE,
    CONTRACT_REPORT,
    CONTRACT_REVIEW,
    CONTRACT_REVIEW_FAILED,
    CONTRACT_REVIEW_FIXED,
    CONTRACT_REVIEW_PASSED,
    CONTRACT_REVISION,
    CONTRACT_TASK,
    LEVEL_CEO,
    LEVEL_MANAGER,
    LEVEL_QA_WORKER,
    LEVEL_WORKER,
)
from agentoffice.tools.org_utils import load_org

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Choice definitions per level
# ---------------------------------------------------------------------------

WORKER_CHOICES = {
    "submit_report": {
        "label": "A. 提交完成报告",
        "description": "自动发送report contract给直属Manager",
        "contract_type": CONTRACT_REPORT,
        "target": "reports_to",  # resolved dynamically
    },
    "report_failure": {
        "label": "B. 任务失败，无法完成",
        "description": "自动发送failure contract给直属Manager，附带原因",
        "contract_type": CONTRACT_FAILURE,
        "target": "reports_to",
    },
    "request_clarification": {
        "label": "C. 需要更多信息",
        "description": "自动发送clarification contract给直属Manager",
        "contract_type": CONTRACT_CLARIFICATION,
        "target": "reports_to",
    },
    "request_assistance": {
        "label": "D. 需要其他部门协助",
        "description": "选择目标部门，自动发送assistance contract给该部门Manager",
        "contract_type": CONTRACT_ASSISTANCE,
        "target": "dynamic",  # from choice_payload.department
    },
    "request_escalation": {
        "label": "E. 缺少工具/权限",
        "description": "自动发送escalation contract给直属Manager",
        "contract_type": CONTRACT_ESCALATION,
        "target": "reports_to",
    },
}

MANAGER_REPORT_CHOICES = {
    "dispatch_review": {
        "label": "A. 派出质检",
        "description": "自动创建review contract发送给质检Worker",
        "contract_type": CONTRACT_REVIEW,
        "target": "dynamic",  # from choice_payload.reviewer
    },
    "reject_revision": {
        "label": "B. 直接打回重做",
        "description": "自动创建revision contract发回原Worker，附带修改意见",
        "contract_type": CONTRACT_REVISION,
        "target": "dynamic",  # from original contract.from
    },
    "request_supplement": {
        "label": "C. 需要补充调研",
        "description": "自动创建supplementary contract发送给指定Worker",
        "contract_type": CONTRACT_TASK,
        "target": "dynamic",
    },
    "report_to_ceo": {
        "label": "D. 向CEO汇报（本部门任务全部完成）",
        "description": "自动创建report contract发送给CEO",
        "contract_type": CONTRACT_REPORT,
        "target": "reports_to",
    },
    "request_cross_department": {
        "label": "E. 需要其他部门配合",
        "description": "选择目标部门，自动发送cross_department contract",
        "contract_type": CONTRACT_CROSS_DEPARTMENT,
        "target": "dynamic",
    },
    "escalate_to_ceo": {
        "label": "F. 升级问题给CEO",
        "description": "自动创建escalation contract发送给CEO",
        "contract_type": CONTRACT_ESCALATION,
        "target": "reports_to",
    },
}

QA_WORKER_CHOICES = {
    "review_passed": {
        "label": "A. 质检通过",
        "description": "自动发送review_passed contract给Manager",
        "contract_type": CONTRACT_REVIEW_PASSED,
        "target": "reports_to",
    },
    "review_fixed": {
        "label": "B. 质检不通过，已修复",
        "description": "自动发送review_fixed contract给Manager，附带修改内容",
        "contract_type": CONTRACT_REVIEW_FIXED,
        "target": "reports_to",
    },
    "review_failed": {
        "label": "C. 质检不通过，无法修复",
        "description": "自动发送review_failed contract给Manager，附带问题说明",
        "contract_type": CONTRACT_REVIEW_FAILED,
        "target": "reports_to",
    },
}

MANAGER_REVIEW_CHOICES = {
    "accept_output": {
        "label": "A. 质检通过，收录该Worker的产出",
        "description": "更新本次任务的产出集合。如果所有子任务都已完成则自动汇报CEO",
        "contract_type": CONTRACT_REPORT,
        "target": "reports_to",
    },
    "reject_after_review": {
        "label": "B. 质检未通过，打回原Worker重做",
        "description": "自动创建revision contract",
        "contract_type": CONTRACT_REVISION,
        "target": "dynamic",
    },
    "accept_fixed": {
        "label": "C. 质检修复版本可接受",
        "description": "同A，收录修复版本",
        "contract_type": CONTRACT_REPORT,
        "target": "reports_to",
    },
    "escalate_severe": {
        "label": "D. 问题严重，升级给CEO",
        "description": "自动创建escalation contract",
        "contract_type": CONTRACT_ESCALATION,
        "target": "reports_to",
    },
}

CEO_CHOICES = {
    "approve_complete": {
        "label": "A. 结果达标，任务完成",
        "description": "自动整合所有部门产出，生成最终报告给用户（董事会）",
        "contract_type": CONTRACT_REPORT,
        "target": "board",
    },
    "request_revision": {
        "label": "B. 结果不达标，要求修改",
        "description": "自动创建revision contract发回该Manager",
        "contract_type": CONTRACT_REVISION,
        "target": "dynamic",  # from original contract.from
    },
    "request_additional_dept": {
        "label": "C. 需要额外部门介入",
        "description": "指定部门，自动通过HR创建新任务",
        "contract_type": CONTRACT_TASK,
        "target": "hr_lead",
    },
    "partial_approve": {
        "label": "D. 部分达标，等待其他部门",
        "description": "标记该部门完成，继续等待",
        "contract_type": None,  # no new contract, just update state
        "target": None,
    },
}

# Map of level + context → choice set
CHOICE_SETS: dict[str, dict] = {
    LEVEL_WORKER: WORKER_CHOICES,
    LEVEL_QA_WORKER: QA_WORKER_CHOICES,
    f"{LEVEL_MANAGER}_report": MANAGER_REPORT_CHOICES,
    f"{LEVEL_MANAGER}_review": MANAGER_REVIEW_CHOICES,
    LEVEL_CEO: CEO_CHOICES,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_choices_for_agent(
    agent_id: str,
    level: str,
    contract_type: str | None = None,
) -> dict:
    """Get the valid choices for an agent based on level and context.

    Returns the choice set dict.
    """
    if level == LEVEL_MANAGER:
        # Determine which manager choice set based on incoming contract type
        if contract_type in (CONTRACT_REVIEW_PASSED, CONTRACT_REVIEW_FIXED, CONTRACT_REVIEW_FAILED):
            return MANAGER_REVIEW_CHOICES
        return MANAGER_REPORT_CHOICES
    return CHOICE_SETS.get(level, WORKER_CHOICES)


def format_choices_prompt(choices: dict, agent_id: str) -> str:
    """Format the choice menu as text to append to the LLM prompt."""
    org = load_org()
    departments = org.get("departments", [])
    dept_list = ", ".join(d["id"] for d in departments if d["id"] not in ("executive", "hr"))

    lines = [
        "",
        "---",
        "你已完成当前工作，请从以下选项中选择下一步（在JSON的choice字段中填写选项ID）：",
        "",
    ]
    for choice_id, choice_def in choices.items():
        lines.append(f"  {choice_def['label']}  (choice: \"{choice_id}\")")
        lines.append(f"    → {choice_def['description']}")

    has_dynamic = any(c.get("target") == "dynamic" for c in choices.values())
    if has_dynamic and dept_list:
        lines.append(f"\n可选部门：[{dept_list}]")

    lines.append("\n如需向特定agent发送，请在choice_payload中指明to字段。")
    return "\n".join(lines)


def resolve_choice_target(
    agent_id: str,
    choice_id: str,
    choice_def: dict,
    choice_payload: dict[str, Any],
    source_contract: dict,
) -> str | None:
    """Resolve the target agent_id for a choice.

    - "reports_to": look up in org.yaml chain_of_command
    - "board": return "board" (terminal)
    - "dynamic": read from choice_payload["to"] or source contract
    - None: no target (state update only)
    """
    target_spec = choice_def.get("target")

    if target_spec is None:
        return None

    if target_spec == "board":
        return "board"

    if target_spec == "reports_to":
        org = load_org()
        chain = org.get("chain_of_command", {}).get(agent_id, {})
        return chain.get("reports_to")

    if target_spec == "dynamic":
        # First check explicit payload
        if "to" in choice_payload:
            return choice_payload["to"]
        # For revisions, send back to the original sender
        if choice_id in ("reject_revision", "reject_after_review", "request_revision"):
            return source_contract.get("from")
        # For department requests, find the department manager
        if "department" in choice_payload:
            return _find_department_head(choice_payload["department"])
        # For review dispatch, use reviewer from payload
        if "reviewer" in choice_payload:
            return choice_payload["reviewer"]

        logger.warning(
            "Cannot resolve dynamic target for choice '%s' of agent '%s'. "
            "choice_payload=%s",
            choice_id, agent_id, choice_payload,
        )
        return None

    return target_spec


def _find_department_head(department_id: str) -> str | None:
    """Find the manager/head of a department from org.yaml."""
    org = load_org()
    for dept in org.get("departments", []):
        if dept["id"] == department_id:
            positions = dept.get("positions", [])
            # The first position is typically the head/manager
            if positions:
                return positions[0]
    return None
