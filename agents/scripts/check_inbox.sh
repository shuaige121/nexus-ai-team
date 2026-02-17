#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# check_inbox.sh — List mail in an agent's INBOX
#
# Usage: check_inbox.sh <agent_id> [--unread | --all | --type <type>]
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

VALID_TYPES=(
    "contract" "report" "request" "hire" "fire" "review" "result"
    "tool_request" "tool_installed"
    "directive" "review_feedback" "inquiry" "hr_request"
    "agent_created" "agent_deleted" "confirmation"
    "tool_configured" "tool_fixed"
    "sub_contract" "qa_request" "completion_report" "hire_request"
    "fire_request" "status_update" "rework_request"
    "qa_report" "blocked"
    "task_completed" "context_overflow"
)

usage() {
    cat <<'EOF'
Usage: check_inbox.sh <agent_id> [--unread | --all | --type <type>]

List mail messages in an agent's inbox.

Arguments:
  agent_id    The agent ID (e.g. ceo, hr, it-support)

Options:
  --all       List all mail: unread and read (default)
  --unread    List only unread mail (files still in INBOX/, not in INBOX/read/)
  --type TYPE Filter by mail type (contract, report, request, hire, fire,
              review, result, tool_request, tool_installed)
  --help      Show this help message

Output format (one line per mail, newest first):
  TIMESTAMP  FROM  TYPE  SUBJECT  [UNREAD]

Examples:
  check_inbox.sh ceo
  check_inbox.sh hr --unread
  check_inbox.sh ceo --type request
EOF
}

# --help check
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# --- Argument parsing -------------------------------------------------------

if [[ $# -lt 1 ]]; then
    echo "Error: Missing agent_id." >&2
    echo "Run 'check_inbox.sh --help' for usage." >&2
    exit 1
fi

AGENT_ID="$1"
shift

MODE="all"        # all | unread
FILTER_TYPE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)
            MODE="all"
            shift
            ;;
        --unread)
            MODE="unread"
            shift
            ;;
        --type)
            if [[ $# -lt 2 ]]; then
                echo "Error: --type requires a value." >&2
                exit 1
            fi
            FILTER_TYPE="$2"
            # Validate type
            type_valid=false
            for t in "${VALID_TYPES[@]}"; do
                if [[ "$FILTER_TYPE" == "$t" ]]; then
                    type_valid=true
                    break
                fi
            done
            if [[ "$type_valid" == false ]]; then
                echo "Error: Invalid type '$FILTER_TYPE'." >&2
                echo "Valid types: ${VALID_TYPES[*]}" >&2
                exit 1
            fi
            shift 2
            ;;
        *)
            echo "Error: Unknown option '$1'." >&2
            echo "Run 'check_inbox.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

# --- Validate agent INBOX --------------------------------------------------

INBOX_DIR="${AGENTS_ROOT}/${AGENT_ID}/INBOX"
READ_DIR="${INBOX_DIR}/read"

if [[ ! -d "$INBOX_DIR" ]]; then
    echo "Error: Inbox '${INBOX_DIR}' does not exist." >&2
    exit 1
fi

# --- Collect mail files -----------------------------------------------------

# parse_mail_filename extracts fields from a filename like:
#   20260216_143000_ceo_request_q4-review.md
# Output: TIMESTAMP FROM TYPE SUBJECT STATUS
parse_and_print() {
    local filepath="$1"
    local status="$2"
    local filename
    filename="$(basename "$filepath")"

    # Skip non-.md files and .gitkeep
    if [[ "$filename" != *.md ]]; then
        return
    fi

    # Skip files that don't match the mail naming convention
    # Mail files: YYYYMMDD_HHMMSS[nanoseconds]_from_type_subject.md
    # Contract files (CTR-*.md) and other non-mail files are skipped
    if [[ ! "$filename" =~ ^[0-9]{8}_[0-9]{6,}_ ]]; then
        return
    fi

    # Extract fields from filename: {timestamp}_{from}_{type}_{subject}.md
    # timestamp = YYYYMMDD_HHMMSS (two underscore-separated parts)
    # So pattern: part1_part2_from_type_subject.md
    local name_no_ext="${filename%.md}"

    # Split on underscores — we know the first two parts form the timestamp
    # Format: YYYYMMDD_HHMMSS_from_type_subject
    local date_part time_part rest
    date_part="$(echo "$name_no_ext" | cut -d'_' -f1)"
    time_part="$(echo "$name_no_ext" | cut -d'_' -f2)"
    local from_agent type_field subject_field
    from_agent="$(echo "$name_no_ext" | cut -d'_' -f3)"
    type_field="$(echo "$name_no_ext" | cut -d'_' -f4)"
    # Subject is everything after the 4th underscore
    subject_field="$(echo "$name_no_ext" | cut -d'_' -f5-)"

    # Format timestamp for display: YYYY-MM-DD HH:MM:SS
    local ts_display="${date_part:0:4}-${date_part:4:2}-${date_part:6:2} ${time_part:0:2}:${time_part:2:2}:${time_part:4:2}"

    # Apply type filter
    if [[ -n "$FILTER_TYPE" && "$type_field" != "$FILTER_TYPE" ]]; then
        return
    fi

    local status_tag=""
    if [[ "$status" == "unread" ]]; then
        status_tag="  [UNREAD]"
    fi

    # Output for sorting: raw timestamp first (for sort), then display line
    echo "${date_part}${time_part}|${ts_display}  ${from_agent}  ${type_field}  ${subject_field}${status_tag}"
}

RESULTS=()

# Unread mail (files directly in INBOX/)
collect_unread() {
    for f in "${INBOX_DIR}"/*.md; do
        [[ -e "$f" ]] || continue
        local line
        line="$(parse_and_print "$f" "unread")"
        if [[ -n "$line" ]]; then
            RESULTS+=("$line")
        fi
    done
}

# Read mail (files in INBOX/read/)
collect_read() {
    if [[ ! -d "$READ_DIR" ]]; then
        return
    fi
    for f in "${READ_DIR}"/*.md; do
        [[ -e "$f" ]] || continue
        local line
        line="$(parse_and_print "$f" "read")"
        if [[ -n "$line" ]]; then
            RESULTS+=("$line")
        fi
    done
}

case "$MODE" in
    unread)
        collect_unread
        ;;
    all)
        collect_unread
        collect_read
        ;;
esac

# --- Output (sorted by timestamp, newest first) ----------------------------

if [[ ${#RESULTS[@]} -eq 0 ]]; then
    echo "No mail found."
    exit 0
fi

# Sort by the sort-key prefix (descending), then strip it for display
printf '%s\n' "${RESULTS[@]}" | sort -t'|' -k1 -r | cut -d'|' -f2-
