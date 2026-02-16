from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, cast

ProviderName = Literal["anthropic", "openai", "ollama"]
AgentRole = Literal["ceo", "director", "intern", "admin"]
Difficulty = Literal["trivial", "normal", "complex", "unclear"]

PROVIDER_API_KEY_ENV: dict[ProviderName, str | None] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "ollama": "OLLAMA_API_KEY",
}

PROVIDER_BASE_URL_ENV: dict[ProviderName, str | None] = {
    "anthropic": "ANTHROPIC_BASE_URL",
    "openai": "OPENAI_BASE_URL",
    "ollama": "OLLAMA_BASE_URL",
}

PROVIDER_DEFAULT_BASE_URL: dict[ProviderName, str | None] = {
    "anthropic": None,
    "openai": None,
    "ollama": "http://localhost:11434",
}

DIFFICULTY_TO_ROLE: dict[Difficulty, AgentRole] = {
    "trivial": "intern",
    "normal": "director",
    "complex": "ceo",
    "unclear": "admin",
}


@dataclass(frozen=True)
class ModelTarget:
    role: str
    provider: ProviderName
    model: str
    max_tokens: int
    temperature: float = 0.2
    api_key_env: str | None = None
    base_url_env: str | None = None
    default_base_url: str | None = None

    def resolved_api_key(self) -> str | None:
        if not self.api_key_env:
            return None
        value = os.getenv(self.api_key_env, "").strip()
        return value or None

    def resolved_base_url(self) -> str | None:
        if self.base_url_env:
            env_value = os.getenv(self.base_url_env, "").strip()
            if env_value:
                return env_value
        return self.default_base_url


def ensure_provider_prefix(provider: ProviderName, model: str) -> str:
    if model.startswith(f"{provider}/"):
        return model
    if "/" in model:
        return model
    return f"{provider}/{model}"


def build_target(
    provider: ProviderName,
    model: str,
    *,
    role: str,
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> ModelTarget:
    return ModelTarget(
        role=role,
        provider=provider,
        model=ensure_provider_prefix(provider, model),
        max_tokens=max_tokens,
        temperature=temperature,
        api_key_env=PROVIDER_API_KEY_ENV[provider],
        base_url_env=PROVIDER_BASE_URL_ENV[provider],
        default_base_url=PROVIDER_DEFAULT_BASE_URL[provider],
    )


def get_tiered_payroll_models() -> dict[AgentRole, ModelTarget]:
    """
    Tiered Payroll from PROJECT_PLAN.md:
    - CEO      -> Claude Opus 4.6 (Anthropic)
    - Director -> Claude Sonnet 4.5 (Anthropic)
    - Intern   -> Claude Haiku 3.5 (Anthropic)
    - Admin    -> Qwen3 8B/14B (Ollama, local)
    """
    return {
        "ceo": build_target(
            "anthropic",
            os.getenv("NEXUS_MODEL_CEO", "claude-opus-4-6"),
            role="ceo",
            max_tokens=8192,
            temperature=0.2,
        ),
        "director": build_target(
            "anthropic",
            os.getenv("NEXUS_MODEL_DIRECTOR", "claude-sonnet-4-5-20250929"),
            role="director",
            max_tokens=8192,
            temperature=0.2,
        ),
        "intern": build_target(
            "anthropic",
            os.getenv("NEXUS_MODEL_INTERN", "claude-haiku-3-5"),
            role="intern",
            max_tokens=4096,
            temperature=0.3,
        ),
        "admin": build_target(
            "ollama",
            os.getenv("NEXUS_MODEL_ADMIN", "qwen3:8b"),
            role="admin",
            max_tokens=4096,
            temperature=0.1,
        ),
    }


def get_openai_fallback_target() -> ModelTarget:
    return build_target(
        "openai",
        os.getenv("NEXUS_MODEL_OPENAI_FALLBACK", "gpt-4.1-mini"),
        role="openai_fallback",
        max_tokens=8192,
        temperature=0.2,
    )


def get_model_target(role: str) -> ModelTarget:
    payroll = get_tiered_payroll_models()
    if role not in payroll:
        valid = ", ".join(sorted(payroll.keys()))
        raise KeyError(f"Unknown role '{role}'. Expected one of: {valid}")
    return payroll[cast(AgentRole, role)]


def owner_for_difficulty(difficulty: Difficulty) -> AgentRole:
    return DIFFICULTY_TO_ROLE[difficulty]
