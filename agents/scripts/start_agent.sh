#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# start_agent.sh — Start a single Agent's Claude Code process
#
# Usage: start_agent.sh <agent_id> [--model <model>] [--background] [--log <file>]
#
# Reads agent configuration from registry.yaml (if present), verifies the
# workspace, generates CLAUDE.md, and launches claude in headless (--print)
# mode with the agent's working directory.
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

REGISTRY_FILE="${AGENTS_ROOT}/registry.yaml"

# claude CLI command — override via CLAUDE_CMD for mock/testing
CLAUDE_CMD="${CLAUDE_CMD:-claude}"

# Default model mapping (mirrors create_agent.sh)
DEFAULT_MODEL_WORKER="sonnet"
DEFAULT_MODEL_QA="sonnet"
DEFAULT_MODEL_MANAGER="opus"
DEFAULT_MODEL_CEO="opus"
DEFAULT_MODEL_HR="sonnet"
DEFAULT_MODEL_IT="sonnet"

usage() {
    cat <<'EOF'
Usage: start_agent.sh <agent_id> [--model <model>] [--background] [--log <file>]

Start a single Agent's Claude Code process.

Arguments:
  agent_id    The agent ID to start (e.g. ceo, dept-gateway-dev-01)

Options:
  --model <model>   LLM model override (default: read from registry or role default)
  --background      Run in background with nohup, detached from terminal
  --log <file>      Log file path (default: agents/{agent_id}/agent.log)
  --help            Show this help message

Behavior:
  1. Reads agent config from registry.yaml (if exists), else checks directory
  2. Verifies workspace: JD.md, TOOL.md, MEMORY.md, INBOX/
  3. Generates CLAUDE.md in the agent's workspace from JD.md
  4. Builds and executes the claude CLI command in the agent's directory
  5. If sudo available and agent Linux user exists: runs as agent-{agent_id}
  6. Records PID to agents/{agent_id}/.pid
  7. In --background mode: uses nohup with output to log file

Examples:
  start_agent.sh ceo
  start_agent.sh dept-gateway-dev-01 --model sonnet --background
  start_agent.sh ceo --log /tmp/ceo.log --background
EOF
}

# --help check (before anything else)
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# --- Argument parsing --------------------------------------------------------

