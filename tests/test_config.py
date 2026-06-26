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


def test_config_loader_missing_config_has_helpful_error(tmp_path: Path) -> None:
    missing_config = tmp_path / ".vibebench" / "config.yaml"

    with pytest.raises(ConfigError, match='Run "vibebench init"'):
        load_config(missing_config)
