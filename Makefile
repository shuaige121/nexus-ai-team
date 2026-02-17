# ══════════════════════════════════════════════════════════════════════════════
# NEXUS AI Team — Makefile
# ══════════════════════════════════════════════════════════════════════════════
#
# Quick commands for Docker Compose operations and common tasks.
#
# Usage:
#   make up          — Start all services
#   make down        — Stop all services
#   make logs        — Show logs from all services
#   make logs-gateway — Show logs from gateway only
#   make ps          — Show running containers
#   make restart     — Restart all services
#   make clean       — Stop services and remove volumes (WARNING: deletes data)
#

.PHONY: help up down logs logs-gateway logs-dashboard ps restart build clean test health

# Default target
help:
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║                    NEXUS AI Team — Makefile                    ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make up              Start all services (detached mode)"
	@echo "  make down            Stop all services"
	@echo "  make restart         Restart all services"
	@echo "  make ps              Show running containers"
	@echo "  make logs            Show logs from all services"
	@echo "  make logs-gateway    Show logs from gateway service"
	@echo "  make logs-dashboard  Show logs from dashboard service"
	@echo "  make logs-postgres   Show logs from PostgreSQL"
	@echo "  make logs-redis      Show logs from Redis"
	@echo ""
	@echo "Build Commands:"
	@echo "  make build           Build all Docker images"
	@echo "  make build-gateway   Build gateway image only"
	@echo "  make build-dashboard Build dashboard image only"
	@echo ""
	@echo "Development Commands:"
	@echo "  make dev             Start services in development mode"
	@echo "  make shell           Open shell in gateway container"
	@echo "  make test            Run tests"
	@echo ""
	@echo "Maintenance Commands:"
	@echo "  make health          Check health of all services"
	@echo "  make clean           Stop services and remove volumes (⚠️  deletes data)"
	@echo "  make prune           Remove unused Docker resources"
	@echo ""

# ── Docker Compose Operations ────────────────────────────────────────────────

up:
	@echo "🚀 Starting NEXUS services..."
	docker compose up -d
	@echo "✅ Services started. Check status with: make ps"

down:
	@echo "🛑 Stopping NEXUS services..."
	docker compose down
	@echo "✅ Services stopped."

restart: down up
	@echo "♻️  Services restarted."

ps:
	@docker compose ps

logs:
	docker compose logs -f

logs-gateway:
	docker compose logs -f gateway

logs-dashboard:
	docker compose logs -f dashboard

logs-postgres:
	docker compose logs -f postgres

logs-redis:
	docker compose logs -f redis

# ── Build Commands ────────────────────────────────────────────────────────────

build:
	@echo "🏗️  Building all images..."
	docker compose build

build-gateway:
	@echo "🏗️  Building gateway image..."
	docker compose build gateway

build-dashboard:
	@echo "🏗️  Building dashboard image..."
	docker compose build dashboard

# ── Development ───────────────────────────────────────────────────────────────

dev:
	@echo "🔧 Starting NEXUS in development mode..."
	DOCKER_BUILD_TARGET=development DASHBOARD_BUILD_TARGET=development VOLUME_MODE=rw docker compose up

shell:
	@docker compose exec gateway /bin/bash

shell-dashboard:
	@docker compose exec dashboard /bin/sh

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	@echo "🧪 Running tests..."
	docker compose exec gateway pytest

test-local:
	@echo "🧪 Running tests locally..."
	pytest

# ── Health & Monitoring ───────────────────────────────────────────────────────

health:
	@echo "🏥 Checking service health..."
	@echo ""
	@echo "Gateway:"
	@curl -sf http://localhost:8000/health && echo "✅ Gateway healthy" || echo "❌ Gateway unhealthy"
	@echo ""
	@echo "Dashboard:"
	@curl -sf http://localhost:3000/health && echo "✅ Dashboard healthy" || echo "❌ Dashboard unhealthy"
	@echo ""
	@echo "Detailed Health:"
	@curl -sf http://localhost:8000/api/health/detailed | python3 -m json.tool || echo "❌ Failed to fetch detailed health"

# ── Maintenance ───────────────────────────────────────────────────────────────

clean:
	@echo "⚠️  WARNING: This will delete all volumes and data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "🧹 Cleaning up..."; \
		docker compose down -v; \
		echo "✅ Cleanup complete."; \
	else \
		echo "❌ Cleanup cancelled."; \
	fi

prune:
	@echo "🧹 Removing unused Docker resources..."
	docker system prune -f
	@echo "✅ Prune complete."

# ── Quick Access ──────────────────────────────────────────────────────────────

open:
	@echo "🌐 Opening services in browser..."
	@command -v xdg-open > /dev/null && xdg-open http://localhost:3000 || open http://localhost:3000 || echo "Please open http://localhost:3000 manually"

api-docs:
	@echo "📚 Opening API documentation..."
	@command -v xdg-open > /dev/null && xdg-open http://localhost:8000/docs || open http://localhost:8000/docs || echo "Please open http://localhost:8000/docs manually"