if [[ $# -lt 1 ]]; then
    echo "Error: Missing agent_id." >&2
    echo "Run 'start_agent.sh --help' for usage." >&2
    exit 1
fi

AGENT_ID="$1"
shift

MODEL=""
BACKGROUND=false
LOG_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)
            if [[ $# -lt 2 ]]; then
                echo "Error: --model requires a value." >&2
                exit 1
            fi
            MODEL="$2"
            shift 2
            ;;
        --background)
            BACKGROUND=true
            shift
            ;;
        --log)
            if [[ $# -lt 2 ]]; then
                echo "Error: --log requires a value." >&2
                exit 1
            fi
            LOG_FILE="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'." >&2
            echo "Run 'start_agent.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

# --- Validate agent workspace ------------------------------------------------

AGENT_DIR="${AGENTS_ROOT}/${AGENT_ID}"

if [[ ! -d "$AGENT_DIR" ]]; then
    echo "Error: Agent directory '${AGENT_DIR}' does not exist." >&2
    echo "Create the agent first with create_agent.sh." >&2
    exit 1
fi

# Check required workspace files
for required_file in JD.md TOOL.md MEMORY.md; do
    if [[ ! -f "${AGENT_DIR}/${required_file}" ]]; then
        echo "Error: Required file '${AGENT_DIR}/${required_file}' not found." >&2
        exit 1
    fi
done

if [[ ! -d "${AGENT_DIR}/INBOX" ]]; then
    echo "Error: INBOX directory '${AGENT_DIR}/INBOX' not found." >&2
    exit 1
fi

# --- Read configuration from registry ----------------------------------------

ROLE=""
REG_MODEL=""

if [[ -f "$REGISTRY_FILE" ]]; then
    # Try to read role and model from registry for this agent
    if grep -q "^  ${AGENT_ID}:" "$REGISTRY_FILE" 2>/dev/null; then
        ROLE=$(awk -v agent_id="  ${AGENT_ID}:" '
            BEGIN { in_agent = 0 }
            $0 == agent_id { in_agent = 1; next }
            in_agent && /^    role:/ {
                sub(/^    role: */, "")
                gsub(/[[:space:]]*$/, "")
                print
                exit
            }
            in_agent && /^  [^ ]/ { exit }
        ' "$REGISTRY_FILE")

        REG_MODEL=$(awk -v agent_id="  ${AGENT_ID}:" '
            BEGIN { in_agent = 0 }
            $0 == agent_id { in_agent = 1; next }
            in_agent && /^    model:/ {
                sub(/^    model: */, "")
                gsub(/[[:space:]]*$/, "")
                print
                exit
            }
            in_agent && /^  [^ ]/ { exit }
        ' "$REGISTRY_FILE")

        # Check if agent is active
        AGENT_STATUS=$(awk -v agent_id="  ${AGENT_ID}:" '
            BEGIN { in_agent = 0 }
            $0 == agent_id { in_agent = 1; next }
            in_agent && /^    status:/ {
                sub(/^    status: */, "")
                gsub(/[[:space:]]*$/, "")
                print
                exit
            }
            in_agent && /^  [^ ]/ { exit }
        ' "$REGISTRY_FILE")

        if [[ "$AGENT_STATUS" == "archived" ]]; then
            echo "Error: Agent '${AGENT_ID}' is archived in registry. Cannot start." >&2
            exit 1
        fi
    fi
fi

# --- Determine model ---------------------------------------------------------

# Priority: CLI --model > registry model > role default > fallback
if [[ -z "$MODEL" ]]; then
    if [[ -n "$REG_MODEL" ]]; then
        MODEL="$REG_MODEL"
    elif [[ -n "$ROLE" ]]; then
        case "$ROLE" in
            worker)     MODEL="$DEFAULT_MODEL_WORKER" ;;
            qa)         MODEL="$DEFAULT_MODEL_QA" ;;
            manager)    MODEL="$DEFAULT_MODEL_MANAGER" ;;
            ceo)        MODEL="$DEFAULT_MODEL_CEO" ;;
            hr)         MODEL="$DEFAULT_MODEL_HR" ;;
            it-support) MODEL="$DEFAULT_MODEL_IT" ;;
            *)          MODEL="sonnet" ;;
        esac
    else
        MODEL="sonnet"
    fi
fi

# --- Check if already running ------------------------------------------------

PID_FILE="${AGENT_DIR}/.pid"

if [[ -f "$PID_FILE" ]]; then
    OLD_PID="$(cat "$PID_FILE")"
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Error: Agent '${AGENT_ID}' is already running (PID ${OLD_PID})." >&2
        echo "Stop it first with stop_agent.sh, or remove ${PID_FILE} if stale." >&2
        exit 1
    else
        # Stale PID file — clean up
        echo "Warning: Removing stale PID file (PID ${OLD_PID} no longer running)." >&2
        rm -f "$PID_FILE"
    fi
fi

# --- Generate CLAUDE.md ------------------------------------------------------

# CLAUDE.md is read automatically by Claude Code when working in a directory.
# We populate it with the agent's JD.md content plus operational instructions.

CLAUDE_MD="${AGENT_DIR}/CLAUDE.md"

JD_CONTENT="$(cat "${AGENT_DIR}/JD.md")"
TOOL_CONTENT="$(cat "${AGENT_DIR}/TOOL.md")"

cat > "$CLAUDE_MD" <<CLAUDEMD
# Agent: ${AGENT_ID}

## Job Description

${JD_CONTENT}

## Available Tools

${TOOL_CONTENT}

## Operational Instructions

1. Check your INBOX/ directory for new .md files (unread mail).
2. Process each mail according to your JD workflow above.
3. Use the scripts in agents/scripts/ for communication:
   - send_mail.sh: Send mail to other agents
   - check_inbox.sh: List inbox contents
   - read_mail.sh: Read a specific mail
   - write_memory.sh: Write to your MEMORY.md
4. After processing all inbox items and completing your workflow, you may exit.
5. Always write important decisions and status to MEMORY.md.
CLAUDEMD

# --- Set default log file ----------------------------------------------------

