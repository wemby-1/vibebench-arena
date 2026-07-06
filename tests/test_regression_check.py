import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

runner = CliRunner()


def metrics_payload(*, score: int = 100, risk: str = "low") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": "demo-project",
        "created_at": "2026-07-06T12:00:00Z",
        "overall_status": "passed",
        "score": score,
        "risk_level": risk,
        "command_results": [],
        "diff_analysis": {
            "git_available": True,
            "changed_file_count": 0,
            "total_added_lines": 0,
            "total_deleted_lines": 0,
            "total_patch_lines": 0,
        },
        "risk_findings": [],
        "summary": {
            "total_commands": 0,
            "passed_commands": 0,
            "failed_commands": 0,
            "total_findings": 0,
        },
    }


def write_run(
    project_root: Path,
    name: str,
    *,
    score: int = 100,
    risk: str = "low",
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = metrics_payload(score=score, risk=risk)
    payload["run_dir"] = str(run_dir)
    payload["metrics_path"] = str(run_dir / "metrics.json")
    payload["log_path"] = str(run_dir / "check.log")
    run_dir.joinpath("metrics.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    return run_dir


def run_regression_check(project_root: Path, *args: str) -> object:
    return runner.invoke(
        app,
        ["regression-check", "--project-root", str(project_root), *args],
    )


def test_regression_check_skips_without_baseline_by_default(tmp_path: Path) -> None:
    write_run(tmp_path, "20260706_120000")

    result = run_regression_check(tmp_path, "--json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "skipped"
    assert "No previous baseline" in payload["message"]


def test_regression_check_fails_without_baseline_when_required(
    tmp_path: Path,
) -> None:
    write_run(tmp_path, "20260706_120000")

    result = run_regression_check(tmp_path, "--require-baseline", "--json")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "failed"
    assert payload["failures"][0]["code"] == "missing_baseline"


def test_regression_check_passes_when_score_and_risk_unchanged(
    tmp_path: Path,
) -> None:
    write_run(tmp_path, "20260706_120000", score=95, risk="medium")
    write_run(tmp_path, "20260706_130000", score=95, risk="medium")

    result = run_regression_check(tmp_path, "--json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "passed"
    assert payload["deltas"]["score_delta"] == 0
    assert payload["deltas"]["risk_delta"] == 0


def test_regression_check_fails_when_score_drops_beyond_threshold(
    tmp_path: Path,
) -> None:
    write_run(tmp_path, "20260706_120000", score=100)
    write_run(tmp_path, "20260706_130000", score=97)

    result = run_regression_check(tmp_path, "--json")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "failed"
    assert payload["failures"][0]["code"] == "score_regression"


def test_regression_check_passes_when_score_drop_is_allowed(
    tmp_path: Path,
) -> None:
    write_run(tmp_path, "20260706_120000", score=100)
    write_run(tmp_path, "20260706_130000", score=98)

    result = run_regression_check(tmp_path, "--max-score-drop", "2", "--json")

    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "passed"


def test_regression_check_fails_when_risk_increases_beyond_threshold(
    tmp_path: Path,
) -> None:
    write_run(tmp_path, "20260706_120000", risk="low")
    write_run(tmp_path, "20260706_130000", risk="medium")

    result = run_regression_check(tmp_path, "--json")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "failed"
    assert payload["failures"][0]["code"] == "risk_regression"


def test_regression_check_passes_when_risk_increase_is_allowed(
    tmp_path: Path,
) -> None:
    write_run(tmp_path, "20260706_120000", risk="low")
    write_run(tmp_path, "20260706_130000", risk="medium")

    result = run_regression_check(tmp_path, "--max-risk-increase", "1", "--json")

    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "passed"


def test_regression_check_explicit_run_paths_work(tmp_path: Path) -> None:
    baseline = write_run(tmp_path, "baseline", score=90, risk="medium")
    candidate = write_run(tmp_path, "candidate", score=91, risk="low")

    result = run_regression_check(
        tmp_path,
        "--baseline-run",
        str(baseline),
        "--candidate-run",
        str(candidate),
        "--json",
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert payload["baseline_run_id"] == "baseline"
    assert payload["candidate_run_id"] == "candidate"


def test_regression_check_json_stdout_is_pure_json(tmp_path: Path) -> None:
    write_run(tmp_path, "20260706_120000")
    write_run(tmp_path, "20260706_130000")

    result = run_regression_check(tmp_path, "--json")

    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "passed"
    assert "VibeBench Regression Check" not in result.output


def test_regression_check_json_output_writes_valid_json(tmp_path: Path) -> None:
    write_run(tmp_path, "20260706_120000")
    write_run(tmp_path, "20260706_130000")
    output = tmp_path / "regression-check.json"

    result = run_regression_check(tmp_path, "--json-output", str(output))

    assert result.exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "passed"


def test_regression_check_summary_output_writes_markdown(tmp_path: Path) -> None:
    write_run(tmp_path, "20260706_120000")
    write_run(tmp_path, "20260706_130000")
    output = tmp_path / "regression-check.md"

    result = run_regression_check(tmp_path, "--summary-output", str(output))

    assert result.exit_code == 0
    content = output.read_text(encoding="utf-8")
    assert "# VibeBench Regression Check" in content
    assert "local quality regression gate" in content
    assert "not a benchmark certification" in content


def test_regression_check_all_outputs_keep_stdout_pure_json(tmp_path: Path) -> None:
    write_run(tmp_path, "20260706_120000")
    write_run(tmp_path, "20260706_130000")
    json_output = tmp_path / "regression-check.json"
    summary_output = tmp_path / "regression-check.md"

    result = run_regression_check(
        tmp_path,
        "--json",
        "--json-output",
        str(json_output),
        "--summary-output",
        str(summary_output),
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "passed"
    assert json.loads(json_output.read_text(encoding="utf-8"))["status"] == "passed"
    assert summary_output.read_text(encoding="utf-8").startswith(
        "# VibeBench Regression Check"
    )
    assert "Regression-check Markdown" not in result.output


def test_regression_check_invalid_run_path_fails_clearly(tmp_path: Path) -> None:
    candidate = write_run(tmp_path, "candidate")

    result = run_regression_check(
        tmp_path,
        "--baseline-run",
        str(tmp_path / "missing"),
        "--candidate-run",
        str(candidate),
    )

    assert result.exit_code == 1
    assert "Run directory does not exist" in result.output
