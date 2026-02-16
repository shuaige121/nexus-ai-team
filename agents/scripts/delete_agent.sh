#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# delete_agent.sh — Delete (archive) an Agent instance
#
# Usage: delete_agent.sh <agent_id> [--force]
#
# Archives the agent's workspace to agents/archived/ and marks the agent
# as archived in registry.yaml.
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

REGISTRY_FILE="${AGENTS_ROOT}/registry.yaml"
ARCHIVE_DIR="${AGENTS_ROOT}/archived"

usage() {
    cat <<'EOF'
Usage: delete_agent.sh <agent_id> [--force]

Delete (archive) an Agent instance.

The agent's workspace is backed up to agents/archived/{agent_id}_{timestamp}/,
the workspace directory is removed, and the agent is marked as "archived" in
registry.yaml.

Arguments:
  agent_id    The ID of the agent to delete

Options:
  --force     Force deletion even if the agent has subordinates (e.g. a manager
              with active workers). Without --force, deletion of a manager with
              subordinates is refused.
  --help      Show this help message

Examples:
  delete_agent.sh dept-gateway-dev-01
  delete_agent.sh dept-gateway-manager --force
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
    echo "Run 'delete_agent.sh --help' for usage." >&2
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
            echo "Run 'delete_agent.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

# --- Validation --------------------------------------------------------------

AGENT_DIR="${AGENTS_ROOT}/${AGENT_ID}"

# Check agent directory exists
if [[ ! -d "$AGENT_DIR" ]]; then
    echo "Error: Agent directory '${AGENT_DIR}' does not exist." >&2
    echo "Agent '${AGENT_ID}' may not exist or has already been deleted." >&2
    exit 1
fi

# Check registry exists
if [[ ! -f "$REGISTRY_FILE" ]]; then
    echo "Error: Registry file '${REGISTRY_FILE}' not found." >&2
    exit 1
fi

# Check agent exists in registry
if ! grep -q "^  ${AGENT_ID}:" "$REGISTRY_FILE" 2>/dev/null; then
    echo "Warning: Agent '${AGENT_ID}' not found in registry. Proceeding with directory cleanup only." >&2
fi

# Check if agent is already archived
if grep -A 10 "^  ${AGENT_ID}:" "$REGISTRY_FILE" 2>/dev/null | grep -q "status: archived"; then
    echo "Error: Agent '${AGENT_ID}' is already archived." >&2
    exit 1
fi

# Determine the agent's role from registry
AGENT_ROLE=""
if grep -q "^  ${AGENT_ID}:" "$REGISTRY_FILE" 2>/dev/null; then
    AGENT_ROLE=$(grep -A 1 "^  ${AGENT_ID}:" "$REGISTRY_FILE" | grep "role:" | sed 's/.*role: *//' | tr -d '[:space:]')
fi

# Check for subordinates (agents that report to this agent)
if [[ "$FORCE" == false ]]; then
    SUBORDINATES=()
    # Search registry for agents whose reports_to matches this agent_id and are active
    while IFS= read -r line; do
        # Extract agent_id from lines like "  some-agent-id:"
        if [[ "$line" =~ ^[[:space:]]{2}([a-zA-Z0-9][a-zA-Z0-9_-]*):$ ]]; then
            current_check_id="${BASH_REMATCH[1]}"
        fi
        if [[ "$line" =~ reports_to:[[:space:]]*(.+) ]]; then
            rt="${BASH_REMATCH[1]}"
            rt="$(echo "$rt" | tr -d '[:space:]')"
            if [[ "$rt" == "$AGENT_ID" && "${current_check_id:-}" != "$AGENT_ID" ]]; then
                # Also check if this subordinate is active
                SUBORDINATES+=("${current_check_id}")
            fi
        fi
    done < "$REGISTRY_FILE"

    # Filter to only active subordinates
    ACTIVE_SUBORDINATES=()
    for sub in "${SUBORDINATES[@]+"${SUBORDINATES[@]}"}"; do
        if grep -A 10 "^  ${sub}:" "$REGISTRY_FILE" | grep -q "status: active"; then
            ACTIVE_SUBORDINATES+=("$sub")
        fi
    done

    if [[ ${#ACTIVE_SUBORDINATES[@]} -gt 0 ]]; then
        echo "Error: Agent '${AGENT_ID}' has ${#ACTIVE_SUBORDINATES[@]} active subordinate(s):" >&2
        for sub in "${ACTIVE_SUBORDINATES[@]}"; do
            echo "  - ${sub}" >&2
        done
        echo "" >&2
        echo "Please reassign or delete subordinates first, or use --force to override." >&2
        exit 1
    fi
fi

# --- Backup to archive -------------------------------------------------------

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_DEST="${ARCHIVE_DIR}/${AGENT_ID}_${TIMESTAMP}"

echo "Archiving agent '${AGENT_ID}'..."

mkdir -p "$ARCHIVE_DIR"
cp -r "$AGENT_DIR" "$ARCHIVE_DEST"

echo "  Backed up to: ${ARCHIVE_DEST}"

# --- Remove workspace directory -----------------------------------------------

rm -rf "$AGENT_DIR"

echo "  Removed directory: ${AGENT_DIR}"

# --- Update registry.yaml: mark status as archived ----------------------------

if grep -q "^  ${AGENT_ID}:" "$REGISTRY_FILE" 2>/dev/null; then
    TMPFILE="$(mktemp)"
    awk -v agent_id="  ${AGENT_ID}:" '
        BEGIN { in_agent = 0 }
        $0 == agent_id { in_agent = 1; print; next }
        in_agent && /^    status:/ {
            print "    status: archived"
            in_agent = 0
            next
        }
        in_agent && /^  [^ ]/ { in_agent = 0 }
        { print }
    ' "$REGISTRY_FILE" > "$TMPFILE"
    mv "$TMPFILE" "$REGISTRY_FILE"

    echo "  Registry updated: status -> archived"
fi

# --- Update departments section: remove from members list ---------------------

# Determine department from registry
AGENT_DEPT=""
if grep -q "^  ${AGENT_ID}:" "$REGISTRY_FILE" 2>/dev/null; then
    # Read the department field from the agent's entry
    AGENT_DEPT=$(awk -v agent_id="  ${AGENT_ID}:" '
        BEGIN { in_agent = 0 }
        $0 == agent_id { in_agent = 1; next }
        in_agent && /^    department:/ {
            sub(/^    department: */, "")
            print
            exit
        }
        in_agent && /^  [^ ]/ { exit }
    ' "$REGISTRY_FILE")
fi

if [[ -n "$AGENT_DEPT" ]]; then
    # Check if this agent is listed as a member in the department
    if grep -A 50 "^  ${AGENT_DEPT}:" "$REGISTRY_FILE" | grep -q -- "- ${AGENT_ID}$"; then
        TMPFILE="$(mktemp)"
        awk -v agent_id="$AGENT_ID" '
            /^      - / {
                # Extract the member name
                member = $0
                sub(/^      - /, "", member)
                # Trim whitespace
                gsub(/[[:space:]]/, "", member)
                if (member == agent_id) {
                    next  # Skip this line (remove member)
                }
            }
            { print }
        ' "$REGISTRY_FILE" > "$TMPFILE"
        mv "$TMPFILE" "$REGISTRY_FILE"

        echo "  Removed from department '${AGENT_DEPT}' members list"
    fi

    # If this agent was the manager of the department, clear the manager field
    if [[ "$AGENT_ROLE" == "manager" ]]; then
        if grep -A 50 "^  ${AGENT_DEPT}:" "$REGISTRY_FILE" | grep -q "manager: ${AGENT_ID}"; then
            TMPFILE="$(mktemp)"
            awk -v dept="  ${AGENT_DEPT}:" -v agent_id="$AGENT_ID" '
                BEGIN { in_dept = 0 }
                $0 == dept { in_dept = 1; print; next }
                in_dept && /^    manager:/ {
                    # Check if this manager matches
                    manager_val = $0
                    sub(/^    manager: */, "", manager_val)
                    gsub(/[[:space:]]/, "", manager_val)
                    if (manager_val == agent_id) {
                        print "    manager: null"
                        next
                    }
                }
                in_dept && /^  [^ ]/ { in_dept = 0 }
                { print }
            ' "$REGISTRY_FILE" > "$TMPFILE"
            mv "$TMPFILE" "$REGISTRY_FILE"

            echo "  Cleared manager role in department '${AGENT_DEPT}'"
        fi
    fi
fi

# --- Summary ------------------------------------------------------------------

echo ""
echo "Agent deleted successfully!"
echo "  ID:       ${AGENT_ID}"
echo "  Archive:  ${ARCHIVE_DEST}"
echo "  Registry: status -> archived"
