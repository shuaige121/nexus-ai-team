#!/usr/bin/env python3
"""Nexus Skill Manager - Install, manage, and onboard skills from GitHub."""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


NEXUS_HOME = Path.home() / ".nexus"
SKILLS_DIR = NEXUS_HOME / "skills"
REGISTRY_FILE = SKILLS_DIR / "registry.json"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / "agents"
AGENTS_REGISTRY = AGENTS_DIR / "registry.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    if yaml:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return _parse_yaml_minimal(path)


def _parse_yaml_minimal(path: Path) -> dict[str, Any]:
    """Bare-bones YAML parser for manifest files when PyYAML is unavailable."""
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    with open(path) as f:
        for raw_line in f:
            line = raw_line.rstrip()
            stripped = line.lstrip()

            if not stripped or stripped.startswith("#"):
                continue

            if stripped.startswith("- "):
                value = stripped[2:].strip().strip('"').strip("'")
                if current_list is not None:
                    current_list.append(value)
                continue

            if ":" in stripped:
                if current_key and current_list is not None:
                    result[current_key] = current_list

                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")

                if val:
                    result[key] = val
                    current_key = None
                    current_list = None
                else:
                    current_key = key
                    current_list = []

    if current_key and current_list is not None:
        result[current_key] = current_list

    return result


def _load_registry() -> dict[str, Any]:
    if not REGISTRY_FILE.exists():
        return {"skills": {}}
    with open(REGISTRY_FILE) as f:
        return json.load(f)


def _save_registry(registry: dict[str, Any]) -> None:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def _load_agents_registry() -> dict[str, Any]:
    if not AGENTS_REGISTRY.exists():
        return {}
    return _load_yaml(AGENTS_REGISTRY)


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _resolve_skill_name(url: str) -> str:
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def _get_agents_for_departments(departments: list[str]) -> list[str]:
    agents_data = _load_agents_registry()
    agents = agents_data.get("agents", {})
    matched: list[str] = []
    for agent_id, info in agents.items():
        if isinstance(info, dict) and info.get("department") in departments:
            matched.append(agent_id)
    return sorted(matched)


def _get_agents_by_role(role_names: list[str]) -> list[str]:
    agents_data = _load_agents_registry()
    agents = agents_data.get("agents", {})
    matched: list[str] = []
    for agent_id, info in agents.items():
        if isinstance(info, dict) and info.get("role") in role_names:
            matched.append(agent_id)
    return sorted(matched)


def _update_agent_tools(agent_id: str, skill_name: str, capabilities: list[str], skill_type: str) -> bool:
    """Append skill tools to an agent's TOOL.md. Creates dir/file if needed."""
    agent_dir = AGENTS_DIR / agent_id
    if not agent_dir.exists():
        agent_dir.mkdir(parents=True, exist_ok=True)

    tool_md = agent_dir / "TOOL.md"
    if not tool_md.exists():
        header = "# " + agent_id + " - Available Tools\n"
        tool_md.write_text(header)

    content = tool_md.read_text()
    marker = "<!-- skill:" + skill_name + " -->"
    if marker in content:
        return True

    section_lines = [
        "",
        "",
        marker,
        "## Skill: " + skill_name + " (" + skill_type + ")",
    ]
    for cap in capabilities:
        section_lines.append("- `" + cap + "` — via " + skill_name + " skill")
    section_lines.append("<!-- /skill:" + skill_name + " -->")

    tool_md.write_text(content + "\n".join(section_lines))
    return True


def _remove_skill_from_tool_md(agent_id: str, skill_name: str) -> bool:
    tool_md = AGENTS_DIR / agent_id / "TOOL.md"
    if not tool_md.exists():
        return False

    content = tool_md.read_text()
    start_marker = "<!-- skill:" + skill_name + " -->"
    end_marker = "<!-- /skill:" + skill_name + " -->"

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    if start_idx == -1 or end_idx == -1:
        return False

    before = content[:start_idx].rstrip("\n")
    after = content[end_idx + len(end_marker):]
    tool_md.write_text(before + after)
    return True


def _ensure_list(val: Any) -> list[str]:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [val]
    return []


