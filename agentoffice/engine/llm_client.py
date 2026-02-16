"""LLM client — unified interface for calling models based on race.yaml config."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import yaml

from agentoffice.config import AGENTS_DIR

logger = logging.getLogger(__name__)


def load_race(agent_id: str) -> dict:
    """Load race.yaml for an agent."""
    race_path = AGENTS_DIR / agent_id / "race.yaml"
    with open(race_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def call_llm(
    agent_id: str,
    system_prompt: str,
    user_message: str,
    race: dict | None = None,
) -> dict[str, Any]:
    """Call the LLM configured in the agent's race.yaml.

    Uses litellm for unified API access across providers.

    Args:
        agent_id: The agent whose model to use.
        system_prompt: System prompt (jd + resume + memory + context).
        user_message: User message (contract content + choice menu).
        race: Pre-loaded race config (optional, loads from file if None).

    Returns:
        Parsed JSON response from the LLM, or raw text wrapped in a dict.
    """
    if race is None:
        race = load_race(agent_id)

    provider = race["provider"]
    model = race["model"]
    params = race.get("parameters", {})
    api_key_env = race.get("api_key_env", "")
    endpoint = race.get("endpoint", "")

    # Resolve API key from environment
    api_key = os.environ.get(api_key_env, "") if api_key_env else None

    # Build litellm model string
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

    try:
        import litellm

        # Configure provider-specific settings
        kwargs: dict[str, Any] = {
            "model": litellm_model,
            "messages": messages,
            "temperature": params.get("temperature", 0.2),
            "max_tokens": params.get("max_tokens", 4096),
        }

        if api_key:
            kwargs["api_key"] = api_key
        if endpoint and provider not in ("anthropic", "openai"):
            kwargs["api_base"] = endpoint

        response = litellm.completion(**kwargs)

        raw_text = response.choices[0].message.content or ""
        token_usage = {
            "input_tokens": getattr(response.usage, "prompt_tokens", 0),
            "output_tokens": getattr(response.usage, "completion_tokens", 0),
        }

        logger.info(
            "LLM response for '%s': %d input tokens, %d output tokens",
            agent_id, token_usage["input_tokens"], token_usage["output_tokens"],
        )

        # Try to parse as JSON
        parsed = _extract_json(raw_text)
        if parsed is not None:
            parsed["_token_usage"] = token_usage
            return parsed

        # Fallback: wrap raw text
        return {
            "action": {"summary": "raw_response", "output": raw_text},
            "memory_update": None,
            "choice": None,
            "choice_payload": {},
            "tool_calls": [],
            "_raw_text": raw_text,
            "_token_usage": token_usage,
        }

    except Exception:
        logger.exception("LLM call failed for agent '%s'", agent_id)
        raise


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

    # Don't double-prefix if model already has provider prefix
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

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start) if "```" in text[start:] else len(text)
        try:
            return json.loads(text[start:end].strip())
        except (json.JSONDecodeError, ValueError):
            pass

    if "```" in text:
        start = text.index("```") + 3
        # Skip optional language identifier on same line
        newline = text.index("\n", start) if "\n" in text[start:] else start
        end = text.index("```", newline) if "```" in text[newline:] else len(text)
        try:
            return json.loads(text[newline:end].strip())
        except (json.JSONDecodeError, ValueError):
            pass

    # Try finding JSON object boundaries
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    return None
