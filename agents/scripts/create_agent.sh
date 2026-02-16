#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# create_agent.sh — Create a new Agent instance from a role template
#
# Usage: create_agent.sh <agent_id> <role> <department> <reports_to> [options]
#
# Creates the agent workspace directory, populates it from templates, and
# registers the agent in registry.yaml.
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

VALID_ROLES=("ceo" "hr" "it-support" "manager" "worker" "qa")
# Roles that get a WORKSPACE/ directory by default
WORKSPACE_DEFAULT_ROLES=("worker" "qa")
# Default model mapping
DEFAULT_MODEL_WORKER="sonnet"
DEFAULT_MODEL_QA="sonnet"
DEFAULT_MODEL_MANAGER="opus"
DEFAULT_MODEL_CEO="opus"
DEFAULT_MODEL_HR="sonnet"
DEFAULT_MODEL_IT="sonnet"

REGISTRY_FILE="${AGENTS_ROOT}/registry.yaml"

usage() {
    cat <<'EOF'
Usage: create_agent.sh <agent_id> <role> <department> <reports_to> [options]

Create a new Agent instance from a role template.

Arguments:
  agent_id    Unique agent identifier (e.g. dept-gateway-dev-01)
  role        Role type: ceo | hr | it-support | manager | worker | qa
  department  Department name (e.g. dept-gateway)
  reports_to  Agent ID of direct supervisor

Options:
  --model <model>    LLM model to use (default: sonnet for worker/qa, opus for manager)
  --workspace        Force creation of WORKSPACE/ directory (worker/qa get it by default)
  --no-workspace     Skip WORKSPACE/ directory even for worker/qa
  --help             Show this help message

Directory structure created:
  agents/{agent_id}/
  ├── JD.md          From templates/{role}/JD.md with placeholders replaced
  ├── TOOL.md        From templates/{role}/TOOL.md with placeholders replaced
  ├── MEMORY.md      Initialized with "# Memory"
  ├── INBOX/
  │   └── read/
  └── WORKSPACE/     Only for worker and qa (or with --workspace)

Examples:
  create_agent.sh dept-gateway-dev-01 worker dept-gateway dept-gateway-manager
  create_agent.sh dept-gateway-manager manager dept-gateway ceo --model opus
  create_agent.sh dept-gateway-qa qa dept-gateway dept-gateway-manager --model sonnet
EOF
}

# --help check (before anything else)
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# --- Argument parsing --------------------------------------------------------

