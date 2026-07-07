from pathlib import Path

import pytest
from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.config import ConfigError, load_config

runner = CliRunner()

def test_config_loader_reads_generated_config(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    assert result.exit_code == 0

    config = load_config(tmp_path / ".vibebench" / "config.yaml")

    assert config.project.name == "vibebench-project"
    assert config.checks.test == [
        "python3 -c \"print('vibebench generic check')\""
    ]
    assert config.checks.lint == []
    assert config.risk_rules.forbidden_paths == [".env", ".env.*", "secrets/"]
    assert config.risk_rules.large_patch_lines == 500
    assert config.gate.min_score == 80
    assert config.gate.max_risk == "medium"
    assert config.gate.allow_findings == 0
    assert config.gate.require_status_passed is True
    assert config.regression.enabled is False
    assert config.regression.baseline_label == "stable"
    assert config.regression.require_baseline is False
    assert config.regression.max_score_drop == 0.0
    assert config.regression.max_risk_increase == 0.0
    assert config.regression.fail_on_missing_metrics is True

def test_config_loader_missing_config_has_helpful_error(tmp_path: Path) -> None:
    missing_config = tmp_path / ".vibebench" / "config.yaml"

    with pytest.raises(ConfigError, match='Run "vibebench init"'):
        load_config(missing_config)

def write_config(tmp_path: Path, gate_yaml: str) -> Path:
    config_dir = tmp_path / ".vibebench"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        f"""project:
  name: demo
checks:
  test:
    - pytest -q
  lint:
    - ruff check .
risk_rules:
  forbidden_paths:
    - .env
  warn_if_tests_deleted: true
  warn_if_lockfiles_changed: true
  large_patch_lines: 500
gate:
{gate_yaml}
""",
        encoding="utf-8",
    )
    return config_path

def test_invalid_gate_max_risk_fails_clearly(tmp_path: Path) -> None:
    config_path = write_config(tmp_path, "  max_risk: severe\n")

    with pytest.raises(ConfigError, match="gate.max_risk"):
        load_config(config_path)

def test_invalid_gate_min_score_fails_clearly(tmp_path: Path) -> None:
    config_path = write_config(tmp_path, "  min_score: 101\n")

    with pytest.raises(ConfigError, match="gate.min_score"):
        load_config(config_path)

def test_invalid_gate_allow_findings_fails_clearly(tmp_path: Path) -> None:
    config_path = write_config(tmp_path, "  allow_findings: -1\n")

    with pytest.raises(ConfigError, match="gate.allow_findings"):
        load_config(config_path)

def test_invalid_gate_require_status_passed_fails_clearly(tmp_path: Path) -> None:
    config_path = write_config(tmp_path, "  require_status_passed: maybe\n")

    with pytest.raises(ConfigError, match="gate.require_status_passed"):
        load_config(config_path)

def write_risk_config(tmp_path: Path, risk_yaml: str) -> Path:
    config_dir = tmp_path / ".vibebench"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        f"""project:
  name: demo
checks:
  test:
    - pytest -q
  lint:
    - ruff check .
risk:
{risk_yaml}
""",
        encoding="utf-8",
    )
    return config_path

def test_config_loader_reads_risk_config(tmp_path: Path) -> None:
    config_path = write_risk_config(
        tmp_path,
        """  max_changed_files: 25
  max_patch_lines: 600
  forbidden_paths:
    - private/
  secret_like_paths:
    - "*.pem"
  lockfiles:
    - custom.lock
  test_path_patterns:
    - specs/
""",
    )

    config = load_config(config_path)

    assert config.risk is not None
    assert config.risk.max_changed_files == 25
    assert config.risk.max_patch_lines == 600
    assert config.risk.forbidden_paths == ["private/"]
    assert config.risk.secret_like_paths == ["*.pem"]
    assert config.risk.lockfiles == ["custom.lock"]
    assert config.risk.test_path_patterns == ["specs/"]

def test_invalid_risk_max_changed_files_fails_clearly(tmp_path: Path) -> None:
    config_path = write_risk_config(tmp_path, "  max_changed_files: 0\n")

    with pytest.raises(ConfigError, match="risk.max_changed_files"):
        load_config(config_path)

def test_invalid_risk_max_patch_lines_fails_clearly(tmp_path: Path) -> None:
    config_path = write_risk_config(tmp_path, "  max_patch_lines: 0\n")

    with pytest.raises(ConfigError, match="risk.max_patch_lines"):
        load_config(config_path)

def test_invalid_risk_forbidden_paths_fails_clearly(tmp_path: Path) -> None:
    config_path = write_risk_config(tmp_path, "  forbidden_paths: .env\n")

    with pytest.raises(ConfigError, match="risk.forbidden_paths"):
        load_config(config_path)

def test_invalid_risk_secret_like_paths_fails_clearly(tmp_path: Path) -> None:
    config_path = write_risk_config(tmp_path, "  secret_like_paths: token\n")

    with pytest.raises(ConfigError, match="risk.secret_like_paths"):
        load_config(config_path)

