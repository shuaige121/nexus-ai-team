"""LLM configuration for NEXUS orchestrator — 5060 Ti primary, 5090 fallback.

All roles (CEO, Manager, Worker, QA) use the same model.
Role differentiation is achieved through system prompts, NOT different models.

Primary:  5060 Ti local Ollama (localhost:11434) with qwen2.5-coder:14b
Fallback: 5090 node (192.168.7.6:11434) with qwen2.5-coder:32b
"""
import os

# ---------------------------------------------------------------------------
# Primary Ollama endpoint — 5060 Ti local node
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv(
    "NEXUS_OLLAMA_URL", "http://localhost:11434"
)

# ---------------------------------------------------------------------------
# Primary model — 14B on 5060 Ti
# ---------------------------------------------------------------------------
MODEL_NAME = os.getenv(
    "NEXUS_MODEL_NAME", "ollama/qwen2.5-coder:14b"
)

# ---------------------------------------------------------------------------
# Fallback Ollama endpoint — 5090 node
# Used automatically when primary is unreachable (connection timeout).
# ---------------------------------------------------------------------------
FALLBACK_OLLAMA_BASE_URL = os.getenv(
    "NEXUS_FALLBACK_OLLAMA_URL", "http://192.168.7.6:11434"
)

# ---------------------------------------------------------------------------
# Fallback model — 32B on 5090
# ---------------------------------------------------------------------------
FALLBACK_MODEL_NAME = os.getenv(
    "NEXUS_FALLBACK_MODEL_NAME", "ollama/qwen2.5-coder:32b"
)

# ---------------------------------------------------------------------------
# Parallel execution configuration
# ---------------------------------------------------------------------------
# Maximum number of contracts that can run simultaneously.
# Requests beyond this limit are queued and processed in FIFO order.
MAX_PARALLEL_CONTRACTS = int(os.getenv("NEXUS_MAX_PARALLEL", "3"))
