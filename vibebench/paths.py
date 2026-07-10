"""Shared filesystem paths for VibeBench projects."""

import os
from pathlib import Path

CONFIG_DIR_NAME = ".vibebench"
CONFIG_FILE_NAME = "config.yaml"


def config_dir(project_root: Path | None = None) -> Path:
    """Return the VibeBench config directory for a project root."""
    root = project_root or Path.cwd()
    return root / CONFIG_DIR_NAME


def config_file(project_root: Path | None = None) -> Path:
    """Return the VibeBench config file path for a project root."""
    override = os.environ.get("VIBEBENCH_CONFIG_PATH")
    if override:
        return Path(override)
    return config_dir(project_root) / CONFIG_FILE_NAME
