"""Configuration models and loader for VibeBench Arena."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from vibebench.paths import config_file
from vibebench.project_detect import (
    detect_project,
    select_profile_for_stacks,
)

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


WORKFLOW_CHECK_CI_MODE_ORDER = ["default", "adoption", "adoption-policy"]
WORKFLOW_CHECK_CI_MODE_SET = set(WORKFLOW_CHECK_CI_MODE_ORDER)

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
    "regression": {
        "enabled": False,
        "baseline_label": None,
        "require_baseline": False,
        "max_score_drop": 0.0,
        "max_risk_increase": 0.0,
        "fail_on_missing_metrics": True,
    },
    "metrics_diff": {
        "policy": {
            "enabled": False,
            "baseline_label": "stable",
            "fail_on_added_errors": False,
            "fail_on_added_warnings": False,
            "fail_on_removed_metrics": False,
            "max_score_drop": 0.0,
            "max_risk_increase": 0.0,
            "custom_rules": [],
        },
    },
    "project_scan": {
        "policy": {
            "enabled": False,
            "require_config_valid": True,
            "require_supported_stack": True,
            "allowed_profiles": ["generic", "python", "node", "fullstack"],
            "fail_on_error_findings": True,
            "fail_on_warning_findings": False,
            "require_recommended_profile": False,
        },
    },
    "onboard": {
        "policy": {
            "enabled": False,
            "fail_on_blockers": True,
            "fail_on_errors": True,
            "fail_on_warnings": False,
            "require_config": True,
            "require_ci_ready": False,
        },
    },
    "workflow_check": {
        "policy": {
            "enabled": False,
            "fail_on_blockers": True,
            "fail_on_errors": True,
            "fail_on_warnings": False,
            "require_config": True,
            "require_ci_ready": False,
            "required_ci_modes": [],
            "allowed_workflow_names": [],
            "allowed_action_prefixes": [],
        },
    },
    "preflight": {
        "policy": {
            "enabled": False,
            "fail_on_blockers": True,
            "fail_on_errors": True,
            "fail_on_warnings": False,
            "require_config": True,
            "require_project_scan_ready": True,
            "require_onboard_ready": True,
            "require_workflow_check_ready": True,
            "require_workflow_template_ready": False,
        },
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


class RegressionConfig(BaseModel):
    """Regression-check policy defaults."""

    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool = False
    baseline_label: str | None = None
    require_baseline: StrictBool = False
    max_score_drop: float = Field(default=0.0, ge=0)
    max_risk_increase: float = Field(default=0.0, ge=0)
    fail_on_missing_metrics: StrictBool = True

    @field_validator("baseline_label")
    @classmethod
    def validate_baseline_label(cls, value: str | None) -> str | None:
        """Validate a pinned baseline label without importing CLI helpers."""
        if value is None:
            return None
        selected = value.strip()
        allowed = set(
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789._-"
        )
        if not selected or selected in {".", ".."}:
            raise ValueError("baseline label must not be empty, '.' or '..'")
        if any(char not in allowed for char in selected):
            raise ValueError(
                "baseline label may only contain letters, numbers, '.', '_', or '-'"
            )
        return selected


class MetricsDiffPolicyRuleConfig(BaseModel):
    """Per-metric metrics-diff policy threshold."""

    model_config = ConfigDict(extra="forbid")

    metric: StrictStr
    max_drop: float | None = Field(default=None, ge=0)
    max_increase: float | None = Field(default=None, ge=0)


class MetricsDiffPolicyConfig(BaseModel):
    """Metrics-diff policy gate defaults."""

    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool = False
    baseline_label: str | None = "stable"
    fail_on_added_errors: StrictBool = False
    fail_on_added_warnings: StrictBool = False
    fail_on_removed_metrics: StrictBool = False
    max_score_drop: float = Field(default=0.0, ge=0)
    max_risk_increase: float = Field(default=0.0, ge=0)
    custom_rules: list[MetricsDiffPolicyRuleConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_policy_keys(cls, data: object) -> object:
        """Accept pre-release policy key names without hiding unknown keys."""
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "fail_on_added_metrics" in normalized:
            if "fail_on_added_errors" in normalized:
                raise ValueError(
                    "metrics_diff.policy cannot set both fail_on_added_metrics "
                    "and fail_on_added_errors"
                )
            normalized["fail_on_added_errors"] = normalized.pop(
                "fail_on_added_metrics"
            )
        if "rules" in normalized:
            if "custom_rules" in normalized:
                raise ValueError(
                    "metrics_diff.policy cannot set both rules and custom_rules"
                )
            rules = normalized.pop("rules")
            if isinstance(rules, dict):
                normalized["custom_rules"] = [
                    {"metric": metric, **rule}
                    if isinstance(rule, dict)
                    else {"metric": metric, "value": rule}
                    for metric, rule in rules.items()
                ]
            else:
                normalized["custom_rules"] = rules
        return normalized

    @field_validator("baseline_label")
    @classmethod
    def validate_baseline_label(cls, value: str | None) -> str | None:
        """Validate a pinned baseline label."""
        return RegressionConfig.validate_baseline_label(value)

    @field_validator("custom_rules")
    @classmethod
    def validate_custom_rules(
        cls, value: list[MetricsDiffPolicyRuleConfig]
    ) -> list[MetricsDiffPolicyRuleConfig]:
        """Validate configured metric rule names and shapes."""
        seen: set[str] = set()
        for rule in value:
            metric = rule.metric
            if not metric.strip():
                raise ValueError(
                    "metrics_diff.policy.custom_rules.metric must not be empty"
                )
            if metric in seen:
                raise ValueError(
                    f"metrics_diff.policy.custom_rules.{metric} is duplicated"
                )
            seen.add(metric)
            if rule.max_drop is None and rule.max_increase is None:
                raise ValueError(
                    f"metrics_diff.policy.custom_rules.{metric} must set "
                    "max_drop or max_increase"
                )
        return value

    @property
    def fail_on_added_metrics(self) -> bool:
        """Compatibility alias for the pre-release policy field name."""
        return self.fail_on_added_errors

    @property
    def rules(self) -> dict[str, MetricsDiffPolicyRuleConfig]:
        """Compatibility alias for dict-style pre-release custom rules."""
        return {rule.metric: rule for rule in self.custom_rules}


class MetricsDiffConfig(BaseModel):
    """Metrics-diff configuration."""

    model_config = ConfigDict(extra="forbid")

    policy: MetricsDiffPolicyConfig = Field(default_factory=MetricsDiffPolicyConfig)



class ProjectScanPolicyConfig(BaseModel):
    """Project-scan policy gate defaults."""

    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool = False
    require_config_valid: StrictBool = True
    require_supported_stack: StrictBool = True
    allowed_profiles: list[StrictStr] = Field(
        default_factory=lambda: ["generic", "python", "node", "fullstack"]
    )
    fail_on_error_findings: StrictBool = True
    fail_on_warning_findings: StrictBool = False
    require_recommended_profile: StrictBool = False

    @field_validator("allowed_profiles")
    @classmethod
    def validate_allowed_profiles(cls, value: list[str]) -> list[str]:
        """Validate project-scan profile allowlist."""
        allowed = {"generic", "python", "node", "fullstack"}
        if not value:
            raise ValueError("project_scan.policy.allowed_profiles must not be empty")
        seen: set[str] = set()
        for profile in value:
            if profile not in allowed:
                allowed_text = ", ".join(sorted(allowed))
                raise ValueError(
                    "project_scan.policy.allowed_profiles entries must be one of: "
                    f"{allowed_text}"
                )
            if profile in seen:
                raise ValueError(
                    f"project_scan.policy.allowed_profiles.{profile} is duplicated"
                )
            seen.add(profile)
        return value


class ProjectScanConfig(BaseModel):
    """Project-scan configuration."""

    model_config = ConfigDict(extra="forbid")

    policy: ProjectScanPolicyConfig = Field(default_factory=ProjectScanPolicyConfig)


class OnboardPolicyConfig(BaseModel):
    """Onboarding policy gate defaults."""

    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool = False
    fail_on_blockers: StrictBool = True
    fail_on_errors: StrictBool = True
    fail_on_warnings: StrictBool = False
    require_config: StrictBool = True
    require_ci_ready: StrictBool = False


class OnboardConfig(BaseModel):
    """Onboarding plan configuration."""

    model_config = ConfigDict(extra="forbid")

    policy: OnboardPolicyConfig = Field(default_factory=OnboardPolicyConfig)


class WorkflowCheckPolicyConfig(BaseModel):
    """Workflow-check policy gate defaults."""

    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool = False
    fail_on_blockers: StrictBool = True
    fail_on_errors: StrictBool = True
    fail_on_warnings: StrictBool = False
    require_config: StrictBool = True
    require_ci_ready: StrictBool = False
    required_ci_modes: list[StrictStr] = Field(default_factory=list)
    allowed_workflow_names: list[StrictStr] = Field(default_factory=list)
    allowed_action_prefixes: list[StrictStr] = Field(default_factory=list)

    @field_validator("allowed_workflow_names", "allowed_action_prefixes")
    @classmethod
    def validate_string_allowlist(cls, value: list[str]) -> list[str]:
        """Validate workflow-check policy allowlists."""
        seen: set[str] = set()
        for item in value:
            selected = item.strip()
            if not selected:
                raise ValueError("workflow_check.policy allowlists must not be empty")
            if selected in seen:
                raise ValueError(
                    f"workflow_check.policy allowlist entry {selected!r} is duplicated"
                )
            seen.add(selected)
        return value

    @field_validator("required_ci_modes")
    @classmethod
    def validate_required_ci_modes(cls, value: list[str]) -> list[str]:
        """Validate workflow-check required CI modes."""
        seen: set[str] = set()
        for item in value:
            selected = item.strip()
            if selected not in WORKFLOW_CHECK_CI_MODE_SET:
                allowed = ", ".join(WORKFLOW_CHECK_CI_MODE_ORDER)
                raise ValueError(
                    "workflow_check.policy.required_ci_modes entry "
                    f"{item!r} must be one of: {allowed}"
                )
            seen.add(selected)
        return [mode for mode in WORKFLOW_CHECK_CI_MODE_ORDER if mode in seen]


class WorkflowCheckConfig(BaseModel):
    """Workflow-check configuration."""

    model_config = ConfigDict(extra="forbid")

    policy: WorkflowCheckPolicyConfig = Field(
        default_factory=WorkflowCheckPolicyConfig
    )


class PreflightPolicyConfig(BaseModel):
    """Preflight aggregate policy gate defaults."""

    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool = False
    fail_on_blockers: StrictBool = True
    fail_on_errors: StrictBool = True
    fail_on_warnings: StrictBool = False
    require_config: StrictBool = True
    require_project_scan_ready: StrictBool = True
    require_onboard_ready: StrictBool = True
    require_workflow_check_ready: StrictBool = True
    require_workflow_template_ready: StrictBool = False


class PreflightConfig(BaseModel):
    """Preflight aggregate policy configuration."""

    model_config = ConfigDict(extra="forbid")

    policy: PreflightPolicyConfig = Field(default_factory=PreflightPolicyConfig)


class VibeBenchConfig(BaseModel):
    """Top-level VibeBench configuration."""

    model_config = ConfigDict(extra="forbid")

    project: ProjectConfig
    checks: ChecksConfig
    risk_rules: RiskRulesConfig = Field(default_factory=RiskRulesConfig)
    risk: RiskConfig | None = None
    gate: GateConfig = Field(default_factory=GateConfig)
    compare: CompareConfig = Field(default_factory=CompareConfig)
    regression: RegressionConfig = Field(default_factory=RegressionConfig)
    metrics_diff: MetricsDiffConfig = Field(default_factory=MetricsDiffConfig)
    project_scan: ProjectScanConfig = Field(default_factory=ProjectScanConfig)
    onboard: OnboardConfig = Field(default_factory=OnboardConfig)
    workflow_check: WorkflowCheckConfig = Field(default_factory=WorkflowCheckConfig)
    preflight: PreflightConfig = Field(default_factory=PreflightConfig)

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


def config_example_yaml() -> str:
    """Return a concise starter config example as YAML."""
    payload: dict[str, Any] = {
        "project": {"name": "vibebench-project"},
        "checks": {
            "test": ["pytest -q"],
            "lint": ["ruff check ."],
        },
        "gate": {
            "min_score": 80,
            "max_risk": "medium",
            "allow_findings": 0,
            "require_status_passed": True,
        },
        "compare": {"fail_on_regression": False},
        "regression": {
            "enabled": False,
            "baseline_label": "stable",
            "require_baseline": False,
            "max_score_drop": 0.0,
            "max_risk_increase": 0.0,
            "fail_on_missing_metrics": True,
        },
        "metrics_diff": {
            "policy": {
                "enabled": False,
                "baseline_label": "stable",
                "fail_on_added_errors": False,
                "fail_on_added_warnings": False,
                "fail_on_removed_metrics": False,
                "max_score_drop": 0.0,
                "max_risk_increase": 0.0,
                "custom_rules": [
                    {"metric": "quality.accuracy", "max_drop": 0.01},
                    {"metric": "latency.p95_ms", "max_increase": 50},
                ],
            },
        },
        "project_scan": {
            "policy": {
                "enabled": False,
                "require_config_valid": True,
                "require_supported_stack": True,
                "allowed_profiles": ["generic", "python", "node", "fullstack"],
                "fail_on_error_findings": True,
                "fail_on_warning_findings": False,
                "require_recommended_profile": False,
            },
        },
        "onboard": {
            "policy": {
                "enabled": False,
                "fail_on_blockers": True,
                "fail_on_errors": True,
                "fail_on_warnings": False,
                "require_config": True,
                "require_ci_ready": False,
            },
        },
        "workflow_check": {
            "policy": {
                "enabled": False,
                "fail_on_blockers": True,
                "fail_on_errors": True,
                "fail_on_warnings": False,
                "require_config": True,
                "require_ci_ready": False,
                "required_ci_modes": [],
                "allowed_workflow_names": [],
                "allowed_action_prefixes": [],
            },
        },
        "preflight": {
            "policy": {
                "enabled": False,
                "fail_on_blockers": True,
                "fail_on_errors": True,
                "fail_on_warnings": False,
                "require_config": True,
                "require_project_scan_ready": True,
                "require_onboard_ready": True,
                "require_workflow_check_ready": True,
                "require_workflow_template_ready": False,
            },
        },
    }
    return yaml.safe_dump(payload, sort_keys=False)


INIT_PROFILE_NAMES = {"generic", "python", "node", "fullstack", "auto"}


@dataclass(frozen=True)
class InitProfileResult:
    """Resolved init profile, generated YAML, and detection metadata."""

    selected_profile: str
    config_yaml: str
    detected_stacks: list[str]
    detection_reasons: list[str]
    package_scripts: list[str]


def init_config_profile_yaml(profile: str, project_root: Path) -> tuple[str, str]:
    """Return selected init profile and valid starter config YAML."""
    result = resolve_init_config_profile(profile, project_root)
    return result.selected_profile, result.config_yaml


def resolve_init_config_profile(profile: str, project_root: Path) -> InitProfileResult:
    """Resolve an init profile and render valid starter config YAML."""
    if profile not in INIT_PROFILE_NAMES:
        allowed = ", ".join(sorted(INIT_PROFILE_NAMES))
        raise ConfigError(
            f"Unknown init profile '{profile}'. Choose one of: {allowed}."
        )
    detection = detect_project(project_root)
    detected_stacks = detection.detected_stacks
    detection_reasons = detection.detection_reasons
    selected = select_init_profile(profile, detected_stacks)
    package_scripts = detection.node_scripts
    payload = init_config_profile_payload(selected, package_scripts=package_scripts)
    return InitProfileResult(
        selected_profile=selected,
        config_yaml=yaml.safe_dump(payload, sort_keys=False),
        detected_stacks=detected_stacks,
        detection_reasons=detection_reasons,
        package_scripts=package_scripts,
    )


def select_init_profile(requested_profile: str, detected_stacks: list[str]) -> str:
    """Select the concrete init profile for a request."""
    if requested_profile != "auto":
        return requested_profile
    return select_profile_for_stacks(detected_stacks)


def detect_init_profile(project_root: Path) -> str:
    """Select an init profile from lightweight project markers."""
    return detect_project(project_root).recommended_profile


def init_config_profile_payload(
    profile: str,
    *,
    package_scripts: list[str] | None = None,
) -> dict[str, Any]:
    """Return a starter config payload for an init profile."""
    selected_scripts = package_scripts or []
    if profile == "python":
        checks = python_profile_checks()
    elif profile == "node":
        checks = node_profile_checks(selected_scripts, fallback_to_generic=True)
    elif profile == "fullstack":
        checks = merge_check_groups(
            python_profile_checks(),
            node_profile_checks(selected_scripts, fallback_to_generic=False),
        )
    elif profile == "generic":
        checks = generic_profile_checks()
    else:
        raise ConfigError(f"Unknown init profile '{profile}'.")
    return {
        "project": {"name": "vibebench-project"},
        "checks": checks,
        "gate": {
            "min_score": 80,
            "max_risk": "medium",
            "allow_findings": 0,
            "require_status_passed": True,
        },
        "compare": {"fail_on_regression": False},
        "regression": {
            "enabled": False,
            "baseline_label": "stable",
            "require_baseline": False,
            "max_score_drop": 0.0,
            "max_risk_increase": 0.0,
            "fail_on_missing_metrics": True,
        },
        "metrics_diff": {
            "policy": {
                "enabled": False,
                "baseline_label": "stable",
                "fail_on_added_errors": False,
                "fail_on_added_warnings": False,
                "fail_on_removed_metrics": False,
                "max_score_drop": 0.0,
                "max_risk_increase": 0.0,
                "custom_rules": [],
            },
        },
        "project_scan": {
            "policy": {
                "enabled": False,
                "require_config_valid": True,
                "require_supported_stack": True,
                "allowed_profiles": ["generic", "python", "node", "fullstack"],
                "fail_on_error_findings": True,
                "fail_on_warning_findings": False,
                "require_recommended_profile": False,
            },
        },
        "onboard": {
            "policy": {
                "enabled": False,
                "fail_on_blockers": True,
                "fail_on_errors": True,
                "fail_on_warnings": False,
                "require_config": True,
                "require_ci_ready": False,
            },
        },
        "workflow_check": {
            "policy": {
                "enabled": False,
                "fail_on_blockers": True,
                "fail_on_errors": True,
                "fail_on_warnings": False,
                "require_config": True,
                "require_ci_ready": False,
                "required_ci_modes": [],
                "allowed_workflow_names": [],
                "allowed_action_prefixes": [],
            },
        },
        "preflight": {
            "policy": {
                "enabled": False,
                "fail_on_blockers": True,
                "fail_on_errors": True,
                "fail_on_warnings": False,
                "require_config": True,
                "require_project_scan_ready": True,
                "require_onboard_ready": True,
                "require_workflow_check_ready": True,
                "require_workflow_template_ready": False,
            },
        },
    }


def generic_profile_checks() -> dict[str, list[str]]:
    """Return conservative generic checks."""
    return {
        "test": ["python3 -c \"print('vibebench generic check')\""],
        "lint": [],
    }


def python_profile_checks() -> dict[str, list[str]]:
    """Return Python-oriented checks."""
    return {
        "test": ["python3 -m pytest -q"],
        "lint": ["python3 -m ruff check ."],
    }


def node_profile_checks(
    package_scripts: list[str],
    *,
    fallback_to_generic: bool,
) -> dict[str, list[str]]:
    """Return Node-oriented checks that only reference existing scripts."""
    checks = {"test": [], "lint": []}
    if "test" in package_scripts:
        checks["test"].append("npm test")
    if "lint" in package_scripts:
        checks["lint"].append("npm run lint")
    if checks["test"] or checks["lint"]:
        return checks
    return generic_profile_checks() if fallback_to_generic else checks


def merge_check_groups(
    first: dict[str, list[str]],
    second: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Merge schema-compatible check groups without duplicate commands."""
    merged: dict[str, list[str]] = {"test": [], "lint": []}
    for group in [first, second]:
        for key in merged:
            for command in group.get(key, []):
                if command not in merged[key]:
                    merged[key].append(command)
    return merged


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
                "regression": "built-in defaults",
                "metrics_diff": "built-in defaults",
                "project_scan": "built-in defaults",
                "onboard": "built-in defaults",
                "workflow_check": "built-in defaults",
                "preflight": "built-in defaults",
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
        "regression": (
            "config file" if "regression" in raw_config else "built-in defaults"
        ),
        "metrics_diff": (
            "config file" if "metrics_diff" in raw_config else "built-in defaults"
        ),
        "project_scan": (
            "config file" if "project_scan" in raw_config else "built-in defaults"
        ),
        "onboard": (
            "config file" if "onboard" in raw_config else "built-in defaults"
        ),
        "workflow_check": (
            "config file" if "workflow_check" in raw_config else "built-in defaults"
        ),
        "preflight": (
            "config file" if "preflight" in raw_config else "built-in defaults"
        ),
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
        "regression": result.config.regression.model_dump(),
        "metrics_diff": result.config.metrics_diff.model_dump(),
        "project_scan": result.config.project_scan.model_dump(),
        "onboard": result.config.onboard.model_dump(),
        "workflow_check": result.config.workflow_check.model_dump(),
        "preflight": result.config.preflight.model_dump(),
        "risk": result.config.effective_risk().model_dump(),
    }
    return payload
