"""
Equipment Manager - Manages automation scripts (equipment)
"""

import os
import sys
import yaml
import importlib.util
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from croniter import croniter
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class EquipmentManager:
    """
    Manages deterministic automation scripts (equipment).
    Equipment are scripts that don't need LLM to complete repetitive tasks.
    """

    def __init__(self, registry_path: Optional[str] = None):
        """
        Initialize Equipment Manager.

        Args:
            registry_path: Path to registry.yaml. Defaults to equipment/registry.yaml
        """
        self.base_dir = Path(__file__).parent
        self.registry_path = registry_path or self.base_dir / "registry.yaml"
        self.scripts_dir = self.base_dir / "scripts"
        self.registry: Dict[str, Dict[str, Any]] = {}
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

        # Load registry
        self._load_registry()

    def _load_registry(self):
        """Load equipment registry from YAML file."""
        if not self.registry_path.exists():
            logger.warning(f"Registry file not found: {self.registry_path}")
            self.registry = {}
            return

        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                self.registry = yaml.safe_load(f) or {}
            logger.info(f"Loaded {len(self.registry)} equipment from registry")
        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            self.registry = {}

    def _save_registry(self):
        """Save equipment registry to YAML file."""
        try:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.registry, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"Saved {len(self.registry)} equipment to registry")
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def register_equipment(
        self,
        name: str,
        script_path: str,
        description: str = "",
        schedule: Optional[str] = None,
        enabled: bool = True,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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
        equipment_config = {
            "name": name,
            "script_path": script_path,
            "description": description,
            "schedule": schedule,
            "enabled": enabled,
            "params": params or {},
            "registered_at": datetime.now().isoformat(),
            "last_run": None,
            "run_count": 0,
            "last_status": None
        }

        self.registry[name] = equipment_config
        self._save_registry()

        # Schedule if cron expression provided
        if schedule and enabled:
            self._schedule_equipment(name, schedule)

        logger.info(f"Registered equipment: {name}")
        return equipment_config

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

        # Remove from scheduler
        self.scheduler.remove_job(f"equipment_{name}", jobstore=None)

        # Remove from registry
        del self.registry[name]
        self._save_registry()

        logger.info(f"Unregistered equipment: {name}")
        return True

    def run_equipment(self, name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute an equipment script.

        Args:
            name: Equipment name
            params: Runtime parameters (override default params)

        Returns:
            Execution result with status, output, and error
        """
        if name not in self.registry:
            return {
                "status": "error",
                "error": f"Equipment not found: {name}",
                "output": None
            }

        equipment = self.registry[name]

        if not equipment["enabled"]:
            return {
                "status": "skipped",
                "error": "Equipment is disabled",
                "output": None
            }

        script_path = self.scripts_dir / equipment["script_path"]

        if not script_path.exists():
            return {
                "status": "error",
                "error": f"Script not found: {script_path}",
                "output": None
            }

        # Merge default params with runtime params
        merged_params = {**equipment["params"], **(params or {})}

        try:
            # Load and execute the script
            spec = importlib.util.spec_from_file_location(name, script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Execute the main() function
            if not hasattr(module, 'main'):
                return {
                    "status": "error",
                    "error": "Script must have a main() function",
                    "output": None
                }

            output = module.main(**merged_params)

            # Update registry
            self.registry[name]["last_run"] = datetime.now().isoformat()
            self.registry[name]["run_count"] += 1
            self.registry[name]["last_status"] = "success"
            self._save_registry()

            logger.info(f"Successfully executed equipment: {name}")

            return {
                "status": "success",
                "output": output,
                "error": None
            }

        except Exception as e:
            logger.error(f"Failed to execute equipment {name}: {e}")

            # Update registry
            self.registry[name]["last_run"] = datetime.now().isoformat()
            self.registry[name]["run_count"] += 1
            self.registry[name]["last_status"] = "error"
            self._save_registry()

            return {
                "status": "error",
                "error": str(e),
                "output": None
            }

    def _schedule_equipment(self, name: str, cron_expr: str):
        """
        Schedule equipment with cron expression.

        Args:
            name: Equipment name
            cron_expr: Cron expression (e.g., "0 0 * * *" for daily at midnight)
        """
        try:
            # Validate cron expression
            croniter(cron_expr)

            # Add job to scheduler
            trigger = CronTrigger.from_crontab(cron_expr)
            self.scheduler.add_job(
                func=lambda: self.run_equipment(name),
                trigger=trigger,
                id=f"equipment_{name}",
                replace_existing=True,
                name=f"Equipment: {name}"
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
        self._save_registry()

        if self.registry[name]["enabled"]:
            self._schedule_equipment(name, cron_expr)

        return True

    def list_equipment(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        List all registered equipment.

        Args:
            enabled_only: Only return enabled equipment

        Returns:
            List of equipment configurations
        """
        equipment_list = list(self.registry.values())

        if enabled_only:
            equipment_list = [e for e in equipment_list if e["enabled"]]

        return equipment_list

    def get_equipment(self, name: str) -> Optional[Dict[str, Any]]:
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

        # Schedule if has cron expression
        if self.registry[name]["schedule"]:
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

        # Remove from scheduler
        try:
            self.scheduler.remove_job(f"equipment_{name}")
        except:
            pass

        logger.info(f"Disabled equipment: {name}")
        return True

    def get_scheduled_jobs(self) -> List[Dict[str, Any]]:
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
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        return jobs

    def shutdown(self):
        """Shutdown the scheduler."""
        self.scheduler.shutdown()
        logger.info("Equipment manager shutdown")
