import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.history import get_history

runner = CliRunner()


def metrics_payload(
    *,
    status: str = "passed",
    score: int = 100,
    risk: str = "low",
    changed_files: int = 0,
    patch_lines: int = 0,
    findings: int = 0,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": "demo-project",
        "created_at": "2026-06-27T12:00:00Z",
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
            "total_patch_lines": patch_lines,
            "changed_file_count": changed_files,
            "warnings": [],
            "file_changes": [],
        },
        "risk_findings": [
            {
                "severity": "warning",
                "code": "example",
                "message": "example",
                "paths": [],
            }
            for _ in range(findings)
        ],
        "summary": {
            "total_commands": 2,
            "passed_commands": 2,
            "failed_commands": 0,
            "total_findings": findings,
            "critical_findings": 0,
            "high_findings": 0,
            "warning_findings": findings,
            "info_findings": 0,
        },
        "run_dir": "",
        "metrics_path": "",
        "log_path": "",
    }


def write_run(
    runs_dir: Path,
    name: str,
    payload: dict[str, object] | None = None,
) -> Path:
    run_dir = runs_dir / name
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics = payload or metrics_payload()
    metrics["run_dir"] = str(run_dir)
    metrics["metrics_path"] = str(run_dir / "metrics.json")
    metrics["log_path"] = str(run_dir / "check.log")
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )
    return run_dir


def test_history_lists_newest_runs_first_with_limit(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".vibebench" / "runs"
    write_run(runs_dir, "20260627_120000", metrics_payload(score=90))
    latest = write_run(runs_dir, "20260627_130000", metrics_payload(score=100))

    result = get_history(tmp_path, limit=1)

    assert [run.run_id for run in result.runs] == [latest.name]
    assert result.runs[0].score == 100


def test_history_records_artifact_presence(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".vibebench" / "runs"
    run_dir = write_run(runs_dir, "20260627_120000")
    (run_dir / "report").mkdir()
    (run_dir / "report" / "index.html").write_text("html", encoding="utf-8")
    (run_dir / "pr-comment.md").write_text("comment", encoding="utf-8")
    (run_dir / "github-step-summary.md").write_text("summary", encoding="utf-8")
    (run_dir / "compare.md").write_text("compare", encoding="utf-8")

    result = get_history(tmp_path)
    row = result.runs[0]

    assert row.has_report is True
    assert row.has_pr_comment is True
    assert row.has_github_summary is True
    assert row.has_compare is True


def test_history_cli_empty_runs_is_successful(tmp_path: Path) -> None:
    result = runner.invoke(app, ["history", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "No VibeBench runs found" in result.output


def test_history_cli_supports_runs_dir(tmp_path: Path) -> None:
    custom_runs = tmp_path / "custom-runs"
    write_run(
        custom_runs,
        "20260627_120000",
        metrics_payload(changed_files=3, patch_lines=24, findings=2),
    )

    result = runner.invoke(
        app,
        [
            "history",
            "--project-root",
            str(tmp_path),
            "--runs-dir",
            str(custom_runs),
        ],
    )

    assert result.exit_code == 0
    assert "20260627_120000" in result.output
    assert "24" in result.output


def test_history_skips_corrupt_metrics_when_valid_runs_exist(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".vibebench" / "runs"
    write_run(runs_dir, "20260627_120000")
    corrupt = runs_dir / "20260627_130000"
    corrupt.mkdir(parents=True)
    (corrupt / "metrics.json").write_text("{bad json", encoding="utf-8")

    result = runner.invoke(app, ["history", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Warning:" in result.output
    assert "20260627_120000" in result.output


def test_history_fails_when_all_metrics_are_corrupt(tmp_path: Path) -> None:
    corrupt = tmp_path / ".vibebench" / "runs" / "20260627_120000"
    corrupt.mkdir(parents=True)
    (corrupt / "metrics.json").write_text("{bad json", encoding="utf-8")

    result = runner.invoke(app, ["history", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "No valid VibeBench runs found" in result.output


def test_history_fails_for_invalid_runs_dir(tmp_path: Path) -> None:
    missing = tmp_path / "missing-runs"

    result = runner.invoke(
        app,
        [
            "history",
            "--project-root",
            str(tmp_path),
            "--runs-dir",
            str(missing),
        ],
    )

    assert result.exit_code == 1
    assert "Runs directory does not exist" in result.output


def test_history_fails_for_invalid_limit(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["history", "--project-root", str(tmp_path), "--limit", "0"],
    )

    assert result.exit_code == 1
    assert "--limit must be greater than 0" in result.output
