"""Shared LLM helper for NEXUS tools — dual compute node routing."""
from __future__ import annotations

import logging
import time

import litellm

from nexus.orchestrator.llm_config import LOCAL_OLLAMA_URL, ROLE_BASE_URLS, ROLE_MODELS

logger = logging.getLogger(__name__)


def llm_call(
    role: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2048,
    max_retries: int = 3,
    timeout: int = 120,
) -> str:
    """Call LLM via LiteLLM with role-based model and endpoint selection.

    Worker role routes to remote 5090 (32B model) for heavy code generation.
    All other roles use local 5060 Ti (7B model) for lighter tasks.

    Includes retry logic with exponential backoff for transient failures.

    Args:
        role: The agent role (worker, qa, manager, ceo).
        system_prompt: The system-level instruction for the LLM.
        user_prompt: The user-level message / task content.
        max_tokens: Maximum tokens in the response (default 2048).
        max_retries: Maximum number of retry attempts (default 3).
        timeout: Request timeout in seconds (default 120).

    Returns:
        The LLM response text, stripped of leading/trailing whitespace.

    Raises:
        RuntimeError: If all retry attempts are exhausted.
    """
    model = ROLE_MODELS.get(role, ROLE_MODELS["worker"])
    api_base = ROLE_BASE_URLS.get(role, LOCAL_OLLAMA_URL)
    logger.info("[LLM_HELPER] llm_call: role=%s model=%s endpoint=%s", role, model, api_base)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                api_base=api_base,
                max_tokens=max_tokens,
                temperature=0.3,
                timeout=timeout,
            )
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("LLM returned None content")
            return content.strip()
        except Exception as e:
            last_error = e
            logger.warning(
                "[LLM_HELPER] attempt %d/%d failed for role=%s: %s",
                attempt, max_retries, role, e,
            )
            if attempt < max_retries:
                backoff = 2 ** attempt  # 2s, 4s, 8s
                logger.info("[LLM_HELPER] retrying in %ds...", backoff)
                time.sleep(backoff)

    logger.error("[LLM_HELPER] all %d attempts failed for role=%s", max_retries, role)
    raise RuntimeError(
        f"LLM call failed after {max_retries} attempts (role={role}, model={model}): {last_error}"
    ) from last_error
