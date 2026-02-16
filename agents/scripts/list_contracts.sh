#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# list_contracts.sh — List contracts with optional filters
#
# Usage: list_contracts.sh [--agent <id>] [--status <status>] [--parent <id>]
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

VALID_STATUSES=("pending" "in_progress" "review" "passed" "failed" "cancelled")

usage() {
    cat <<'EOF'
Usage: list_contracts.sh [--agent <id>] [--status <status>] [--parent <id>]

List contracts with optional filters.

Options:
  --agent <id>      Filter by agent (matches FROM or TO)
  --status <status> Filter by status (pending, in_progress, review,
                    passed, failed, cancelled)
  --parent <id>     Filter by parent contract ID
  --help            Show this help message

Output format:
  ID                    FROM    TO              STATUS       DEADLINE

Examples:
  list_contracts.sh
  list_contracts.sh --status in_progress
  list_contracts.sh --agent worker
  list_contracts.sh --parent CTR-20260216-001
EOF
}

# --help check
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# --- Argument parsing --------------------------------------------------------

FILTER_AGENT=""
FILTER_STATUS=""
FILTER_PARENT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --agent)
            if [[ $# -lt 2 ]]; then
                echo "Error: --agent requires a value." >&2
                exit 1
            fi
            FILTER_AGENT="$2"
            shift 2
            ;;
        --status)
            if [[ $# -lt 2 ]]; then
                echo "Error: --status requires a value." >&2
                exit 1
            fi
            FILTER_STATUS="$2"
            # Validate status
            status_valid=false
            for s in "${VALID_STATUSES[@]}"; do
                if [[ "$FILTER_STATUS" == "$s" ]]; then
                    status_valid=true
                    break
                fi
            done
            if [[ "$status_valid" == false ]]; then
                echo "Error: Invalid status '$FILTER_STATUS'." >&2
                echo "Valid statuses: ${VALID_STATUSES[*]}" >&2
                exit 1
            fi
            shift 2
            ;;
        --parent)
            if [[ $# -lt 2 ]]; then
                echo "Error: --parent requires a value." >&2
                exit 1
            fi
            FILTER_PARENT="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'." >&2
            echo "Run 'list_contracts.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

# --- Scan contracts ----------------------------------------------------------

CONTRACTS_DIR="${AGENTS_ROOT}/contracts"

if [[ ! -d "$CONTRACTS_DIR" ]]; then
    echo "No contracts directory found."
    exit 0
fi

# Parse header fields from a contract .md file.
# Header lines are: "KEY: value" before the first "---" separator.
parse_header_field() {
    local file="$1"
    local field="$2"
    grep "^${field}:" "$file" | head -1 | sed "s/^${field}:[[:space:]]*//"
}

# Collect rows: each row is "ID|FROM|TO|STATUS|DEADLINE"
ROWS=()

for contract_file in "${CONTRACTS_DIR}"/*.md; do
    [[ -e "$contract_file" ]] || continue

    filename="$(basename "$contract_file")"

    # Skip non-contract files
    [[ "$filename" == *.md ]] || continue

    # Parse header fields
    c_id="$(parse_header_field "$contract_file" "ID")"
    c_from="$(parse_header_field "$contract_file" "FROM")"
    c_to="$(parse_header_field "$contract_file" "TO")"
    c_status="$(parse_header_field "$contract_file" "STATUS")"
    c_deadline="$(parse_header_field "$contract_file" "DEADLINE")"
    c_parent="$(parse_header_field "$contract_file" "PARENT")"

    # Apply filters
    if [[ -n "$FILTER_AGENT" ]]; then
        if [[ "$c_from" != "$FILTER_AGENT" && "$c_to" != "$FILTER_AGENT" ]]; then
            continue
        fi
    fi

    if [[ -n "$FILTER_STATUS" ]]; then
        if [[ "$c_status" != "$FILTER_STATUS" ]]; then
            continue
        fi
    fi

    if [[ -n "$FILTER_PARENT" ]]; then
        if [[ "$c_parent" != "$FILTER_PARENT" ]]; then
            continue
        fi
    fi

    ROWS+=("${c_id}|${c_from}|${c_to}|${c_status}|${c_deadline}")
done

# --- Output formatted table --------------------------------------------------

if [[ ${#ROWS[@]} -eq 0 ]]; then
    echo "No contracts found."
    exit 0
fi

# Compute column widths (minimum widths from header)
w_id=2    # "ID"
w_from=4  # "FROM"
w_to=2    # "TO"
w_status=6 # "STATUS"
w_deadline=8 # "DEADLINE"

for row in "${ROWS[@]}"; do
    IFS='|' read -r r_id r_from r_to r_status r_deadline <<< "$row"
    (( ${#r_id} > w_id )) && w_id=${#r_id}
    (( ${#r_from} > w_from )) && w_from=${#r_from}
    (( ${#r_to} > w_to )) && w_to=${#r_to}
    (( ${#r_status} > w_status )) && w_status=${#r_status}
    (( ${#r_deadline} > w_deadline )) && w_deadline=${#r_deadline}
done

# Add padding
PAD=2
w_id=$((w_id + PAD))
w_from=$((w_from + PAD))
w_to=$((w_to + PAD))
w_status=$((w_status + PAD))

# Print header
printf "%-${w_id}s %-${w_from}s %-${w_to}s %-${w_status}s %s\n" \
    "ID" "FROM" "TO" "STATUS" "DEADLINE"

# Print separator
total_width=$((w_id + w_from + w_to + w_status + w_deadline + 4))
printf '%*s\n' "$total_width" '' | tr ' ' '-'

# Print rows (sorted by ID)
printf '%s\n' "${ROWS[@]}" | sort | while IFS='|' read -r r_id r_from r_to r_status r_deadline; do
    printf "%-${w_id}s %-${w_from}s %-${w_to}s %-${w_status}s %s\n" \
        "$r_id" "$r_from" "$r_to" "$r_status" "$r_deadline"
done
