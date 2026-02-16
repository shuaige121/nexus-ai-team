#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# read_mail.sh — Read a specific mail and optionally mark it as read
#
# Usage: read_mail.sh <agent_id> <mail_filename> [--peek]
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

usage() {
    cat <<'EOF'
Usage: read_mail.sh <agent_id> <mail_filename> [--peek]

Display the full contents of a mail message.

Arguments:
  agent_id        The agent ID (e.g. ceo, hr, it-support)
  mail_filename   The .md filename of the mail to read

Options:
  --peek    View the mail without marking it as read
  --help    Show this help message

By default, reading a mail moves it from INBOX/ to INBOX/read/.
Use --peek to view without changing its status.

Examples:
  read_mail.sh ceo 20260216_143000_hr_report_q4-review.md
  read_mail.sh hr 20260216_150000_ceo_request_hiring.md --peek
EOF
}

# --help check
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# --- Argument parsing -------------------------------------------------------

if [[ $# -lt 2 ]]; then
    echo "Error: Missing required arguments." >&2
    echo "Run 'read_mail.sh --help' for usage." >&2
    exit 1
fi

AGENT_ID="$1"
MAIL_FILENAME="$2"
PEEK=false

if [[ "${3:-}" == "--peek" ]]; then
    PEEK=true
elif [[ $# -gt 2 ]]; then
    echo "Error: Unknown option '${3}'." >&2
    echo "Run 'read_mail.sh --help' for usage." >&2
    exit 1
fi

# --- Locate the mail file ---------------------------------------------------

INBOX_DIR="${AGENTS_ROOT}/${AGENT_ID}/INBOX"
READ_DIR="${INBOX_DIR}/read"

if [[ ! -d "$INBOX_DIR" ]]; then
    echo "Error: Inbox '${INBOX_DIR}' does not exist." >&2
    exit 1
fi

MAIL_PATH=""
MAIL_LOCATION="" # "inbox" or "read"

if [[ -f "${INBOX_DIR}/${MAIL_FILENAME}" ]]; then
    MAIL_PATH="${INBOX_DIR}/${MAIL_FILENAME}"
    MAIL_LOCATION="inbox"
elif [[ -f "${READ_DIR}/${MAIL_FILENAME}" ]]; then
    MAIL_PATH="${READ_DIR}/${MAIL_FILENAME}"
    MAIL_LOCATION="read"
else
    echo "Error: Mail '${MAIL_FILENAME}' not found in ${AGENT_ID}'s inbox." >&2
    exit 1
fi

# --- Display the mail -------------------------------------------------------

cat "$MAIL_PATH"

# --- Mark as read (move to read/) unless --peek -----------------------------

if [[ "$PEEK" == false && "$MAIL_LOCATION" == "inbox" ]]; then
    mkdir -p "$READ_DIR"
    mv "$MAIL_PATH" "${READ_DIR}/${MAIL_FILENAME}"
    echo ""
    echo "[Marked as read]"
fi
