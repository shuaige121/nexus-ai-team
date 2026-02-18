"""NEXUS AI-Team -- System-level integration tests.

These tests verify that every subsystem (agents, gateway, equipment, heartbeat,
skills, pipeline) can be loaded, parsed, and cross-referenced correctly WITHOUT
requiring running services (postgres, redis, uvicorn).

Run with:
    python -m pytest tests/test_integration_system.py -v
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def agent_registry(project_root: Path) -> dict[str, Any]:
    """Load agents/registry.yaml once per session."""
    path = project_root / "agents" / "registry.yaml"
    assert path.exists(), f"agents/registry.yaml not found at {path}"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert data is not None, "agents/registry.yaml is empty"
    return data


@pytest.fixture(scope="session")
def org_yaml(project_root: Path) -> dict[str, Any]:
    """Load company/org.yaml once per session."""
    path = project_root / "company" / "org.yaml"
    assert path.exists(), f"company/org.yaml not found at {path}"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert data is not None, "company/org.yaml is empty"
    return data


@pytest.fixture(scope="session")
def all_agents(agent_registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the agents sub-dict from registry.yaml."""
    agents = agent_registry.get("agents", {})
    assert len(agents) > 0, "No agents found in registry"
    return agents


@pytest.fixture(scope="session")
def skill_registry_path() -> Path:
    return Path.home() / ".nexus" / "skills" / "registry.json"


# ---------------------------------------------------------------------------
# Test 1: Agent registry loads all agents
# ---------------------------------------------------------------------------


class TestAgentRegistry:
    def test_registry_loads_all_agents(self, all_agents: dict[str, dict[str, Any]]) -> None:
        """agents/registry.yaml loads correctly with all expected fields."""
        required_fields = {"role", "department", "reports_to", "model", "status"}
        for agent_id, info in all_agents.items():
            missing = required_fields - set(info.keys())
            assert not missing, (
                f"Agent '{agent_id}' missing fields: {missing}"
            )

    def test_all_agents_have_active_or_inactive_status(
        self, all_agents: dict[str, dict[str, Any]]
    ) -> None:
        """Every agent has a valid status value."""
        valid_statuses = {"active", "inactive", "suspended"}
        for agent_id, info in all_agents.items():
            assert info.get("status") in valid_statuses, (
                f"Agent '{agent_id}' has invalid status: {info.get('status')}"
            )


# ---------------------------------------------------------------------------
# Test 2: Department routing
# ---------------------------------------------------------------------------


class TestDepartmentRouting:
    def test_department_routing(self, all_agents: dict[str, dict[str, Any]]) -> None:
        """Engineering tasks should route to the engineering department."""
        from gateway.agent_router import AgentRouter

        router = AgentRouter()

        eng_agent = router.route("code")
        assert eng_agent is not None, "No agent found for task_type='code'"
        assert all_agents[eng_agent]["department"] == "engineering", (
            f"Expected engineering dept, got {all_agents[eng_agent]['department']}"
        )

    def test_qa_routing(self, all_agents: dict[str, dict[str, Any]]) -> None:
        """QA tasks should route to the qa department."""
        from gateway.agent_router import AgentRouter

        router = AgentRouter()
        qa_agent = router.route("test")
        assert qa_agent is not None, "No agent found for task_type='test'"
        assert all_agents[qa_agent]["department"] == "qa", (
            f"Expected qa dept, got {all_agents[qa_agent]['department']}"
        )

    def test_unknown_task_falls_back_to_ceo(self) -> None:
        """Unrecognised task types should fall back to CEO."""
        from gateway.agent_router import AgentRouter

        router = AgentRouter()
        agent = router.route("xyzzy_unknown_task")
        assert agent == "ceo", f"Expected fallback to 'ceo', got '{agent}'"

    def test_fallback_when_preferred_excluded(self) -> None:
        """When the preferred agent is excluded, pick another in same dept."""
        from gateway.agent_router import AgentRouter

        router = AgentRouter()
        agent = router.route("code", exclude={"eng_manager"})
        assert agent is not None, "Should find a fallback engineer"
        assert agent != "eng_manager"


# ---------------------------------------------------------------------------
# Test 3: Chain-of-command integrity
# ---------------------------------------------------------------------------


