#!/usr/bin/env bash
# ==============================================================================
# NEXUS AI-Team -- System Startup Script
# ==============================================================================
#
# Starts all NEXUS subsystems in the correct order:
#   1. Docker Compose (postgres + redis)
#   2. Gateway (uvicorn)
#   3. Org scan (latest snapshot)
#   4. Status report
#
# Usage:
#   ./scripts/nexus-start.sh               # normal start
#   ./scripts/nexus-start.sh --skip-docker  # skip docker (services already up)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"

# Colours (safe for non-tty)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    CYAN='\033[0;36m'
    RESET='\033[0m'
else
    GREEN='' YELLOW='' RED='' CYAN='' RESET=''
fi

info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
fail()  { echo -e "${RED}[FAIL]${RESET}  $*"; }

# -- Parse flags ---------------------------------------------------------------

SKIP_DOCKER=false
for arg in "$@"; do
    case "$arg" in
        --skip-docker) SKIP_DOCKER=true ;;
        --help|-h)
            echo "Usage: $0 [--skip-docker]"
            exit 0
            ;;
        *)
            warn "Unknown flag: $arg"
            ;;
    esac
done

# -- Ensure dirs ---------------------------------------------------------------

mkdir -p "$LOG_DIR"

# ==============================================================================
# Step 1 -- Docker Compose (postgres + redis)
# ==============================================================================

if [ "$SKIP_DOCKER" = false ]; then
    info "Starting Docker Compose services (postgres, redis) ..."
    cd "$PROJECT_ROOT"
    docker compose up -d postgres redis 2>&1 | tee "$LOG_DIR/docker-start.log"

    # Wait for postgres readiness (up to 30 s)
    info "Waiting for PostgreSQL to be ready ..."
    for i in $(seq 1 30); do
        if docker compose exec -T postgres pg_isready -U nexus > /dev/null 2>&1; then
            ok "PostgreSQL ready (${i}s)"
            break
        fi
        sleep 1
        if [ "$i" -eq 30 ]; then
            fail "PostgreSQL did not become ready within 30 s"
            exit 1
        fi
    done

    # Quick Redis ping
    if docker compose exec -T redis redis-cli ping | grep -q PONG; then
        ok "Redis ready"
    else
        warn "Redis did not respond to PING -- continuing anyway"
    fi
else
    info "Skipping Docker Compose (--skip-docker)"
fi

# ==============================================================================
# Step 2 -- Gateway (uvicorn)
# ==============================================================================

info "Starting NEXUS Gateway ..."
cd "$PROJECT_ROOT"

# Kill any lingering gateway process
if pgrep -f "uvicorn gateway.main:app" > /dev/null 2>&1; then
    warn "Gateway already running -- restarting ..."
    pkill -f "uvicorn gateway.main:app" || true
    sleep 2
fi

nohup python -m uvicorn gateway.main:app \
    --host 0.0.0.0 --port 8000 \
    --log-level info \
    > "$LOG_DIR/gateway.log" 2>&1 &

GATEWAY_PID=$!
info "Gateway PID: $GATEWAY_PID"

# Wait for health endpoint (up to 15 s)
for i in $(seq 1 15); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        ok "Gateway healthy (${i}s)"
        break
    fi
    sleep 1
    if [ "$i" -eq 15 ]; then
        warn "Gateway health check timed out -- check $LOG_DIR/gateway.log"
    fi
done

# ==============================================================================
# Step 3 -- Org scan (generate latest snapshot)
# ==============================================================================

if command -v nexus-org > /dev/null 2>&1; then
    info "Running org scan ..."
    nexus-org scan 2>&1 | tee "$LOG_DIR/org-scan.log" || warn "org scan returned non-zero"
    ok "Org scan complete"
else
    warn "nexus-org CLI not found -- skipping org scan"
fi

# ==============================================================================
# Step 4 -- Status report
# ==============================================================================

echo ""
echo "================================================================"
echo "  NEXUS AI-Team -- System Status"
echo "================================================================"
echo ""

# Docker services
if [ "$SKIP_DOCKER" = false ]; then
    info "Docker services:"
    docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
    echo ""
fi

# Gateway
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    ok "Gateway:    http://localhost:8000  (PID $GATEWAY_PID)"
else
    fail "Gateway:    NOT RESPONDING"
fi

# Agent count
AGENT_COUNT=$(grep -c "status: active" "$PROJECT_ROOT/agents/registry.yaml" 2>/dev/null || echo "?")
info "Active agents: $AGENT_COUNT"

# Equipment count
EQUIP_COUNT=$(grep -c "enabled: true" "$PROJECT_ROOT/equipment/registry.yaml" 2>/dev/null || echo "?")
info "Equipment (enabled): $EQUIP_COUNT"

echo ""
ok "NEXUS system startup complete."
echo "   Logs dir:  $LOG_DIR"
echo "   API docs:  http://localhost:8000/docs"
echo ""
