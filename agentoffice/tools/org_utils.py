"""Shared utilities for reading and writing org.yaml."""

from pathlib import Path

import yaml

from agentoffice.config import ORG_YAML_PATH


def load_org(path: Path | None = None) -> dict:
    """Load org.yaml and return as dict."""
    p = path or ORG_YAML_PATH
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_org(data: dict, path: Path | None = None) -> None:
    """Write dict back to org.yaml."""
    p = path or ORG_YAML_PATH
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
