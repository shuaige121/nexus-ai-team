"""AI 自动审批 — 用 LLM 做审批决策"""
from __future__ import annotations

import logging

from nexus.orchestrator.approval import ApprovalRequest, ApprovalStatus
from nexus.orchestrator.tools._llm_helper import llm_call

logger = logging.getLogger(__name__)

APPROVAL_SYSTEM_PROMPT = """You are the CEO of a software company reviewing a contract completion.

You must decide: APPROVE or REJECT.

Rules:
- First line MUST be exactly "APPROVE" or "REJECT" (nothing else)
- If REJECT, second line onwards must explain why (mandatory)
- Be strict but fair: approve if the work meets requirements, reject if quality is insufficient
- Consider: code quality, test coverage, security, whether requirements are met
"""


def ai_approve(request: ApprovalRequest, context: str) -> None:
    """让 AI 做审批决策。直接修改 request 状态。

    Args:
        request: The pending ApprovalRequest to resolve. Must have status PENDING.
        context: Additional context string passed to the LLM (e.g. diff, test results).

    Raises:
        ValueError: Propagated from request.reject() if notes are empty (should not
                    happen here because we always supply notes on reject paths).
        litellm.APIConnectionError: If the Ollama backend is unreachable.
    """
    if request.status != ApprovalStatus.PENDING:
        raise ValueError(
            f"审批 {request.request_id} 已经是 {request.status.value}，不能重复操作"
        )

    user_prompt = (
        f"Contract: {request.contract_id}\n"
        f"Title: {request.title}\n"
        f"\nSummary:\n{request.summary}\n"
        f"\nAdditional Context:\n{context}\n"
        f"\nDecision (APPROVE or REJECT):"
    )

    response = llm_call(
        role="ceo",
        system_prompt=APPROVAL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=512,
    )

    lines = response.strip().split("\n")
    first_line = lines[0].strip().strip("*`# ").upper() if lines else ""

    if first_line.startswith("APPROVE"):
        request.approve(by="ai_ceo")
    elif first_line.startswith("REJECT"):
        notes = (
            "\n".join(lines[1:]).strip()
            if len(lines) > 1
            else "AI reviewer rejected without specific reason"
        )
        request.reject(by="ai_ceo", notes=notes)
    else:
        # LLM did not follow the required format — conservative default: reject.
        logger.warning(
            "[AI_APPROVAL] LLM response did not start with APPROVE/REJECT: %r",
            first_line,
        )
        request.reject(
            by="ai_ceo",
            notes=f"AI response unclear, defaulting to reject. Raw response:\n{response}",
        )
