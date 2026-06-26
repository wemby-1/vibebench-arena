from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

runner = CliRunner()


def test_cli_help_works() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Codex-first quality gate" in result.output
    assert "version" in result.output
    assert "init" in result.output


def test_init_creates_config() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init"])

        config_path = Path(".vibebench/config.yaml")
        assert result.exit_code == 0
        assert config_path.exists()
        assert "vibebench-project" in config_path.read_text(encoding="utf-8")
