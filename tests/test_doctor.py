import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.config import default_config_yaml
from vibebench.doctor import run_doctor

runner = CliRunner()


def init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def write_config(path: Path, content: str | None = None) -> Path:
    config_path = path / ".vibebench" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content or default_config_yaml(), encoding="utf-8")
    return config_path


def status_for(result, category: str) -> str:
    return next(check.status for check in result.checks if check.category == category)


def test_doctor_passes_for_ready_project(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_config(tmp_path)

    result = run_doctor(tmp_path)

    assert result.overall_status == "passed"
    assert status_for(result, "python") == "passed"
    assert status_for(result, "git") == "passed"
    assert status_for(result, "config") == "passed"
    assert status_for(result, "configured_commands") == "passed"
    assert status_for(result, "runs_directory") == "passed"
    assert (tmp_path / ".vibebench" / "runs").exists()


def test_doctor_cli_outputs_summary(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_config(tmp_path)

    result = runner.invoke(app, ["doctor", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "VibeBench Doctor" in result.output
    assert "configured_commands" in result.output


def test_doctor_fails_when_config_missing(tmp_path: Path) -> None:
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["doctor", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "No .vibebench/config.yaml found" in result.output


def test_doctor_fails_outside_git_repo(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = run_doctor(tmp_path)

    assert result.overall_status == "failed"
    assert status_for(result, "git") == "failed"


def test_doctor_warns_for_missing_executable(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_config(
        tmp_path,
        """
project:
  name: demo
checks:
  test:
    - definitely-not-a-real-vibebench-command --version
  lint: []
risk_rules:
  forbidden_paths: []
  warn_if_tests_deleted: true
  warn_if_lockfiles_changed: true
  large_patch_lines: 500
""",
    )

    result = run_doctor(tmp_path)

    assert result.overall_status == "passed"
    assert status_for(result, "configured_commands") == "warning"


def test_doctor_fails_for_invalid_config(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_config(tmp_path, "project: {}\n")

    result = runner.invoke(app, ["doctor", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "invalid" in result.output


def test_doctor_fails_for_missing_project_root(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    result = runner.invoke(app, ["doctor", "--project-root", str(missing)])

    assert result.exit_code == 1
    assert "Project root does not exist" in result.output


def test_doctor_json_outputs_valid_json_only(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["doctor", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["overall_status"] == "passed"
    assert payload["project_root"] == str(tmp_path.resolve())
    assert "VibeBench Doctor" not in result.output
    assert isinstance(payload["checks"], list)
    assert payload["checks"]
    for check in payload["checks"]:
        assert set(check) == {"name", "status", "message"}
        assert check["status"] in {"passed", "warning", "failed"}
        assert isinstance(check["message"], str)


def test_doctor_json_uses_same_checks_as_table_mode(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_config(tmp_path)

    cli_result = runner.invoke(
        app,
        ["doctor", "--project-root", str(tmp_path), "--json"],
    )
    direct_result = run_doctor(tmp_path)

    assert cli_result.exit_code == 0
    payload = json.loads(cli_result.output)
    assert [check["name"] for check in payload["checks"]] == [
        check.category for check in direct_result.checks
    ]
    assert [check["status"] for check in payload["checks"]] == [
        check.status for check in direct_result.checks
    ]


def test_doctor_json_preserves_failure_exit_code(tmp_path: Path) -> None:
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["doctor", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["overall_status"] == "failed"
    config = next(check for check in payload["checks"] if check["name"] == "config")
    assert config["status"] == "failed"
    assert "vibebench init" in config["message"]
