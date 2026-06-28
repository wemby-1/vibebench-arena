import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.baseline import baseline_file, set_baseline
from vibebench.cli import app
from vibebench.compare import compare_runs

runner = CliRunner()


def metrics_payload(
    *,
    project: str = "demo-project",
    status: str = "passed",
    score: int = 100,
    risk: str = "low",
    changed_files: int = 0,
    patch_lines: int = 0,
    findings: int = 0,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": project,
        "created_at": "2026-06-28T12:00:00Z",
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


def test_no_baseline_exists_exits_zero(tmp_path: Path) -> None:
    result = runner.invoke(app, ["baseline", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "No baseline saved" in result.output


def test_baseline_set_latest_writes_metadata(tmp_path: Path) -> None:
    write_run(tmp_path, "20260628_120000", metrics_payload(score=90))
    latest = write_run(tmp_path, "20260628_130000", metrics_payload(score=100))

    result = runner.invoke(
        app,
        ["baseline", "--project-root", str(tmp_path), "--set", "latest"],
    )

    payload = json.loads(baseline_file(tmp_path).read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert payload["run_id"] == latest.name
    assert payload["run_path"] == f".vibebench/runs/{latest.name}"
    assert payload["score"] == 100


def test_baseline_set_specific_run_writes_expected_metadata(tmp_path: Path) -> None:
    selected = write_run(
        tmp_path,
        "20260628_120000",
        metrics_payload(project="specific", score=88, risk="medium"),
    )
    write_run(tmp_path, "20260628_130000", metrics_payload(score=100))

    result = set_baseline(tmp_path, selected.name)

    assert result.is_valid is True
    assert result.metadata is not None
    assert result.metadata.run_id == selected.name
    assert result.metadata.project == "specific"
    assert result.metadata.risk_level == "medium"


def test_missing_run_id_fails_clearly(tmp_path: Path) -> None:
    write_run(tmp_path, "20260628_120000")

    result = runner.invoke(
        app,
        ["baseline", "--project-root", str(tmp_path), "--set", "missing"],
    )

    assert result.exit_code == 1
    assert "No VibeBench run found" in result.output


def test_run_without_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260628_120000"
    run_dir.mkdir(parents=True)

    result = runner.invoke(
        app,
        ["baseline", "--project-root", str(tmp_path), "--set", run_dir.name],
    )

    assert result.exit_code == 1
    assert "No metrics.json found" in result.output


def test_corrupt_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260628_120000"
    run_dir.mkdir(parents=True)
    (run_dir / "metrics.json").write_text("{bad json", encoding="utf-8")

    result = runner.invoke(
        app,
        ["baseline", "--project-root", str(tmp_path), "--set", run_dir.name],
    )

    assert result.exit_code == 1
    assert "Could not parse metrics.json" in result.output


def test_existing_baseline_is_shown_and_validated(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000")
    set_baseline(tmp_path, run_dir.name)

    result = runner.invoke(app, ["baseline", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Baseline is valid" in result.output
    assert run_dir.name in result.output


def test_missing_referenced_baseline_run_is_reported(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000")
    set_baseline(tmp_path, run_dir.name)
    for child in run_dir.iterdir():
        child.unlink()
    run_dir.rmdir()

    result = runner.invoke(app, ["baseline", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "Baseline run directory is missing" in result.output


def test_compare_baseline_uses_saved_baseline_and_latest(tmp_path: Path) -> None:
    base = write_run(tmp_path, "20260628_120000", metrics_payload(score=80))
    current = write_run(tmp_path, "20260628_130000", metrics_payload(score=100))
    set_baseline(tmp_path, base.name)

    result = compare_runs(tmp_path, use_baseline=True)

    assert result.base_run == base
    assert result.current_run == current
    assert result.verdict == "improved"


def test_compare_baseline_with_explicit_current_run(tmp_path: Path) -> None:
    base = write_run(tmp_path, "20260628_120000", metrics_payload(score=100))
    current = write_run(tmp_path, "20260628_130000", metrics_payload(score=80))
    write_run(tmp_path, "20260628_140000", metrics_payload(score=100))
    set_baseline(tmp_path, base.name)

    result = compare_runs(tmp_path, current_run=current, use_baseline=True)

    assert result.base_run == base
    assert result.current_run == current
    assert result.verdict == "regressed"


def test_default_compare_behavior_still_uses_latest_two_runs(tmp_path: Path) -> None:
    write_run(tmp_path, "20260628_110000", metrics_payload(score=60))
    base = write_run(tmp_path, "20260628_120000", metrics_payload(score=80))
    current = write_run(tmp_path, "20260628_130000", metrics_payload(score=100))

    result = compare_runs(tmp_path)

    assert result.base_run == base
    assert result.current_run == current
