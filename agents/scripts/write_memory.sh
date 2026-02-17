#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# write_memory.sh — Write to an agent's MEMORY.md file
#
# Usage: write_memory.sh <agent_id> <action> [content]
#
# For append and replace, content is read from stdin.
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

MEMORY_CHAR_LIMIT=4000

usage() {
    cat <<'EOF'
Usage: write_memory.sh <agent_id> <action>

Manage an agent's persistent MEMORY.md file.

Arguments:
  agent_id   The agent ID (e.g. ceo, hr, it-support)
  action     One of:
               append   — Append content to the end (read from stdin)
               replace  — Replace the entire file (read from stdin)
               clear    — Clear the file (reset to "# Memory" header only)

Options:
  --help     Show this help message

Character limit: 4000 characters total.
If a write would exceed the limit, it is rejected and the current usage
is reported.

Examples:
  echo "Hired Alice as engineer." | write_memory.sh ceo append
  echo "# Memory\n\nFresh start." | write_memory.sh hr replace
  write_memory.sh it-support clear
EOF
}

# --help check
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# --- Argument validation ----------------------------------------------------

if [[ $# -lt 2 ]]; then
    echo "Error: Missing required arguments." >&2
    echo "Run 'write_memory.sh --help' for usage." >&2
    exit 1
fi

AGENT_ID="$1"
ACTION="$2"

if [[ "$ACTION" != "append" && "$ACTION" != "replace" && "$ACTION" != "clear" ]]; then
    echo "Error: Invalid action '$ACTION'. Must be one of: append, replace, clear." >&2
    exit 1
fi

MEMORY_FILE="${AGENTS_ROOT}/${AGENT_ID}/MEMORY.md"

if [[ ! -f "$MEMORY_FILE" ]]; then
    echo "Error: Memory file '${MEMORY_FILE}' does not exist." >&2
    echo "Agent '${AGENT_ID}' may not exist." >&2
    exit 1
fi

# --- Perform the action -----------------------------------------------------

case "$ACTION" in
    clear)
        printf '# Memory\n' > "$MEMORY_FILE"
        echo "Memory cleared for ${AGENT_ID}."
        ;;

    append)
        NEW_CONTENT="$(cat)"
        if [[ -z "$NEW_CONTENT" ]]; then
            echo "Error: No content provided on stdin for append." >&2
            exit 1
        fi

        CURRENT="$(cat "$MEMORY_FILE")"
        CURRENT_LEN=${#CURRENT}

        # The appended result: current + newline + new content
        COMBINED="${CURRENT}
${NEW_CONTENT}"
        # +1 for trailing newline added by printf '%s\n'
        COMBINED_LEN=$(( ${#COMBINED} + 1 ))

        if [[ $COMBINED_LEN -gt $MEMORY_CHAR_LIMIT ]]; then
            REMAINING=$((MEMORY_CHAR_LIMIT - CURRENT_LEN - 1))
            echo "Error: Write would exceed the ${MEMORY_CHAR_LIMIT}-character limit." >&2
            echo "  Current size:  ${CURRENT_LEN} characters" >&2
            echo "  Content to add: ${#NEW_CONTENT} characters (+ 1 newline)" >&2
            echo "  Remaining space: ${REMAINING} characters" >&2
            exit 1
        fi

        printf '%s\n' "$COMBINED" > "$MEMORY_FILE"
        echo "Memory updated for ${AGENT_ID}. (${COMBINED_LEN}/${MEMORY_CHAR_LIMIT} chars)"
        ;;

    replace)
        NEW_CONTENT="$(cat)"
        if [[ -z "$NEW_CONTENT" ]]; then
            echo "Error: No content provided on stdin for replace." >&2
            exit 1
        fi

        # +1 for trailing newline added by printf '%s\n'
        NEW_LEN=$(( ${#NEW_CONTENT} + 1 ))

        if [[ $NEW_LEN -gt $MEMORY_CHAR_LIMIT ]]; then
            echo "Error: Content exceeds the ${MEMORY_CHAR_LIMIT}-character limit." >&2
            echo "  Content size: ${NEW_LEN} characters" >&2
            echo "  Limit:        ${MEMORY_CHAR_LIMIT} characters" >&2
            echo "  Over by:      $((NEW_LEN - MEMORY_CHAR_LIMIT)) characters" >&2
            exit 1
        fi

        printf '%s\n' "$NEW_CONTENT" > "$MEMORY_FILE"
        echo "Memory replaced for ${AGENT_ID}. (${NEW_LEN}/${MEMORY_CHAR_LIMIT} chars)"
        ;;
esac
