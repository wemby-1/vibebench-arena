import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

runner = CliRunner()


def metrics_payload(*, score: object = 100, risk: object = "low") -> dict[str, object]:
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
    payload: dict[str, object] | None = None,
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics = payload or metrics_payload()
    metrics["run_dir"] = str(run_dir)
    metrics["metrics_path"] = str(run_dir / "metrics.json")
    metrics["log_path"] = str(run_dir / "check.log")
    run_dir.joinpath("metrics.json").write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )
    return run_dir


def metrics_check(project_root: Path, *args: str) -> object:
    return runner.invoke(
        app,
        ["metrics-check", "--project-root", str(project_root), *args],
    )


def baseline(project_root: Path, *args: str) -> object:
    return runner.invoke(
        app,
        ["baseline", "--project-root", str(project_root), *args],
    )


def test_metrics_check_latest_run_passes(tmp_path: Path) -> None:
    write_run(tmp_path, "20260706_120000")

    result = metrics_check(tmp_path, "--json")

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert payload["usable_for_regression"] is True
    assert payload["usable_as_baseline"] is True
    assert payload["score_value"] == 100
    assert payload["risk_value"] == 0


def test_metrics_check_explicit_run_dir_works(tmp_path: Path) -> None:
    selected = write_run(tmp_path, "selected")
    write_run(tmp_path, "newer")

    result = metrics_check(tmp_path, "--run-dir", str(selected), "--json")

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["run_dir"] == str(selected.resolve())


def test_metrics_check_missing_run_directory_fails(tmp_path: Path) -> None:
    result = metrics_check(tmp_path, "--run-dir", str(tmp_path / "missing"), "--json")

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert any(check["name"] == "run_dir_exists" for check in payload["checks"])


def test_metrics_check_missing_metrics_json_fails(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260706_120000"
    run_dir.mkdir(parents=True)

    result = metrics_check(tmp_path, "--run-dir", str(run_dir), "--json")

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert any(check["name"] == "metrics_json_exists" for check in payload["checks"])


def test_metrics_check_malformed_metrics_json_fails(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260706_120000"
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text("{bad", encoding="utf-8")

    result = metrics_check(tmp_path, "--run-dir", str(run_dir), "--json")

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert any(check["name"] == "metrics_json_valid" for check in payload["checks"])


def test_metrics_check_non_object_metrics_json_fails(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260706_120000"
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text("[]", encoding="utf-8")

    result = metrics_check(tmp_path, "--run-dir", str(run_dir), "--json")

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert any(
        check["name"] == "metrics_payload_object" for check in payload["checks"]
    )


def test_metrics_check_missing_score_risk_is_not_usable(tmp_path: Path) -> None:
    payload = metrics_payload()
    payload.pop("score")
    payload.pop("risk_level")
    write_run(tmp_path, "20260706_120000", payload)

    result = metrics_check(tmp_path, "--json")

    data = json.loads(result.output)
    assert result.exit_code == 1
    assert data["usable_for_regression"] is False
    assert data["usable_as_baseline"] is False
    assert {check["name"] for check in data["checks"]} >= {
        "score_numeric",
        "risk_numeric",
    }


def test_metrics_check_non_numeric_score_or_risk_fails(tmp_path: Path) -> None:
    write_run(tmp_path, "20260706_120000", metrics_payload(score="100", risk="odd"))

    result = metrics_check(tmp_path, "--json")

    data = json.loads(result.output)
    assert result.exit_code == 1
    assert data["status"] == "failed"
    assert data["score_value"] is None
    assert data["risk_value"] is None


def test_metrics_check_valid_score_risk_with_missing_optional_warns(
    tmp_path: Path,
) -> None:
    payload = metrics_payload(score=99, risk="medium")
    payload.pop("summary")
    write_run(tmp_path, "20260706_120000", payload)

    result = metrics_check(tmp_path, "--json")

    data = json.loads(result.output)
    assert result.exit_code == 0
    assert data["status"] == "warning"
    assert data["usable_for_regression"] is True
    assert data["score_value"] == 99
    assert data["risk_value"] == 1


def test_metrics_check_strict_fails_on_warnings(tmp_path: Path) -> None:
    payload = metrics_payload()
    payload.pop("summary")
    write_run(tmp_path, "20260706_120000", payload)

    result = metrics_check(tmp_path, "--strict", "--json")

    data = json.loads(result.output)
    assert result.exit_code == 1
    assert data["status"] == "failed"
    assert data["strict"] is True
    assert any(check["name"] == "strict" for check in data["checks"])


def test_metrics_check_json_stdout_is_pure(tmp_path: Path) -> None:
    write_run(tmp_path, "20260706_120000")

    result = metrics_check(tmp_path, "--json")

    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "passed"
    assert "VibeBench metrics check" not in result.output


def test_metrics_check_json_output_writes_valid_json(tmp_path: Path) -> None:
    write_run(tmp_path, "20260706_120000")
    output = tmp_path / "metrics-check.json"

    result = metrics_check(tmp_path, "--json-output", str(output))

    assert result.exit_code == 0
    assert "VibeBench metrics check" in result.output
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "passed"


def test_metrics_check_summary_output_writes_markdown(tmp_path: Path) -> None:
    write_run(tmp_path, "20260706_120000")
    output = tmp_path / "metrics-check.md"

    result = metrics_check(tmp_path, "--summary-output", str(output))

    assert result.exit_code == 0
    content = output.read_text(encoding="utf-8")
    assert content.startswith("# VibeBench Metrics Check")
    assert "## Checks" in content


def test_baseline_verification_is_consistent_with_metrics_validation(
    tmp_path: Path,
) -> None:
    run_dir = write_run(tmp_path, "20260706_120000", metrics_payload(risk="odd"))

    promote = baseline(
        tmp_path,
        "--promote-run",
        run_dir.name,
        "--label",
        "stable",
        "--json",
    )

    data = json.loads(promote.output)
    assert promote.exit_code == 1
    assert any(
        check["name"] == "metrics_available" and check["status"] == "failed"
        for check in data["checks"]
    )


def test_guarded_baseline_promotion_still_works(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260706_120000")

    result = baseline(
        tmp_path,
        "--promote-run",
        run_dir.name,
        "--label",
        "stable",
        "--json",
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "promoted"


def test_regression_check_snapshot_fallback_still_works(tmp_path: Path) -> None:
    baseline_run = write_run(tmp_path, "20260706_100000", metrics_payload(score=100))
    write_run(tmp_path, "20260706_110000", metrics_payload(score=100))
    assert (
        baseline(
            tmp_path,
            "--promote-run",
            baseline_run.name,
            "--label",
            "stable",
        ).exit_code
        == 0
    )
    baseline_run.joinpath("metrics.json").unlink()
    baseline_run.rmdir()

    result = runner.invoke(
        app,
        [
            "regression-check",
            "--project-root",
            str(tmp_path),
            "--baseline-label",
            "stable",
            "--json",
        ],
    )

    data = json.loads(result.output)
    assert result.exit_code == 0
    assert data["baseline_metrics_source"] == "snapshot"
