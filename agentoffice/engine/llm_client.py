"""LLM client -- unified interface for calling models based on race.yaml config."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import yaml

from agentoffice.config import AGENTS_DIR

logger = logging.getLogger(__name__)

# Budget and retry constants
LLM_CALL_TIMEOUT: int = 60
MAX_RETRIES: int = 3
RETRY_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)
DEFAULT_DAILY_BUDGET_USD: float = 10.0

# Simple in-process daily budget tracker
_daily_cost: float = 0.0
_budget_date: str = ""


def _get_daily_budget() -> float:
    """Read the daily budget limit from environment."""
    try:
        return float(os.environ.get("LLM_DAILY_BUDGET_USD", DEFAULT_DAILY_BUDGET_USD))
    except (ValueError, TypeError):
        return DEFAULT_DAILY_BUDGET_USD


def _check_and_update_budget(cost: float) -> None:
    """Track cumulative daily cost. Resets at midnight UTC."""
    global _daily_cost, _budget_date
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if _budget_date != today:
        _daily_cost = 0.0
        _budget_date = today
    _daily_cost += cost


def _is_budget_exceeded() -> bool:
    """Return True if today's spend has exceeded the budget."""
    global _daily_cost, _budget_date
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if _budget_date != today:
        _daily_cost = 0.0
        _budget_date = today
    return _daily_cost >= _get_daily_budget()


def load_race(agent_id: str) -> dict:
    """Load race.yaml for an agent."""
    race_path = AGENTS_DIR / agent_id / "race.yaml"
    with open(race_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Rough cost estimate in USD based on common model pricing."""
    pricing = {
        "gpt-4": (0.03, 0.06),
        "gpt-4o": (0.005, 0.015),
        "gpt-4o-mini": (0.00015, 0.0006),
        "gpt-3.5-turbo": (0.0005, 0.0015),
        "claude-3-opus": (0.015, 0.075),
        "claude-3-sonnet": (0.003, 0.015),
        "claude-3-haiku": (0.00025, 0.00125),
        "claude-sonnet-4": (0.003, 0.015),
        "deepseek-chat": (0.00014, 0.00028),
    }
    per_1k_in, per_1k_out = 0.002, 0.006  # default fallback
    for key, (pi, po) in pricing.items():
        if key in model.lower():
            per_1k_in, per_1k_out = pi, po
            break
    return (input_tokens / 1000) * per_1k_in + (output_tokens / 1000) * per_1k_out


def call_llm(
    agent_id: str,
    system_prompt: str,
    user_message: str,
    race: dict | None = None,
) -> dict[str, Any]:
    """Call the LLM configured in the agent's race.yaml.

    Uses litellm for unified API access across providers.
    Includes timeout, exponential-backoff retry, and daily budget guard.

    Args:
        agent_id: The agent whose model to use.
        system_prompt: System prompt (jd + resume + memory + context).
        user_message: User message (contract content + choice menu).
        race: Pre-loaded race config (optional, loads from file if None).

    Returns:
        Parsed JSON response from the LLM, or raw text wrapped in a dict.

    Raises:
        RuntimeError: If daily budget is exceeded.
    """
    if _is_budget_exceeded():
        budget = _get_daily_budget()
        raise RuntimeError(
            f"LLM daily budget exceeded (${_daily_cost:.2f} / ${budget:.2f}). "
            "Set LLM_DAILY_BUDGET_USD to increase."
        )

    if race is None:
        race = load_race(agent_id)

    provider = race["provider"]
    model = race["model"]
    params = race.get("parameters", {})
    api_key_env = race.get("api_key_env", "")
    endpoint = race.get("endpoint", "")

    api_key = os.environ.get(api_key_env, "") if api_key_env else None

    litellm_model = _build_litellm_model(provider, model)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    logger.info(
        "Calling LLM for agent '%s': provider=%s model=%s temp=%.2f max_tokens=%d",
        agent_id, provider, model,
        params.get("temperature", 0.2),
        params.get("max_tokens", 4096),
    )

    import litellm

    kwargs: dict[str, Any] = {
        "model": litellm_model,
        "messages": messages,
        "temperature": params.get("temperature", 0.2),
        "max_tokens": params.get("max_tokens", 4096),
        "timeout": LLM_CALL_TIMEOUT,
    }

    if api_key:
        kwargs["api_key"] = api_key
    if endpoint and provider not in ("anthropic", "openai"):
        kwargs["api_base"] = endpoint

    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.monotonic()
            response = litellm.completion(**kwargs)
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            raw_text = response.choices[0].message.content or ""
            input_tokens = getattr(response.usage, "prompt_tokens", 0)
            output_tokens = getattr(response.usage, "completion_tokens", 0)
            cost = _estimate_cost(litellm_model, input_tokens, output_tokens)
            _check_and_update_budget(cost)

            token_usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

            logger.info(
                "LLM call for '%s': model=%s tokens=%d+%d cost=$%.4f elapsed=%dms (attempt %d)",
                agent_id, litellm_model,
                input_tokens, output_tokens, cost,
                elapsed_ms, attempt + 1,
            )

            parsed = _extract_json(raw_text)
            if parsed is not None:
                parsed["_token_usage"] = token_usage
                return parsed

            return {
                "action": {"summary": "raw_response", "output": raw_text},
                "memory_update": None,
                "choice": None,
                "choice_payload": {},
                "tool_calls": [],
                "_raw_text": raw_text,
                "_token_usage": token_usage,
            }

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                logger.warning(
                    "LLM call failed for '%s' (attempt %d/%d), retrying in %.1fs: %s",
                    agent_id, attempt + 1, MAX_RETRIES, delay, e,
                )
                time.sleep(delay)
            else:
                logger.exception(
                    "LLM call failed for '%s' after %d attempts", agent_id, MAX_RETRIES
                )

    raise last_error  # type: ignore[misc]


def _build_litellm_model(provider: str, model: str) -> str:
    """Build litellm model identifier string."""
    prefix_map = {
        "anthropic": "anthropic/",
        "openai": "openai/",
        "deepseek": "deepseek/",
        "local": "ollama/",
        "ollama": "ollama/",
    }
    prefix = prefix_map.get(provider, "")

    if model.startswith(prefix) or "/" in model:
        return model

    return f"{prefix}{model}"


def _extract_json(text: str) -> dict | None:
    """Try to extract a JSON object from LLM response text.

    Handles common patterns:
    - Pure JSON
    - JSON wrapped in markdown code blocks
    - JSON with leading/trailing text
    """
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start) if "```" in text[start:] else len(text)
        try:
            return json.loads(text[start:end].strip())
        except (json.JSONDecodeError, ValueError):
            pass

    if "```" in text:
        start = text.index("```") + 3
        newline = text.index("\n", start) if "\n" in text[start:] else start
        end = text.index("```", newline) if "```" in text[newline:] else len(text)
        try:
            return json.loads(text[newline:end].strip())
        except (json.JSONDecodeError, ValueError):
            pass

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    return None
