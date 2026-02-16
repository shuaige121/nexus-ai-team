#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# create_contract.sh — Create a new Contract and deliver it to an agent
#
# Usage: create_contract.sh <from> <to> [options]
#
# The contract body is read from stdin as JSON.
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

VALID_PRIORITIES=("high" "medium" "low")

usage() {
    cat <<'EOF'
Usage: create_contract.sh <from> <to> [options]

Create a new Contract from one agent to another.

Arguments:
  from    Sender agent ID (e.g. ceo, manager)
  to      Recipient agent ID (e.g. worker, qa)

Options:
  --parent <id>            Parent contract ID (creates a sub-contract)
  --deadline <date>        Deadline in YYYY-MM-DD format
  --priority <level>       Priority: high | medium | low (default: medium)
  --help                   Show this help message

The contract body is read from stdin as JSON with these fields:
  {
    "background": "...",
    "objective": "...",
    "requirements": ["req1", "req2"],
    "restrictions": ["no1"],
    "input": "...",
    "output": "...",
    "acceptance_criteria": ["crit1", "crit2"],
    "context_budget": "小型"
  }

Examples:
  echo '{"background":"...","objective":"..."}' | \
    create_contract.sh ceo manager --deadline 2026-02-17

  echo '{"background":"..."}' | \
    create_contract.sh manager worker --parent CTR-20260216-001 --priority high
EOF
}

# --help check
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# --- Argument parsing --------------------------------------------------------