if [[ $# -lt 4 ]]; then
    echo "Error: Expected at least 4 arguments, got $#." >&2
    echo "Run 'create_agent.sh --help' for usage." >&2
    exit 1
fi

AGENT_ID="$1"
ROLE="$2"
DEPARTMENT="$3"
REPORTS_TO="$4"
shift 4

MODEL=""
FORCE_WORKSPACE=""  # empty = use default, "yes" = force create, "no" = force skip

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)
            if [[ $# -lt 2 ]]; then
                echo "Error: --model requires a value." >&2
                exit 1
            fi
            MODEL="$2"
            shift 2
            ;;
        --workspace)
            FORCE_WORKSPACE="yes"
            shift
            ;;
        --no-workspace)
            FORCE_WORKSPACE="no"
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'." >&2
            echo "Run 'create_agent.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

# --- Validation --------------------------------------------------------------

# Validate role
role_valid=false
for r in "${VALID_ROLES[@]}"; do
    if [[ "$ROLE" == "$r" ]]; then
        role_valid=true
        break
    fi
done
if [[ "$role_valid" == false ]]; then
    echo "Error: Invalid role '$ROLE'." >&2
    echo "Valid roles: ${VALID_ROLES[*]}" >&2
    exit 1
fi

# Validate agent_id format (alphanumeric, hyphens, no spaces)
if [[ ! "$AGENT_ID" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]]; then
    echo "Error: Invalid agent_id '$AGENT_ID'." >&2
    echo "Agent ID must start with a letter or digit and contain only letters, digits, hyphens, and underscores." >&2
    exit 1
fi

# Check agent_id not already taken (directory exists)
AGENT_DIR="${AGENTS_ROOT}/${AGENT_ID}"
if [[ -d "$AGENT_DIR" ]]; then
    echo "Error: Agent '$AGENT_ID' already exists at '${AGENT_DIR}'." >&2
    exit 1
fi

# Also check registry.yaml for the agent_id (may be archived but still registered)
if [[ -f "$REGISTRY_FILE" ]]; then
    if grep -q "^  ${AGENT_ID}:" "$REGISTRY_FILE" 2>/dev/null; then
        echo "Error: Agent '$AGENT_ID' already exists in registry." >&2
        exit 1
    fi
fi

# Validate template exists
TEMPLATE_DIR="${AGENTS_ROOT}/templates/${ROLE}"
if [[ ! -d "$TEMPLATE_DIR" ]]; then
    echo "Error: Template directory not found: '${TEMPLATE_DIR}'." >&2
    echo "Available templates:" >&2
    for d in "${AGENTS_ROOT}/templates"/*/; do
        [[ -d "$d" ]] && echo "  - $(basename "$d")" >&2
    done
    exit 1
fi

if [[ ! -f "${TEMPLATE_DIR}/JD.md" ]]; then
    echo "Error: Template JD.md not found at '${TEMPLATE_DIR}/JD.md'." >&2
    exit 1
fi

if [[ ! -f "${TEMPLATE_DIR}/TOOL.md" ]]; then
    echo "Error: Template TOOL.md not found at '${TEMPLATE_DIR}/TOOL.md'." >&2
    exit 1
fi

# --- Determine defaults ------------------------------------------------------

# Default model based on role
if [[ -z "$MODEL" ]]; then
    case "$ROLE" in
        worker)     MODEL="$DEFAULT_MODEL_WORKER" ;;
        qa)         MODEL="$DEFAULT_MODEL_QA" ;;
        manager)    MODEL="$DEFAULT_MODEL_MANAGER" ;;
        ceo)        MODEL="$DEFAULT_MODEL_CEO" ;;
        hr)         MODEL="$DEFAULT_MODEL_HR" ;;
        it-support) MODEL="$DEFAULT_MODEL_IT" ;;
    esac
fi

# Determine whether to create WORKSPACE/
CREATE_WORKSPACE=false
if [[ "$FORCE_WORKSPACE" == "yes" ]]; then
    CREATE_WORKSPACE=true
elif [[ "$FORCE_WORKSPACE" == "no" ]]; then
    CREATE_WORKSPACE=false
else
    # Default: worker and qa get workspace
    for wr in "${WORKSPACE_DEFAULT_ROLES[@]}"; do
        if [[ "$ROLE" == "$wr" ]]; then
            CREATE_WORKSPACE=true
            break
        fi
    done
fi

CREATED_DATE="$(date -u +%Y-%m-%d)"
WORKSPACE_PATH="${AGENT_DIR}/WORKSPACE"

# --- Create directory structure -----------------------------------------------

echo "Creating agent '${AGENT_ID}' (role=${ROLE}, department=${DEPARTMENT})..."

mkdir -p "${AGENT_DIR}/INBOX/read"

if [[ "$CREATE_WORKSPACE" == true ]]; then
    mkdir -p "${WORKSPACE_PATH}"
fi

# --- Copy and process templates -----------------------------------------------

# Replace placeholders in a template file and write to destination
process_template() {
    local src="$1"
    local dst="$2"

    sed \
        -e "s|{agent_id}|${AGENT_ID}|g" \
        -e "s|{role}|${ROLE}|g" \
        -e "s|{department}|${DEPARTMENT}|g" \
        -e "s|{reports_to}|${REPORTS_TO}|g" \
        -e "s|{model}|${MODEL}|g" \
        -e "s|{created_date}|${CREATED_DATE}|g" \
        -e "s|{workspace_path}|${WORKSPACE_PATH}|g" \
        "$src" > "$dst"
}

process_template "${TEMPLATE_DIR}/JD.md" "${AGENT_DIR}/JD.md"
process_template "${TEMPLATE_DIR}/TOOL.md" "${AGENT_DIR}/TOOL.md"

# Create initial MEMORY.md
printf '# Memory\n' > "${AGENT_DIR}/MEMORY.md"

# --- Update registry.yaml ----------------------------------------------------

init_registry() {
    cat > "$REGISTRY_FILE" <<'YAML'
# AgentOffice 组织登记表
agents: {}
departments: {}
YAML
}

# Initialize registry if it does not exist
if [[ ! -f "$REGISTRY_FILE" ]]; then
    init_registry
fi

# Add agent entry to registry.yaml
# We insert the agent block right after the "agents:" line (or after existing entries).
# Strategy: build the new agent YAML block and insert it into the agents section.

# Build the agent entry (2-space indented under agents)
AGENT_ENTRY="  ${AGENT_ID}:
    role: ${ROLE}
    department: ${DEPARTMENT}
    reports_to: ${REPORTS_TO}
    model: ${MODEL}
    created: ${CREATED_DATE}
    status: active"

# We need to insert AGENT_ENTRY into the agents section of registry.yaml.
# The file structure is:
#   # AgentOffice 组织登记表
#   agents: {}            (or agents:\n  existing-agent:\n  ...)
#   departments: {}       (or departments:\n  existing-dept:\n  ...)
#
# Approach: read the file, manipulate sections, and rewrite.

# Read current registry content
REGISTRY_CONTENT="$(cat "$REGISTRY_FILE")"

# Check if agents section is empty (contains "agents: {}")
if echo "$REGISTRY_CONTENT" | grep -q "^agents: {}"; then
    # Replace "agents: {}" with "agents:" followed by the new entry
    # Use a temp file to avoid sed issues with multiline
    TMPFILE="$(mktemp)"
    # Write everything before "agents: {}"
    # Then write "agents:\n" + entry
    # Then write everything after "agents: {}"
    awk -v entry="$AGENT_ENTRY" '
        /^agents: \{\}/ {
            print "agents:"
            print entry
            next
        }
        { print }
    ' "$REGISTRY_FILE" > "$TMPFILE"
    mv "$TMPFILE" "$REGISTRY_FILE"
else
    # agents section already has entries; insert before the departments line
    # Find the line number of "departments:" or "departments: {}"
    DEPT_LINE=$(grep -n "^departments" "$REGISTRY_FILE" | head -1 | cut -d: -f1)
    if [[ -n "$DEPT_LINE" ]]; then
        # Insert the agent entry before the departments line
        # Remove any blank lines immediately before the departments line,
        # then insert entry + one blank line + departments
        TMPFILE="$(mktemp)"
        awk -v entry="$AGENT_ENTRY" -v dept_line="$DEPT_LINE" '
            # Buffer blank lines so we can drop those right before departments
            /^[[:space:]]*$/ && NR < dept_line {
                blanks = blanks "\n"
                next
            }
            NR == dept_line {
                print entry
                print ""
            }
            {
                if (blanks != "" && NR < dept_line) {
                    printf "%s", blanks
                }
                blanks = ""
                print
            }
        ' "$REGISTRY_FILE" > "$TMPFILE"
        mv "$TMPFILE" "$REGISTRY_FILE"
    else
        # No departments line found; just append to end of file
        echo "" >> "$REGISTRY_FILE"
        echo "$AGENT_ENTRY" >> "$REGISTRY_FILE"
    fi
fi

# --- Update departments section -----------------------------------------------

# Check if the department already exists in registry
update_departments() {
    local dept="$DEPARTMENT"
    local agent_id="$AGENT_ID"
    local role="$ROLE"

    # Read registry content fresh
    local content
    content="$(cat "$REGISTRY_FILE")"

    # Check if departments section is empty
    if echo "$content" | grep -q "^departments: {}"; then
        # Replace "departments: {}" with new department block
        local dept_block="departments:
  ${dept}:
    manager: null
    members:"

        if [[ "$role" == "manager" ]]; then
            dept_block="departments:
  ${dept}:
    manager: ${agent_id}
    members: []"
        else
            dept_block="departments:
  ${dept}:
    manager: null
    members:
      - ${agent_id}"
        fi

        TMPFILE="$(mktemp)"
        awk -v block="$dept_block" '
            /^departments: \{\}/ {
                print block
                next
            }
            { print }
        ' "$REGISTRY_FILE" > "$TMPFILE"
        mv "$TMPFILE" "$REGISTRY_FILE"
        return
    fi

    # Check if department already exists in the departments section
    if grep -q "^  ${dept}:" "$REGISTRY_FILE"; then
        # Department exists — update it
        if [[ "$role" == "manager" ]]; then
            # Update the manager field for this department
            TMPFILE="$(mktemp)"
            awk -v dept="  ${dept}:" -v agent_id="$agent_id" '
                BEGIN { in_dept = 0 }
                $0 == dept { in_dept = 1; print; next }
                in_dept && /^    manager:/ {
                    print "    manager: " agent_id
                    in_dept = 0
                    next
                }
                in_dept && /^  [^ ]/ { in_dept = 0 }
                { print }
            ' "$REGISTRY_FILE" > "$TMPFILE"
            mv "$TMPFILE" "$REGISTRY_FILE"
        else
            # Add agent_id to the members list
            # First check if members is "members: []"
            if grep -A 100 "^  ${dept}:" "$REGISTRY_FILE" | grep -q "members: \[\]"; then
                # Replace "members: []" with "members:" + entry
                TMPFILE="$(mktemp)"
                awk -v dept="  ${dept}:" -v agent_id="$agent_id" '
                    BEGIN { in_dept = 0 }
                    $0 == dept { in_dept = 1; print; next }
                    in_dept && /^    members: \[\]/ {
                        print "    members:"
                        print "      - " agent_id
                        in_dept = 0
                        next
                    }
                    in_dept && /^  [^ ]/ { in_dept = 0 }
                    { print }
                ' "$REGISTRY_FILE" > "$TMPFILE"
                mv "$TMPFILE" "$REGISTRY_FILE"
            else
                # Find the last member line under this department and append after it
                # Or if "members:" has no entries yet, add the first one
                TMPFILE="$(mktemp)"
                awk -v dept="  ${dept}:" -v agent_id="$agent_id" '
                    BEGIN { in_dept = 0; in_members = 0; inserted = 0 }
                    $0 == dept { in_dept = 1; print; next }
                    in_dept && /^    members:/ { in_members = 1; print; next }
                    in_dept && in_members && /^      - / { print; next }
                    in_dept && in_members && !/^      - / {
                        # End of members list — insert here
                        print "      - " agent_id
                        in_members = 0
                        in_dept = 0
                        inserted = 1
                        print
                        next
                    }
                    in_dept && /^  [^ ]/ {
                        # Hit next department without finding members
                        in_dept = 0
                    }
                    { print }
                    END {
                        if (in_members && !inserted) {
                            print "      - " agent_id
                        }
                    }
                ' "$REGISTRY_FILE" > "$TMPFILE"
                mv "$TMPFILE" "$REGISTRY_FILE"
            fi
        fi
    else
        # Department does not exist — append it
        local dept_block
        if [[ "$role" == "manager" ]]; then
            dept_block="  ${dept}:
    manager: ${agent_id}
    members: []"
        else
            dept_block="  ${dept}:
    manager: null
    members:
      - ${agent_id}"
        fi

        # Append to end of file
        echo "$dept_block" >> "$REGISTRY_FILE"
    fi
}

update_departments

# --- Summary ------------------------------------------------------------------

echo ""
echo "Agent created successfully!"
echo "  ID:         ${AGENT_ID}"
echo "  Role:       ${ROLE}"
echo "  Department: ${DEPARTMENT}"
echo "  Reports to: ${REPORTS_TO}"
echo "  Model:      ${MODEL}"
echo "  Directory:  ${AGENT_DIR}"
if [[ "$CREATE_WORKSPACE" == true ]]; then
    echo "  Workspace:  ${WORKSPACE_PATH}"
fi
echo "  Registry:   ${REGISTRY_FILE}"