class TestChainOfCommand:
    def test_chain_of_command_integrity(
        self, all_agents: dict[str, dict[str, Any]], org_yaml: dict[str, Any]
    ) -> None:
        """Every agent's reports_to should reference an existing agent or a known org position."""
        # Valid targets: all agent IDs + 'board' + all positions from org.yaml chain_of_command
        chain_positions = set(org_yaml.get("chain_of_command", {}).keys())
        valid_targets = set(all_agents.keys()) | {"board"} | chain_positions
        for agent_id, info in all_agents.items():
            reports_to = info.get("reports_to")
            assert reports_to is not None, (
                f"Agent '{agent_id}' missing reports_to"
            )
            assert reports_to in valid_targets, (
                f"Agent '{agent_id}' reports_to '{reports_to}' does not exist. "
                f"Valid targets: {sorted(valid_targets)}"
            )


# ---------------------------------------------------------------------------
# Test 4: JD file completeness
# ---------------------------------------------------------------------------


class TestJDFiles:
    # Known mappings: registry agent_id -> JD directory name
    JD_ALIASES: dict[str, str] = {
        "hr": "hr_lead",
    }

    def test_all_agents_have_jd(
        self, project_root: Path, all_agents: dict[str, dict[str, Any]]
    ) -> None:
        """Every registered agent should have a jd.md in company/agents/.

        Agents prefixed with 'dept-' or 'it-support' are skipped (legacy structure).
        """
        agents_dir = project_root / "company" / "agents"
        missing: list[str] = []
        for agent_id in all_agents:
            # Skip dept-gateway agents and legacy it-support (uses different structure)
            if agent_id.startswith("dept-") or agent_id == "it-support":
                continue
            role = all_agents[agent_id].get("role", agent_id)
            alias = self.JD_ALIASES.get(agent_id)
            # Check by agent_id, by role, or by alias
            candidates = [agent_id, role]
            if alias:
                candidates.append(alias)
            found = any((agents_dir / c / "jd.md").exists() for c in candidates)
            if not found:
                missing.append(agent_id)
        assert not missing, (
            f"Agents missing jd.md: {missing}"
        )


# ---------------------------------------------------------------------------
# Test 5: Skill registry format
# ---------------------------------------------------------------------------


class TestSkillRegistry:
    def test_skill_registry_format(self, skill_registry_path: Path) -> None:
        """If skill registry exists, it should be valid JSON with expected structure."""
        if not skill_registry_path.exists():
            pytest.skip("Skill registry not found -- no skills installed yet")

        with open(skill_registry_path, encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, (dict, list)), (
            f"Skill registry should be dict or list, got {type(data).__name__}"
        )

        # If dict with 'skills' key
        if isinstance(data, dict) and "skills" in data:
            skills = data["skills"]
            assert isinstance(skills, dict), "skills should be a dict"
            for name, _meta in skills.items():
                assert isinstance(name, str), f"Skill name should be str, got {type(name)}"

    def test_skill_registry_importable(self) -> None:
        """The SkillRegistry class can be imported and instantiated."""
        from gateway.skill_registry import SkillRegistry

        sr = SkillRegistry()
        skills = sr.list_skills()
        assert isinstance(skills, list)


# ---------------------------------------------------------------------------
# Test 6: Equipment module integration
# ---------------------------------------------------------------------------


class TestEquipmentIntegration:
    def test_equipment_manager_loads(self, project_root: Path) -> None:
        """EquipmentManager loads all equipment from registry.yaml."""
        from equipment import EquipmentManager

        registry_path = project_root / "equipment" / "registry.yaml"
        if not registry_path.exists():
            pytest.skip("equipment/registry.yaml not found")

        mgr = EquipmentManager(registry_path=str(registry_path))
        equipment_list = mgr.list_equipment()
        assert isinstance(equipment_list, list)
        assert len(equipment_list) > 0, "Expected at least one registered equipment"

        # Verify each has required fields
        for eq in equipment_list:
            assert "name" in eq, f"Equipment entry missing 'name': {eq}"
            assert "enabled" in eq, f"Equipment '{eq.get('name')}' missing 'enabled'"

        mgr.shutdown()

    def test_equipment_registry_entries_have_scripts(self, project_root: Path) -> None:
        """Each equipment entry references a script_path that exists."""
        registry_path = project_root / "equipment" / "registry.yaml"
        if not registry_path.exists():
            pytest.skip("equipment/registry.yaml not found")

        with open(registry_path, encoding="utf-8") as f:
            registry = yaml.safe_load(f) or {}

        scripts_dir = project_root / "equipment" / "scripts"
        missing_scripts: list[str] = []
        for name, entry in registry.items():
            script = entry.get("script_path", "")
            if script and not (scripts_dir / script).exists():
                missing_scripts.append(f"{name} -> {script}")

        assert not missing_scripts, (
            f"Equipment with missing scripts: {missing_scripts}"
        )