def test_invalid_risk_lockfiles_fails_clearly(tmp_path: Path) -> None:
    config_path = write_risk_config(tmp_path, "  lockfiles: package-lock.json\n")

    with pytest.raises(ConfigError, match="risk.lockfiles"):
        load_config(config_path)

def test_invalid_risk_test_path_patterns_fails_clearly(tmp_path: Path) -> None:
    config_path = write_risk_config(tmp_path, "  test_path_patterns: tests/\n")

    with pytest.raises(ConfigError, match="risk.test_path_patterns"):
        load_config(config_path)

def test_invalid_risk_forbidden_path_item_fails_clearly(tmp_path: Path) -> None:
    config_path = write_risk_config(
        tmp_path,
        """  forbidden_paths:
    - 123
""",
    )

    with pytest.raises(ConfigError, match="risk.forbidden_paths"):
        load_config(config_path)


def write_regression_config(tmp_path: Path, regression_yaml: str) -> Path:
    config_dir = tmp_path / ".vibebench"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        f"""project:
  name: demo
checks:
  test:
    - pytest -q
  lint:
    - ruff check .
regression:
{regression_yaml}
""",
        encoding="utf-8",
    )
    return config_path


def test_config_loader_reads_regression_policy(tmp_path: Path) -> None:
    config_path = write_regression_config(
        tmp_path,
        """  enabled: true
  baseline_label: stable
  require_baseline: true
  max_score_drop: 1.5
  max_risk_increase: 1
  fail_on_missing_metrics: false
""",
    )

    config = load_config(config_path)

    assert config.regression.enabled is True
    assert config.regression.baseline_label == "stable"
    assert config.regression.require_baseline is True
    assert config.regression.max_score_drop == 1.5
    assert config.regression.max_risk_increase == 1
    assert config.regression.fail_on_missing_metrics is False


def test_invalid_regression_threshold_fails_clearly(tmp_path: Path) -> None:
    config_path = write_regression_config(tmp_path, "  max_score_drop: -1\n")

    with pytest.raises(ConfigError, match="regression.max_score_drop"):
        load_config(config_path)


def test_invalid_regression_boolean_fails_clearly(tmp_path: Path) -> None:
    config_path = write_regression_config(tmp_path, "  enabled: maybe\n")

    with pytest.raises(ConfigError, match="regression.enabled"):
        load_config(config_path)


def test_invalid_regression_baseline_label_fails_clearly(tmp_path: Path) -> None:
    config_path = write_regression_config(tmp_path, "  baseline_label: 'bad label'\n")

    with pytest.raises(ConfigError, match="regression.baseline_label"):
        load_config(config_path)


def write_metrics_diff_config(tmp_path: Path, policy_yaml: str) -> Path:
    config_dir = tmp_path / ".vibebench"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        f"""project:
  name: demo
checks:
  test:
    - pytest -q
  lint:
    - ruff check .
metrics_diff:
  policy:
{policy_yaml}
""",
        encoding="utf-8",
    )
    return config_path


def test_config_loader_reads_metrics_diff_policy(tmp_path: Path) -> None:
    config_path = write_metrics_diff_config(
        tmp_path,
        """    enabled: true
    baseline_label: stable
    fail_on_added_errors: true
    fail_on_added_warnings: false
    fail_on_removed_metrics: true
    max_score_drop: 1.5
    max_risk_increase: 1
    custom_rules:
      - metric: latency_ms
        max_increase: 50
      - metric: pass_rate
        max_drop: 0.01
""",
    )

    config = load_config(config_path)

    policy = config.metrics_diff.policy
    assert policy.enabled is True
    assert policy.baseline_label == "stable"
    assert policy.fail_on_added_errors is True
    assert policy.fail_on_added_warnings is False
    assert policy.fail_on_removed_metrics is True
    assert policy.max_score_drop == 1.5
    assert policy.max_risk_increase == 1
    assert policy.rules["latency_ms"].max_increase == 50
    assert policy.rules["pass_rate"].max_drop == 0.01


def test_invalid_metrics_diff_policy_boolean_fails_clearly(tmp_path: Path) -> None:
    config_path = write_metrics_diff_config(tmp_path, "    enabled: maybe\n")

    with pytest.raises(ConfigError, match="metrics_diff.policy.enabled"):
        load_config(config_path)


def test_invalid_metrics_diff_policy_threshold_fails_clearly(tmp_path: Path) -> None:
    config_path = write_metrics_diff_config(tmp_path, "    max_score_drop: -1\n")

    with pytest.raises(ConfigError, match="metrics_diff.policy.max_score_drop"):
        load_config(config_path)


def test_invalid_metrics_diff_policy_rule_shape_fails_clearly(tmp_path: Path) -> None:
    config_path = write_metrics_diff_config(
        tmp_path,
        """    custom_rules:
      - metric: latency_ms
        unknown: 1
""",
    )

    with pytest.raises(
        ConfigError, match="metrics_diff.policy.custom_rules.0.unknown"
    ):
        load_config(config_path)


def write_project_scan_config(tmp_path: Path, policy_yaml: str) -> Path:
    config_dir = tmp_path / ".vibebench"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        f"""project:
  name: demo
checks:
  test:
    - pytest -q
  lint:
    - ruff check .
project_scan:
  policy:
{policy_yaml}
""",
        encoding="utf-8",
    )
    return config_path


