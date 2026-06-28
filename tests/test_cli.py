from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.config import load_config

runner = CliRunner()


def test_cli_help_works() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Codex-first quality gate" in result.output
    assert "version" in result.output
    assert "init" in result.output


def config_path(root: Path) -> Path:
    return root / ".vibebench" / "config.yaml"


def workflow_path(root: Path) -> Path:
    return root / ".github" / "workflows" / "vibebench.yml"


def test_init_creates_config_and_workflow(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert config_path(tmp_path).exists()
    assert workflow_path(tmp_path).exists()
    assert "vibebench-project" in config_path(tmp_path).read_text(encoding="utf-8")
    assert "created" in result.output
    assert "python -m vibebench doctor" in result.output


def test_init_generated_config_loads(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    config = load_config(config_path(tmp_path))
    assert config.project.name == "vibebench-project"
    assert config.gate.min_score == 80
    assert config.risk is not None
    assert config.risk.max_patch_lines == 500


def test_init_generated_workflow_contains_required_commands(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    workflow = workflow_path(tmp_path).read_text(encoding="utf-8")
    assert "actions/checkout@v5" in workflow
    assert "actions/setup-python@v6" in workflow
    assert "python -m pip install -e" in workflow
    assert "git+https://github.com/wemby-1/vibebench-arena.git@main" in workflow
    assert "python -m vibebench check" in workflow
    assert "python -m vibebench gate --write-gate-summary" in workflow
    assert "python -m vibebench report" in workflow
    assert "python -m vibebench pr-comment" in workflow
    assert "python -m vibebench gh-summary" in workflow
    assert "actions/upload-artifact@v7" in workflow
    assert workflow.count("if: always()") >= 4


def test_init_does_not_overwrite_existing_files_by_default(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    workflow_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("existing config", encoding="utf-8")
    workflow_path(tmp_path).write_text("existing workflow", encoding="utf-8")

    result = runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert config_path(tmp_path).read_text(encoding="utf-8") == "existing config"
    assert workflow_path(tmp_path).read_text(encoding="utf-8") == "existing workflow"
    assert "skipped" in result.output


def test_init_force_overwrites_existing_files(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    workflow_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("existing config", encoding="utf-8")
    workflow_path(tmp_path).write_text("existing workflow", encoding="utf-8")

    result = runner.invoke(app, ["init", "--project-root", str(tmp_path), "--force"])

    assert result.exit_code == 0
    assert "vibebench-project" in config_path(tmp_path).read_text(encoding="utf-8")
    assert "python -m vibebench check" in workflow_path(tmp_path).read_text(
        encoding="utf-8"
    )


def test_init_no_workflow_creates_only_config(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["init", "--project-root", str(tmp_path), "--no-workflow"]
    )

    assert result.exit_code == 0
    assert config_path(tmp_path).exists()
    assert not workflow_path(tmp_path).exists()


def test_init_workflow_only_creates_only_workflow(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["init", "--project-root", str(tmp_path), "--workflow-only"]
    )

    assert result.exit_code == 0
    assert not config_path(tmp_path).exists()
    assert workflow_path(tmp_path).exists()


def test_init_conflicting_workflow_options_fail_clearly(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--project-root",
            str(tmp_path),
            "--no-workflow",
            "--workflow-only",
        ],
    )

    assert result.exit_code == 1
    assert "cannot be used together" in result.output
