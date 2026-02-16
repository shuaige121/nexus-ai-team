#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# orchestrator.sh — Multi-agent process orchestrator
#
# Usage: orchestrator.sh <command> [args]
#
# Commands:
#   start               Start all active agents in hierarchy order
#                       (CEO -> Manager -> Worker/QA)
#   stop                Stop all agents in reverse hierarchy order
#   status              Display status table of all agents
#   restart <agent_id>  Restart a specific agent
#   logs <agent_id>     Tail the agent's log file
#   dispatch <agent_id> Wake up an agent (start if not running)
#
# The orchestrator is a process manager, NOT an Agent itself.
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

REGISTRY_FILE="${AGENTS_ROOT}/registry.yaml"

# Role hierarchy for startup ordering (lower number = start first)
# CEO(0) -> HR/IT-Support(1) -> Manager(2) -> Worker/QA(3)
declare -A ROLE_ORDER=(
    ["ceo"]=0
    ["hr"]=1
    ["it-support"]=1
    ["manager"]=2
    ["worker"]=3
    ["qa"]=3
)

# Delay between starting agents in the same tier (seconds)
TIER_START_DELAY=1
# Delay between tiers (seconds)
INTER_TIER_DELAY=2

usage() {
    cat <<'EOF'
Usage: orchestrator.sh <command> [args]

Multi-agent process orchestrator for AgentOffice.

Commands:
  start                Start all active agents in hierarchy order
                       (CEO -> HR/IT -> Manager -> Worker/QA)
  stop                 Stop all agents in reverse hierarchy order
  status               Display status table of all registered agents
  restart <agent_id>   Restart a specific agent
  logs <agent_id>      Tail the agent's log file (Ctrl+C to stop)
  dispatch <agent_id>  Wake up an agent — start it if not running

Options:
  --help               Show this help message

Environment:
  AGENTOFFICE_ROOT     Override the agents root directory
  CLAUDE_CMD           Override the claude CLI command (for testing)

Examples:
  orchestrator.sh start
  orchestrator.sh status
  orchestrator.sh restart ceo
  orchestrator.sh logs dept-gateway-dev-01
  orchestrator.sh dispatch ceo
EOF
}

# --help check
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" || $# -eq 0 ]]; then
    usage
    if [[ $# -eq 0 ]]; then
        exit 1
    fi
    exit 0
fi

COMMAND="$1"
shift

# =============================================================================
# Helper functions
# =============================================================================

# Get all active agents from registry as "agent_id role" lines
get_active_agents() {
    if [[ ! -f "$REGISTRY_FILE" ]]; then
        echo "Warning: Registry file not found at '${REGISTRY_FILE}'." >&2
        # Fall back to scanning directories
        for dir in "${AGENTS_ROOT}"/*/; do
            local agent_id
            agent_id="$(basename "$dir")"
            # Skip non-agent directories
            case "$agent_id" in
                scripts|templates|archived|contracts|README.md) continue ;;
            esac
            if [[ -f "${dir}/JD.md" ]]; then
                echo "${agent_id} unknown"
            fi
        done
        return
    fi

    # Parse registry.yaml for active agents with their roles
    awk '
        /^agents:/ { in_agents = 1; next }
        /^[a-z]/ { in_agents = 0 }
        in_agents && /^  [a-zA-Z0-9]/ {
            # Extract agent_id
            gsub(/:.*/, "")
            gsub(/^  /, "")
            agent_id = $0
            next
        }
        in_agents && /^    role:/ {
            role = $0
            gsub(/^    role: */, "", role)
            gsub(/[[:space:]]*$/, "", role)
            roles[agent_id] = role
            next
        }
        in_agents && /^    status:/ {
            status = $0
            gsub(/^    status: */, "", status)
            gsub(/[[:space:]]*$/, "", status)
            if (status == "active") {
                print agent_id " " roles[agent_id]
            }
        }
    ' "$REGISTRY_FILE"
}

# Get the status of a single agent
get_agent_status() {
    local agent_id="$1"
    local agent_dir="${AGENTS_ROOT}/${agent_id}"
    local pid_file="${agent_dir}/.pid"

    if [[ ! -f "$pid_file" ]]; then
        echo "stopped"
        return
    fi

    local pid
    pid="$(cat "$pid_file")"

    if [[ ! "$pid" =~ ^[0-9]+$ ]]; then
        echo "stopped"
        return
    fi

    if kill -0 "$pid" 2>/dev/null; then
        echo "running"
    else
        echo "stopped"
    fi
}

