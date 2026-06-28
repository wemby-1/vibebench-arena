import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.baseline import set_baseline
from vibebench.cli import app
from vibebench.gate import run_gate

runner = CliRunner()


def metrics_payload(
    *,
    status: str = "passed",
    score: int = 100,
    risk: str = "low",
    findings: int = 0,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": "demo-project",
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
            "total_patch_lines": 0,
            "changed_file_count": 0,
            "warnings": [],
            "file_changes": [],
        },
        "risk_findings": [
            {"severity": "warning", "code": "example", "message": "x", "paths": []}
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


def test_gate_passes_good_run_with_defaults(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000")

    result = run_gate(tmp_path, run_dir=run_dir)

    assert result.passed is True
    assert result.reasons == []


def test_gate_fails_when_score_below_default(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000", metrics_payload(score=79))

    result = run_gate(tmp_path, run_dir=run_dir)

    assert result.passed is False
    assert any("below minimum" in reason for reason in result.reasons)


def test_gate_passes_when_min_score_lowered(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000", metrics_payload(score=79))

    assert run_gate(tmp_path, run_dir=run_dir, min_score=70).passed is True


def test_gate_fails_when_risk_above_max(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000", metrics_payload(risk="high"))

    result = run_gate(tmp_path, run_dir=run_dir)

    assert result.passed is False
    assert any("risk high" in reason for reason in result.reasons)


def test_gate_passes_when_max_risk_allows_it(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000", metrics_payload(risk="high"))

    assert run_gate(tmp_path, run_dir=run_dir, max_risk="high").passed is True


def test_gate_fails_when_findings_exceed_allowed(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000", metrics_payload(findings=1))

    result = run_gate(tmp_path, run_dir=run_dir)

    assert result.passed is False
    assert any("risk findings" in reason for reason in result.reasons)


def test_gate_passes_when_allow_findings_allows_them(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000", metrics_payload(findings=1))

    assert run_gate(tmp_path, run_dir=run_dir, allow_findings=1).passed is True


def test_gate_fails_when_status_failed(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000", metrics_payload(status="failed"))

    result = run_gate(tmp_path, run_dir=run_dir)

    assert result.passed is False
    assert any("overall status" in reason for reason in result.reasons)


def test_gate_can_ignore_failed_status(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000", metrics_payload(status="failed"))

    assert (
        run_gate(tmp_path, run_dir=run_dir, require_status_passed=False).passed is True
    )


def test_gate_run_dir_option_works(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000")

    result = runner.invoke(
        app,
        ["gate", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 0
    assert "Result: passed" in result.output


def test_gate_missing_run_dir_fails_clearly(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["gate", "--project-root", str(tmp_path), "--run-dir", str(tmp_path / "no")],
    )

    assert result.exit_code == 1
    assert "Run directory does not exist" in result.output


def test_gate_corrupt_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260628_120000"
    run_dir.mkdir(parents=True)
    (run_dir / "metrics.json").write_text("{bad json", encoding="utf-8")

    result = runner.invoke(
        app,
        ["gate", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 1
    assert "Could not parse metrics.json" in result.output


def test_gate_baseline_passes_when_not_worse(tmp_path: Path) -> None:
    base = write_run(tmp_path, "20260628_120000", metrics_payload(score=90))
    current = write_run(tmp_path, "20260628_130000", metrics_payload(score=100))
    set_baseline(tmp_path, base.name)

    result = run_gate(tmp_path, run_dir=current, use_baseline=True)

    assert result.passed is True


def test_gate_baseline_fails_when_score_regresses(tmp_path: Path) -> None:
    base = write_run(tmp_path, "20260628_120000", metrics_payload(score=100))
    current = write_run(tmp_path, "20260628_130000", metrics_payload(score=90))
    set_baseline(tmp_path, base.name)

    result = run_gate(tmp_path, run_dir=current, use_baseline=True)

    assert result.passed is False
    assert any("score regressed" in reason for reason in result.reasons)


def test_gate_baseline_fails_when_risk_worsens(tmp_path: Path) -> None:
    base = write_run(tmp_path, "20260628_120000", metrics_payload(risk="low"))
    current = write_run(tmp_path, "20260628_130000", metrics_payload(risk="medium"))
    set_baseline(tmp_path, base.name)

    result = run_gate(tmp_path, run_dir=current, use_baseline=True)

    assert result.passed is False
    assert any("risk worsened" in reason for reason in result.reasons)


def test_gate_baseline_fails_when_findings_increase(tmp_path: Path) -> None:
    base = write_run(tmp_path, "20260628_120000", metrics_payload(findings=0))
    current = write_run(tmp_path, "20260628_130000", metrics_payload(findings=1))
    set_baseline(tmp_path, base.name)

    result = run_gate(
        tmp_path,
        run_dir=current,
        allow_findings=1,
        use_baseline=True,
    )

    assert result.passed is False
    assert any("risk findings increased" in reason for reason in result.reasons)


def test_gate_baseline_without_saved_baseline_fails_clearly(tmp_path: Path) -> None:
    write_run(tmp_path, "20260628_120000")

    result = runner.invoke(app, ["gate", "--project-root", str(tmp_path), "--baseline"])

    assert result.exit_code == 1
    assert "baseline --set latest" in result.output


def test_gate_summary_is_written(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000")

    result = run_gate(tmp_path, run_dir=run_dir, write_gate_summary=True)
    summary_path = run_dir / "gate-summary.md"

    assert result.summary_path == summary_path
    assert summary_path.exists()
    assert "VibeBench Gate Summary" in summary_path.read_text(encoding="utf-8")
