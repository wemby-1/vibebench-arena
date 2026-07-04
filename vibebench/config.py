"""Configuration models and loader for VibeBench Arena."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError

from vibebench.paths import config_file

DEFAULT_RISK_FORBIDDEN_PATHS = [".env", ".env.*", "secrets/"]
DEFAULT_SECRET_LIKE_PATHS = [
    "*secret*",
    "*token*",
    "*credential*",
    "*credentials*",
    "*private_key*",
    "*api_key*",
    "*apikey*",
    "*password*",
    "*passwd*",
]
DEFAULT_LOCKFILES = [
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "requirements.lock",
]
DEFAULT_TEST_PATH_PATTERNS = [
    "tests/",
    "test_*.py",
    "*_test.py",
    "__tests__/",
    "*.test.ts",
    "*.test.tsx",
    "*.spec.ts",
    "*.spec.tsx",
]


DEFAULT_CONFIG: dict[str, Any] = {
    "project": {
        "name": "vibebench-project",
    },
    "checks": {
        "test": ["pytest -q"],
        "lint": ["ruff check ."],
    },
    "risk_rules": {
        "forbidden_paths": DEFAULT_RISK_FORBIDDEN_PATHS,
        "warn_if_tests_deleted": True,
        "warn_if_lockfiles_changed": True,
        "large_patch_lines": 500,
    },
    "risk": {
        "max_changed_files": 20,
        "max_patch_lines": 500,
        "forbidden_paths": DEFAULT_RISK_FORBIDDEN_PATHS,
        "secret_like_paths": DEFAULT_SECRET_LIKE_PATHS,
        "lockfiles": DEFAULT_LOCKFILES,
        "test_path_patterns": DEFAULT_TEST_PATH_PATTERNS,
    },
    "gate": {
        "min_score": 80,
        "max_risk": "medium",
        "allow_findings": 0,
        "require_status_passed": True,
    },
    "compare": {
        "fail_on_regression": False,
    },
}


class ConfigError(Exception):
    """User-readable configuration error."""


@dataclass(frozen=True)
class EffectiveConfigResult:
    """Loaded effective config and source metadata."""

    config: "VibeBenchConfig"
    sources: dict[str, str]
    config_path: Path
    config_exists: bool


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
    """Legacy risk rules kept for backward compatibility."""

    model_config = ConfigDict(extra="forbid")

    forbidden_paths: list[StrictStr] = Field(
        default_factory=lambda: DEFAULT_RISK_FORBIDDEN_PATHS.copy()
    )
    warn_if_tests_deleted: bool = True
    warn_if_lockfiles_changed: bool = True
    large_patch_lines: int = Field(default=500, gt=0)


class RiskConfig(BaseModel):
    """Configurable Git diff risk detection policy."""

    model_config = ConfigDict(extra="forbid")

    max_changed_files: int = Field(default=20, ge=1)
    max_patch_lines: int = Field(default=500, ge=1)
    forbidden_paths: list[StrictStr] = Field(
        default_factory=lambda: DEFAULT_RISK_FORBIDDEN_PATHS.copy()
    )
    secret_like_paths: list[StrictStr] = Field(
        default_factory=lambda: DEFAULT_SECRET_LIKE_PATHS.copy()
    )
    lockfiles: list[StrictStr] = Field(default_factory=lambda: DEFAULT_LOCKFILES.copy())
    test_path_patterns: list[StrictStr] = Field(
        default_factory=lambda: DEFAULT_TEST_PATH_PATTERNS.copy()
    )


class GateConfig(BaseModel):
    """Quality gate policy defaults."""

    model_config = ConfigDict(extra="forbid")

    min_score: int = Field(default=80, ge=0, le=100)
    max_risk: Literal["low", "medium", "high", "critical"] = "medium"
    allow_findings: int = Field(default=0, ge=0)
    require_status_passed: bool = True


class CompareConfig(BaseModel):
    """Compare artifact policy defaults."""

    model_config = ConfigDict(extra="forbid")

    fail_on_regression: bool = False


class VibeBenchConfig(BaseModel):
    """Top-level VibeBench configuration."""

    model_config = ConfigDict(extra="forbid")

    project: ProjectConfig
    checks: ChecksConfig
    risk_rules: RiskRulesConfig = Field(default_factory=RiskRulesConfig)
    risk: RiskConfig | None = None
    gate: GateConfig = Field(default_factory=GateConfig)
    compare: CompareConfig = Field(default_factory=CompareConfig)

    def effective_risk(self) -> RiskConfig:
        """Return the active Git diff risk policy."""
        if self.risk is not None:
            return self.risk
        return RiskConfig(
            max_patch_lines=self.risk_rules.large_patch_lines,
            forbidden_paths=self.risk_rules.forbidden_paths,
        )


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


def default_config_model() -> VibeBenchConfig:
    """Return the built-in default config as a validated model."""
    return VibeBenchConfig.model_validate(DEFAULT_CONFIG)


def load_effective_config(path: Path | None = None) -> EffectiveConfigResult:
    """Load config if present, otherwise return built-in defaults with sources."""
    config_path = path or config_file()
    if not config_path.exists():
        return EffectiveConfigResult(
            config=default_config_model(),
            sources={
                "project": "built-in defaults",
                "checks": "built-in defaults",
                "gate": "built-in defaults",
                "risk": "built-in defaults",
                "compare": "built-in defaults",
            },
            config_path=config_path,
            config_exists=False,
        )

    config = load_config(config_path)
    raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw_config, dict):
        raw_config = {}
    sources = {
        "project": "config file" if "project" in raw_config else "built-in defaults",
        "checks": "config file" if "checks" in raw_config else "built-in defaults",
        "gate": "config file" if "gate" in raw_config else "built-in defaults",
        "risk": "config file" if "risk" in raw_config else "built-in defaults",
        "compare": "config file" if "compare" in raw_config else "built-in defaults",
    }
    return EffectiveConfigResult(
        config=config,
        sources=sources,
        config_path=config_path,
        config_exists=True,
    )


def effective_config_payload(result: EffectiveConfigResult) -> dict[str, Any]:
    """Return stable serializable effective config payload."""
    payload: dict[str, Any] = {
        "project": result.config.project.model_dump(),
        "checks": result.config.checks.model_dump(),
        "gate": result.config.gate.model_dump(),
        "compare": result.config.compare.model_dump(),
        "risk": result.config.effective_risk().model_dump(),
    }
    return payload