# Get PID for an agent (or "-" if not running)
get_agent_pid() {
    local agent_id="$1"
    local agent_dir="${AGENTS_ROOT}/${agent_id}"
    local pid_file="${agent_dir}/.pid"

    if [[ ! -f "$pid_file" ]]; then
        echo "-"
        return
    fi

    local pid
    pid="$(cat "$pid_file")"

    if [[ ! "$pid" =~ ^[0-9]+$ ]]; then
        echo "-"
        return
    fi

    if kill -0 "$pid" 2>/dev/null; then
        echo "$pid"
    else
        echo "-"
    fi
}

# Count unread messages in an agent's INBOX
count_unread() {
    local agent_id="$1"
    local inbox_dir="${AGENTS_ROOT}/${agent_id}/INBOX"

    if [[ ! -d "$inbox_dir" ]]; then
        echo "0"
        return
    fi

    local count=0
    for f in "${inbox_dir}"/*.md; do
        [[ -e "$f" ]] || continue
        count=$((count + 1))
    done
    echo "$count"
}

# Sort agents by role hierarchy order
# Input: lines of "agent_id role"
# Output: sorted lines of "agent_id role tier"
sort_by_hierarchy() {
    while IFS=' ' read -r agent_id role; do
        local tier="${ROLE_ORDER[$role]:-99}"
        echo "${tier} ${agent_id} ${role}"
    done | sort -n -k1
}

# Sort agents by reverse role hierarchy order
sort_by_reverse_hierarchy() {
    while IFS=' ' read -r agent_id role; do
        local tier="${ROLE_ORDER[$role]:-99}"
        echo "${tier} ${agent_id} ${role}"
    done | sort -rn -k1
}

# =============================================================================
# Command: start
# =============================================================================

cmd_start() {
    echo "=== AgentOffice Orchestrator: Starting all agents ==="
    echo ""

    local agents_list
    agents_list="$(get_active_agents)"

    if [[ -z "$agents_list" ]]; then
        echo "No active agents found in registry."
        exit 0
    fi

    local sorted_agents
    sorted_agents="$(echo "$agents_list" | sort_by_hierarchy)"

    local current_tier=-1
    local started=0
    local skipped=0
    local failed=0

    while IFS=' ' read -r tier agent_id role; do
        # Add delay between tiers
        if [[ "$current_tier" -ne -1 && "$tier" -ne "$current_tier" ]]; then
            echo ""
            echo "--- Waiting ${INTER_TIER_DELAY}s before next tier ---"
            sleep "$INTER_TIER_DELAY"
        fi
        current_tier="$tier"

        # Check if already running
        local status
        status="$(get_agent_status "$agent_id")"
        if [[ "$status" == "running" ]]; then
            local pid
            pid="$(get_agent_pid "$agent_id")"
            echo "[SKIP] ${agent_id} (${role}) — already running (PID ${pid})"
            skipped=$((skipped + 1))
            continue
        fi

        echo "[START] ${agent_id} (${role})..."

        if "${SCRIPT_DIR}/start_agent.sh" "$agent_id" --background 2>&1 | while IFS= read -r line; do echo "  ${line}"; done; then
            started=$((started + 1))
        else
            echo "  [FAIL] Failed to start ${agent_id}"
            failed=$((failed + 1))
        fi

        # Brief delay between agents in the same tier
        sleep "$TIER_START_DELAY"

    done <<< "$sorted_agents"

    echo ""
    echo "=== Start complete: ${started} started, ${skipped} skipped, ${failed} failed ==="
}

# =============================================================================
# Command: stop
# =============================================================================

cmd_stop() {
    echo "=== AgentOffice Orchestrator: Stopping all agents ==="
    echo ""

    local agents_list
    agents_list="$(get_active_agents)"

    if [[ -z "$agents_list" ]]; then
        echo "No active agents found in registry."
        exit 0
    fi

    local sorted_agents
    sorted_agents="$(echo "$agents_list" | sort_by_reverse_hierarchy)"

    local stopped=0
    local skipped=0
    local failed=0

    while IFS=' ' read -r tier agent_id role; do
        local status
        status="$(get_agent_status "$agent_id")"
        if [[ "$status" != "running" ]]; then
            echo "[SKIP] ${agent_id} (${role}) — not running"
            skipped=$((skipped + 1))
            continue
        fi

        echo "[STOP] ${agent_id} (${role})..."

        if "${SCRIPT_DIR}/stop_agent.sh" "$agent_id" --force 2>&1 | while IFS= read -r line; do echo "  ${line}"; done; then
            stopped=$((stopped + 1))
        else
            echo "  [FAIL] Failed to stop ${agent_id}"
            failed=$((failed + 1))
        fi

    done <<< "$sorted_agents"

    echo ""
    echo "=== Stop complete: ${stopped} stopped, ${skipped} skipped, ${failed} failed ==="
}

# =============================================================================
# Command: status
# =============================================================================

cmd_status() {
    local agents_list
    agents_list="$(get_active_agents)"

    # Print header
    printf "%-25s %-12s %-8s %-10s %s\n" "AGENT ID" "ROLE" "PID" "STATUS" "INBOX"
    printf "%-25s %-12s %-8s %-10s %s\n" "--------" "----" "---" "------" "-----"

    if [[ -z "$agents_list" ]]; then
        echo "(no active agents found)"
        return
    fi

    local sorted_agents
    sorted_agents="$(echo "$agents_list" | sort_by_hierarchy)"

    while IFS=' ' read -r tier agent_id role; do
        local pid status unread

        pid="$(get_agent_pid "$agent_id")"
        status="$(get_agent_status "$agent_id")"
        unread="$(count_unread "$agent_id")"

        local inbox_display="${unread} unread"

        printf "%-25s %-12s %-8s %-10s %s\n" "$agent_id" "$role" "$pid" "$status" "$inbox_display"
    done <<< "$sorted_agents"
}

# =============================================================================
# Command: restart
# =============================================================================

cmd_restart() {
    if [[ $# -lt 1 ]]; then
        echo "Error: restart requires an agent_id." >&2
        echo "Usage: orchestrator.sh restart <agent_id>" >&2
        exit 1
    fi

    local agent_id="$1"
    local agent_dir="${AGENTS_ROOT}/${agent_id}"

    if [[ ! -d "$agent_dir" ]]; then
        echo "Error: Agent directory '${agent_dir}' does not exist." >&2
        exit 1
    fi

    echo "=== Restarting agent '${agent_id}' ==="
    echo ""

    # Stop if running
    local status
    status="$(get_agent_status "$agent_id")"
    if [[ "$status" == "running" ]]; then
        echo "[STOP] Stopping ${agent_id}..."
        "${SCRIPT_DIR}/stop_agent.sh" "$agent_id" --force 2>&1 | while IFS= read -r line; do echo "  ${line}"; done
        echo ""
    else
        echo "[INFO] Agent ${agent_id} is not running."
    fi

    # Start
    echo "[START] Starting ${agent_id}..."
    "${SCRIPT_DIR}/start_agent.sh" "$agent_id" --background 2>&1 | while IFS= read -r line; do echo "  ${line}"; done

    echo ""
    echo "=== Restart complete ==="
}

# =============================================================================
# Command: logs
# =============================================================================

cmd_logs() {
    if [[ $# -lt 1 ]]; then
        echo "Error: logs requires an agent_id." >&2
        echo "Usage: orchestrator.sh logs <agent_id>" >&2
        exit 1
    fi

    local agent_id="$1"
    local agent_dir="${AGENTS_ROOT}/${agent_id}"
    local log_file="${agent_dir}/agent.log"

    if [[ ! -d "$agent_dir" ]]; then
        echo "Error: Agent directory '${agent_dir}' does not exist." >&2
        exit 1
    fi

    if [[ ! -f "$log_file" ]]; then
        echo "No log file found at '${log_file}'."
        echo "The agent may not have been started yet."
        exit 1
    fi

    echo "=== Tailing logs for agent '${agent_id}' (Ctrl+C to stop) ==="
    echo "Log file: ${log_file}"
    echo ""

    tail -f "$log_file"
}

# =============================================================================
# Command: dispatch
# =============================================================================

cmd_dispatch() {
    if [[ $# -lt 1 ]]; then
        echo "Error: dispatch requires an agent_id." >&2
        echo "Usage: orchestrator.sh dispatch <agent_id>" >&2
        exit 1
    fi

    local agent_id="$1"
    local agent_dir="${AGENTS_ROOT}/${agent_id}"

    if [[ ! -d "$agent_dir" ]]; then
        echo "Error: Agent directory '${agent_dir}' does not exist." >&2
        exit 1
    fi

    local status
    status="$(get_agent_status "$agent_id")"

    if [[ "$status" == "running" ]]; then
        local pid
        pid="$(get_agent_pid "$agent_id")"
        echo "Agent '${agent_id}' is already running (PID ${pid}). No action needed."
    else
        echo "Agent '${agent_id}' is not running. Starting..."
        "${SCRIPT_DIR}/start_agent.sh" "$agent_id" --background
    fi
}

# =============================================================================
# Command dispatch
# =============================================================================

case "$COMMAND" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    status)
        cmd_status
        ;;
    restart)
        cmd_restart "$@"
        ;;
    logs)
        cmd_logs "$@"
        ;;
    dispatch)
        cmd_dispatch "$@"
        ;;
    --help|-h)
        usage
        exit 0
        ;;
    *)
        echo "Error: Unknown command '${COMMAND}'." >&2
        echo "Run 'orchestrator.sh --help' for usage." >&2
        exit 1
        ;;
esac