# ---------------------------------------------------------------------------
# Test 7: Heartbeat module integration
# ---------------------------------------------------------------------------


class TestHeartbeatIntegration:
    def test_heartbeat_importable(self) -> None:
        """All heartbeat sub-modules can be imported."""
        mod = importlib.import_module("heartbeat")
        assert hasattr(mod, "HealthMonitor"), "Missing HealthMonitor"
        assert hasattr(mod, "AlertManager"), "Missing AlertManager"
        assert hasattr(mod, "RecoveryManager"), "Missing RecoveryManager"

    def test_heartbeat_monitor_importable(self) -> None:
        """heartbeat.monitor can be imported."""
        mod = importlib.import_module("heartbeat.monitor")
        assert hasattr(mod, "HealthMonitor")

    def test_heartbeat_alerts_importable(self) -> None:
        """heartbeat.alerts can be imported."""
        mod = importlib.import_module("heartbeat.alerts")
        assert hasattr(mod, "AlertManager")

    def test_heartbeat_recovery_importable(self) -> None:
        """heartbeat.recovery can be imported."""
        mod = importlib.import_module("heartbeat.recovery")
        assert hasattr(mod, "RecoveryManager")


# ---------------------------------------------------------------------------
# Test 8: Gateway health endpoint (offline -- schema check)
# ---------------------------------------------------------------------------


class TestGatewayHealth:
    def test_gateway_health_schema(self) -> None:
        """HealthResponse schema has the expected fields."""
        from gateway.schemas import HealthResponse

        resp = HealthResponse()
        assert resp.status == "ok"
        assert resp.version == "0.1.0"
        assert resp.timestamp is not None

    def test_gateway_app_importable(self) -> None:
        """The FastAPI app can be imported (does not start the server)."""
        from gateway.main import app

        assert app.title == "NEXUS Gateway"

        # Verify /health route is registered
        routes = [r.path for r in app.routes]
        assert "/health" in routes, f"/health not found in routes: {routes}"

    def test_gateway_skills_route_registered(self) -> None:
        """The /api/skills route should be registered in the app."""
        from gateway.main import app

        routes = [r.path for r in app.routes]
        assert "/api/skills" in routes, f"/api/skills not found in routes: {routes}"


# ---------------------------------------------------------------------------
# Test 9: Org chart consistency
# ---------------------------------------------------------------------------


class TestOrgChartConsistency:
    def test_org_chart_matches_registry(
        self,
        org_yaml: dict[str, Any],
        all_agents: dict[str, dict[str, Any]],
    ) -> None:
        """Departments in org.yaml should have matching agents in registry.yaml."""
        # Build set of department IDs from org.yaml
        org_depts: dict[str, set[str]] = {}
        for dept in org_yaml.get("departments", []):
            dept_id = dept.get("id", "")
            positions = set(dept.get("positions", []))
            org_depts[dept_id] = positions

        # Build set of departments from registry
        registry_depts: dict[str, set[str]] = {}
        for agent_id, info in all_agents.items():
            if agent_id.startswith("dept-"):
                continue  # Skip legacy dept-gateway agents
            dept = info.get("department", "unknown")
            role = info.get("role", agent_id)
            registry_depts.setdefault(dept, set()).add(role)
            # Also add agent_id itself
            registry_depts[dept].add(agent_id)

        # Every org.yaml department should exist with at least one matching agent
        for dept_id, positions in org_depts.items():
            registry_roles = registry_depts.get(dept_id, set())
            overlap = positions & registry_roles
            assert overlap, (
                f"Department '{dept_id}' in org.yaml has positions {positions} "
                f"but no matching roles in registry (found {registry_roles})"
            )

    def test_chain_of_command_in_org_yaml(
        self, org_yaml: dict[str, Any]
    ) -> None:
        """chain_of_command entries should reference valid positions."""
        chain = org_yaml.get("chain_of_command", {})
        all_positions = set(chain.keys()) | {"board"}
        for pos, info in chain.items():
            reports_to = info.get("reports_to")
            assert reports_to in all_positions, (
                f"'{pos}' reports_to '{reports_to}' not in chain_of_command keys"
            )
            for sub in info.get("can_command", []):
                assert sub in all_positions, (
                    f"'{pos}' can_command '{sub}' not in chain_of_command keys"
                )


