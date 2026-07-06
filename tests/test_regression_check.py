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


def write_project_config(project_root: Path, regression_yaml: str) -> None:
    config_dir = project_root / ".vibebench"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_dir.joinpath("config.yaml").write_text(
        f"""project:
  name: demo
checks:
  test:
    - python -c "print(1)"
regression:
{regression_yaml}
""",
        encoding="utf-8",
    )


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



def pin_baseline(project_root: Path, run_id: str, label: str = "stable") -> None:
    result = runner.invoke(
        app,
        [
            "baseline",
            "--project-root",
            str(project_root),
            "--set-run",
            run_id,
            "--label",
            label,
        ],
    )
    assert result.exit_code == 0


def test_regression_check_uses_pinned_baseline_label(tmp_path: Path) -> None:
    pinned = write_run(tmp_path, "20260706_100000", score=100, risk="low")
    write_run(tmp_path, "20260706_110000", score=80, risk="low")
    write_run(tmp_path, "20260706_120000", score=80, risk="low")
    pin_baseline(tmp_path, pinned.name)

    result = run_regression_check(tmp_path, "--baseline-label", "stable", "--json")

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["baseline_source"] == "pinned"
    assert payload["baseline_label"] == "stable"
    assert payload["baseline_run_id"] == pinned.name
    assert payload["failures"][0]["code"] == "score_regression"


def test_regression_check_explicit_baseline_takes_precedence_over_pinned(
    tmp_path: Path,
) -> None:
    pinned = write_run(tmp_path, "20260706_100000", score=100, risk="low")
    explicit = write_run(tmp_path, "20260706_110000", score=80, risk="low")
    write_run(tmp_path, "20260706_120000", score=80, risk="low")
    pin_baseline(tmp_path, pinned.name)

    result = run_regression_check(
        tmp_path,
        "--baseline-label",
        "stable",
        "--baseline-run",
        str(explicit),
        "--json",
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["baseline_source"] == "explicit"
    assert payload["baseline_label"] is None
    assert payload["baseline_run_id"] == explicit.name


def test_regression_check_missing_pinned_baseline_skips_without_auto_fallback(
    tmp_path: Path,
) -> None:
    write_run(tmp_path, "20260706_100000", score=100)
    candidate = write_run(tmp_path, "20260706_110000", score=100)

    result = run_regression_check(tmp_path, "--baseline-label", "stable", "--json")

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "skipped"
    assert payload["baseline_source"] == "missing"
    assert payload["candidate_run_id"] == candidate.name


def test_regression_check_missing_pinned_baseline_fails_when_required(
    tmp_path: Path,
) -> None:
    write_run(tmp_path, "20260706_110000", score=100)

    result = run_regression_check(
        tmp_path,
        "--baseline-label",
        "stable",
        "--require-baseline",
        "--json",
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert payload["baseline_source"] == "missing"
    assert payload["failures"][0]["code"] == "missing_baseline"


def test_regression_check_stale_pinned_baseline_fails_clearly(
    tmp_path: Path,
) -> None:
    pinned = write_run(tmp_path, "20260706_100000", score=100)
    write_run(tmp_path, "20260706_110000", score=100)
    pin_baseline(tmp_path, pinned.name)
    pinned.joinpath("metrics.json").unlink()
    pinned.rmdir()

    result = run_regression_check(tmp_path, "--baseline-label", "stable")

    assert result.exit_code == 1
    assert "Baseline run directory is missing" in result.output



def test_regression_check_json_reports_effective_policy(tmp_path: Path) -> None:
    write_run(tmp_path, "20260706_120000")
    write_run(tmp_path, "20260706_130000")

    result = run_regression_check(tmp_path, "--json")

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["policy_source"] == "default"
    assert payload["effective_policy"] == {
        "baseline_label": None,
        "require_baseline": False,
        "max_score_drop": 0.0,
        "max_risk_increase": 0.0,
        "fail_on_missing_metrics": True,
    }


def test_regression_check_markdown_includes_effective_policy(tmp_path: Path) -> None:
    write_run(tmp_path, "20260706_120000")
    write_run(tmp_path, "20260706_130000")
    output = tmp_path / "regression-check.md"

    result = run_regression_check(tmp_path, "--summary-output", str(output))

    assert result.exit_code == 0
    assert "## Effective policy" in output.read_text(encoding="utf-8")


def test_regression_check_uses_config_thresholds_when_cli_absent(
    tmp_path: Path,
) -> None:
    write_project_config(tmp_path, "  max_score_drop: 5\n")
    write_run(tmp_path, "20260706_120000", score=100)
    write_run(tmp_path, "20260706_130000", score=97)

    result = run_regression_check(tmp_path, "--json")

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert payload["policy_source"] == "config"
    assert payload["effective_policy"]["max_score_drop"] == 5


def test_regression_check_cli_threshold_overrides_config(tmp_path: Path) -> None:
    write_project_config(tmp_path, "  max_score_drop: 5\n")
    write_run(tmp_path, "20260706_120000", score=100)
    write_run(tmp_path, "20260706_130000", score=97)

    result = run_regression_check(tmp_path, "--max-score-drop", "1", "--json")

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["policy_source"] == "cli"
    assert payload["effective_policy"]["max_score_drop"] == 1
    assert payload["failures"][0]["code"] == "score_regression"


def test_regression_check_uses_config_baseline_label(tmp_path: Path) -> None:
    pinned = write_run(tmp_path, "20260706_100000", score=100)
    write_run(tmp_path, "20260706_110000", score=100)
    write_project_config(tmp_path, "  baseline_label: stable\n")
    pin_baseline(tmp_path, pinned.name)

    result = run_regression_check(tmp_path, "--json")

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["policy_source"] == "config"
    assert payload["baseline_source"] == "pinned"
    assert payload["baseline_label"] == "stable"
    assert payload["baseline_run_id"] == pinned.name


def test_regression_check_cli_baseline_label_overrides_config(
    tmp_path: Path,
) -> None:
    stable = write_run(tmp_path, "20260706_100000", score=80)
    experimental = write_run(tmp_path, "20260706_110000", score=100)
    write_run(tmp_path, "20260706_120000", score=100)
    write_project_config(tmp_path, "  baseline_label: stable\n")
    pin_baseline(tmp_path, stable.name, label="stable")
    pin_baseline(tmp_path, experimental.name, label="experimental")

    result = run_regression_check(
        tmp_path,
        "--baseline-label",
        "experimental",
        "--json",
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["policy_source"] == "cli"
    assert payload["baseline_label"] == "experimental"
    assert payload["baseline_run_id"] == experimental.name


def test_regression_check_missing_metrics_can_be_allowed_by_config(
    tmp_path: Path,
) -> None:
    baseline = write_run(tmp_path, "20260706_120000", score=100)
    candidate = write_run(tmp_path, "20260706_130000", score=100)
    for run_dir in [baseline, candidate]:
        metrics = json.loads(run_dir.joinpath("metrics.json").read_text())
        metrics.pop("risk_level")
        run_dir.joinpath("metrics.json").write_text(
            json.dumps(metrics), encoding="utf-8"
        )
    write_project_config(tmp_path, "  fail_on_missing_metrics: false\n")

    result = run_regression_check(tmp_path, "--json")

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert any(item["code"] == "missing_metric" for item in payload["warnings"])