if [[ $# -lt 2 ]]; then
    echo "Error: Missing required arguments <from> and <to>." >&2
    echo "Run 'create_contract.sh --help' for usage." >&2
    exit 1
fi

FROM="$1"
TO="$2"
shift 2

PARENT=""
DEADLINE=""
PRIORITY="medium"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --parent)
            if [[ $# -lt 2 ]]; then
                echo "Error: --parent requires a value." >&2
                exit 1
            fi
            PARENT="$2"
            shift 2
            ;;
        --deadline)
            if [[ $# -lt 2 ]]; then
                echo "Error: --deadline requires a value." >&2
                exit 1
            fi
            DEADLINE="$2"
            shift 2
            ;;
        --priority)
            if [[ $# -lt 2 ]]; then
                echo "Error: --priority requires a value." >&2
                exit 1
            fi
            PRIORITY="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'." >&2
            echo "Run 'create_contract.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

# --- Validate priority -------------------------------------------------------

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

# --- Validate destination INBOX exists ----------------------------------------

INBOX_DIR="${AGENTS_ROOT}/${TO}/INBOX"
if [[ ! -d "$INBOX_DIR" ]]; then
    echo "Error: Inbox directory '${INBOX_DIR}' does not exist." >&2
    echo "Agent '${TO}' may not exist." >&2
    exit 1
fi

# --- Generate Contract ID ----------------------------------------------------

CONTRACTS_DIR="${AGENTS_ROOT}/contracts"
COUNTER_FILE="${CONTRACTS_DIR}/counter"
TEMPLATE_FILE="${AGENTS_ROOT}/templates/contract.md"

mkdir -p "$CONTRACTS_DIR"

if [[ ! -f "$COUNTER_FILE" ]]; then
    echo "0" > "$COUNTER_FILE"
fi

if [[ ! -f "$TEMPLATE_FILE" ]]; then
    echo "Error: Template file '${TEMPLATE_FILE}' not found." >&2
    exit 1
fi

TODAY="$(date +%Y%m%d)"
CREATED_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ -n "$PARENT" ]]; then
    # Sub-contract: find existing sub-contracts under this parent to determine
    # the next letter suffix (A, B, C, ...)
    existing_count=0
    for f in "${CONTRACTS_DIR}/${PARENT}"-*.md; do
        [[ -e "$f" ]] || continue
        existing_count=$((existing_count + 1))
    done
    # Convert count to letter: 0->A, 1->B, 2->C, ...
    letter_index=$existing_count
    if [[ $letter_index -gt 25 ]]; then
        echo "Error: Too many sub-contracts under parent '${PARENT}' (max 26)." >&2
        exit 1
    fi
    SUFFIX=$(printf "\\$(printf '%03o' $((65 + letter_index)))")
    CONTRACT_ID="${PARENT}-${SUFFIX}"
else
    # Top-level contract: read counter, increment, write back
    COUNTER=$(cat "$COUNTER_FILE")
    COUNTER=$((COUNTER + 1))
    echo "$COUNTER" > "$COUNTER_FILE"
    CONTRACT_ID=$(printf "CTR-%s-%03d" "$TODAY" "$COUNTER")
fi

# --- Read and parse JSON from stdin -------------------------------------------

JSON_INPUT="$(cat)"

if [[ -z "$JSON_INPUT" ]]; then
    echo "Error: No JSON input provided on stdin." >&2
    exit 1
fi

# JSON field extraction: prefer jq if available, fall back to grep/sed
extract_json_string() {
    local json="$1"
    local field="$2"

    if command -v jq &>/dev/null; then
        echo "$json" | jq -r ".${field} // empty" 2>/dev/null || echo ""
    else
        # Simple grep/sed extraction for string fields
        echo "$json" | grep -o "\"${field}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" \
            | sed "s/\"${field}\"[[:space:]]*:[[:space:]]*\"//" \
            | sed 's/"$//' || echo ""
    fi
}

extract_json_array() {
    local json="$1"
    local field="$2"

    if command -v jq &>/dev/null; then
        local result
        result=$(echo "$json" | jq -r "if .${field} then (.${field} | if type == \"array\" then .[] else . end) else empty end" 2>/dev/null || echo "")
        echo "$result"
    else
        # Fallback: extract array contents between [ and ], then split items
        local array_content
        array_content=$(echo "$json" \
            | tr '\n' ' ' \
            | grep -o "\"${field}\"[[:space:]]*:[[:space:]]*\[[^]]*\]" \
            | sed "s/\"${field}\"[[:space:]]*:[[:space:]]*\[//" \
            | sed 's/\]$//' \
            | tr ',' '\n' \
            | sed 's/^[[:space:]]*"//' \
            | sed 's/"[[:space:]]*$//' \
            | sed '/^[[:space:]]*$/d' || echo "")
        echo "$array_content"
    fi
}

BACKGROUND="$(extract_json_string "$JSON_INPUT" "background")"
OBJECTIVE="$(extract_json_string "$JSON_INPUT" "objective")"
INPUT_DESC="$(extract_json_string "$JSON_INPUT" "input")"
OUTPUT_DESC="$(extract_json_string "$JSON_INPUT" "output")"
CONTEXT_BUDGET="$(extract_json_string "$JSON_INPUT" "context_budget")"

# Array fields: format as bullet list
format_as_bullets() {
    local items="$1"
    if [[ -z "$items" ]]; then
        echo "(none)"
        return
    fi
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        echo "- ${line}"
    done <<< "$items"
}

REQUIREMENTS_RAW="$(extract_json_array "$JSON_INPUT" "requirements")"
RESTRICTIONS_RAW="$(extract_json_array "$JSON_INPUT" "restrictions")"
ACCEPTANCE_RAW="$(extract_json_array "$JSON_INPUT" "acceptance_criteria")"

REQUIREMENTS="$(format_as_bullets "$REQUIREMENTS_RAW")"
RESTRICTIONS="$(format_as_bullets "$RESTRICTIONS_RAW")"
ACCEPTANCE_CRITERIA="$(format_as_bullets "$ACCEPTANCE_RAW")"

# --- Fill template -----------------------------------------------------------

# Set defaults for empty fields
[[ -z "$BACKGROUND" ]] && BACKGROUND="(none)"
[[ -z "$OBJECTIVE" ]] && OBJECTIVE="(none)"
[[ -z "$INPUT_DESC" ]] && INPUT_DESC="(none)"
[[ -z "$OUTPUT_DESC" ]] && OUTPUT_DESC="(none)"
[[ -z "$CONTEXT_BUDGET" ]] && CONTEXT_BUDGET="(none)"
[[ -z "$DEADLINE" ]] && DEADLINE="(none)"

CONTRACT_CONTENT="$(cat "$TEMPLATE_FILE")"

# Replace placeholders using parameter expansion (safer than sed for multi-line)
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{contract_id\}/$CONTRACT_ID}"
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{from\}/$FROM}"
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{to\}/$TO}"
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{created_date\}/$CREATED_DATE}"
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{deadline\}/$DEADLINE}"
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{priority\}/$PRIORITY}"
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{background\}/$BACKGROUND}"
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{objective\}/$OBJECTIVE}"
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{requirements\}/$REQUIREMENTS}"
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{restrictions\}/$RESTRICTIONS}"
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{input_description\}/$INPUT_DESC}"
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{output_description\}/$OUTPUT_DESC}"
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{acceptance_criteria\}/$ACCEPTANCE_CRITERIA}"
CONTRACT_CONTENT="${CONTRACT_CONTENT//\{context_budget\}/$CONTEXT_BUDGET}"

if [[ -n "$PARENT" ]]; then
    CONTRACT_CONTENT="${CONTRACT_CONTENT//\{parent_contract_id\}/$PARENT}"
else
    CONTRACT_CONTENT="${CONTRACT_CONTENT//\{parent_contract_id\}/(none)}"
fi

# --- Write contract file -----------------------------------------------------

CONTRACT_FILE="${CONTRACTS_DIR}/${CONTRACT_ID}.md"
printf '%s\n' "$CONTRACT_CONTENT" > "$CONTRACT_FILE"

# --- Copy to recipient INBOX -------------------------------------------------

cp "$CONTRACT_FILE" "${INBOX_DIR}/${CONTRACT_ID}.md"

# --- Output ------------------------------------------------------------------

echo "Contract created: ${CONTRACT_ID}"
echo "  File: ${CONTRACT_FILE}"
echo "  Delivered to: ${TO}/INBOX/${CONTRACT_ID}.md"
