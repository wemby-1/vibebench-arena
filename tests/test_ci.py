import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.config import default_config_yaml
from vibebench.manifest import check_manifest

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_github_step_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent CI tests from writing to a real GitHub Actions summary."""
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


def config_path(root: Path) -> Path:
    return root / ".vibebench" / "config.yaml"


def workflow_path(root: Path) -> Path:
    return root / ".github" / "workflows" / "vibebench.yml"


def write_config(root: Path, test_command: str | None = None) -> None:
    config_path(root).parent.mkdir(parents=True, exist_ok=True)
    selected_test_command = test_command or f"{sys.executable} -c 'print(1)'"
    config = default_config_yaml()
    config = config.replace("pytest -q", selected_test_command)
    config = config.replace("ruff check .", f"{sys.executable} -c 'print(2)'")
    config_path(root).write_text(config, encoding="utf-8")
    write_package_metadata(root)


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
version = "0.2.0"
readme = "README.md"
requires-python = ">=3.11"
license = { file = "LICENSE" }

[project.scripts]
vibebench = "vibebench.cli:main"
""".strip()
        + "\n",
        encoding="utf-8",
    )


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
    assert run_dir.joinpath("run-index.json").exists()
    assert run_dir.joinpath("run-index.md").exists()
    assert run_dir.joinpath("config-check.json").exists()
    assert run_dir.joinpath("config-check.md").exists()
    assert run_dir.joinpath("package-check.json").exists()
    assert run_dir.joinpath("package-check.md").exists()
    assert run_dir.joinpath("manifest.json").exists()
    assert "config-check" in result.output
    assert "manifest-check" in result.output
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
    assert run_dir.joinpath("run-index.json").exists()
    assert run_dir.joinpath("run-index.md").exists()
    assert run_dir.joinpath("config-check.json").exists()
    assert run_dir.joinpath("config-check.md").exists()
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
            "--skip-run-index",
            "--skip-config-check",
            "--skip-package-check",
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
    assert not run_dir.joinpath("run-index.json").exists()
    assert not run_dir.joinpath("run-index.md").exists()
    assert not run_dir.joinpath("config-check.json").exists()
    assert not run_dir.joinpath("config-check.md").exists()
    assert not run_dir.joinpath("package-check.json").exists()
    assert not run_dir.joinpath("package-check.md").exists()
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
    assert run_dir.joinpath("config-check.json").exists()
    assert run_dir.joinpath("config-check.md").exists()
    assert run_dir.joinpath("manifest.json").exists()
    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "export.json" in names
    assert "badge.json" in names
    assert "badge.md" in names
    assert "status-block.md" in names
    assert "trend.md" in names
    assert "trend.json" in names
    assert "config-check.json" in names
    assert "config-check.md" in names
    assert "manifest.json" in names
    summary = run_dir.joinpath("github-step-summary.md").read_text(encoding="utf-8")
    assert "`export.json` (available)" in summary
    assert "`badge.json` (available)" in summary
    assert "`badge.md` (available)" in summary
    assert "`status-block.md` (available)" in summary
    assert "`trend.md` (available)" in summary
    assert "`trend.json` (available)" in summary
    assert "`manifest.json` (available)" in summary
    assert result.output.index("manifest") < result.output.index("bundle")
    assert result.output.index("manifest-check") < result.output.index("bundle")

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

def test_ci_dry_run_does_not_create_run_or_execute_commands(tmp_path: Path) -> None:
    marker = tmp_path / "executed.txt"
    command = (
        "python -c "
        f"'from pathlib import Path; Path({str(marker)!r}).write_text(\"ran\")'"
    )
    write_config(tmp_path, command)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path), "--dry-run"])

    assert result.exit_code == 0
    assert "VibeBench CI plan" in result.output
    assert "Dry run" in result.output
    assert "Final CI verdict: planned" in result.output
    assert not marker.exists()
    assert not (tmp_path / ".vibebench" / "runs").exists()


def test_ci_dry_run_human_output_includes_ordered_steps(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path), "--dry-run"])

    assert result.exit_code == 0
    expected_steps = [
        "check",
        "gate",
        "config-check",
        "package-check",
        "report",
        "pr-comment",
        "explain",
        "export",
        "badge",
        "status-block",
        "trend",
        "run-index",
        "manifest",
        "manifest-check",
        "release-check",
        "annotate",
        "bundle",
        "gh-summary",
    ]
    positions = [result.output.index(step) for step in expected_steps]
    assert positions == sorted(positions)


