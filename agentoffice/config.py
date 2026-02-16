"""AgentOffice configuration — paths, constants, and defaults."""

from pathlib import Path

# Base directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPANY_DIR = PROJECT_ROOT / "company"

# Data paths
ORG_YAML_PATH = COMPANY_DIR / "org.yaml"
AGENTS_DIR = COMPANY_DIR / "agents"
CONTRACTS_DIR = COMPANY_DIR / "contracts"
TEMPLATES_DIR = COMPANY_DIR / "templates"

# Contract subdirectories
PENDING_DIR = CONTRACTS_DIR / "pending"
COMPLETED_DIR = CONTRACTS_DIR / "completed"
ARCHIVED_DIR = CONTRACTS_DIR / "archived"

# Agent file names
JD_FILE = "jd.md"
RESUME_FILE = "resume.md"
MEMORY_FILE = "memory.md"
RACE_FILE = "race.yaml"

# Limits
MEMORY_CHAR_LIMIT = 2000

# Agent levels
LEVEL_CEO = "ceo"
LEVEL_MANAGER = "manager"
LEVEL_WORKER = "worker"
LEVEL_QA_WORKER = "qa_worker"

# Contract types
CONTRACT_TASK = "task"
CONTRACT_REPORT = "report"
CONTRACT_CLARIFICATION = "clarification"
CONTRACT_REVISION = "revision"
CONTRACT_ESCALATION = "escalation"
CONTRACT_ASSISTANCE = "assistance"
CONTRACT_REVIEW = "review"
CONTRACT_REVIEW_PASSED = "review_passed"
CONTRACT_REVIEW_FIXED = "review_fixed"
CONTRACT_REVIEW_FAILED = "review_failed"
CONTRACT_CROSS_DEPARTMENT = "cross_department"
CONTRACT_FAILURE = "failure"

# Priority levels
PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"
