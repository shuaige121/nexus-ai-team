"""
Equipment Manager - Manages automation scripts (equipment)
"""

import contextlib
import importlib.util
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from croniter import croniter

logger = logging.getLogger(__name__)


class EquipmentManager:
    """
    Manages deterministic automation scripts (equipment).
    Equipment are scripts that don't need LLM to complete repetitive tasks.
    """

    def __init__(self, registry_path: str | None = None) -> None:
        """
        Initialize Equipment Manager.

        Args:
            registry_path: Path to registry.yaml. Defaults to equipment/registry.yaml
        """
        self.base_dir: Path = Path(__file__).parent
        self.registry_path: Path = Path(registry_path) if registry_path else self.base_dir / "registry.yaml"
        self.scripts_dir: Path = self.base_dir / "scripts"
        self.registry: dict[str, dict[str, Any]] = {}
        self.scheduler: BackgroundScheduler = BackgroundScheduler()
        self.scheduler.start()
        self._load_registry()

    def _load_registry(self) -> None:
        """Load equipment registry from YAML file."""
        if not self.registry_path.exists():
            logger.warning(f"Registry file not found: {self.registry_path}")
            self.registry = {}
            return
        try:
            with open(self.registry_path, encoding="utf-8") as f:
                self.registry = yaml.safe_load(f) or {}
            logger.info(f"Loaded {len(self.registry)} equipment from registry")
        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            self.registry = {}

    def _save_registry(self) -> None:
        """Save equipment registry to YAML file."""
        try:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_path, "w", encoding="utf-8") as f:
                yaml.dump(self.registry, f)
            logger.info(f"Saved {len(self.registry)} equipment to registry")
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def register_equipment(
        self,
        name: str,
        script_path: str,
        description: str = "",
        schedule: str | None = None,
        enabled: bool = True,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Register a new equipment (script).

        Args:
            name: Unique equipment name
            script_path: Path to the Python script (relative to scripts/)
            description: Equipment description
            schedule: Cron expression for scheduling (optional)
            enabled: Whether equipment is enabled
            params: Default parameters for the equipment

        Returns:
            Equipment configuration
        """
        entry: dict[str, Any] = {
            "name": name,
            "script_path": script_path,
            "description": description,
            "schedule": schedule,
            "enabled": enabled,
            "params": params or {},
            "last_run": None,
            "run_count": 0,
            "last_status": None,
            "registered_at": datetime.now().isoformat(),
        }
        self.registry[name] = entry
        self._save_registry()

        if schedule and enabled:
            self._schedule_equipment(name, schedule)

        logger.info(f"Registered equipment: {name}")
        return entry

    def unregister_equipment(self, name: str) -> bool:
        """
        Unregister an equipment.

        Args:
            name: Equipment name

        Returns:
            True if unregistered, False if not found
        """
        if name not in self.registry:
            return False
        del self.registry[name]
        with contextlib.suppress(Exception):
            self.scheduler.remove_job(f"equipment_{name}")
        self._save_registry()
        logger.info(f"Unregistered equipment: {name}")
        return True

    def run_equipment(self, name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Execute an equipment script.

        Args:
            name: Equipment name
            params: Runtime parameters (override default params)

        Returns:
            Execution result with status, output, and error
        """
        if name not in self.registry:
            return {"status": "error", "error": f"Equipment not found: {name}"}

        equipment = self.registry[name]
        if not equipment.get("enabled"):
            return {"status": "skipped", "error": "Equipment is disabled"}

        script_file = self.scripts_dir / equipment["script_path"]
        if not script_file.exists():
            return {"status": "error", "error": f"Script not found: {script_file}"}

        # Merge default params with runtime params
        run_params = {**(equipment.get("params") or {}), **(params or {})}

        try:
            spec = importlib.util.spec_from_file_location(name, script_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if not hasattr(module, "main"):
                return {"status": "error", "error": "Script must have a main() function"}

            output = module.main(**run_params) if run_params else module.main()

            equipment["last_run"] = datetime.now().isoformat()
            equipment["run_count"] = equipment.get("run_count", 0) + 1
            equipment["last_status"] = "success"
            self._save_registry()

            logger.info(f"Successfully executed equipment: {name}")
            return {"status": "success", "output": output}

        except Exception as e:
            equipment["last_run"] = datetime.now().isoformat()
            equipment["last_status"] = "error"
            self._save_registry()
            logger.error(f"Failed to execute equipment {name}: {e}")
            return {"status": "error", "error": str(e)}

    def _schedule_equipment(self, name: str, cron_expr: str) -> None:
        """
        Schedule equipment with cron expression.

        Args:
            name: Equipment name
            cron_expr: Cron expression (e.g., "0 0 * * *" for daily at midnight)
        """
        try:
            croniter(cron_expr)  # validate
            trigger = CronTrigger.from_crontab(cron_expr)
            self.scheduler.add_job(
                self.run_equipment,
                trigger,
                args=[name],
                id=f"equipment_{name}",
                replace_existing=True,
            )
            logger.info(f"Scheduled equipment {name} with cron: {cron_expr}")
        except Exception as e:
            logger.error(f"Failed to schedule equipment {name}: {e}")

    def schedule_equipment(self, name: str, cron_expr: str) -> bool:
        """
        Schedule or update schedule for an equipment.

        Args:
            name: Equipment name
            cron_expr: Cron expression

        Returns:
            True if scheduled, False if equipment not found
        """
        if name not in self.registry:
            return False
        self.registry[name]["schedule"] = cron_expr
        self.registry[name]["enabled"] = True
        self._save_registry()
        self._schedule_equipment(name, cron_expr)
        return True

    def list_equipment(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        """
        List all registered equipment.

        Args:
            enabled_only: Only return enabled equipment

        Returns:
            List of equipment configurations
        """
        if enabled_only:
            return [eq for eq in self.registry.values() if eq.get("enabled")]
        return list(self.registry.values())

    def get_equipment(self, name: str) -> dict[str, Any] | None:
        """
        Get equipment configuration by name.

        Args:
            name: Equipment name

        Returns:
            Equipment configuration or None if not found
        """
        return self.registry.get(name)

    def enable_equipment(self, name: str) -> bool:
        """
        Enable an equipment.

        Args:
            name: Equipment name

        Returns:
            True if enabled, False if not found
        """
        if name not in self.registry:
            return False
        self.registry[name]["enabled"] = True
        self._save_registry()
        if self.registry[name].get("schedule"):
            self._schedule_equipment(name, self.registry[name]["schedule"])
        logger.info(f"Enabled equipment: {name}")
        return True

    def disable_equipment(self, name: str) -> bool:
        """
        Disable an equipment.

        Args:
            name: Equipment name

        Returns:
            True if disabled, False if not found
        """
        if name not in self.registry:
            return False
        self.registry[name]["enabled"] = False
        self._save_registry()
        with contextlib.suppress(Exception):
            self.scheduler.remove_job(f"equipment_{name}")
        logger.info(f"Disabled equipment: {name}")
        return True

    def get_scheduled_jobs(self) -> list[dict[str, Any]]:
        """
        Get all scheduled equipment jobs.

        Returns:
            List of scheduled jobs with details
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return jobs

    def shutdown(self) -> None:
        """Shutdown the scheduler."""
        self.scheduler.shutdown()
        logger.info("Equipment manager shutdown")
