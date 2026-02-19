"""Shared LLM helper for NEXUS tools — 5060 Ti primary, 5090 fallback.

All roles use the same model and endpoint. Role differentiation is
achieved through the system_prompt parameter, not model selection.

If the primary endpoint (5060 Ti) is unreachable within 5 seconds,
the helper automatically falls back to the 5090 node.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import litellm

from nexus.orchestrator.llm_config import (
    FALLBACK_MODEL_NAME,
    FALLBACK_OLLAMA_BASE_URL,
    MODEL_NAME,
    OLLAMA_BASE_URL,
)

logger = logging.getLogger(__name__)

# Connection timeout for the primary endpoint (seconds).
# If we get no response within this window, we switch to fallback.
_PRIMARY_CONNECT_TIMEOUT = 5


def _try_completion(
    model: str,
    api_base: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    timeout: int,
) -> Optional[str]:
    """Attempt a single LLM completion call. Returns text or None on failure."""
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


def llm_call(
    role: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2048,
    max_retries: int = 3,
    timeout: int = 120,
) -> str:
    """Call LLM via LiteLLM with automatic fallback.

    First tries the primary endpoint (5060 Ti / 14B) with a short connect
    timeout.  If that fails due to connection issues, switches to the
    fallback endpoint (5090 / 32B) for remaining retries.

    All roles (worker, qa, manager, ceo) use the same model on each
    endpoint. Role-specific behaviour is driven entirely by system_prompt.

    Includes retry logic with exponential backoff for transient failures.

    Args:
        role: The agent role (worker, qa, manager, ceo) -- for logging only.
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
    logger.info(
        "[LLM_HELPER] llm_call: role=%s primary=%s/%s fallback=%s/%s",
        role, OLLAMA_BASE_URL, MODEL_NAME,
        FALLBACK_OLLAMA_BASE_URL, FALLBACK_MODEL_NAME,
    )

    # -- Attempt 1: try the primary endpoint with a short timeout -----------
    try:
        result = _try_completion(
            model=MODEL_NAME,
            api_base=OLLAMA_BASE_URL,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            timeout=_PRIMARY_CONNECT_TIMEOUT,
        )
        return result
    except Exception as primary_err:
        logger.warning(
            "[LLM_HELPER] primary endpoint failed for role=%s: %s  -- switching to fallback",
            role, primary_err,
        )

    # -- Remaining retries on the fallback endpoint -------------------------
    active_model = FALLBACK_MODEL_NAME
    active_base = FALLBACK_OLLAMA_BASE_URL

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            result = _try_completion(
                model=active_model,
                api_base=active_base,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            return result
        except Exception as e:
            last_error = e
            logger.warning(
                "[LLM_HELPER] fallback attempt %d/%d failed for role=%s: %s",
                attempt, max_retries, role, e,
            )
            if attempt < max_retries:
                backoff = 2 ** attempt  # 2s, 4s, 8s
                logger.info("[LLM_HELPER] retrying in %ds...", backoff)
                time.sleep(backoff)

    logger.error("[LLM_HELPER] all attempts failed for role=%s", role)
    raise RuntimeError(
        f"LLM call failed after primary + {max_retries} fallback attempts "
        f"(role={role}, primary={MODEL_NAME}, fallback={active_model}): {last_error}"
    ) from last_error
