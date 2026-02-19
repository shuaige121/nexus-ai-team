"""Gateway configuration loaded from environment variables."""

from pydantic import field_validator
from pydantic_settings import BaseSettings

_WEAK_JWT_SECRETS = frozenset({"secret", "changeme", "password", "jwt_secret", "your-secret-here"})


class Settings(BaseSettings):
    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: str = "info"

    # --- Auth ---
    api_secret: str = ""
    jwt_secret: str  # Required: Must be set via environment variable
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # --- Rate Limiting ---
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # --- CORS ---
    cors_origins: str = "*"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- AI Providers ---
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # --- LiteLLM ---
    litellm_base_url: str = "http://localhost:4000"

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""

    # --- Database ---
    database_url: str  # Required: Must be set via environment variable


    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_strong_enough(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                f"jwt_secret must be at least 32 characters (got {len(v)})"
            )
        if v.lower() in _WEAK_JWT_SECRETS:
            raise ValueError(
                f"jwt_secret is a known weak value ({v!r}); choose a proper secret"
            )
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
