"""LLM configuration for NEXUS orchestrator MVP."""

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "ollama/qwen2.5-coder:7b"

# Role-specific model mapping (all same for MVP, can diverge later)
ROLE_MODELS = {
    "worker": DEFAULT_MODEL,
    "qa": DEFAULT_MODEL,
    "manager": DEFAULT_MODEL,
    "ceo": DEFAULT_MODEL,
}