if [[ -z "$LOG_FILE" ]]; then
    LOG_FILE="${AGENT_DIR}/agent.log"
fi

# --- Build the system prompt -------------------------------------------------

SYSTEM_PROMPT="You are agent '${AGENT_ID}'. Your working directory is ${AGENT_DIR}. Check your INBOX/ for new .md files and process them according to your JD.md workflow. Use the bash scripts in ${SCRIPT_DIR}/ for communication and tool operations. When finished processing all tasks, exit cleanly."

# --- Build the launch command ------------------------------------------------

# Construct the prompt that tells the agent to start working
AGENT_PROMPT="Start working. Check INBOX/ for new mail, then follow your JD.md workflow."

# Build the claude command arguments
CLAUDE_ARGS=()
CLAUDE_ARGS+=("--print")
CLAUDE_ARGS+=("--model" "$MODEL")
CLAUDE_ARGS+=("--system-prompt" "$SYSTEM_PROMPT")
CLAUDE_ARGS+=("--verbose")

# --- Determine execution user ------------------------------------------------

# If we have sudo privileges and a dedicated Linux user exists, run as that user
RUN_AS_USER=""
AGENT_LINUX_USER="agent-${AGENT_ID}"

if command -v sudo &>/dev/null && sudo -n true 2>/dev/null; then
    if id "$AGENT_LINUX_USER" &>/dev/null; then
        RUN_AS_USER="$AGENT_LINUX_USER"
        echo "Will run as Linux user: ${RUN_AS_USER}"
    fi
fi

# --- Launch the agent --------------------------------------------------------

echo "Starting agent '${AGENT_ID}'..."
echo "  Directory: ${AGENT_DIR}"
echo "  Model:     ${MODEL}"
echo "  Role:      ${ROLE:-unknown}"
echo "  Log:       ${LOG_FILE}"
echo "  Background: ${BACKGROUND}"

if [[ "$BACKGROUND" == true ]]; then
    # Background mode: use nohup, redirect output to log, record PID
    if [[ -n "$RUN_AS_USER" ]]; then
        nohup sudo -u "$RUN_AS_USER" \
            bash -c "cd \"${AGENT_DIR}\" && ${CLAUDE_CMD} ${CLAUDE_ARGS[*]} \"${AGENT_PROMPT}\"" \
            > "$LOG_FILE" 2>&1 &
    else
        nohup bash -c "cd \"${AGENT_DIR}\" && ${CLAUDE_CMD} ${CLAUDE_ARGS[*]} \"${AGENT_PROMPT}\"" \
            > "$LOG_FILE" 2>&1 &
    fi

    AGENT_PID=$!
    echo "$AGENT_PID" > "$PID_FILE"

    echo ""
    echo "Agent '${AGENT_ID}' started in background."
    echo "  PID: ${AGENT_PID}"
    echo "  PID file: ${PID_FILE}"
    echo "  Log: ${LOG_FILE}"
    echo ""
    echo "Monitor with: tail -f ${LOG_FILE}"
    echo "Stop with:    stop_agent.sh ${AGENT_ID}"
else
    # Foreground mode: run directly, record PID, clean up on exit
    if [[ -n "$RUN_AS_USER" ]]; then
        sudo -u "$RUN_AS_USER" \
            bash -c "cd \"${AGENT_DIR}\" && ${CLAUDE_CMD} ${CLAUDE_ARGS[*]} \"${AGENT_PROMPT}\"" \
            > >(tee -a "$LOG_FILE") 2>&1 &
    else
        bash -c "cd \"${AGENT_DIR}\" && ${CLAUDE_CMD} ${CLAUDE_ARGS[*]} \"${AGENT_PROMPT}\"" \
            > >(tee -a "$LOG_FILE") 2>&1 &
    fi

    AGENT_PID=$!
    echo "$AGENT_PID" > "$PID_FILE"

    echo ""
    echo "Agent '${AGENT_ID}' started (PID ${AGENT_PID})."

    # Wait for the process to complete and clean up PID file
    wait "$AGENT_PID" 2>/dev/null || true

    echo "Agent '${AGENT_ID}' exited."
    rm -f "$PID_FILE"
fi
