import json
import subprocess
from pathlib import Path

import yaml
from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.runner import score_from_failures

runner = CliRunner()


def write_config(
    project_root: Path,
    test_commands: list[str],
    lint_commands: list[str],
    commit: bool = False,
) -> None:
    config_dir = project_root / ".vibebench"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config = {
        "project": {"name": "test-project"},
        "checks": {"test": test_commands, "lint": lint_commands},
        "risk_rules": {
            "forbidden_paths": [".env", ".env.*", "secrets/"],
            "warn_if_tests_deleted": True,
            "warn_if_lockfiles_changed": True,
            "large_patch_lines": 500,
        },
    }
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    if commit:
        subprocess.run(
            ["git", "add", ".vibebench/config.yaml"],
            cwd=project_root,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add config"],
            cwd=project_root,
            check=True,
        )


def init_repo(project_root: Path) -> None:
    subprocess.run(["git", "init"], cwd=project_root, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=project_root, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=project_root,
        check=True,
    )
    (project_root / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=project_root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=project_root, check=True)


def latest_metrics(project_root: Path) -> dict[str, object]:
    metrics_dir = project_root / ".vibebench" / "runs"
    metrics_files = sorted(metrics_dir.glob("*/metrics.json"))
    assert metrics_files
    return json.loads(metrics_files[-1].read_text(encoding="utf-8"))


def test_check_command_succeeds_when_configured_commands_pass(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_config(
        tmp_path,
        ["python -c \"print('tests ok')\""],
        ["python -c \"print('lint ok')\""],
        commit=True,
    )

    result = runner.invoke(app, ["check", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "VibeBench check" in result.output
    assert "passed" in result.output

    metrics = latest_metrics(tmp_path)
    assert metrics["overall_status"] == "passed"
    assert metrics["score"] == 100
    assert metrics["risk_level"] == "low"
    assert metrics["summary"] == {
        "total_commands": 2,
        "passed_commands": 2,
        "failed_commands": 0,
        "total_findings": 0,
        "critical_findings": 0,
        "high_findings": 0,
        "warning_findings": 0,
        "info_findings": 0,
    }
    assert metrics["diff_analysis"]["git_available"] is True
    assert metrics["diff_analysis"]["changed_file_count"] == 0
    assert metrics["risk_findings"] == []


def test_check_command_records_failure_and_continues(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_config(
        tmp_path,
        ["python -c \"import sys; print('bad test'); sys.exit(3)\""],
        ["python -c \"print('lint still runs')\""],
        commit=True,
    )

    result = runner.invoke(app, ["check", "--project-root", str(tmp_path)])

    assert result.exit_code == 1

    metrics = latest_metrics(tmp_path)
    assert metrics["overall_status"] == "failed"
    assert metrics["score"] == 60
    assert metrics["risk_level"] == "high"
    assert metrics["summary"]["failed_commands"] == 1
    assert metrics["summary"]["passed_commands"] == 1
    assert [command["status"] for command in metrics["command_results"]] == [
        "failed",
        "passed",
    ]
    assert metrics["command_results"][0]["exit_code"] == 3
    assert "bad test" in metrics["command_results"][0]["stdout"]
    assert Path(metrics["log_path"]).exists()


def test_metrics_json_is_created(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_config(
        tmp_path,
        ["python -c \"print('ok')\""],
        ["python -c \"print('ok')\""],
        commit=True,
    )

    result = runner.invoke(app, ["check", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    metrics_files = list((tmp_path / ".vibebench" / "runs").glob("*/metrics.json"))
    log_files = list((tmp_path / ".vibebench" / "runs").glob("*/check.log"))
    assert len(metrics_files) == 1
    assert len(log_files) == 1


def test_score_logic_with_failed_commands() -> None:
    assert score_from_failures(0) == 100
    assert score_from_failures(1) == 60
    assert score_from_failures(3) == 0


def test_check_missing_config_has_helpful_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["check", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert (
        "No .vibebench/config.yaml found. Run 'vibebench init' first."
        in result.output
    )


def test_check_metrics_include_diff_analysis_and_findings(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_config(
        tmp_path,
        ["python -c \"print('ok')\""],
        ["python -c \"print('ok')\""],
        commit=True,
    )
    (tmp_path / ".env.local").write_text("TOKEN=value\n", encoding="utf-8")

    result = runner.invoke(app, ["check", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    metrics = latest_metrics(tmp_path)
    assert "diff_analysis" in metrics
    assert "risk_findings" in metrics
    assert metrics["diff_analysis"]["forbidden_paths_touched"] == [".env.local"]
    assert metrics["risk_findings"][0]["code"] == "forbidden_paths_touched"
    assert metrics["overall_status"] == "failed"
