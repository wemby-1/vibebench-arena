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
    assert "# VibeBench Run Comparison" in markdown
    assert "| VibeScore | 92 | 100 | +8 |" in markdown
    assert "Quality improved compared with the base run." in markdown
    assert (current / "compare.json").exists()


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


def test_compare_reports_insufficient_data_successfully(tmp_path: Path) -> None:
    write_run(tmp_path, "20260627_120000")

    result = runner.invoke(app, ["compare", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "insufficient-data" in result.output
    assert "Need at least two valid VibeBench runs" in result.output


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


def test_compare_cli_json_output_is_clean(tmp_path: Path) -> None:
    write_run(tmp_path, "20260627_120000", metrics_payload(score=90))
    write_run(tmp_path, "20260627_130000", metrics_payload(score=95))

    result = runner.invoke(app, ["compare", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["verdict"] == "improved"
    assert payload["score_delta"] == 5
    assert payload["base_run_id"] == "20260627_120000"
    assert payload["head_run_id"] == "20260627_130000"


def test_compare_cli_write_json(tmp_path: Path) -> None:
    write_run(tmp_path, "20260627_120000", metrics_payload(score=90))
    write_run(tmp_path, "20260627_130000", metrics_payload(score=95))
    output = tmp_path / "compare-output.json"

    result = runner.invoke(
        app,
        [
            "compare",
            "--project-root",
            str(tmp_path),
            "--write-json",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["score_delta"] == 5


def test_compare_cli_write_summary(tmp_path: Path) -> None:
    write_run(tmp_path, "20260627_120000", metrics_payload(score=90))
    write_run(tmp_path, "20260627_130000", metrics_payload(score=95))
    output = tmp_path / "compare-output.md"

    result = runner.invoke(
        app,
        [
            "compare",
            "--project-root",
            str(tmp_path),
            "--write-summary",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "# VibeBench Run Comparison" in output.read_text(encoding="utf-8")


def test_compare_json_stdout_stays_clean_with_write_json(tmp_path: Path) -> None:
    write_run(tmp_path, "20260627_120000", metrics_payload(score=90))
    write_run(tmp_path, "20260627_130000", metrics_payload(score=95))
    output = tmp_path / "compare-output.json"

    result = runner.invoke(
        app,
        [
            "compare",
            "--project-root",
            str(tmp_path),
            "--json",
            "--write-json",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["score_delta"] == 5
    assert json.loads(output.read_text(encoding="utf-8"))["score_delta"] == 5


def test_compare_skips_corrupt_and_partial_old_runs(tmp_path: Path) -> None:
    partial = tmp_path / ".vibebench" / "runs" / "20260627_110000"
    partial.mkdir(parents=True)
    corrupt = tmp_path / ".vibebench" / "runs" / "20260627_115000"
    corrupt.mkdir(parents=True)
    corrupt.joinpath("metrics.json").write_text("{nope", encoding="utf-8")
    write_run(tmp_path, "20260627_120000", metrics_payload(score=90))
    write_run(tmp_path, "20260627_130000", metrics_payload(score=95))

    result = runner.invoke(app, ["compare", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["verdict"] == "improved"
    assert len(payload["skipped_runs"]) == 2


def test_compare_status_and_artifact_deltas(tmp_path: Path) -> None:
    base_payload = metrics_payload(score=90, risk="medium", findings=1)
    base_payload["command_results"] = [{"command": "pytest", "status": "failed"}]
    head_payload = metrics_payload(score=95, risk="low", findings=0)
    head_payload["command_results"] = [{"command": "pytest", "status": "passed"}]
    base = write_run(tmp_path, "20260627_120000", base_payload)
    head = write_run(tmp_path, "20260627_130000", head_payload)
    base.joinpath("compare.md").write_text("old\n", encoding="utf-8")

    result = compare_runs(tmp_path, base_run=base, head_run=head)

    assert result.score_delta == 5
    assert result.risk_level_change == "medium -> low"
    assert result.risk_findings_delta == -1
    assert result.command_status_changes[0].base_status == "failed"
    assert result.command_status_changes[0].head_status == "passed"
    assert any(
        item.artifact == "compare.md"
        and item.base_available
        and not item.head_available
        for item in result.artifact_availability_changes
    )


def test_compare_supports_run_ids_and_runs_dir(tmp_path: Path) -> None:
    runs_dir = tmp_path / "custom-runs"
    base = runs_dir / "base"
    head = runs_dir / "head"
    for run_dir, score in [(base, 90), (head, 95)]:
        run_dir.mkdir(parents=True)
        run_dir.joinpath("metrics.json").write_text(
            json.dumps(metrics_payload(score=score)),
            encoding="utf-8",
        )

    result = runner.invoke(
        app,
        [
            "compare",
            "--project-root",
            str(tmp_path),
            "--runs-dir",
            str(runs_dir),
            "--base",
            "base",
            "--head",
            "head",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["score_delta"] == 5
