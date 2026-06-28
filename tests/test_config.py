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
    assert config.checks.test == ["pytest -q"]
    assert config.checks.lint == ["ruff check ."]
    assert config.risk_rules.forbidden_paths == [".env", ".env.*", "secrets/"]
    assert config.risk_rules.large_patch_lines == 500
    assert config.gate.min_score == 80
    assert config.gate.max_risk == "medium"
    assert config.gate.allow_findings == 0
    assert config.gate.require_status_passed is True

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
