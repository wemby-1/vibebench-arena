import json
import subprocess
import sys
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from vibebench.artifacts import collect_artifact_inventory
from vibebench.bundle import create_bundle
from vibebench.cli import app
from vibebench.config import default_config_yaml
from vibebench.manifest import generate_manifest
from vibebench.release_check import (
    run_release_check,
    write_release_check_json,
    write_release_check_summary,
)

runner = CliRunner()


def config_path(root: Path) -> Path:
    return root / ".vibebench" / "config.yaml"


def write_config(root: Path) -> None:
    config_path(root).parent.mkdir(parents=True, exist_ok=True)
    config = default_config_yaml()
    config = config.replace("pytest -q", f"{sys.executable} -c 'print(1)'")
    config = config.replace("ruff check .", f"{sys.executable} -c 'print(2)'")
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


def write_package_metadata(root: Path) -> None:
    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    root.joinpath("README.md").write_text("# Demo\n", encoding="utf-8")
    root.joinpath("README.zh-CN.md").write_text("# Demo\n", encoding="utf-8")
    root.joinpath("LICENSE").write_text("Apache-2.0\n", encoding="utf-8")
    docs.joinpath("quickstart.md").write_text("# Quickstart\n", encoding="utf-8")
    docs.joinpath("github-actions.md").write_text("# Actions\n", encoding="utf-8")
    root.joinpath("ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    root.joinpath("pyproject.toml").write_text(
        """
[project]
name = "vibebench-arena"
version = "0.3.0"
readme = "README.md"
requires-python = ">=3.11"
license = { file = "LICENSE" }

[project.scripts]
vibebench = "vibebench.cli:main"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def create_ready_project(root: Path) -> Path:
    write_config(root)
    write_package_metadata(root)
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
    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["run_index"]["status"] == "passed"
    assert checks["compare"]["status"] == "passed"
    assert "insufficient data" in checks["compare"]["message"]


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

def test_release_check_write_json(tmp_path: Path) -> None:
    create_ready_project(tmp_path)
    output_path = tmp_path / "release-check.json"

    result = runner.invoke(
        app,
        [
            "release-check",
            "--project-root",
            str(tmp_path),
            "--write-json",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "ready"
    assert payload["project_root"] == str(tmp_path.resolve())


def test_release_check_write_summary(tmp_path: Path) -> None:
    create_ready_project(tmp_path)
    output_path = tmp_path / "release-check.md"

    result = runner.invoke(
        app,
        [
            "release-check",
            "--project-root",
            str(tmp_path),
            "--write-summary",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    content = output_path.read_text(encoding="utf-8")
    assert "# VibeBench Release Check" in content
    assert "Release" in content
    assert "ready" in content


def test_release_check_json_stdout_stays_pure_when_writing_json(
    tmp_path: Path,
) -> None:
    create_ready_project(tmp_path)
    output_path = tmp_path / "release-check.json"

    result = runner.invoke(
        app,
        [
            "release-check",
            "--project-root",
            str(tmp_path),
            "--json",
            "--write-json",
            str(output_path),
        ],
    )

    stdout_payload = json.loads(result.output)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert stdout_payload == file_payload
    assert stdout_payload["status"] == "ready"


def test_release_check_write_summary_rejects_missing_parent(
    tmp_path: Path,
) -> None:
    create_ready_project(tmp_path)
    output_path = tmp_path / "missing" / "release-check.md"

    result = runner.invoke(
        app,
        [
            "release-check",
            "--project-root",
            str(tmp_path),
            "--write-summary",
            str(output_path),
        ],
    )

    assert result.exit_code == 1
    assert "Output parent directory does not exist" in result.output


def write_release_check_artifacts_for_test(
    root: Path,
    run_dir: Path,
) -> None:
    result = run_release_check(root)
    write_release_check_json(result, run_dir / "release-check.json")
    write_release_check_summary(result, run_dir / "release-check.md")


def test_release_check_artifacts_are_registered_in_inventory(
    tmp_path: Path,
) -> None:
    run_dir = create_ready_project(tmp_path)
    write_release_check_artifacts_for_test(tmp_path, run_dir)

    inventory = collect_artifact_inventory(tmp_path, run_dir)
    items = {artifact.name: artifact for artifact in inventory.artifacts}

    assert items["release-check.json"].available is True
    assert items["release-check.md"].available is True


def test_release_check_latest_artifact_lookup(
    tmp_path: Path,
) -> None:
    run_dir = create_ready_project(tmp_path)
    write_release_check_artifacts_for_test(tmp_path, run_dir)

    json_result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "release-check-json",
            "--path-only",
        ],
    )
    md_result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "release-check-md",
            "--path-only",
        ],
    )

    assert json_result.exit_code == 0
    assert "release-check.json" in json_result.output
    assert run_dir.name in json_result.output
    assert md_result.exit_code == 0
    assert "release-check.md" in md_result.output
    assert run_dir.name in md_result.output


def test_release_check_bundle_includes_written_artifacts(
    tmp_path: Path,
) -> None:
    run_dir = create_ready_project(tmp_path)
    write_release_check_artifacts_for_test(tmp_path, run_dir)

    create_bundle(tmp_path, run_dir)

    with zipfile.ZipFile(run_dir / "vibebench-bundle.zip") as archive:
        names = set(archive.namelist())

    assert "release-check.json" in names
    assert "release-check.md" in names


def test_release_check_manifest_lists_written_artifacts(
    tmp_path: Path,
) -> None:
    run_dir = create_ready_project(tmp_path)
    write_release_check_artifacts_for_test(tmp_path, run_dir)

    result = generate_manifest(tmp_path, run_dir)
    artifacts = {
        item["name"]: item
        for item in result.payload["artifacts"]
    }

    assert artifacts["release-check.json"]["available"] is True
    assert artifacts["release-check.md"]["available"] is True