def test_ci_dry_run_json_outputs_plan_payload(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "planned"
    assert payload["dry_run"] is True
    assert payload["run_dir"] is None
    assert payload["run_id"] is None
    assert [step["name"] for step in payload["steps"]] == [
        "check",
        "gate",
        "config-check",
        "package-check",
        "report",
        "pr-comment",
        "explain",
        "export",
        "badge",
        "status-block",
        "trend",
        "run-index",
        "manifest",
        "manifest-check",
        "release-check",
        "annotate",
        "bundle",
        "gh-summary",
    ]
    for step in payload["steps"]:
        assert set(step) == {
            "name",
            "status",
            "exit_code",
            "artifact",
            "message",
            "duration_seconds",
        }
        assert step["status"] == "planned"
        assert step["exit_code"] is None
        assert step["artifact"] is None
        assert step["duration_seconds"] is None


def test_ci_plan_alias_json_outputs_plan_payload(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--plan", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "planned"
    assert payload["dry_run"] is True


def test_ci_dry_run_skip_flags_mark_steps_skipped(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-manifest",
            "--skip-config-check",
            "--skip-package-check",
            "--skip-bundle",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["config-check"]["status"] == "skipped"
    assert steps["config-check"]["message"] == "Skipped by --skip-config-check"
    assert steps["package-check"]["status"] == "skipped"
    assert steps["package-check"]["message"] == "Skipped by --skip-package-check"
    assert steps["manifest"]["status"] == "skipped"
    assert steps["manifest-check"]["status"] == "skipped"
    assert steps["manifest"]["message"] == "Skipped by --skip-manifest"
    assert steps["manifest-check"]["message"] == "Skipped by --skip-manifest"
    assert steps["bundle"]["status"] == "skipped"
    assert steps["bundle"]["message"] == "Skipped by --skip-bundle"
    assert steps["check"]["status"] == "planned"


def test_ci_dry_run_json_output_writes_plan_file(tmp_path: Path) -> None:
    write_config(tmp_path)
    output_path = tmp_path / "ci-plan.json"

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--json-output",
            str(output_path),
        ],
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert payload["status"] == "planned"
    assert payload["dry_run"] is True
    assert "VibeBench CI plan" in result.output
    assert "CI JSON:" in result.output


def test_ci_dry_run_json_and_output_use_same_payload(tmp_path: Path) -> None:
    write_config(tmp_path)
    output_path = tmp_path / "ci-plan.json"

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--json",
            "--json-output",
            str(output_path),
        ],
    )

    stdout_payload = json.loads(result.output)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert stdout_payload == file_payload


def test_ci_dry_run_write_plan_creates_plan_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--write-plan"],
    )

    assert result.exit_code == 0
    plan_dir = latest_run(tmp_path)
    assert plan_dir.name.endswith("_plan")
    assert plan_dir.joinpath("metrics.json").exists()
    assert plan_dir.joinpath("ci-plan.json").exists()
    assert plan_dir.joinpath("ci-plan.md").exists()
    payload = json.loads(plan_dir.joinpath("ci-plan.json").read_text())
    markdown = plan_dir.joinpath("ci-plan.md").read_text(encoding="utf-8")
    assert payload["status"] == "planned"
    assert payload["dry_run"] is True
    assert "# VibeBench CI Plan" in markdown
    assert "| check | planned |" in markdown
    assert "CI plan directory:" in result.output


def test_ci_dry_run_write_plan_json_stdout_stays_clean(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--write-plan",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    plan_dir = latest_run(tmp_path)
    file_payload = json.loads(plan_dir.joinpath("ci-plan.json").read_text())
    assert result.exit_code == 0
    assert payload == file_payload
    assert "CI plan directory" not in result.output
    assert plan_dir.joinpath("ci-plan.md").exists()


def test_ci_dry_run_plan_output_overrides(tmp_path: Path) -> None:
    write_config(tmp_path)
    json_output = tmp_path / "custom-plan.json"
    markdown_output = tmp_path / "custom-plan.md"

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--plan-json-output",
            str(json_output),
            "--plan-summary-output",
            str(markdown_output),
        ],
    )

    assert result.exit_code == 0
    assert json.loads(json_output.read_text())["status"] == "planned"
    assert "# VibeBench CI Plan" in markdown_output.read_text(encoding="utf-8")
    assert not (tmp_path / ".vibebench" / "runs").exists()


def test_ci_dry_run_written_plan_reflects_skip_flags(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--write-plan",
            "--skip-bundle",
            "--skip-manifest",
        ],
    )

    assert result.exit_code == 0
    plan_dir = latest_run(tmp_path)
    payload = json.loads(plan_dir.joinpath("ci-plan.json").read_text())
    markdown = plan_dir.joinpath("ci-plan.md").read_text(encoding="utf-8")
    steps = {step["name"]: step for step in payload["steps"]}
    assert steps["bundle"]["status"] == "skipped"
    assert steps["manifest"]["status"] == "skipped"
    assert steps["manifest-check"]["status"] == "skipped"
    assert "| bundle | skipped |" in markdown
    assert "Skipped by --skip-manifest" in markdown


