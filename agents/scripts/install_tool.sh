#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# install_tool.sh — Install a tool for a target agent and update its TOOL.md
#
# Usage: install_tool.sh <target_agent_id> <tool_name> [options]
#
# Only IT Support should invoke this script.
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

VALID_TYPES=("apt" "pip" "npm" "binary" "script" "github")

usage() {
    cat <<'EOF'
Usage: install_tool.sh <target_agent_id> <tool_name> [options]

Install a tool for a target agent and register it in the agent's TOOL.md.

Arguments:
  target_agent_id   The agent ID (e.g. ceo, hr, worker-1)
  tool_name         Name of the tool / package to install

Options:
  --type <type>         Install method: apt | pip | npm | binary | script | github
                        (default: apt)
  --source <url>        Source URL (required for binary, script, github)
  --description <desc>  Short description of the tool's purpose
  --usage <usage>       Usage example string
  --dry-run             Show what would be done without executing
  --help                Show this help message

Examples:
  install_tool.sh worker-1 jq --type apt --description "JSON processor"
  install_tool.sh worker-1 black --type pip --usage "black <file.py>"
  install_tool.sh worker-1 mytool --type github --source https://github.com/user/mytool
  install_tool.sh worker-1 prettier --type npm --dry-run
EOF
}

# --help check (before anything else so it works even without arguments)
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# --- Argument parsing --------------------------------------------------------

if [[ $# -lt 2 ]]; then
    echo "Error: Missing required arguments." >&2
    echo "Run 'install_tool.sh --help' for usage." >&2
    exit 1
fi

TARGET_AGENT="$1"
TOOL_NAME="$2"
shift 2

INSTALL_TYPE="apt"
SOURCE_URL=""
DESCRIPTION="${TOOL_NAME}"
USAGE_EXAMPLE="${TOOL_NAME} --help"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)
            if [[ $# -lt 2 ]]; then
                echo "Error: --type requires a value." >&2
                exit 1
            fi
            INSTALL_TYPE="$2"
            shift 2
            ;;
        --source)
            if [[ $# -lt 2 ]]; then
                echo "Error: --source requires a value." >&2
                exit 1
            fi
            SOURCE_URL="$2"
            shift 2
            ;;
        --description)
            if [[ $# -lt 2 ]]; then
                echo "Error: --description requires a value." >&2
                exit 1
            fi
            DESCRIPTION="$2"
            shift 2
            ;;
        --usage)
            if [[ $# -lt 2 ]]; then
                echo "Error: --usage requires a value." >&2
                exit 1
            fi
            USAGE_EXAMPLE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Error: Unknown option '$1'." >&2
            echo "Run 'install_tool.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

# --- Validate install type ---------------------------------------------------

type_valid=false
for t in "${VALID_TYPES[@]}"; do
    if [[ "$INSTALL_TYPE" == "$t" ]]; then
        type_valid=true
        break
    fi
done
if [[ "$type_valid" == false ]]; then
    echo "Error: Invalid install type '$INSTALL_TYPE'." >&2
    echo "Valid types: ${VALID_TYPES[*]}" >&2
    exit 1
fi

# --- Validate source URL for types that require it ---------------------------

if [[ "$INSTALL_TYPE" == "binary" || "$INSTALL_TYPE" == "script" || "$INSTALL_TYPE" == "github" ]]; then
    if [[ -z "$SOURCE_URL" ]]; then
        echo "Error: --source is required for install type '$INSTALL_TYPE'." >&2
        exit 1
    fi
fi

# --- Validate target agent exists --------------------------------------------

AGENT_DIR="${AGENTS_ROOT}/${TARGET_AGENT}"
TOOL_MD="${AGENT_DIR}/TOOL.md"

if [[ ! -d "$AGENT_DIR" ]]; then
    echo "Error: Agent directory '${AGENT_DIR}' does not exist." >&2
    echo "Agent '${TARGET_AGENT}' may not exist." >&2
    exit 1
fi

if [[ ! -f "$TOOL_MD" ]]; then
    echo "Error: TOOL.md not found at '${TOOL_MD}'." >&2
    exit 1
fi

# --- Check if tool is already registered -------------------------------------

if grep -q "^\- \`${TOOL_NAME}\`" "$TOOL_MD" 2>/dev/null; then
    echo "Error: Tool '${TOOL_NAME}' is already registered in ${TARGET_AGENT}/TOOL.md." >&2
    echo "Remove it first with remove_tool.sh if you want to reinstall." >&2
    exit 1
fi

# --- Dry-run banner ----------------------------------------------------------

if [[ "$DRY_RUN" == true ]]; then
    echo "=== DRY RUN === (no changes will be made)"
    echo ""
fi

# --- Execute installation ----------------------------------------------------

TODAY="$(date +%Y-%m-%d)"
INSTALL_OK=true
INSTALL_OUTPUT=""

run_install() {
    case "$INSTALL_TYPE" in
        apt)
            echo "[install] apt install ${TOOL_NAME} ..."
            if [[ "$DRY_RUN" == true ]]; then
                echo "[dry-run] Would run: sudo apt-get install -y ${TOOL_NAME}"
            else
                if command -v sudo &>/dev/null; then
                    if sudo -n true 2>/dev/null; then
                        INSTALL_OUTPUT="$(sudo apt-get install -y "$TOOL_NAME" 2>&1)" || INSTALL_OK=false
                    else
                        echo "Warning: sudo requires a password. Attempting without sudo ..." >&2
                        echo "Hint: You may need to run this with sudo privileges for apt packages." >&2
                        INSTALL_OUTPUT="$(apt-get install -y "$TOOL_NAME" 2>&1)" || INSTALL_OK=false
                    fi
                else
                    echo "Warning: sudo is not available. Attempting apt-get without sudo ..." >&2
                    echo "Hint: apt install typically requires root privileges." >&2
                    INSTALL_OUTPUT="$(apt-get install -y "$TOOL_NAME" 2>&1)" || INSTALL_OK=false
                fi
            fi
            ;;
        pip)
            echo "[install] pip install ${TOOL_NAME} ..."
            if [[ "$DRY_RUN" == true ]]; then
                echo "[dry-run] Would run: pip install ${TOOL_NAME}"
            else
                INSTALL_OUTPUT="$(pip install "$TOOL_NAME" 2>&1)" || INSTALL_OK=false
            fi
            ;;
        npm)
            echo "[install] npm install -g ${TOOL_NAME} ..."
            if [[ "$DRY_RUN" == true ]]; then
                echo "[dry-run] Would run: npm install -g ${TOOL_NAME}"
            else
                INSTALL_OUTPUT="$(npm install -g "$TOOL_NAME" 2>&1)" || INSTALL_OK=false
            fi
            ;;
        binary)
            echo "[install] Downloading binary from ${SOURCE_URL} ..."
            if [[ "$DRY_RUN" == true ]]; then
                echo "[dry-run] Would run: curl -fsSL '${SOURCE_URL}' -o /usr/local/bin/${TOOL_NAME} && chmod +x /usr/local/bin/${TOOL_NAME}"
            else
                INSTALL_OUTPUT="$(curl -fsSL "$SOURCE_URL" -o "/usr/local/bin/${TOOL_NAME}" 2>&1 && chmod +x "/usr/local/bin/${TOOL_NAME}" 2>&1)" || INSTALL_OK=false
            fi
            ;;
        script)
            echo "[install] Running install script from ${SOURCE_URL} ..."
            if [[ "$DRY_RUN" == true ]]; then
                echo "[dry-run] Would run: curl -fsSL '${SOURCE_URL}' | bash"
            else
                INSTALL_OUTPUT="$(curl -fsSL "$SOURCE_URL" | bash 2>&1)" || INSTALL_OK=false
            fi
            ;;
        github)
            echo "[install] Cloning from ${SOURCE_URL} ..."
            if [[ "$DRY_RUN" == true ]]; then
                echo "[dry-run] Would run: git clone '${SOURCE_URL}' /opt/${TOOL_NAME}"
            else
                if command -v gh &>/dev/null; then
                    INSTALL_OUTPUT="$(gh repo clone "$SOURCE_URL" "/opt/${TOOL_NAME}" 2>&1)" || {
                        echo "Warning: gh clone failed, falling back to git clone ..." >&2
                        INSTALL_OUTPUT="$(git clone "$SOURCE_URL" "/opt/${TOOL_NAME}" 2>&1)" || INSTALL_OK=false
                    }
                else
                    INSTALL_OUTPUT="$(git clone "$SOURCE_URL" "/opt/${TOOL_NAME}" 2>&1)" || INSTALL_OK=false
                fi
            fi
            ;;
    esac
}

