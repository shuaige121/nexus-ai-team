"""LLM configuration for NEXUS orchestrator — dual compute nodes."""
import os

# Dual Ollama endpoints
LOCAL_OLLAMA_URL = os.getenv("NEXUS_LOCAL_OLLAMA", "http://localhost:11434")
REMOTE_OLLAMA_URL = os.getenv("NEXUS_REMOTE_OLLAMA", "http://192.168.7.6:11434")

# Models
LOCAL_MODEL = "ollama/qwen2.5-coder:7b"
REMOTE_MODEL = "ollama/qwen2.5-coder:32b"

# Role → model: Worker needs power for code gen, others are lighter tasks
ROLE_MODELS = {
    "worker": REMOTE_MODEL,
    "qa": LOCAL_MODEL,
    "manager": LOCAL_MODEL,
    "ceo": LOCAL_MODEL,
}

# Role → base URL: matches ROLE_MODELS to appropriate Ollama instance
ROLE_BASE_URLS = {
    "worker": REMOTE_OLLAMA_URL,
    "qa": LOCAL_OLLAMA_URL,
    "manager": LOCAL_OLLAMA_URL,
    "ceo": LOCAL_OLLAMA_URL,
}
