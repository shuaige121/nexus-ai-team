#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# stop_agent.sh — Stop a running Agent's Claude Code process
#
# Usage: stop_agent.sh <agent_id> [--force]
#
# Reads the .pid file, sends SIGTERM for graceful shutdown, waits up to 10
# seconds, and optionally sends SIGKILL with --force.
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

# Grace period before force-kill (seconds)
GRACE_PERIOD=10

usage() {
    cat <<'EOF'
Usage: stop_agent.sh <agent_id> [--force]

Stop a running Agent's Claude Code process.

Arguments:
  agent_id    The agent ID to stop (e.g. ceo, dept-gateway-dev-01)

Options:
  --force     If the agent does not stop within 10 seconds after SIGTERM,
              send SIGKILL to force termination
  --help      Show this help message

Behavior:
  1. Reads PID from agents/{agent_id}/.pid
  2. Sends SIGTERM for graceful shutdown
  3. Waits up to 10 seconds for the process to exit
  4. With --force: sends SIGKILL if still running after grace period
  5. Cleans up the .pid file

Examples:
  stop_agent.sh ceo
  stop_agent.sh dept-gateway-dev-01 --force
EOF
}

# --help check
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# --- Argument parsing --------------------------------------------------------

if [[ $# -lt 1 ]]; then
    echo "Error: Missing agent_id." >&2
    echo "Run 'stop_agent.sh --help' for usage." >&2
    exit 1
fi

AGENT_ID="$1"
shift

FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'." >&2
            echo "Run 'stop_agent.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

# --- Validate agent ----------------------------------------------------------

AGENT_DIR="${AGENTS_ROOT}/${AGENT_ID}"
PID_FILE="${AGENT_DIR}/.pid"

if [[ ! -d "$AGENT_DIR" ]]; then
    echo "Error: Agent directory '${AGENT_DIR}' does not exist." >&2
    exit 1
fi

if [[ ! -f "$PID_FILE" ]]; then
    echo "Error: No PID file found at '${PID_FILE}'." >&2
    echo "Agent '${AGENT_ID}' may not be running." >&2
    exit 1
fi

AGENT_PID="$(cat "$PID_FILE")"

# Validate PID is a number
if [[ ! "$AGENT_PID" =~ ^[0-9]+$ ]]; then
    echo "Error: Invalid PID '${AGENT_PID}' in ${PID_FILE}." >&2
    rm -f "$PID_FILE"
    exit 1
fi

# --- Check if process is actually running ------------------------------------

if ! kill -0 "$AGENT_PID" 2>/dev/null; then
    echo "Agent '${AGENT_ID}' (PID ${AGENT_PID}) is not running. Cleaning up PID file."
    rm -f "$PID_FILE"
    exit 0
fi

# --- Send SIGTERM (graceful stop) --------------------------------------------

echo "Stopping agent '${AGENT_ID}' (PID ${AGENT_PID})..."
echo "  Sending SIGTERM..."

kill -TERM "$AGENT_PID" 2>/dev/null || true

# --- Wait for grace period ---------------------------------------------------

echo "  Waiting up to ${GRACE_PERIOD} seconds for graceful shutdown..."

elapsed=0
while [[ $elapsed -lt $GRACE_PERIOD ]]; do
    if ! kill -0 "$AGENT_PID" 2>/dev/null; then
        echo "  Agent stopped gracefully after ${elapsed} second(s)."
        rm -f "$PID_FILE"
        echo ""
        echo "Agent '${AGENT_ID}' stopped successfully."
        exit 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done

# --- Process still running after grace period ---------------------------------

if kill -0 "$AGENT_PID" 2>/dev/null; then
    if [[ "$FORCE" == true ]]; then
        echo "  Agent did not stop within ${GRACE_PERIOD} seconds. Sending SIGKILL..."
        kill -KILL "$AGENT_PID" 2>/dev/null || true
        sleep 1

        if kill -0 "$AGENT_PID" 2>/dev/null; then
            echo "Error: Failed to kill agent '${AGENT_ID}' (PID ${AGENT_PID})." >&2
            echo "  The process may require manual intervention." >&2
            exit 1
        fi

        echo "  Agent force-killed."
        rm -f "$PID_FILE"
        echo ""
        echo "Agent '${AGENT_ID}' stopped (forced)."
    else
        echo "Warning: Agent '${AGENT_ID}' (PID ${AGENT_PID}) did not stop within ${GRACE_PERIOD} seconds." >&2
        echo "  Use --force to send SIGKILL." >&2
        exit 1
    fi
else
    # Process exited during the final check
    echo "  Agent stopped."
    rm -f "$PID_FILE"
    echo ""
    echo "Agent '${AGENT_ID}' stopped successfully."
fi
