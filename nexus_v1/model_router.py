from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from .config import Difficulty, ProviderName, build_target, get_model_target, owner_for_difficulty

try:
    import litellm as _litellm
except ImportError:  # pragma: no cover - covered by dry-run mock path
    _litellm = None

CompletionFn = Callable[..., Any]


@dataclass
class RouterResponse:
    provider: str
    model: str
    content: str
    raw: Any
    usage: dict[str, int] | None = None


def _read(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _coerce_message_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = _read(item, "text", "")
            if text:
                parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content)


def _extract_text(raw_response: Any) -> str:
    choices = _read(raw_response, "choices", [])
    if not choices:
        return ""
    first = choices[0]
    message = _read(first, "message", {})
    return _coerce_message_content(_read(message, "content", ""))


def _extract_usage(raw_response: Any) -> dict[str, int] | None:
    usage = _read(raw_response, "usage")
    if usage is None:
        return None

    prompt_tokens = int(_read(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(_read(usage, "completion_tokens", 0) or 0)
    total_tokens = int(_read(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)

    if prompt_tokens == 0 and completion_tokens == 0 and total_tokens == 0:
        return None

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


class ModelRouter:
    """
    LiteLLM wrapper used by agents to route calls across Anthropic/OpenAI/Ollama.
    """

    def __init__(self, completion_fn: CompletionFn | None = None) -> None:
        self._completion_fn = completion_fn

    def _resolve_completion_fn(self) -> CompletionFn:
        if self._completion_fn is not None:
            return self._completion_fn
        if _litellm is None:
            raise RuntimeError("LiteLLM is not installed. Install with: pip install litellm")
        return _litellm.completion

    @staticmethod
    def _sanitize_messages(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
        clean: list[dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "")).strip()
            if not role:
                raise ValueError("Every message must include a non-empty 'role'.")
            content = _coerce_message_content(message.get("content", ""))
            clean.append({"role": role, "content": content})
        if not clean:
            raise ValueError("At least one message is required.")
        return clean

    def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        role: str | None = None,
        provider: ProviderName | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_params: Mapping[str, Any] | None = None,
    ) -> RouterResponse:
        if role:
            target = get_model_target(role)
        else:
            if provider is None or model is None:
                raise ValueError("Provide either role=... or both provider=... and model=...")
            target = build_target(
                provider,
                model,
                role="adhoc",
                max_tokens=max_tokens or 2048,
                temperature=temperature if temperature is not None else 0.2,
            )

        api_key = target.resolved_api_key()
        if target.provider != "ollama" and not api_key:
            env_name = target.api_key_env or "API_KEY"
            raise OSError(f"Missing {env_name} for provider '{target.provider}'.")

        request: dict[str, Any] = {
            "model": target.model,
            "messages": self._sanitize_messages(messages),
            "max_tokens": max_tokens if max_tokens is not None else target.max_tokens,
            "temperature": temperature if temperature is not None else target.temperature,
        }
        if api_key:
            request["api_key"] = api_key

        api_base = target.resolved_base_url()
        if api_base:
            request["api_base"] = api_base

        if extra_params:
            request.update(dict(extra_params))

        raw_response = self._resolve_completion_fn()(**request)
        return RouterResponse(
            provider=target.provider,
            model=str(_read(raw_response, "model", target.model)),
            content=_extract_text(raw_response),
            raw=raw_response,
            usage=_extract_usage(raw_response),
        )

    def route_by_difficulty(
        self,
        difficulty: str,
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_params: Mapping[str, Any] | None = None,
    ) -> RouterResponse:
        allowed_difficulties = {"trivial", "normal", "complex", "unclear"}
        if difficulty not in allowed_difficulties:
            raise ValueError(
                f"Unknown difficulty '{difficulty}'. Expected one of: "
                f"{', '.join(sorted(allowed_difficulties))}"
            )
        owner = owner_for_difficulty(cast(Difficulty, difficulty))
        return self.chat(
            messages,
            role=owner,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_params=extra_params,
        )