def test_ci_plan_artifacts_are_discoverable(tmp_path: Path) -> None:
    write_config(tmp_path)
    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--write-plan"],
    )
    assert result.exit_code == 0
    plan_dir = latest_run(tmp_path)

    artifacts = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )
    artifact_payload = json.loads(artifacts.output)
    artifact_map = {item["name"]: item for item in artifact_payload["artifacts"]}
    assert artifacts.exit_code == 0
    assert artifact_map["ci-plan.json"]["available"] is True
    assert artifact_map["ci-plan.md"]["available"] is True

    latest = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "ci-plan-json",
            "--path-only",
        ],
    )
    assert latest.exit_code == 0
    assert latest.output.strip().endswith("ci-plan.json")

    bundle = runner.invoke(
        app,
        ["bundle", "--project-root", str(tmp_path), "--run-dir", str(plan_dir)],
    )
    assert bundle.exit_code == 0
    names = zip_names(plan_dir / "vibebench-bundle.zip")
    assert "ci-plan.json" in names
    assert "ci-plan.md" in names

    manifest = runner.invoke(
        app,
        ["manifest", "--project-root", str(tmp_path), "--run-dir", str(plan_dir)],
    )
    assert manifest.exit_code == 0
    manifest_payload = json.loads(plan_dir.joinpath("manifest.json").read_text())
    manifest_artifacts = {item["name"]: item for item in manifest_payload["artifacts"]}
    assert manifest_artifacts["ci-plan.json"]["available"] is True
    assert manifest_artifacts["ci-plan.md"]["available"] is True


def test_ci_plan_output_options_require_plan_mode(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--write-plan"],
    )

    assert result.exit_code == 1
    assert "require --dry-run or --plan" in result.output


def test_ci_json_outputs_parseable_payload(tmp_path: Path) -> None:
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
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert payload["run_dir"] == str(run_dir.resolve())
    assert payload["run_id"] == run_dir.name
    step_names = [step["name"] for step in payload["steps"]]
    assert step_names == [
        "check",
        "gate",
        "config-check",
        "package-check",
        "report",
        "pr-comment",
        "explain",
        "export",
        "badge",
        "status-block",
        "trend",
        "run-index",
        "manifest",
        "manifest-check",
        "release-check",
        "annotate",
        "bundle",
        "gh-summary",
    ]
    for step in payload["steps"]:
        assert set(step) == {
            "name",
            "status",
            "exit_code",
            "artifact",
            "message",
            "duration_seconds",
        }
        assert step["status"] in {"passed", "failed", "skipped"}
        assert isinstance(step["exit_code"], int)
        assert isinstance(step["duration_seconds"], int | float)
        assert step["duration_seconds"] >= 0


def test_ci_json_output_writes_payload_file(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)
    output_path = tmp_path / "ci-result.json"

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--json-output",
            str(output_path),
        ],
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert output_path.exists()
    assert payload["status"] == "passed"
    assert payload["run_id"] == run_dir.name
    assert "Final CI verdict: passed" in result.output
    assert "CI JSON:" in result.output


def test_ci_json_and_json_output_use_same_payload(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)
    output_path = tmp_path / "ci-result.json"

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--json",
            "--json-output",
            str(output_path),
        ],
    )

    stdout_payload = json.loads(result.output)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert stdout_payload == file_payload


def test_ci_json_reflects_skipped_steps(tmp_path: Path) -> None:
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
            "--skip-badge",
            "--skip-status-block",
            "--skip-trend",
            "--skip-config-check",
            "--skip-manifest",
            "--skip-annotate",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    for name in [
        "export",
        "badge",
        "status-block",
        "trend",
        "config-check",
        "manifest",
        "manifest-check",
        "annotate",
    ]:
        assert steps[name]["status"] == "skipped"
        assert steps[name]["exit_code"] == 0
        assert steps[name]["artifact"] is None
        assert steps[name]["message"] == "skipped by flag"


def test_ci_json_reports_failed_required_step(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path, metrics=sample_metrics(score=70))

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert steps["gate"]["status"] == "failed"
    assert steps["gate"]["exit_code"] == 1


def test_ci_json_suppresses_annotation_stdout(tmp_path: Path) -> None:
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
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert "::warning" not in result.output
    assert "demo_warning" not in result.output
    steps = {step["name"]: step for step in payload["steps"]}
    assert steps["annotate"]["status"] == "passed"


