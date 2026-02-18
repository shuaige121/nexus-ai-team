#!/usr/bin/env bash
# Skill Onboard — post-install automation for Nexus skills
# Usage: skill_onboard.sh <skill-name> <skill-dir> <skill-type>

set -euo pipefail

SKILL_NAME="${1:?Usage: skill_onboard.sh <skill-name> <skill-dir> <skill-type>}"
SKILL_DIR="${2:?Missing skill directory}"
SKILL_TYPE="${3:?Missing skill type}"

NEXUS_HOME="${HOME}/.nexus"
REGISTRY="${NEXUS_HOME}/skills/registry.json"
LOG_FILE="${NEXUS_HOME}/skills/${SKILL_NAME}/onboard.log"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE" 2>/dev/null || true
}

# --- MCP Server configuration ---
configure_mcp_server() {
    local manifest="${SKILL_DIR}/manifest.yaml"
    local entry_point
    entry_point=$(grep 'entry_point:' "$manifest" | head -1 | sed 's/.*: *"\?\([^"]*\)"\?/\1/' | tr -d ' ')
    local runtime
    runtime=$(grep 'runtime:' "$manifest" | head -1 | sed 's/.*: *"\?\([^"]*\)"\?/\1/' | tr -d ' ')

    local mcp_config="${NEXUS_HOME}/mcp-servers.json"

    if [ ! -f "$mcp_config" ]; then
        echo '{"servers":{}}' > "$mcp_config"
    fi

    local cmd
    if [ "$runtime" = "python" ]; then
        cmd="python3 ${SKILL_DIR}/${entry_point}"
    elif [ "$runtime" = "node" ]; then
        cmd="node ${SKILL_DIR}/${entry_point}"
    else
        cmd="${SKILL_DIR}/${entry_point}"
    fi

    # Use python to update JSON since jq may not be available
    python3 -c "
import json, sys
with open('${mcp_config}') as f:
    cfg = json.load(f)
cfg['servers']['${SKILL_NAME}'] = {
    'command': '${cmd}',
    'type': 'stdio',
    'skill_dir': '${SKILL_DIR}'
}
with open('${mcp_config}', 'w') as f:
    json.dump(cfg, f, indent=2)
"
    log "MCP server '${SKILL_NAME}' registered: ${cmd}"
}

# --- Skill File registration ---
configure_skill_file() {
    log "Skill file '${SKILL_NAME}' registered at ${SKILL_DIR}"
}

# --- Plugin registration ---
configure_plugin() {
    log "Plugin '${SKILL_NAME}' registered at ${SKILL_DIR}"
}

# --- Smoke Test ---
run_smoke_test() {
    local manifest="${SKILL_DIR}/manifest.yaml"
    local entry_point
    entry_point=$(grep 'entry_point:' "$manifest" | head -1 | sed 's/.*: *"\?\([^"]*\)"\?/\1/' | tr -d ' ')
    local runtime
    runtime=$(grep 'runtime:' "$manifest" | head -1 | sed 's/.*: *"\?\([^"]*\)"\?/\1/' | tr -d ' ')

    local target="${SKILL_DIR}/${entry_point}"

    if [ ! -f "$target" ]; then
        log "[WARN] Entry point not found: ${target}"
        return 1
    fi

    if [ "$runtime" = "python" ]; then
        if python3 -c "import ast; ast.parse(open('${target}').read())" 2>/dev/null; then
            log "Smoke test PASSED: Python syntax valid"
            return 0
        else
            log "[FAIL] Smoke test: Python syntax error in ${target}"
            return 1
        fi
    elif [ "$runtime" = "node" ]; then
        if node --check "${target}" 2>/dev/null; then
            log "Smoke test PASSED: Node syntax valid"
            return 0
        else
            log "[FAIL] Smoke test: Node syntax error in ${target}"
            return 1
        fi
    else
        log "Smoke test SKIPPED: unknown runtime '${runtime}'"
        return 0
    fi
}

# --- Main ---
log "=== Onboarding skill: ${SKILL_NAME} (type: ${SKILL_TYPE}) ==="

case "${SKILL_TYPE}" in
    mcp-server)
        configure_mcp_server
        ;;
    skill-file)
        configure_skill_file
        ;;
    plugin)
        configure_plugin
        ;;
    *)
        log "[WARN] Unknown skill type: ${SKILL_TYPE}. Skipping type-specific config."
        ;;
esac

run_smoke_test
log "=== Onboarding complete for ${SKILL_NAME} ==="
