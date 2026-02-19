"""Shared LLM helper for NEXUS tools — dual compute node routing."""
from __future__ import annotations

import logging

import litellm

from nexus.orchestrator.llm_config import LOCAL_OLLAMA_URL, ROLE_BASE_URLS, ROLE_MODELS

logger = logging.getLogger(__name__)


def llm_call(
    role: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2048,
) -> str:
    """Call LLM via LiteLLM with role-based model and endpoint selection.

    Worker role routes to remote 5090 (32B model) for heavy code generation.
    All other roles use local 5060 Ti (7B model) for lighter tasks.

    Args:
        role: The agent role (worker, qa, manager, ceo).
        system_prompt: The system-level instruction for the LLM.
        user_prompt: The user-level message / task content.
        max_tokens: Maximum tokens in the response (default 2048).

    Returns:
        The LLM response text, stripped of leading/trailing whitespace.
    """
    model = ROLE_MODELS.get(role, ROLE_MODELS["worker"])
    api_base = ROLE_BASE_URLS.get(role, LOCAL_OLLAMA_URL)
    logger.info("[LLM_HELPER] llm_call: role=%s model=%s endpoint=%s", role, model, api_base)

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        api_base=api_base,
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()
