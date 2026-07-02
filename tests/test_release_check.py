import json
import subprocess
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from vibebench.bundle import create_bundle
from vibebench.cli import app
from vibebench.config import default_config_yaml
from vibebench.manifest import generate_manifest

runner = CliRunner()


def config_path(root: Path) -> Path:
    return root / ".vibebench" / "config.yaml"


def write_config(root: Path) -> None:
    config_path(root).parent.mkdir(parents=True, exist_ok=True)
    config = default_config_yaml()
    config = config.replace("pytest -q", "python -c 'print(1)'")
    config = config.replace("ruff check .", "python -c 'print(2)'")
    config_path(root).write_text(config, encoding="utf-8")


def init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=root,
        check=True,
        capture_output=True,
    )


def metrics() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": "release-demo",
        "created_at": "2026-07-02T00:00:00Z",
        "overall_status": "passed",
        "score": 100,
        "risk_level": "low",
        "command_results": [],
        "diff_analysis": {
            "git_available": True,
            "changed_files": [],
            "deleted_files": [],
            "added_files": [],
            "modified_files": [],
            "renamed_files": [],
            "test_files_changed": [],
            "tests_deleted": [],
            "forbidden_paths_touched": [],
            "secret_like_files_touched": [],
            "lockfiles_changed": [],
            "total_added_lines": 0,
            "total_deleted_lines": 0,
            "total_patch_lines": 0,
            "changed_file_count": 0,
            "warnings": [],
            "file_changes": [],
        },
        "risk_findings": [],
        "summary": {
            "total_commands": 0,
            "passed_commands": 0,
            "failed_commands": 0,
            "total_findings": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "warning_findings": 0,
            "info_findings": 0,
        },
    }


def create_ready_project(root: Path) -> Path:
    write_config(root)
    workflow = root / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text("name: CI\n", encoding="utf-8")
    run_dir = root / ".vibebench" / "runs" / "20260702_120000"
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text(
        json.dumps(metrics(), indent=2),
        encoding="utf-8",
    )
    run_dir.joinpath("report").mkdir()
    run_dir.joinpath("report", "index.html").write_text(
        "<html></html>",
        encoding="utf-8",
    )
    init_git_repo(root)
    create_bundle(root, run_dir)
    generate_manifest(root, run_dir)
    return run_dir


def git_status(root: Path) -> str:
    return subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout


def test_release_check_ready_case(tmp_path: Path) -> None:
    run_dir = create_ready_project(tmp_path)

    result = runner.invoke(app, ["release-check", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Release readiness:" in result.output
    assert "ready" in result.output
    assert run_dir.name in result.output


def test_release_check_json_output_is_pure(tmp_path: Path) -> None:
    run_dir = create_ready_project(tmp_path)

    result = runner.invoke(
        app,
        ["release-check", "--project-root", str(tmp_path), "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "ready"
    assert payload["project_root"] == str(tmp_path.resolve())
    assert payload["latest_run_id"] == run_dir.name
    assert payload["latest_run_dir"] == str(run_dir.resolve())
    assert all(
        set(check) == {"name", "status", "message"}
        for check in payload["checks"]
    )


def test_release_check_missing_config_fails(tmp_path: Path) -> None:
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["release-check", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "not-ready" in result.output
    assert "config" in result.output


def test_release_check_invalid_config_fails(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("project: [not-valid", encoding="utf-8")
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["release-check", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "not-ready" in result.output
    assert "config" in result.output


def test_release_check_missing_latest_run_fails(tmp_path: Path) -> None:
    write_config(tmp_path)
    workflow = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text("name: CI\n", encoding="utf-8")
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["release-check", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "not-ready" in result.output
    assert "latest_run" in result.output


def test_release_check_does_not_modify_tracked_files(tmp_path: Path) -> None:
    create_ready_project(tmp_path)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "ready"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    before = git_status(tmp_path)

    result = runner.invoke(app, ["release-check", "--project-root", str(tmp_path)])
    after = git_status(tmp_path)

    assert result.exit_code == 0
    assert before == ""
    assert after == ""


def test_release_check_help_exposes_command() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "release-check" in result.output


def test_release_check_manifest_drift_fails(tmp_path: Path) -> None:
    run_dir = create_ready_project(tmp_path)
    with zipfile.ZipFile(run_dir / "vibebench-bundle.zip", "a") as archive:
        archive.writestr("extra.txt", "x")

    result = runner.invoke(
        app,
        ["release-check", "--project-root", str(tmp_path), "--json"],
    )

    payload = json.loads(result.output)
    checks = {check["name"]: check for check in payload["checks"]}
    assert result.exit_code == 1
    assert payload["status"] == "not-ready"
    assert checks["manifest"]["status"] == "failed"
