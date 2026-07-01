import json
import subprocess
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
    assert "python -m ruff check ." in workflow
    assert "python -m pytest -q" in workflow
    assert "python -m vibebench ci" in workflow
    assert "actions/upload-artifact@v7" in workflow
    assert workflow.count("if: always()") >= 1


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
    assert "python -m vibebench ci" in workflow_path(tmp_path).read_text(
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



def test_config_command_without_file_prints_defaults(tmp_path: Path) -> None:
    result = runner.invoke(app, ["config", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "built-in defaults" in result.output
    assert "project" in result.output
    assert "checks" in result.output
    assert "gate" in result.output
    assert "risk" in result.output


def test_config_command_with_valid_config(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--project-root", str(tmp_path), "--no-workflow"])

    result = runner.invoke(app, ["config", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "vibebench-project" in result.output
    assert "pytest -q" in result.output
    assert "max_patch_lines" in result.output


def test_config_command_json_is_valid(tmp_path: Path) -> None:
    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert sorted(payload) == ["checks", "gate", "project", "risk"]
    assert payload["project"]["name"] == "vibebench-project"
    assert payload["checks"]["test"] == ["pytest -q"]
    assert payload["gate"]["min_score"] == 80
    assert payload["risk"]["max_patch_lines"] == 500


def test_config_command_validate_succeeds_for_valid_config(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--project-root", str(tmp_path), "--no-workflow"])

    result = runner.invoke(
        app, ["config", "--project-root", str(tmp_path), "--validate"]
    )

    assert result.exit_code == 0
    assert "VibeBench config is valid" in result.output


def test_config_command_invalid_config_fails_clearly(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("project:\n  name: ''\n", encoding="utf-8")

    result = runner.invoke(app, ["config", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "invalid" in result.output
    assert "project.name" in result.output


def test_config_command_show_source_includes_sources(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--project-root", str(tmp_path), "--no-workflow"])

    result = runner.invoke(
        app, ["config", "--project-root", str(tmp_path), "--show-source"]
    )

    assert result.exit_code == 0
    assert "Source" in result.output
    assert "config file" in result.output


def test_config_command_does_not_break_existing_check_and_gate(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--project-root", str(tmp_path), "--no-workflow"])
    config = config_path(tmp_path).read_text(encoding="utf-8")
    config = config.replace("pytest -q", "python -c \"print('test ok')\"")
    config = config.replace("ruff check .", "python -c \"print('lint ok')\"")
    config_path(tmp_path).write_text(config, encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True)

    check = runner.invoke(app, ["check", "--project-root", str(tmp_path)])
    gate = runner.invoke(app, ["gate", "--project-root", str(tmp_path)])

    assert check.exit_code == 0
    assert gate.exit_code == 0


def test_config_show_human_output(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--project-root", str(tmp_path), "--no-workflow"])

    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--show"])

    assert result.exit_code == 0
    assert str(config_path(tmp_path)) in result.output.replace("\n", "")
    assert "vibebench-project" in result.output
    assert "pytest -q" in result.output
    assert "min_score" in result.output
    assert "max_patch_lines" in result.output


def test_config_show_json_output(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--project-root", str(tmp_path), "--no-workflow"])

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--show", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert sorted(payload) == ["commands", "config_path", "gate", "project", "risk"]
    assert payload["config_path"] == str(config_path(tmp_path))
    assert payload["project"]["name"] == "vibebench-project"
    assert payload["commands"]["test"] == ["pytest -q"]
    assert payload["gate"]["min_score"] == 80
    assert payload["risk"]["max_patch_lines"] == 500


def test_config_show_missing_config_fails_clearly(tmp_path: Path) -> None:
    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--show"])

    assert result.exit_code == 1
    assert "No VibeBench config found" in result.output


def test_config_show_json_missing_config_keeps_stdout_clean(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--show", "--json"],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No VibeBench config found" in result.stderr


def test_config_show_invalid_config_fails_clearly(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("project:\n  name: ''\n", encoding="utf-8")

    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--show"])

    assert result.exit_code == 1
    assert "invalid" in result.output
    assert "project.name" in result.output


def test_config_validate_still_works_with_show_option_added(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--project-root", str(tmp_path), "--no-workflow"])

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--validate"],
    )

    assert result.exit_code == 0
    assert "VibeBench config is valid" in result.output
