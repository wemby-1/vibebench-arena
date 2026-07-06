import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

runner = CliRunner()


def metrics(
    *,
    score: int = 100,
    risk: str = "low",
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "project_name": "demo",
        "created_at": "2026-07-01T00:00:00Z",
        "overall_status": "passed",
        "score": score,
        "risk_level": risk,
        "summary": {
            "total_commands": 2,
            "passed_commands": 2,
            "failed_commands": 0,
            "total_findings": 0,
        },
        "diff_analysis": {
            "changed_file_count": 1,
            "total_patch_lines": 10,
        },
        "command_results": [],
        "risk_findings": [],
    }
    if extra:
        payload.update(extra)
    return payload


def write_run(
    project_root: Path,
    run_id: str,
    payload: dict[str, object] | None = None,
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / run_id
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text(
        json.dumps(payload or metrics()),
        encoding="utf-8",
    )
    return run_dir


def changes_by_metric(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {item["metric"]: item for item in payload["changes"]}


def test_metrics_diff_compares_latest_to_previous(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(score=90))
    write_run(tmp_path, "20260701_110000", metrics(score=95))

    result = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--json"],
    )

    payload = json.loads(result.output)
    changes = changes_by_metric(payload)
    assert result.exit_code == 0
    assert payload["baseline_source"] == "previous_run"
    assert payload["candidate_run"] == "20260701_110000"
    assert changes["score"]["classification"] == "improved"


def test_metrics_diff_explicit_runs(tmp_path: Path) -> None:
    base = write_run(tmp_path, "20260701_100000", metrics(score=95))
    head = write_run(tmp_path, "20260701_110000", metrics(score=90))

    result = runner.invoke(
        app,
        [
            "metrics-diff",
            "--project-root",
            str(tmp_path),
            "--baseline-run",
            str(base),
            "--candidate-run",
            str(head),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert changes_by_metric(payload)["score"]["classification"] == "regressed"


def test_metrics_diff_baseline_label_live_metrics(tmp_path: Path) -> None:
    baseline = write_run(tmp_path, "20260701_100000", metrics(score=90))
    write_run(tmp_path, "20260701_110000", metrics(score=95))
    pin = runner.invoke(
        app,
        [
            "baseline",
            "--project-root",
            str(tmp_path),
            "--set-run",
            baseline.name,
            "--label",
            "stable",
            "--json",
        ],
    )
    assert pin.exit_code == 0

    result = runner.invoke(
        app,
        [
            "metrics-diff",
            "--project-root",
            str(tmp_path),
            "--baseline-label",
            "stable",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["baseline_source"] == "baseline_label"
    assert payload["baseline_metrics_source"] == "live"


def test_metrics_diff_baseline_label_snapshot_fallback(tmp_path: Path) -> None:
    baseline = write_run(tmp_path, "20260701_100000", metrics(score=90))
    write_run(tmp_path, "20260701_110000", metrics(score=95))
    pin = runner.invoke(
        app,
        [
            "baseline",
            "--project-root",
            str(tmp_path),
            "--promote-run",
            baseline.name,
            "--label",
            "stable",
            "--json",
        ],
    )
    assert pin.exit_code == 0
    baseline.joinpath("metrics.json").unlink()

    result = runner.invoke(
        app,
        [
            "metrics-diff",
            "--project-root",
            str(tmp_path),
            "--baseline-label",
            "stable",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["baseline_metrics_source"] == "snapshot"
    assert changes_by_metric(payload)["score"]["classification"] == "improved"


def test_metrics_diff_missing_baseline_skips_and_strict_fails(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_110000")

    skipped = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--json"],
    )
    failed = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--strict", "--json"],
    )

    assert skipped.exit_code == 0
    assert json.loads(skipped.output)["status"] == "skipped"
    assert failed.exit_code == 1
    assert json.loads(failed.output)["status"] == "failed"


def test_metrics_diff_score_and_risk_semantics(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(score=90, risk="medium"))
    write_run(tmp_path, "20260701_110000", metrics(score=95, risk="low"))

    result = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--json"],
    )

    changes = changes_by_metric(json.loads(result.output))
    assert result.exit_code == 0
    assert changes["score"]["classification"] == "improved"
    assert changes["risk"]["classification"] == "improved"


def test_metrics_diff_risk_up_regresses(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(score=100, risk="low"))
    write_run(tmp_path, "20260701_110000", metrics(score=100, risk="high"))

    result = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert changes_by_metric(payload)["risk"]["classification"] == "regressed"


def test_metrics_diff_added_removed_and_unchanged(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(extra={"old_metric": 1}))
    write_run(tmp_path, "20260701_110000", metrics(extra={"new_metric": 2}))

    hidden = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--json"],
    )
    shown = runner.invoke(
        app,
        [
            "metrics-diff",
            "--project-root",
            str(tmp_path),
            "--include-unchanged",
            "--json",
        ],
    )

    hidden_changes = changes_by_metric(json.loads(hidden.output))
    shown_changes = changes_by_metric(json.loads(shown.output))
    assert hidden_changes["new_metric"]["classification"] == "added"
    assert hidden_changes["old_metric"]["classification"] == "removed"
    assert "score" not in hidden_changes
    assert shown_changes["score"]["classification"] == "unchanged"


def test_metrics_diff_top_limits_changes(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(extra={"a": 1, "b": 10}))
    write_run(tmp_path, "20260701_110000", metrics(extra={"a": 2, "b": 30}))

    result = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--top", "1", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert len(payload["changes"]) == 1
    assert payload["changes"][0]["metric"] == "b"


def test_metrics_diff_outputs_json_and_markdown(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(score=90))
    write_run(tmp_path, "20260701_110000", metrics(score=95))
    json_output = tmp_path / "metrics-diff.json"
    summary_output = tmp_path / "metrics-diff.md"

    result = runner.invoke(
        app,
        [
            "metrics-diff",
            "--project-root",
            str(tmp_path),
            "--json",
            "--json-output",
            str(json_output),
            "--summary-output",
            str(summary_output),
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "passed"
    assert json.loads(json_output.read_text())["status"] == "passed"
    assert "# VibeBench Metrics Diff" in summary_output.read_text()
