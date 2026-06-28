"""Configuration models and loader for VibeBench Arena."""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from vibebench.paths import config_file

DEFAULT_CONFIG: dict[str, Any] = {
    "project": {
        "name": "vibebench-project",
    },
    "checks": {
        "test": ["pytest -q"],
        "lint": ["ruff check ."],
    },
    "risk_rules": {
        "forbidden_paths": [".env", ".env.*", "secrets/"],
        "warn_if_tests_deleted": True,
        "warn_if_lockfiles_changed": True,
        "large_patch_lines": 500,
    },
    "gate": {
        "min_score": 80,
        "max_risk": "medium",
        "allow_findings": 0,
        "require_status_passed": True,
    },
}


class ConfigError(Exception):
    """User-readable configuration error."""


class ProjectConfig(BaseModel):
    """Project metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)


class ChecksConfig(BaseModel):
    """Commands VibeBench runs during checks."""

    model_config = ConfigDict(extra="forbid")

    test: list[str] = Field(default_factory=list)
    lint: list[str] = Field(default_factory=list)


class RiskRulesConfig(BaseModel):
    """Risk rules for future code-change checks."""

    model_config = ConfigDict(extra="forbid")

    forbidden_paths: list[str] = Field(default_factory=list)
    warn_if_tests_deleted: bool = True
    warn_if_lockfiles_changed: bool = True
    large_patch_lines: int = Field(default=500, gt=0)


class GateConfig(BaseModel):
    """Quality gate policy defaults."""

    model_config = ConfigDict(extra="forbid")

    min_score: int = Field(default=80, ge=0, le=100)
    max_risk: Literal["low", "medium", "high", "critical"] = "medium"
    allow_findings: int = Field(default=0, ge=0)
    require_status_passed: bool = True


class VibeBenchConfig(BaseModel):
    """Top-level VibeBench configuration."""

    model_config = ConfigDict(extra="forbid")

    project: ProjectConfig
    checks: ChecksConfig
    risk_rules: RiskRulesConfig
    gate: GateConfig = Field(default_factory=GateConfig)


def default_config_yaml() -> str:
    """Return the default project config as YAML."""
    return yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False)


def load_config(path: Path | None = None) -> VibeBenchConfig:
    """Load and validate a VibeBench config file."""
    config_path = path or config_file()

    if not config_path.exists():
        raise ConfigError(
            f"No VibeBench config found at {config_path}.\n"
            'Run "vibebench init" to create one.'
        )

    try:
        raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        message = f"Could not read YAML config at {config_path}: {exc}"
        raise ConfigError(message) from exc

    if raw_config is None:
        raw_config = {}

    try:
        return VibeBenchConfig.model_validate(raw_config)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ConfigError(
            f"VibeBench config at {config_path} is invalid.\n{details}"
        ) from exc
