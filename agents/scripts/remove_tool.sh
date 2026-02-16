#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# remove_tool.sh — Remove a tool from a target agent and update its TOOL.md
#
# Usage: remove_tool.sh <target_agent_id> <tool_name> [--force]
#
# Only IT Support should invoke this script.
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

usage() {
    cat <<'EOF'
Usage: remove_tool.sh <target_agent_id> <tool_name> [--force]

Remove a tool from a target agent and deregister it from the agent's TOOL.md.

Arguments:
  target_agent_id   The agent ID (e.g. ceo, hr, worker-1)
  tool_name         Name of the tool / package to remove

Options:
  --force           Skip confirmation prompt and force removal
  --help            Show this help message

Examples:
  remove_tool.sh worker-1 jq
  remove_tool.sh worker-1 black --force
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
    echo "Run 'remove_tool.sh --help' for usage." >&2
    exit 1
fi

TARGET_AGENT="$1"
TOOL_NAME="$2"
shift 2

FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE=true
            shift
            ;;
        *)
            echo "Error: Unknown option '$1'." >&2
            echo "Run 'remove_tool.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

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

# --- Check that the tool is registered in TOOL.md ---------------------------

if ! grep -q "^\- \`${TOOL_NAME}\`" "$TOOL_MD" 2>/dev/null; then
    echo "Error: Tool '${TOOL_NAME}' is not registered in ${TARGET_AGENT}/TOOL.md." >&2
    exit 1
fi

# --- Detect the install type from TOOL.md ------------------------------------

INSTALL_TYPE=""
# Look for the "安装方式:" line following the tool entry
INSTALL_TYPE_LINE="$(grep -A 3 "^\- \`${TOOL_NAME}\`" "$TOOL_MD" | grep "安装方式:" || true)"
if [[ -n "$INSTALL_TYPE_LINE" ]]; then
    INSTALL_TYPE="$(echo "$INSTALL_TYPE_LINE" | sed 's/.*安装方式: *//')"
fi

# --- Confirmation (unless --force) -------------------------------------------

if [[ "$FORCE" == false ]]; then
    echo "About to remove tool '${TOOL_NAME}' from agent '${TARGET_AGENT}'."
    if [[ -n "$INSTALL_TYPE" ]]; then
        echo "  Install type: ${INSTALL_TYPE}"
    fi
    read -r -p "Continue? [y/N] " confirm
    case "$confirm" in
        [yY][eE][sS]|[yY])
            ;;
        *)
            echo "Aborted."
            exit 0
            ;;
    esac
fi

# --- Execute uninstall -------------------------------------------------------

UNINSTALL_OK=true
UNINSTALL_OUTPUT=""

case "$INSTALL_TYPE" in
    apt)
        echo "[remove] apt remove ${TOOL_NAME} ..."
        if command -v sudo &>/dev/null; then
            if sudo -n true 2>/dev/null; then
                UNINSTALL_OUTPUT="$(sudo apt-get remove -y "$TOOL_NAME" 2>&1)" || UNINSTALL_OK=false
            else
                echo "Warning: sudo requires a password. Attempting without sudo ..." >&2
                echo "Hint: You may need sudo privileges for apt remove." >&2
                UNINSTALL_OUTPUT="$(apt-get remove -y "$TOOL_NAME" 2>&1)" || UNINSTALL_OK=false
            fi
        else
            echo "Warning: sudo is not available. Attempting apt-get without sudo ..." >&2
            UNINSTALL_OUTPUT="$(apt-get remove -y "$TOOL_NAME" 2>&1)" || UNINSTALL_OK=false
        fi
        ;;
    pip)
        echo "[remove] pip uninstall ${TOOL_NAME} ..."
        UNINSTALL_OUTPUT="$(pip uninstall -y "$TOOL_NAME" 2>&1)" || UNINSTALL_OK=false
        ;;
    npm)
        echo "[remove] npm uninstall -g ${TOOL_NAME} ..."
        UNINSTALL_OUTPUT="$(npm uninstall -g "$TOOL_NAME" 2>&1)" || UNINSTALL_OK=false
        ;;
    binary)
        echo "[remove] Removing binary /usr/local/bin/${TOOL_NAME} ..."
        if [[ -f "/usr/local/bin/${TOOL_NAME}" ]]; then
            UNINSTALL_OUTPUT="$(rm -f "/usr/local/bin/${TOOL_NAME}" 2>&1)" || UNINSTALL_OK=false
        else
            echo "Warning: Binary not found at /usr/local/bin/${TOOL_NAME}, skipping file removal." >&2
        fi
        ;;
    script)
        echo "[remove] Install type is 'script' — no automatic uninstall available."
        echo "Warning: You may need to manually clean up files installed by the script." >&2
        ;;
    github)
        echo "[remove] Removing cloned repo /opt/${TOOL_NAME} ..."
        if [[ -d "/opt/${TOOL_NAME}" ]]; then
            UNINSTALL_OUTPUT="$(rm -rf "/opt/${TOOL_NAME}" 2>&1)" || UNINSTALL_OK=false
        else
            echo "Warning: Directory /opt/${TOOL_NAME} not found, skipping." >&2
        fi
        ;;
    "")
        echo "Warning: Could not detect install type from TOOL.md. Skipping system uninstall." >&2
        echo "Only the TOOL.md entry will be removed." >&2
        ;;
    *)
        echo "Warning: Unknown install type '${INSTALL_TYPE}'. Skipping system uninstall." >&2
        echo "Only the TOOL.md entry will be removed." >&2
        ;;
esac

if [[ "$UNINSTALL_OK" == false ]]; then
    echo "Warning: System uninstall returned an error (continuing with TOOL.md cleanup)." >&2
    echo "Output: ${UNINSTALL_OUTPUT}" >&2
fi

# --- Remove tool entry from TOOL.md -----------------------------------------

# The tool entry consists of the main line and indented sub-lines that follow it.
# We remove from "- `tool_name`" through any following lines that start with "  " (two spaces).
TEMP_FILE="$(mktemp)"
trap 'rm -f "$TEMP_FILE"' EXIT

in_block=false
while IFS= read -r line; do
    if [[ "$line" =~ ^-\ \`${TOOL_NAME}\` ]]; then
        # Start of the tool block — skip this line
        in_block=true
        continue
    fi
    if [[ "$in_block" == true ]]; then
        # Sub-lines of the tool block start with "  " (indented)
        if [[ "$line" =~ ^[[:space:]]{2,} ]]; then
            continue
        else
            # End of block
            in_block=false
        fi
    fi
    printf '%s\n' "$line"
done < "$TOOL_MD" > "$TEMP_FILE"

# Remove possible trailing blank lines left by the removal
# (keep at most one trailing newline)
cp "$TEMP_FILE" "$TOOL_MD"

echo "TOOL.md updated for agent '${TARGET_AGENT}' — removed '${TOOL_NAME}'."

# --- Log to install_log.md ---------------------------------------------------

LOG_FILE="${AGENTS_ROOT}/it-support/install_log.md"
TIMESTAMP_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

LOG_ENTRY="| ${TIMESTAMP_ISO} | remove | ${TARGET_AGENT} | ${TOOL_NAME} | ${INSTALL_TYPE:-unknown} | — |"

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

# --- Summary -----------------------------------------------------------------

echo ""
echo "Successfully removed '${TOOL_NAME}' from agent '${TARGET_AGENT}'."
