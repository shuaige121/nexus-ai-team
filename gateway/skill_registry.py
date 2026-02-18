"""Skill Registry — Loads installed skills and exposes them to the gateway.

On startup the gateway loads ``~/.nexus/skills/registry.json`` (if it exists)
and builds an in-memory catalogue.  The ``/api/skills`` endpoint then returns
the list of available skills together with their metadata.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SKILL_REGISTRY_PATH: Path = Path.home() / ".nexus" / "skills" / "registry.json"
DEFAULT_SKILL_DIR: Path = Path.home() / ".nexus" / "skills"


class SkillRegistry:
    """In-memory catalogue of installed Nexus skills."""

    def __init__(self, registry_path: str | Path | None = None) -> None:
        self.registry_path: Path = Path(registry_path) if registry_path else DEFAULT_SKILL_REGISTRY_PATH
        self.skills: dict[str, dict[str, Any]] = {}
        self._load()

    # ── Loading ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Read the JSON registry from disk."""
        if not self.registry_path.exists():
            logger.info("No skill registry found at %s — starting empty", self.registry_path)
            return

        try:
            with open(self.registry_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            logger.exception("Failed to load skill registry from %s", self.registry_path)
            return

        if isinstance(data, dict):
            # Expect {"skills": {...}} or flat dict
            self.skills = data.get("skills", data) if "skills" in data else data
        elif isinstance(data, list):
            self.skills = {s["name"]: s for s in data if isinstance(s, dict) and "name" in s}
        else:
            logger.warning("Unexpected skill registry format — ignoring")
            return

        logger.info("SkillRegistry loaded %d skill(s)", len(self.skills))

    def reload(self) -> None:
        """Re-read from disk."""
        self.skills.clear()
        self._load()

    # ── Queries ───────────────────────────────────────────────────────────

    def list_skills(self) -> list[dict[str, Any]]:
        """Return all skills as a list of dicts (safe for JSON serialisation)."""
        result: list[dict[str, Any]] = []
        for name, meta in self.skills.items():
            entry: dict[str, Any] = {"name": name}
            if isinstance(meta, dict):
                entry.update(meta)
            result.append(entry)
        return result

    def get_skill(self, name: str) -> dict[str, Any] | None:
        """Look up a single skill by name."""
        return self.skills.get(name)

    def has_skill(self, name: str) -> bool:
        return name in self.skills

    def skill_dir_exists(self, name: str) -> bool:
        """Check whether the skill's directory is actually present on disk."""
        skill_dir = DEFAULT_SKILL_DIR / name
        return skill_dir.is_dir()

    # ── Capabilities ──────────────────────────────────────────────────────

    def get_capabilities(self) -> dict[str, list[str]]:
        """Build a capability -> [skill_name, ...] map.

        Each skill entry may optionally contain a ``capabilities`` list.
        """
        cap_map: dict[str, list[str]] = {}
        for name, meta in self.skills.items():
            if not isinstance(meta, dict):
                continue
            for cap in meta.get("capabilities", []):
                cap_map.setdefault(cap, []).append(name)
        return cap_map

    # ── Persistence ───────────────────────────────────────────────────────

    def save(self) -> None:
        """Write the current skill catalogue back to disk."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump({"skills": self.skills}, f, indent=2, ensure_ascii=False)
        logger.info("SkillRegistry saved %d skill(s) to %s", len(self.skills), self.registry_path)

    def install(self, name: str, metadata: dict[str, Any] | None = None) -> None:
        """Register a new skill (does NOT download/install files)."""
        self.skills[name] = metadata or {"name": name}
        self.save()
        logger.info("Skill installed: %s", name)

    def uninstall(self, name: str) -> bool:
        """Remove a skill from the registry."""
        if name not in self.skills:
            return False
        del self.skills[name]
        self.save()
        logger.info("Skill uninstalled: %s", name)
        return True
