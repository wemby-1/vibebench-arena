import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.compare import (
    compare_runs,
    find_comparable_runs,
    load_run_snapshot,
    verdict_for,
)
from vibebench.report import ReportError

runner = CliRunner()


def metrics_payload(
    *,
    status: str = "passed",
    score: int = 100,
    risk: str = "low",
    total_commands: int = 2,
    passed_commands: int = 2,
    failed_commands: int = 0,
    changed_files: int = 0,
    added_lines: int = 0,
    deleted_lines: int = 0,
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
            "total_added_lines": added_lines,
            "total_deleted_lines": deleted_lines,
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
            "total_commands": total_commands,
            "passed_commands": passed_commands,
            "failed_commands": failed_commands,
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
    project_root: Path,
    name: str,
    payload: dict[str, object] | None = None,
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / name
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


def test_find_comparable_runs_uses_only_runs_with_metrics(tmp_path: Path) -> None:
    first = write_run(tmp_path, "20260627_120000")
    missing_metrics = tmp_path / ".vibebench" / "runs" / "20260627_130000"
    missing_metrics.mkdir(parents=True)
    second = write_run(tmp_path, "20260627_140000")

    assert find_comparable_runs(tmp_path) == [first, second]


def test_compare_latest_against_previous_writes_markdown(tmp_path: Path) -> None:
    write_run(tmp_path, "20260627_120000", metrics_payload(score=92, risk="medium"))
    current = write_run(tmp_path, "20260627_130000", metrics_payload(score=100))

    result = compare_runs(tmp_path)

    compare_path = current / "compare.md"
    markdown = compare_path.read_text(encoding="utf-8")
    assert result.output_path == compare_path
    assert result.verdict == "improved"
    assert "# VibeBench Compare" in markdown
    assert "| VibeScore | 92 | 100 | +8 |" in markdown
    assert "Quality improved compared with the previous run." in markdown


def test_compare_explicit_run_dirs(tmp_path: Path) -> None:
    base = write_run(tmp_path, "20260627_120000", metrics_payload(score=100))
    current = write_run(
        tmp_path,
        "20260627_130000",
        metrics_payload(score=60, risk="high", findings=1),
    )

    result = compare_runs(tmp_path, current_run=current, base_run=base)

    assert result.verdict == "regressed"
    assert result.score_delta == -40
    assert result.output_path == current / "compare.md"


def test_compare_cli_supports_explicit_run_dirs(tmp_path: Path) -> None:
    base = write_run(tmp_path, "20260627_120000", metrics_payload(score=90))
    current = write_run(tmp_path, "20260627_130000", metrics_payload(score=90))

    result = runner.invoke(
        app,
        [
            "compare",
            "--project-root",
            str(tmp_path),
            "--base-run",
            str(base),
            "--current-run",
            str(current),
        ],
    )

    assert result.exit_code == 0
    assert "Verdict:" in result.output
    assert "stable" in result.output
    assert (current / "compare.md").exists()


def test_compare_requires_two_runs_without_explicit_dirs(tmp_path: Path) -> None:
    write_run(tmp_path, "20260627_120000")

    result = runner.invoke(app, ["compare", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "Need at least two VibeBench runs with metrics.json" in result.output


def test_invalid_explicit_run_dir_has_helpful_error(tmp_path: Path) -> None:
    base = tmp_path / ".vibebench" / "runs" / "20260627_120000"
    base.mkdir(parents=True)
    current = write_run(tmp_path, "20260627_130000")

    with pytest.raises(ReportError, match="No metrics.json found"):
        compare_runs(tmp_path, current_run=current, base_run=base)


def test_verdict_rules_handle_unknown_risk_without_crashing(tmp_path: Path) -> None:
    base_dir = write_run(tmp_path, "20260627_120000", metrics_payload(risk="unknown"))
    current_dir = write_run(tmp_path, "20260627_130000", metrics_payload(score=100))
    base = load_run_snapshot(base_dir)
    current = load_run_snapshot(current_dir)

    assert verdict_for(base, current) == "stable"