def test_generated_init_workflow_uses_ci_command(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    workflow = workflow_path(tmp_path).read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert "python -m ruff check ." in workflow
    assert "python -m pytest -q" in workflow
    assert "python -m vibebench ci" in workflow
    assert "pull-requests: write" in workflow
    assert "if: github.event_name == 'pull_request'" in workflow
    assert "python -m vibebench pr-comment --post --no-fail-on-error" in workflow
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in workflow
    assert "python -m vibebench check" not in workflow

def test_active_github_workflow_uses_ci_command() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python -m ruff check ." in workflow
    assert "python -m pytest -q" in workflow
    assert "python -m vibebench ci" in workflow
    assert "pull-requests: write" in workflow
    assert "if: github.event_name == 'pull_request'" in workflow
    assert "python -m vibebench pr-comment --post --no-fail-on-error" in workflow
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in workflow
    assert "actions/upload-artifact@v7" in workflow
    assert "name: vibebench-run-artifacts" in workflow
    assert ".vibebench/runs/**/metrics.json" in workflow
    assert ".vibebench/runs/**/release-check.md" in workflow
    assert ".vibebench/runs/**/package-check.json" in workflow
    assert ".vibebench/runs/**/package-check.md" in workflow
    assert "vibebench check" not in workflow

def test_example_github_workflow_posts_pr_comments_safely() -> None:
    workflow = Path("docs/examples/github-actions/vibebench.yml").read_text(
        encoding="utf-8"
    )

    assert "pull-requests: write" in workflow
    assert "if: github.event_name == 'pull_request'" in workflow
    assert "python -m vibebench pr-comment --post --no-fail-on-error" in workflow
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in workflow
    assert "actions/upload-artifact@v7" in workflow

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
    assert "manifest-check" in result.output
    assert "skipped" in result.output

def test_ci_skip_config_check_skips_config_check_generation(tmp_path: Path) -> None:
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
            "--skip-config-check",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("config-check.json").exists()
    assert not run_dir.joinpath("config-check.md").exists()
    assert "config-check" in result.output
    assert "skipped" in result.output


def test_ci_dry_run_skip_run_index_marks_step_skipped(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-run-index",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["run-index"]["status"] == "skipped"
    assert steps["run-index"]["message"] == "Skipped by --skip-run-index"


def test_ci_skip_run_index_skips_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--skip-run-index",
        ],
    )

    assert result.exit_code == 0
    run_dir = latest_run(tmp_path)
    assert not run_dir.joinpath("run-index.json").exists()
    assert not run_dir.joinpath("run-index.md").exists()
    assert "run-index" in result.output


def test_ci_dry_run_skip_package_check_marks_step_skipped(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-package-check",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["package-check"]["status"] == "skipped"
    assert steps["package-check"]["message"] == "Skipped by --skip-package-check"


def test_ci_accepts_skip_package_check_option(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--skip-package-check"],
    )

    assert result.exit_code == 0
    assert "package-check" in result.output
    assert "skipped" in result.output


def test_ci_skip_package_check_skips_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--skip-package-check",
        ],
    )

    assert result.exit_code == 0
    run_dir = latest_run(tmp_path)
    assert not run_dir.joinpath("package-check.json").exists()
    assert not run_dir.joinpath("package-check.md").exists()
    assert "package-check" in result.output


def test_ci_dry_run_skip_release_check_marks_step_skipped(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-release-check",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["release-check"]["status"] == "skipped"
    assert steps["release-check"]["message"] == "Skipped by --skip-release-check"


def test_ci_accepts_skip_release_check_option(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--skip-release-check"],
    )

    assert result.exit_code == 0
    assert "release-check" in result.output
    assert "skipped" in result.output


def test_ci_refreshes_manifest_after_late_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    manifest_check = check_manifest(tmp_path, latest_run(tmp_path))
    assert manifest_check.passed is True


def test_ci_generates_release_check_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    run_dir = latest_run(tmp_path)
    assert run_dir.joinpath("release-check.json").exists()
    assert run_dir.joinpath("release-check.md").exists()
    payload = json.loads(run_dir.joinpath("release-check.json").read_text())
    assert payload["status"] in {"ready", "not-ready"}


def test_ci_skip_release_check_skips_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--skip-release-check",
        ],
    )

    assert result.exit_code == 0
    run_dir = latest_run(tmp_path)
    assert not run_dir.joinpath("release-check.json").exists()
    assert not run_dir.joinpath("release-check.md").exists()
    assert "release-check" in result.output


def test_ci_bundle_includes_release_check_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    run_dir = latest_run(tmp_path)
    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "package-check.json" in names
    assert "package-check.md" in names
    assert "run-index.json" in names
    assert "run-index.md" in names
    assert "release-check.json" in names
    assert "release-check.md" in names
