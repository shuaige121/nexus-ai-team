#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# inbox_watcher.sh — Poll all Agent INBOX directories and dispatch on new mail
#
# Usage: inbox_watcher.sh [--interval <seconds>] [--once]
#
# Continuously monitors all agents' INBOX/ directories for new .md files.
# When new mail is detected for an agent, it dispatches (wakes up) that agent
# via orchestrator.sh dispatch.
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

REGISTRY_FILE="${AGENTS_ROOT}/registry.yaml"

# State directory for tracking known mail files
STATE_DIR="${AGENTS_ROOT}/.inbox_watcher_state"

# Default poll interval in seconds
DEFAULT_INTERVAL=10

usage() {
    cat <<'EOF'
Usage: inbox_watcher.sh [--interval <seconds>] [--once]

Poll all Agent INBOX directories for new mail and dispatch agents.

Options:
  --interval <seconds>  Polling interval in seconds (default: 10)
  --once                Run a single check and exit (no loop)
  --help                Show this help message

Behavior:
  - Scans all registered agents' INBOX/ directories for .md files
  - Tracks which files have been seen using a state directory
  - When a new .md file appears in an agent's INBOX/, dispatches that agent
    (starts it if not already running)
  - Agents that naturally exit after processing are NOT restarted until
    new mail arrives

State tracking:
  State files are stored in agents/.inbox_watcher_state/
  Each agent gets a file listing known INBOX entries.

Environment:
  AGENTOFFICE_ROOT     Override the agents root directory

Examples:
  inbox_watcher.sh                    # Poll every 10 seconds
  inbox_watcher.sh --interval 5       # Poll every 5 seconds
  inbox_watcher.sh --once             # Check once and exit
EOF
}

# --help check
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# --- Argument parsing --------------------------------------------------------

INTERVAL="$DEFAULT_INTERVAL"
ONCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --interval)
            if [[ $# -lt 2 ]]; then
                echo "Error: --interval requires a value." >&2
                exit 1
            fi
            INTERVAL="$2"
            if [[ ! "$INTERVAL" =~ ^[0-9]+$ ]] || [[ "$INTERVAL" -lt 1 ]]; then
                echo "Error: --interval must be a positive integer." >&2
                exit 1
            fi
            shift 2
            ;;
        --once)
            ONCE=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'." >&2
            echo "Run 'inbox_watcher.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

# --- Initialize state directory ----------------------------------------------

mkdir -p "$STATE_DIR"

# --- Helper functions --------------------------------------------------------

# Get list of agent IDs to monitor (active agents from registry, or scan dirs)
get_agent_ids() {
    if [[ -f "$REGISTRY_FILE" ]]; then
        awk '
            /^agents:/ { in_agents = 1; next }
            /^[a-z]/ { in_agents = 0 }
            in_agents && /^  [a-zA-Z0-9]/ {
                gsub(/:.*/, "")
                gsub(/^  /, "")
                agent_id = $0
                next
            }
            in_agents && /^    status:/ {
                status = $0
                gsub(/^    status: */, "", status)
                gsub(/[[:space:]]*$/, "", status)
                if (status == "active") {
                    print agent_id
                }
            }
        ' "$REGISTRY_FILE"
    else
        # Fall back to scanning directories
        for dir in "${AGENTS_ROOT}"/*/; do
            local agent_id
            agent_id="$(basename "$dir")"
            case "$agent_id" in
                scripts|templates|archived|contracts|README.md|.inbox_watcher_state) continue ;;
            esac
            if [[ -d "${dir}/INBOX" ]]; then
                echo "$agent_id"
            fi
        done
    fi
}

# Get current list of .md files in an agent's INBOX (filenames only, not in read/)
get_inbox_files() {
    local agent_id="$1"
    local inbox_dir="${AGENTS_ROOT}/${agent_id}/INBOX"

    if [[ ! -d "$inbox_dir" ]]; then
        return
    fi

    for f in "${inbox_dir}"/*.md; do
        [[ -e "$f" ]] || continue
        basename "$f"
    done
}

# Get previously known files for an agent from state
get_known_files() {
    local agent_id="$1"
    local state_file="${STATE_DIR}/${agent_id}.known"

    if [[ -f "$state_file" ]]; then
        cat "$state_file"
    fi
}

# Update known files for an agent
update_known_files() {
    local agent_id="$1"
    local state_file="${STATE_DIR}/${agent_id}.known"

    get_inbox_files "$agent_id" > "$state_file"
}

# Check for new mail and dispatch if found
check_and_dispatch() {
    local agent_ids
    agent_ids="$(get_agent_ids)"

    if [[ -z "$agent_ids" ]]; then
        return
    fi

    while IFS= read -r agent_id; do
        [[ -z "$agent_id" ]] && continue

        local current_files known_files new_files

        current_files="$(get_inbox_files "$agent_id")"
        known_files="$(get_known_files "$agent_id")"

        # Find files in current that are not in known
        new_files=""
        if [[ -n "$current_files" ]]; then
            while IFS= read -r file; do
                [[ -z "$file" ]] && continue
                if ! echo "$known_files" | grep -qxF "$file" 2>/dev/null; then
                    new_files="${new_files}${file}\n"
                fi
            done <<< "$current_files"
        fi

        if [[ -n "$new_files" ]]; then
            local new_count
            new_count="$(echo -e "$new_files" | grep -c '.' || true)"

            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Agent '${agent_id}': ${new_count} new mail detected"

            # List the new files
            echo -e "$new_files" | while IFS= read -r file; do
                [[ -z "$file" ]] && continue
                echo "  + ${file}"
            done

            # Dispatch the agent
            echo "  -> Dispatching agent '${agent_id}'..."
            "${SCRIPT_DIR}/orchestrator.sh" dispatch "$agent_id" 2>&1 | while IFS= read -r line; do
                echo "     ${line}"
            done

            # Update known files AFTER dispatch so we don't re-trigger
            update_known_files "$agent_id"
        else
            # No new mail — just update the known list (handles deleted files)
            update_known_files "$agent_id"
        fi

    done <<< "$agent_ids"
}

# --- Signal handling ---------------------------------------------------------

RUNNING=true

cleanup() {
    RUNNING=false
    echo ""
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Inbox watcher stopped."
    exit 0
}

trap cleanup SIGTERM SIGINT

# --- Main loop ---------------------------------------------------------------

if [[ "$ONCE" == true ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Inbox watcher: single check"
    check_and_dispatch
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Check complete."
    exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Inbox watcher started (interval: ${INTERVAL}s)"
echo "  State dir: ${STATE_DIR}"
echo "  Press Ctrl+C to stop."
echo ""

# Initialize known files for all agents (so we only trigger on truly new mail)
agent_ids="$(get_agent_ids)"
if [[ -n "$agent_ids" ]]; then
    while IFS= read -r agent_id; do
        [[ -z "$agent_id" ]] && continue
        update_known_files "$agent_id"
    done <<< "$agent_ids"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Initialized known state for all agents. Watching..."
echo ""

while [[ "$RUNNING" == true ]]; do
    check_and_dispatch
    sleep "$INTERVAL" &
    wait $! 2>/dev/null || true
done
