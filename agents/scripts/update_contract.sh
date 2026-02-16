#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# update_contract.sh — Update the status of a Contract
#
# Usage: update_contract.sh <contract_id> <new_status> [--note <note>]
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

VALID_STATUSES=("pending" "in_progress" "review" "passed" "failed" "cancelled")

usage() {
    cat <<'EOF'
Usage: update_contract.sh <contract_id> <new_status> [--note <note>]

Update the status of an existing Contract.

Arguments:
  contract_id   The contract ID (e.g. CTR-20260216-001)
  new_status    The new status to set

Valid statuses:
  pending, in_progress, review, passed, failed, cancelled

Valid transitions:
  pending     -> in_progress | cancelled
  in_progress -> review | cancelled
  review      -> passed | failed
  failed      -> in_progress

Options:
  --note <text>   Add a note to the status change record
  --help          Show this help message

Examples:
  update_contract.sh CTR-20260216-001 in_progress
  update_contract.sh CTR-20260216-001 review --note "All tasks completed"
  update_contract.sh CTR-20260216-001 passed --note "Verified output quality"
EOF
}

# --help check
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# --- Argument parsing --------------------------------------------------------

if [[ $# -lt 2 ]]; then
    echo "Error: Missing required arguments." >&2
    echo "Run 'update_contract.sh --help' for usage." >&2
    exit 1
fi

CONTRACT_ID="$1"
NEW_STATUS="$2"
shift 2

NOTE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --note)
            if [[ $# -lt 2 ]]; then
                echo "Error: --note requires a value." >&2
                exit 1
            fi
            NOTE="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'." >&2
            echo "Run 'update_contract.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

# --- Validate new status -----------------------------------------------------

status_valid=false
for s in "${VALID_STATUSES[@]}"; do
    if [[ "$NEW_STATUS" == "$s" ]]; then
        status_valid=true
        break
    fi
done
if [[ "$status_valid" == false ]]; then
    echo "Error: Invalid status '$NEW_STATUS'." >&2
    echo "Valid statuses: ${VALID_STATUSES[*]}" >&2
    exit 1
fi

# --- Locate contract file ----------------------------------------------------

CONTRACTS_DIR="${AGENTS_ROOT}/contracts"
CONTRACT_FILE="${CONTRACTS_DIR}/${CONTRACT_ID}.md"

if [[ ! -f "$CONTRACT_FILE" ]]; then
    echo "Error: Contract file '${CONTRACT_FILE}' not found." >&2
    exit 1
fi

# --- Read current status -----------------------------------------------------

CURRENT_STATUS=""
CURRENT_STATUS=$(grep '^STATUS:' "$CONTRACT_FILE" | head -1 | sed 's/^STATUS:[[:space:]]*//')

if [[ -z "$CURRENT_STATUS" ]]; then
    echo "Error: Could not read current STATUS from '${CONTRACT_FILE}'." >&2
    exit 1
fi

# --- Validate state transition -----------------------------------------------

transition_valid=false

case "$CURRENT_STATUS" in
    pending)
        if [[ "$NEW_STATUS" == "in_progress" || "$NEW_STATUS" == "cancelled" ]]; then
            transition_valid=true
        fi
        ;;
    in_progress)
        if [[ "$NEW_STATUS" == "review" || "$NEW_STATUS" == "cancelled" ]]; then
            transition_valid=true
        fi
        ;;
    review)
        if [[ "$NEW_STATUS" == "passed" || "$NEW_STATUS" == "failed" ]]; then
            transition_valid=true
        fi
        ;;
    failed)
        if [[ "$NEW_STATUS" == "in_progress" ]]; then
            transition_valid=true
        fi
        ;;
    *)
        # passed, cancelled — terminal states, no transitions allowed
        ;;
esac

if [[ "$transition_valid" == false ]]; then
    echo "Error: Invalid transition '${CURRENT_STATUS}' -> '${NEW_STATUS}'." >&2
    echo "Allowed transitions from '${CURRENT_STATUS}':" >&2
    case "$CURRENT_STATUS" in
        pending)       echo "  -> in_progress, cancelled" >&2 ;;
        in_progress)   echo "  -> review, cancelled" >&2 ;;
        review)        echo "  -> passed, failed" >&2 ;;
        failed)        echo "  -> in_progress" >&2 ;;
        passed)        echo "  (terminal state — no transitions allowed)" >&2 ;;
        cancelled)     echo "  (terminal state — no transitions allowed)" >&2 ;;
    esac
    exit 1
fi

# --- Update STATUS field in the file -----------------------------------------

sed -i "s/^STATUS:[[:space:]]*.*/STATUS: ${NEW_STATUS}/" "$CONTRACT_FILE"

# --- Append status change record ---------------------------------------------

TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

{
    echo ""
    echo "---"
    echo "## [Status Change] ${TIMESTAMP}"
    echo "- FROM: ${CURRENT_STATUS}"
    echo "- TO: ${NEW_STATUS}"
    if [[ -n "$NOTE" ]]; then
        echo "- NOTE: ${NOTE}"
    fi
} >> "$CONTRACT_FILE"

# --- Output ------------------------------------------------------------------

echo "Contract ${CONTRACT_ID}: ${CURRENT_STATUS} -> ${NEW_STATUS}"
if [[ -n "$NOTE" ]]; then
    echo "  Note: ${NOTE}"
fi
