"""Gateway configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: str = "info"

    # --- Auth ---
    api_secret: str = ""
    jwt_secret: str = "change-me-in-production"
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
