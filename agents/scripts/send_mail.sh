#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# send_mail.sh — Send a mail message from one agent to another
#
# Usage: send_mail.sh <from> <to> <type> <subject> [priority]
#
# The mail body is read from stdin.
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

VALID_TYPES=("contract" "report" "request" "hire" "fire" "review" "result" "tool_request" "tool_installed")
VALID_PRIORITIES=("high" "medium" "low")

usage() {
    cat <<'EOF'
Usage: send_mail.sh <from> <to> <type> <subject> [priority]

Send a mail message from one agent to another.

Arguments:
  from       Sender agent ID (e.g. ceo, hr, it-support)
  to         Recipient agent ID
  type       Mail type: contract | report | request | hire | fire | review |
             result | tool_request | tool_installed
  subject    Mail subject (hyphen-separated, no spaces)
  priority   Optional: high | medium | low (default: medium)

The mail body is read from stdin.

Examples:
  echo "Please review the Q4 report." | send_mail.sh ceo hr request q4-review
  echo "Hiring approved." | send_mail.sh hr ceo result hiring-approved high
EOF
}

# --help check
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# --- Argument validation ---------------------------------------------------

if [[ $# -lt 4 || $# -gt 5 ]]; then
    echo "Error: Expected 4 or 5 arguments, got $#." >&2
    echo "Run 'send_mail.sh --help' for usage." >&2
    exit 1
fi

FROM="$1"
TO="$2"
TYPE="$3"
SUBJECT="$4"
PRIORITY="${5:-medium}"

# Validate type
type_valid=false
for t in "${VALID_TYPES[@]}"; do
    if [[ "$TYPE" == "$t" ]]; then
        type_valid=true
        break
    fi
done
if [[ "$type_valid" == false ]]; then
    echo "Error: Invalid type '$TYPE'." >&2
    echo "Valid types: ${VALID_TYPES[*]}" >&2
    exit 1
fi

# Validate priority
priority_valid=false
for p in "${VALID_PRIORITIES[@]}"; do
    if [[ "$PRIORITY" == "$p" ]]; then
        priority_valid=true
        break
    fi
done
if [[ "$priority_valid" == false ]]; then
    echo "Error: Invalid priority '$PRIORITY'." >&2
    echo "Valid priorities: ${VALID_PRIORITIES[*]}" >&2
    exit 1
fi

# Validate subject (no spaces)
if [[ "$SUBJECT" =~ [[:space:]] ]]; then
    echo "Error: Subject must not contain spaces. Use hyphens instead." >&2
    exit 1
fi

# Validate destination INBOX exists
INBOX_DIR="${AGENTS_ROOT}/${TO}/INBOX"
if [[ ! -d "$INBOX_DIR" ]]; then
    echo "Error: Inbox directory '${INBOX_DIR}' does not exist." >&2
    echo "Agent '${TO}' may not exist." >&2
    exit 1
fi

# --- Build the mail ---------------------------------------------------------

TIMESTAMP_FILE="$(date +%Y%m%d_%H%M%S)"
TIMESTAMP_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

FILENAME="${TIMESTAMP_FILE}_${FROM}_${TYPE}_${SUBJECT}.md"
FILEPATH="${INBOX_DIR}/${FILENAME}"

# Read body from stdin
BODY="$(cat)"

# Write the mail file
cat > "$FILEPATH" <<MAIL
# MAIL
FROM: ${FROM}
TO: ${TO}
TYPE: ${TYPE}
PRIORITY: ${PRIORITY}
TIMESTAMP: ${TIMESTAMP_ISO}
---

${BODY}
MAIL

echo "Mail sent: ${TO}/INBOX/${FILENAME}"
