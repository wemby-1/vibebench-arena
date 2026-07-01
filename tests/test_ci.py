import json
import subprocess
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.config import default_config_yaml

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_github_step_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent CI tests from writing to a real GitHub Actions summary."""
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


def config_path(root: Path) -> Path:
    return root / ".vibebench" / "config.yaml"


def workflow_path(root: Path) -> Path:
    return root / ".github" / "workflows" / "vibebench.yml"


def write_config(root: Path, test_command: str = "python -c 'print(1)'") -> None:
    config_path(root).parent.mkdir(parents=True, exist_ok=True)
    config = default_config_yaml()
    config = config.replace("pytest -q", test_command)
    config = config.replace("ruff check .", "python -c 'print(2)'")
    config_path(root).write_text(config, encoding="utf-8")


def init_git_repo(root: Path) -> None:
    """Create a clean git baseline for check runs."""
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
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=root,
        check=True,
        capture_output=True,
    )


def sample_metrics(
    *,
    status: str = "passed",
    score: int = 100,
    risk: str = "low",
    findings: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": "demo-project",
        "created_at": "2026-06-29T12:00:00Z",
        "overall_status": status,
        "score": score,
        "risk_level": risk,
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
        "risk_findings": findings or [],
        "summary": {
            "total_commands": 0,
            "passed_commands": 0,
            "failed_commands": 0,
            "total_findings": len(findings or []),
            "critical_findings": 0,
            "high_findings": 0,
            "warning_findings": 0,
            "info_findings": 0,
        },
    }


def write_run(
    project_root: Path,
    name: str = "20260629_120000",
    *,
    metrics: dict[str, object] | None = None,
    with_report_asset: bool = False,
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics or sample_metrics(), indent=2),
        encoding="utf-8",
    )
    (run_dir / "check.log").write_text("check log\n", encoding="utf-8")
    if with_report_asset:
        asset_dir = run_dir / "report" / "assets"
        asset_dir.mkdir(parents=True)
        asset_dir.joinpath("style.css").write_text("body {}\n", encoding="utf-8")
    return run_dir


def latest_run(root: Path) -> Path:
    return sorted((root / ".vibebench" / "runs").iterdir())[-1]


def zip_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return sorted(archive.namelist())


def test_ci_command_succeeds_on_clean_passing_run(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Final CI verdict: passed" in result.output
    run_dir = latest_run(tmp_path)
    assert run_dir.joinpath("metrics.json").exists()


def test_ci_command_creates_standard_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    run_dir = latest_run(tmp_path)
    assert run_dir.joinpath("report", "index.html").exists()
    assert run_dir.joinpath("pr-comment.md").exists()
    assert run_dir.joinpath("explain.md").exists()
    assert run_dir.joinpath("vibebench-bundle.zip").exists()
    assert run_dir.joinpath("export.json").exists()
    assert run_dir.joinpath("badge.json").exists()
    assert run_dir.joinpath("badge.md").exists()
    assert run_dir.joinpath("status-block.md").exists()
    assert run_dir.joinpath("trend.md").exists()
    assert run_dir.joinpath("trend.json").exists()
    assert run_dir.joinpath("manifest.json").exists()
    assert run_dir.joinpath("gate-summary.md").exists()
    assert run_dir.joinpath("github-step-summary.md").exists()


def test_ci_attempts_artifacts_when_gate_fails(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path, metrics=sample_metrics(score=70))

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 1
    assert "gate" in result.output
    assert "failed" in result.output
    assert run_dir.joinpath("report", "index.html").exists()
    assert run_dir.joinpath("pr-comment.md").exists()
    assert run_dir.joinpath("explain.md").exists()
    assert run_dir.joinpath("vibebench-bundle.zip").exists()
    assert run_dir.joinpath("export.json").exists()
    assert run_dir.joinpath("badge.json").exists()
    assert run_dir.joinpath("badge.md").exists()
    assert run_dir.joinpath("status-block.md").exists()
    assert run_dir.joinpath("trend.md").exists()
    assert run_dir.joinpath("trend.json").exists()
    assert run_dir.joinpath("manifest.json").exists()
    assert run_dir.joinpath("github-step-summary.md").exists()


def test_skip_flags_skip_artifact_generation(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-report",
            "--skip-pr-comment",
            "--skip-explain",
            "--skip-bundle",
            "--skip-export",
            "--skip-badge",
            "--skip-status-block",
            "--skip-trend",
            "--skip-manifest",
            "--skip-gh-summary",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("report", "index.html").exists()
    assert not run_dir.joinpath("pr-comment.md").exists()
    assert not run_dir.joinpath("explain.md").exists()
    assert not run_dir.joinpath("vibebench-bundle.zip").exists()
    assert not run_dir.joinpath("export.json").exists()
    assert not run_dir.joinpath("badge.json").exists()
    assert not run_dir.joinpath("badge.md").exists()
    assert not run_dir.joinpath("status-block.md").exists()
    assert not run_dir.joinpath("trend.md").exists()
    assert not run_dir.joinpath("trend.json").exists()
    assert not run_dir.joinpath("manifest.json").exists()
    assert not run_dir.joinpath("github-step-summary.md").exists()
    assert "skipped" in result.output


def test_bundle_include_report_assets_passes_through(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path, with_report_asset=True)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-report",
            "--bundle-include-report-assets",
        ],
    )

    assert result.exit_code == 0
    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "report/assets/style.css" in names


def test_bundle_strict_passes_through(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-report",
            "--skip-pr-comment",
            "--skip-explain",
            "--skip-export",
            "--skip-badge",
            "--skip-status-block",
            "--skip-trend",
            "--skip-gh-summary",
            "--bundle-strict",
        ],
    )

    assert result.exit_code == 1
    assert "bundle" in result.output
    assert "bundle" in result.output
    assert "failed" in result.output


def test_gate_override_flags_affect_gate_decision(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path, metrics=sample_metrics(score=70))

    failed = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )
    passed = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--min-score",
            "70",
            "--max-risk",
            "medium",
            "--allow-findings",
            "0",
        ],
    )

    assert failed.exit_code == 1
    assert passed.exit_code == 0


def test_no_require_status_passed_override(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(
        tmp_path,
        metrics=sample_metrics(status="failed", score=100, risk="low"),
    )

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--no-require-status-passed",
        ],
    )

    assert result.exit_code == 0


def test_run_dir_mode_does_not_create_fresh_check_run(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    run_dirs = list((tmp_path / ".vibebench" / "runs").iterdir())
    assert result.exit_code == 0
    assert run_dirs == [run_dir]
    assert "using --run-dir" in result.output


def test_ci_writes_only_to_explicit_github_summary_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)
    summary_file = tmp_path / "step-summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 0
    assert summary_file.exists()
    assert "# VibeBench Summary" in summary_file.read_text(encoding="utf-8")
    assert not run_dir.joinpath("github-step-summary.md").exists()


def test_invalid_run_dir_fails_clearly(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--run-dir", str(tmp_path / "x")],
    )

    assert result.exit_code == 1
    assert "Run directory does not exist" in result.output



def test_ci_runs_export_and_badge_before_bundle_and_summary(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 0
    assert run_dir.joinpath("export.json").exists()
    assert run_dir.joinpath("badge.json").exists()
    assert run_dir.joinpath("badge.md").exists()
    assert run_dir.joinpath("status-block.md").exists()
    assert run_dir.joinpath("trend.md").exists()
    assert run_dir.joinpath("trend.json").exists()
    assert run_dir.joinpath("manifest.json").exists()
    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "export.json" in names
    assert "badge.json" in names
    assert "badge.md" in names
    assert "status-block.md" in names
    assert "trend.md" in names
    assert "trend.json" in names
    assert "manifest.json" in names
    summary = run_dir.joinpath("github-step-summary.md").read_text(encoding="utf-8")
    assert "`export.json` (available)" in summary
    assert "`badge.json` (available)" in summary
    assert "`badge.md` (available)" in summary
    assert "`status-block.md` (available)" in summary
    assert "`trend.md` (available)" in summary
    assert "`trend.json` (available)" in summary
    assert "`manifest.json` (available)" in summary


def test_ci_skip_export_skips_export_generation(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-export",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("export.json").exists()
    assert "export" in result.output
    assert "skipped" in result.output


def test_ci_skip_badge_skips_badge_generation(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-badge",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("badge.json").exists()
    assert not run_dir.joinpath("badge.md").exists()
    assert "badge" in result.output
    assert "skipped" in result.output


def test_ci_skip_status_block_skips_status_block_generation(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-status-block",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("status-block.md").exists()
    assert "status-block" in result.output
    assert "skipped" in result.output


def test_ci_skip_trend_skips_trend_generation(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-trend",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("trend.md").exists()
    assert not run_dir.joinpath("trend.json").exists()
    assert "trend" in result.output
    assert "skipped" in result.output

def test_ci_runs_annotations_by_default(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(
        tmp_path,
        metrics=sample_metrics(
            findings=[
                {
                    "severity": "warning",
                    "code": "demo_warning",
                    "message": "Review this change.",
                    "paths": ["src/app.py"],
                }
            ]
        ),
    )

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--allow-findings",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert "annotate" in result.output
    assert "::warning" in result.output
    assert "demo_warning" in result.output


def test_ci_skip_annotate_suppresses_annotation_output(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(
        tmp_path,
        metrics=sample_metrics(
            findings=[
                {
                    "severity": "warning",
                    "code": "demo_warning",
                    "message": "Review this change.",
                    "paths": ["src/app.py"],
                }
            ]
        ),
    )

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--allow-findings",
            "1",
            "--skip-annotate",
        ],
    )

    assert result.exit_code == 0
    assert "annotate" in result.output
    assert "skipped" in result.output
    assert "::warning" not in result.output
    assert "demo_warning" not in result.output

def test_generated_init_workflow_uses_ci_command(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    workflow = workflow_path(tmp_path).read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert "python -m ruff check ." in workflow
    assert "python -m pytest -q" in workflow
    assert "python -m vibebench ci" in workflow
    assert "python -m vibebench check" not in workflow


def test_active_github_workflow_uses_ci_command() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python -m ruff check ." in workflow
    assert "python -m pytest -q" in workflow
    assert "python -m vibebench ci" in workflow
    assert "vibebench check" not in workflow


def test_ci_skip_manifest_skips_manifest_generation(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-manifest",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("manifest.json").exists()
    assert "manifest" in result.output
    assert "skipped" in result.output
