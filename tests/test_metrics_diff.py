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


def write_policy_config(project_root: Path, policy_yaml: str) -> None:
    config_dir = project_root / ".vibebench"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_dir.joinpath("config.yaml").write_text(
        """project:
  name: demo
checks:
  test:
    - pytest -q
metrics_diff:
  policy:
"""
        + policy_yaml,
        encoding="utf-8",
    )


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
    assert result.exit_code == 0
    assert payload["status"] == "passed"
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
    assert result.exit_code == 0
    assert payload["status"] == "passed"
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


def test_metrics_diff_enforce_policy_passes_within_threshold(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(score=90, risk="medium"))
    write_run(tmp_path, "20260701_110000", metrics(score=95, risk="low"))

    result = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--enforce-policy", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert payload["policy_status"] == "passed"
    assert payload["policy_enforced"] is True
    assert payload["policy_findings"] == []


def test_metrics_diff_allow_policy_failure_is_report_only(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(score=95))
    write_run(tmp_path, "20260701_110000", metrics(score=90))

    result = runner.invoke(
        app,
        [
            "metrics-diff",
            "--project-root",
            str(tmp_path),
            "--allow-policy-failure",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert payload["policy_status"] == "failed"
    assert payload["policy_enforced"] is False


def test_metrics_diff_enforce_policy_fails_on_score_drop(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(score=95))
    write_run(tmp_path, "20260701_110000", metrics(score=90))

    result = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--enforce-policy", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert payload["policy_status"] == "failed"
    assert payload["policy_error_count"] == 1
    assert payload["policy_findings"][0]["rule"] == "score.max_drop"


def test_metrics_diff_enforce_policy_fails_on_risk_increase(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(risk="low"))
    write_run(tmp_path, "20260701_110000", metrics(risk="high"))

    result = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--enforce-policy", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["policy_findings"][0]["rule"] == "risk.max_increase"


def test_metrics_diff_policy_custom_max_drop_rule(tmp_path: Path) -> None:
    write_policy_config(
        tmp_path,
        """    enabled: true
    baseline_label: null
    custom_rules:
      - metric: pass_rate
        max_drop: 0.01
""",
    )
    write_run(tmp_path, "20260701_100000", metrics(extra={"pass_rate": 0.99}))
    write_run(tmp_path, "20260701_110000", metrics(extra={"pass_rate": 0.95}))

    result = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--enforce-policy", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["policy_source"] == "config"
    assert payload["policy_findings"][0]["metric"] == "pass_rate"
    assert payload["policy_findings"][0]["rule"] == "max_drop"


def test_metrics_diff_policy_custom_max_increase_rule(tmp_path: Path) -> None:
    write_policy_config(
        tmp_path,
        """    enabled: true
    baseline_label: null
    custom_rules:
      - metric: latency_ms
        max_increase: 50
""",
    )
    write_run(tmp_path, "20260701_100000", metrics(extra={"latency_ms": 100}))
    write_run(tmp_path, "20260701_110000", metrics(extra={"latency_ms": 180}))

    result = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--enforce-policy", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["policy_findings"][0]["metric"] == "latency_ms"
    assert payload["policy_findings"][0]["rule"] == "max_increase"


def test_metrics_diff_added_removed_metrics_warn_by_default(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(extra={"old_metric": 1}))
    write_run(tmp_path, "20260701_110000", metrics(extra={"new_metric": 2}))

    result = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--enforce-policy", "--json"],
    )

    payload = json.loads(result.output)
    severities = {
        finding["rule"]: finding["severity"]
        for finding in payload["policy_findings"]
    }
    assert result.exit_code == 0
    assert payload["policy_status"] == "passed"
    assert payload["policy_warning_count"] == 2
    assert severities == {"added_metric": "warning", "removed_metric": "warning"}


def test_metrics_diff_added_removed_metrics_fail_when_configured(
    tmp_path: Path,
) -> None:
    write_policy_config(
        tmp_path,
        """    enabled: true
    baseline_label: null
    fail_on_added_errors: true
    fail_on_removed_metrics: true
""",
    )
    write_run(tmp_path, "20260701_100000", metrics(extra={"old_metric": 1}))
    write_run(tmp_path, "20260701_110000", metrics(extra={"new_metric": 2}))

    result = runner.invoke(
        app,
        ["metrics-diff", "--project-root", str(tmp_path), "--enforce-policy", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["policy_error_count"] == 2
    assert {finding["severity"] for finding in payload["policy_findings"]} == {"error"}


def test_metrics_diff_policy_uses_configured_pinned_baseline_label(
    tmp_path: Path,
) -> None:
    write_policy_config(
        tmp_path,
        """    enabled: true
    baseline_label: stable
""",
    )
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
        ["metrics-diff", "--project-root", str(tmp_path), "--enforce-policy", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["baseline_source"] == "baseline_label"
    assert payload["baseline_label"] == "stable"


def test_metrics_diff_policy_snapshot_fallback_still_works(tmp_path: Path) -> None:
    write_policy_config(
        tmp_path,
        """    enabled: true
    baseline_label: stable
""",
    )
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
        ["metrics-diff", "--project-root", str(tmp_path), "--enforce-policy", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["baseline_metrics_source"] == "snapshot"
    assert payload["policy_status"] == "passed"


def test_metrics_diff_policy_json_output_and_markdown_section(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(score=95))
    write_run(tmp_path, "20260701_110000", metrics(score=90))
    json_output = tmp_path / "policy.json"
    summary_output = tmp_path / "policy.md"

    result = runner.invoke(
        app,
        [
            "metrics-diff",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--json",
            "--json-output",
            str(json_output),
            "--summary-output",
            str(summary_output),
        ],
    )

    stdout_payload = json.loads(result.output)
    file_payload = json.loads(json_output.read_text())
    markdown = summary_output.read_text()
    assert result.exit_code == 1
    assert result.output.lstrip().startswith("{")
    assert stdout_payload["policy_status"] == "failed"
    assert file_payload["policy_status"] == "failed"
    assert "## Policy" in markdown
    assert "Score/risk use built-in semantics" in markdown