run_install

if [[ "$INSTALL_OK" == false && "$DRY_RUN" == false ]]; then
    echo "Error: Installation of '${TOOL_NAME}' failed." >&2
    echo "Output:" >&2
    echo "$INSTALL_OUTPUT" >&2
    exit 1
fi

# --- Update TOOL.md ----------------------------------------------------------

TOOL_ENTRY="- \`${TOOL_NAME}\` — ${DESCRIPTION}
  - 用法: \`${USAGE_EXAMPLE}\`
  - 安装方式: ${INSTALL_TYPE}
  - 安装日期: ${TODAY}"

if [[ "$DRY_RUN" == true ]]; then
    echo ""
    echo "[dry-run] Would append to ${TOOL_MD}:"
    echo "$TOOL_ENTRY"
else
    # Ensure file ends with a newline before appending
    if [[ -s "$TOOL_MD" ]]; then
        # Check if file ends with newline
        if [[ "$(tail -c 1 "$TOOL_MD" | wc -l)" -eq 0 ]]; then
            printf '\n' >> "$TOOL_MD"
        fi
    fi
    printf '%s\n' "$TOOL_ENTRY" >> "$TOOL_MD"
    echo "TOOL.md updated for agent '${TARGET_AGENT}'."
fi

# --- Log to install_log.md ---------------------------------------------------

LOG_FILE="${AGENTS_ROOT}/it-support/install_log.md"
TIMESTAMP_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

LOG_ENTRY="| ${TIMESTAMP_ISO} | install | ${TARGET_AGENT} | ${TOOL_NAME} | ${INSTALL_TYPE} | ${DESCRIPTION} |"

if [[ "$DRY_RUN" == true ]]; then
    echo ""
    echo "[dry-run] Would append to ${LOG_FILE}:"
    echo "$LOG_ENTRY"
else
    # Create log file with header if it does not exist
    if [[ ! -f "$LOG_FILE" ]]; then
        cat > "$LOG_FILE" <<'HEADER'
# IT Support — Install Log

| Timestamp | Action | Agent | Tool | Type | Description |
|-----------|--------|-------|------|------|-------------|
HEADER
    fi
    echo "$LOG_ENTRY" >> "$LOG_FILE"
    echo "Install log updated."
fi

# --- Summary -----------------------------------------------------------------

echo ""
if [[ "$DRY_RUN" == true ]]; then
    echo "=== DRY RUN COMPLETE ==="
else
    echo "Successfully installed '${TOOL_NAME}' for agent '${TARGET_AGENT}' via ${INSTALL_TYPE}."
fi