# ---------------------------------------------------------------------------
# Test 10: Race (model) configs valid
# ---------------------------------------------------------------------------


class TestRaceConfigs:
    # Known valid model ID prefixes / patterns
    VALID_MODEL_PREFIXES: list[str] = [
        "claude-",
        "gpt-",
        "o1",
        "o3",
        "o4",
        "gemini-",
        "llama",
        "mixtral",
        "deepseek",
        "qwen",
        "codestral",
    ]

    def test_race_configs_valid(self, project_root: Path) -> None:
        """All race.yaml files should have a valid 'model' field."""
        agents_dir = project_root / "company" / "agents"
        race_files = list(agents_dir.glob("*/race.yaml"))
        assert len(race_files) > 0, "No race.yaml files found"

        errors: list[str] = []
        for race_path in race_files:
            with open(race_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data is None:
                errors.append(f"{race_path.parent.name}: empty file")
                continue

            model = data.get("model")
            if not model:
                errors.append(f"{race_path.parent.name}: missing 'model' field")
                continue

            if not isinstance(model, str):
                errors.append(f"{race_path.parent.name}: 'model' is not a string")
                continue

            # Check model is a known pattern
            model_lower = model.lower()
            if not any(model_lower.startswith(p) for p in self.VALID_MODEL_PREFIXES):
                errors.append(
                    f"{race_path.parent.name}: unknown model '{model}'"
                )

        assert not errors, (
            "Invalid race.yaml configs:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    def test_race_configs_have_provider(self, project_root: Path) -> None:
        """Every race.yaml should specify a provider."""
        agents_dir = project_root / "company" / "agents"
        race_files = list(agents_dir.glob("*/race.yaml"))

        missing: list[str] = []
        for race_path in race_files:
            with open(race_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if "provider" not in data:
                missing.append(race_path.parent.name)

        assert not missing, f"race.yaml without 'provider': {missing}"


# ---------------------------------------------------------------------------
# Test 11: AgentRouter full lifecycle
# ---------------------------------------------------------------------------


class TestAgentRouterLifecycle:
    def test_router_loads_correct_count(
        self, all_agents: dict[str, dict[str, Any]]
    ) -> None:
        """AgentRouter should load the same number of agents as the registry."""
        from gateway.agent_router import AgentRouter

        router = AgentRouter()
        assert len(router.agents) == len(all_agents)

    def test_router_get_active_agents(self) -> None:
        """get_active_agents returns only active ones."""
        from gateway.agent_router import AgentRouter

        router = AgentRouter()
        active = router.get_active_agents()
        for _aid, info in active.items():
            assert info["status"] == "active"

    def test_route_to_department_direct(self) -> None:
        """route_to_department bypasses task-type inference."""
        from gateway.agent_router import AgentRouter

        router = AgentRouter()
        agent = router.route_to_department("qa")
        assert agent is not None
        assert router.agents[agent]["department"] == "qa"

    def test_route_with_all_excluded_returns_none(self) -> None:
        """If every candidate is excluded, route returns None."""
        from gateway.agent_router import AgentRouter

        router = AgentRouter()
        all_ids = set(router.agents.keys())
        agent = router.route("code", exclude=all_ids)
        assert agent is None


# ---------------------------------------------------------------------------
# Test 12: Cross-module import smoke test
# ---------------------------------------------------------------------------


class TestCrossModuleImports:
    @pytest.mark.parametrize(
        "module_path",
        [
            "gateway.main",
            "gateway.schemas",
            "gateway.config",
            "gateway.agent_router",
            "gateway.skill_registry",
            "equipment",
            "heartbeat",
        ],
    )
    def test_module_importable(self, module_path: str) -> None:
        """Core modules should be importable without errors."""
        mod = importlib.import_module(module_path)
        assert mod is not None