def install_skill(url: str, force: bool = False) -> int:
    skill_name = _resolve_skill_name(url)
    skill_dir = SKILLS_DIR / skill_name
    registry = _load_registry()

    if skill_name in registry.get("skills", {}) and not force:
        print("[ERROR] Skill '" + skill_name + "' already installed. Use --force to reinstall.")
        return 1

    # Step 1: Clone
    print("[1/6] Cloning " + url + " ...")
    if skill_dir.exists():
        shutil.rmtree(skill_dir)

    if url.startswith("/") or url.startswith("./") or url.startswith("../"):
        shutil.copytree(url, skill_dir)
    else:
        result = _run(["git", "clone", "--depth=1", url, str(skill_dir)])
        if result.returncode != 0:
            print("[ERROR] git clone failed: " + result.stderr.strip())
            return 1

    # Step 2: Read manifest
    print("[2/6] Reading manifest.yaml ...")
    manifest_path = skill_dir / "manifest.yaml"
    if not manifest_path.exists():
        print("[ERROR] No manifest.yaml found in skill repository.")
        shutil.rmtree(skill_dir)
        return 1

    manifest = _load_yaml(manifest_path)
    required_keys = ["name", "version", "entry_point", "type"]
    missing = [k for k in required_keys if k not in manifest]
    if missing:
        print("[ERROR] manifest.yaml missing required keys: " + str(missing))
        shutil.rmtree(skill_dir)
        return 1

    desc = manifest.get("description", "no description")
    print("       " + manifest["name"] + " v" + manifest["version"] + " — " + desc)

    # Step 3: Install dependencies
    print("[3/6] Installing dependencies ...")
    runtime = manifest.get("runtime")
    if not runtime:
        install_block = manifest.get("install", {})
        if isinstance(install_block, dict):
            runtime = install_block.get("runtime")

    deps = manifest.get("dependencies")
    if deps is None:
        install_block = manifest.get("install", {})
        if isinstance(install_block, dict):
            deps = install_block.get("dependencies")

    deps = _ensure_list(deps) if deps else []

    if deps:
        if runtime == "python":
            result = _run([sys.executable, "-m", "pip", "install", "--quiet"] + deps)
            if result.returncode != 0:
                print("[WARN] pip install had issues: " + result.stderr.strip())
        elif runtime == "node":
            result = _run(["npm", "install", "--save"] + deps, cwd=skill_dir)
            if result.returncode != 0:
                print("[WARN] npm install had issues: " + result.stderr.strip())
    elif (skill_dir / "requirements.txt").exists():
        _run([sys.executable, "-m", "pip", "install", "--quiet", "-r", str(skill_dir / "requirements.txt")])
    elif (skill_dir / "package.json").exists():
        _run(["npm", "install"], cwd=skill_dir)
    else:
        print("       No dependencies to install.")

    # Step 4: Validate
    print("[4/6] Validating skill ...")
    entry = skill_dir / manifest["entry_point"]
    if not entry.exists():
        print("[ERROR] Entry point '" + manifest["entry_point"] + "' not found.")
        shutil.rmtree(skill_dir)
        return 1

    skill_type = manifest.get("type", "unknown")
    if skill_type == "mcp-server" and runtime == "python":
        result = _run([sys.executable, "-c", "import ast; ast.parse(open('" + str(entry) + "').read())"])
        if result.returncode != 0:
            print("[ERROR] Syntax error in " + str(entry) + ": " + result.stderr.strip())
            shutil.rmtree(skill_dir)
            return 1

    # Step 5: Register
    print("[5/6] Registering skill ...")
    capabilities = _ensure_list(manifest.get("capabilities", []))
    compatible_depts = _ensure_list(manifest.get("compatible_departments", []))
    auto_assign = _ensure_list(manifest.get("auto_assign_to", []))

    registry["skills"][skill_name] = {
        "name": manifest.get("name", skill_name),
        "version": manifest.get("version", "0.0.0"),
        "description": manifest.get("description", ""),
        "type": skill_type,
        "runtime": runtime,
        "entry_point": str(entry),
        "capabilities": capabilities,
        "compatible_departments": compatible_depts,
        "auto_assign_to": auto_assign,
        "install_path": str(skill_dir),
        "installed_at": _now_iso(),
    }
    _save_registry(registry)

    # Step 6: Update agent TOOL.md
    print("[6/6] Updating agent tool configurations ...")
    target_agents: list[str] = []
    if auto_assign:
        target_agents = _get_agents_by_role(auto_assign)
    if not target_agents and compatible_depts:
        target_agents = _get_agents_for_departments(compatible_depts)

    updated_agents: list[str] = []
    for agent_id in target_agents:
        if _update_agent_tools(agent_id, skill_name, capabilities, skill_type):
            updated_agents.append(agent_id)

    # Run onboard script
    onboard_script = PROJECT_ROOT / "tools" / "skill_onboard.sh"
    if onboard_script.exists():
        _run(["bash", str(onboard_script), skill_name, str(skill_dir), skill_type])

    print()
    print("Skill '" + manifest["name"] + "' installed successfully.")
    if updated_agents:
        print("Available to: " + str(updated_agents))
    else:
        print("Available to: [no agents auto-assigned]")

    return 0


def list_skills() -> int:
    registry = _load_registry()
    skills = registry.get("skills", {})

    if not skills:
        print("No skills installed.")
        print("Install one with: nexus-skill install <github-url>")
        return 0

    print("Installed skills (" + str(len(skills)) + "):\n")
    for name, info in skills.items():
        status = "OK"
        if not Path(info.get("install_path", "")).exists():
            status = "MISSING"
        caps = ", ".join(info.get("capabilities", [])[:3])
        print("  " + name + " v" + info.get("version", "?"))
        print("    Type: " + info.get("type", "?") + "  Runtime: " + str(info.get("runtime", "?")) + "  Status: " + status)
        print("    Capabilities: " + caps)
        print("    Departments: " + ", ".join(info.get("compatible_departments", [])))
        print()

    return 0


