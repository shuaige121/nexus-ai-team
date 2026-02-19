"""Shared LLM helper for NEXUS tools."""
from __future__ import annotations

import logging

import litellm

from nexus.orchestrator.llm_config import OLLAMA_BASE_URL, ROLE_MODELS

logger = logging.getLogger(__name__)


def llm_call(
    role: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2048,
) -> str:
    """Call LLM via LiteLLM with role-based model selection.

    Args:
        role: The agent role (worker, qa, manager, ceo). Used to select
              the appropriate model from ROLE_MODELS.
        system_prompt: The system-level instruction for the LLM.
        user_prompt: The user-level message / task content.
        max_tokens: Maximum tokens in the response (default 2048).

    Returns:
        The LLM response text, stripped of leading/trailing whitespace.

    Raises:
        litellm.APIConnectionError: If Ollama is unreachable.
        litellm.APIError: On any other LiteLLM API error.
    """
    model = ROLE_MODELS.get(role, ROLE_MODELS["worker"])
    logger.info("[LLM_HELPER] llm_call: role=%s model=%s", role, model)

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        api_base=OLLAMA_BASE_URL,
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()