def test_config_loader_reads_project_scan_policy(tmp_path: Path) -> None:
    config_path = write_project_scan_config(
        tmp_path,
        """    enabled: true
    require_config_valid: true
    require_supported_stack: true
    allowed_profiles:
      - python
      - node
    fail_on_error_findings: true
    fail_on_warning_findings: true
    require_recommended_profile: false
""",
    )

    config = load_config(config_path)

    policy = config.project_scan.policy
    assert policy.enabled is True
    assert policy.require_config_valid is True
    assert policy.require_supported_stack is True
    assert policy.allowed_profiles == ["python", "node"]
    assert policy.fail_on_error_findings is True
    assert policy.fail_on_warning_findings is True
    assert policy.require_recommended_profile is False


def test_invalid_project_scan_policy_boolean_fails_clearly(tmp_path: Path) -> None:
    config_path = write_project_scan_config(tmp_path, "    enabled: maybe\n")

    with pytest.raises(ConfigError, match="project_scan.policy.enabled"):
        load_config(config_path)


def test_invalid_project_scan_policy_unknown_key_fails_clearly(
    tmp_path: Path,
) -> None:
    config_path = write_project_scan_config(tmp_path, "    unknown: true\n")

    with pytest.raises(ConfigError, match="project_scan.policy.unknown"):
        load_config(config_path)


def write_onboard_config(tmp_path: Path, policy_yaml: str) -> Path:
    config_dir = tmp_path / ".vibebench"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        f"""project:
  name: demo
checks:
  test:
    - pytest -q
  lint:
    - ruff check .
onboard:
  policy:
{policy_yaml}
""",
        encoding="utf-8",
    )
    return config_path


def test_config_loader_reads_onboard_policy(tmp_path: Path) -> None:
    config_path = write_onboard_config(
        tmp_path,
        """    enabled: true
    fail_on_blockers: true
    fail_on_errors: true
    fail_on_warnings: true
    require_config: true
    require_ci_ready: true
""",
    )

    config = load_config(config_path)

    policy = config.onboard.policy
    assert policy.enabled is True
    assert policy.fail_on_blockers is True
    assert policy.fail_on_errors is True
    assert policy.fail_on_warnings is True
    assert policy.require_config is True
    assert policy.require_ci_ready is True


def test_invalid_onboard_policy_boolean_fails_clearly(tmp_path: Path) -> None:
    config_path = write_onboard_config(tmp_path, "    enabled: maybe\n")

    with pytest.raises(ConfigError, match="onboard.policy.enabled"):
        load_config(config_path)


def test_invalid_onboard_policy_unknown_key_fails_clearly(tmp_path: Path) -> None:
    config_path = write_onboard_config(tmp_path, "    unknown: true\n")

    with pytest.raises(ConfigError, match="onboard.policy.unknown"):
        load_config(config_path)


def write_workflow_check_config(tmp_path: Path, policy_yaml: str) -> Path:
    config_dir = tmp_path / ".vibebench"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        f"""project:
  name: demo
checks:
  test:
    - pytest -q
  lint:
    - ruff check .
workflow_check:
  policy:
{policy_yaml}
""",
        encoding="utf-8",
    )
    return config_path


def test_config_loader_reads_workflow_check_policy(tmp_path: Path) -> None:
    config_path = write_workflow_check_config(
        tmp_path,
        """    enabled: true
    fail_on_blockers: true
    fail_on_errors: true
    fail_on_warnings: true
    require_config: true
    require_ci_ready: true
    allowed_workflow_names:
      - VibeBench
    allowed_action_prefixes:
      - actions/
""",
    )

    config = load_config(config_path)

    policy = config.workflow_check.policy
    assert policy.enabled is True
    assert policy.fail_on_blockers is True
    assert policy.fail_on_errors is True
    assert policy.fail_on_warnings is True
    assert policy.require_config is True
    assert policy.require_ci_ready is True
    assert policy.allowed_workflow_names == ["VibeBench"]
    assert policy.allowed_action_prefixes == ["actions/"]


def test_invalid_workflow_check_policy_boolean_fails_clearly(tmp_path: Path) -> None:
    config_path = write_workflow_check_config(tmp_path, "    enabled: maybe\n")

    with pytest.raises(ConfigError, match="workflow_check.policy.enabled"):
        load_config(config_path)


def test_invalid_workflow_check_policy_unknown_key_fails_clearly(
    tmp_path: Path,
) -> None:
    config_path = write_workflow_check_config(tmp_path, "    unknown: true\n")

    with pytest.raises(ConfigError, match="workflow_check.policy.unknown"):
        load_config(config_path)


def test_invalid_project_scan_policy_allowed_profile_fails_clearly(
    tmp_path: Path,
) -> None:
    config_path = write_project_scan_config(
        tmp_path,
        """    allowed_profiles:
      - rails
""",
    )

    with pytest.raises(ConfigError, match="project_scan.policy.allowed_profiles"):
        load_config(config_path)