def remove_skill(skill_name: str) -> int:
    registry = _load_registry()
    skills = registry.get("skills", {})

    if skill_name not in skills:
        print("[ERROR] Skill '" + skill_name + "' is not installed.")
        return 1

    info = skills[skill_name]

    auto_assign = _ensure_list(info.get("auto_assign_to", []))
    compatible_depts = _ensure_list(info.get("compatible_departments", []))
    target_agents = _get_agents_by_role(auto_assign) if auto_assign else []
    if not target_agents and compatible_depts:
        target_agents = _get_agents_for_departments(compatible_depts)

    for agent_id in target_agents:
        _remove_skill_from_tool_md(agent_id, skill_name)

    install_path = Path(info.get("install_path", ""))
    if install_path.exists():
        shutil.rmtree(install_path)
        print("Removed " + str(install_path))

    del skills[skill_name]
    _save_registry(registry)

    print("Skill '" + skill_name + "' removed successfully.")
    return 0


def update_skill(skill_name: str) -> int:
    registry = _load_registry()
    skills = registry.get("skills", {})

    if skill_name not in skills:
        print("[ERROR] Skill '" + skill_name + "' is not installed.")
        return 1

    info = skills[skill_name]
    install_path = Path(info.get("install_path", ""))

    if not install_path.exists():
        print("[ERROR] Skill directory missing: " + str(install_path))
        return 1

    git_dir = install_path / ".git"
    if not git_dir.exists():
        print("[ERROR] Skill '" + skill_name + "' was not installed from git. Remove and reinstall.")
        return 1

    print("Updating " + skill_name + " ...")
    result = _run(["git", "pull", "--ff-only"], cwd=install_path)
    if result.returncode != 0:
        print("[ERROR] git pull failed: " + result.stderr.strip())
        return 1

    manifest_path = install_path / "manifest.yaml"
    if manifest_path.exists():
        manifest = _load_yaml(manifest_path)
        info["version"] = manifest.get("version", info.get("version"))
        info["capabilities"] = _ensure_list(manifest.get("capabilities", info.get("capabilities", [])))
        _save_registry(registry)

    print("Skill '" + skill_name + "' updated to v" + str(info.get("version", "?")) + ".")
    return 0


def validate_skill(skill_name: str) -> int:
    registry = _load_registry()
    skills = registry.get("skills", {})

    if skill_name not in skills:
        print("[ERROR] Skill '" + skill_name + "' is not installed.")
        return 1

    info = skills[skill_name]
    errors: list[str] = []
    warnings: list[str] = []

    install_path = Path(info.get("install_path", ""))
    if not install_path.exists():
        errors.append("Install directory missing: " + str(install_path))
    else:
        manifest_path = install_path / "manifest.yaml"
        if not manifest_path.exists():
            errors.append("manifest.yaml missing")
        else:
            manifest = _load_yaml(manifest_path)
            for key in ["name", "version", "entry_point", "type"]:
                if key not in manifest:
                    errors.append("manifest.yaml missing required key: " + key)

        entry_point = info.get("entry_point", "")
        if entry_point and not Path(entry_point).exists():
            errors.append("Entry point missing: " + entry_point)

    if not info.get("capabilities"):
        warnings.append("No capabilities defined")

    if not info.get("compatible_departments") and not info.get("auto_assign_to"):
        warnings.append("No department or agent assignment configured")

    print("Validation report for '" + skill_name + "':")
    print("  Version: " + str(info.get("version", "?")))
    print("  Type: " + str(info.get("type", "?")))
    print("  Path: " + str(info.get("install_path", "?")))
    print()

    if errors:
        print("  ERRORS (" + str(len(errors)) + "):")
        for e in errors:
            print("    [x] " + e)
    if warnings:
        print("  WARNINGS (" + str(len(warnings)) + "):")
        for w in warnings:
            print("    [!] " + w)
    if not errors and not warnings:
        print("  Status: VALID")

    return 1 if errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="nexus-skill",
        description="Nexus Skill Manager — install, manage, and onboard skills",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    p_install = sub.add_parser("install", help="Install a skill from GitHub URL or local path")
    p_install.add_argument("url", help="GitHub URL or local path to skill")
    p_install.add_argument("--force", action="store_true", help="Force reinstall")

    sub.add_parser("list", help="List all installed skills")

    p_remove = sub.add_parser("remove", help="Remove an installed skill")
    p_remove.add_argument("skill_name", help="Name of the skill to remove")

    p_update = sub.add_parser("update", help="Update a skill from its git remote")
    p_update.add_argument("skill_name", help="Name of the skill to update")

    p_validate = sub.add_parser("validate", help="Validate a skill configuration")
    p_validate.add_argument("skill_name", help="Name of the skill to validate")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    if args.command == "install":
        sys.exit(install_skill(args.url, force=args.force))
    elif args.command == "list":
        sys.exit(list_skills())
    elif args.command == "remove":
        sys.exit(remove_skill(args.skill_name))
    elif args.command == "update":
        sys.exit(update_skill(args.skill_name))
    elif args.command == "validate":
        sys.exit(validate_skill(args.skill_name))


if __name__ == "__main__":
    main()
