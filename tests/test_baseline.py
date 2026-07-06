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



def test_pinned_baseline_set_latest_writes_labeled_metadata(tmp_path: Path) -> None:
    write_run(tmp_path, "20260628_120000", metrics_payload(score=90))
    latest = write_run(tmp_path, "20260628_130000", metrics_payload(score=100))

    result = runner.invoke(
        app,
        [
            "baseline",
            "--project-root",
            str(tmp_path),
            "--set-latest",
            "--label",
            "stable",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    baseline_path = tmp_path / ".vibebench" / "baselines" / "stable.json"
    stored = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert payload["status"] == "valid"
    assert stored["schema_version"] == "1.0"
    assert stored["label"] == "stable"
    assert stored["run_id"] == latest.name
    assert stored["run_dir"] == latest.name
    assert stored["source"] == "set-latest"
    assert stored["score"] == 100


def test_pinned_baseline_set_run_accepts_id_and_path(tmp_path: Path) -> None:
    selected = write_run(tmp_path, "20260628_120000", metrics_payload(score=88))
    write_run(tmp_path, "20260628_130000", metrics_payload(score=100))

    by_id = runner.invoke(
        app,
        [
            "baseline",
            "--project-root",
            str(tmp_path),
            "--set-run",
            selected.name,
            "--label",
            "by-id",
        ],
    )
    by_path = runner.invoke(
        app,
        [
            "baseline",
            "--project-root",
            str(tmp_path),
            "--set-run",
            str(selected),
            "--label",
            "by-path",
            "--json",
        ],
    )

    assert by_id.exit_code == 0
    assert by_path.exit_code == 0
    assert json.loads(by_path.output)["baseline"]["run_id"] == selected.name


def test_pinned_baseline_show_human_and_json(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000", metrics_payload(score=91))
    runner.invoke(
        app,
        ["baseline", "--project-root", str(tmp_path), "--set-run", run_dir.name],
    )

    human = runner.invoke(app, ["baseline", "--project-root", str(tmp_path), "--show"])
    as_json = runner.invoke(
        app,
        ["baseline", "--project-root", str(tmp_path), "--show", "--json"],
    )

    payload = json.loads(as_json.output)
    assert human.exit_code == 0
    assert "VibeBench baseline" in human.output
    assert "default" in human.output
    assert as_json.exit_code == 0
    assert payload["status"] == "valid"
    assert payload["label"] == "default"
    assert "VibeBench baseline" not in as_json.output


def test_pinned_baseline_clear_removes_labeled_file(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000")
    runner.invoke(
        app,
        [
            "baseline",
            "--project-root",
            str(tmp_path),
            "--set-run",
            run_dir.name,
            "--label",
            "stable",
        ],
    )

    result = runner.invoke(
        app,
        ["baseline", "--project-root", str(tmp_path), "--clear", "--label", "stable"],
    )

    assert result.exit_code == 0
    assert "Cleared pinned baseline" in result.output
    assert not (tmp_path / ".vibebench" / "baselines" / "stable.json").exists()


def test_pinned_baseline_list_and_json_output(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000")
    output = tmp_path / "baseline.json"
    runner.invoke(
        app,
        [
            "baseline",
            "--project-root",
            str(tmp_path),
            "--set-run",
            run_dir.name,
            "--label",
            "stable",
        ],
    )

    result = runner.invoke(
        app,
        [
            "baseline",
            "--project-root",
            str(tmp_path),
            "--list",
            "--json-output",
            str(output),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    written = json.loads(output.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert payload["baselines"][0]["label"] == "stable"
    assert written["baselines"][0]["label"] == "stable"



def baseline_json(project_root: Path, *args: str) -> object:
    return runner.invoke(
        app,
        ["baseline", "--project-root", str(project_root), *args],
    )


def test_baseline_promote_latest_dry_run_does_not_write(tmp_path: Path) -> None:
    latest = write_run(tmp_path, "20260628_130000", metrics_payload(score=100))

    result = baseline_json(
        tmp_path,
        "--promote-latest",
        "--label",
        "stable",
        "--dry-run",
        "--json",
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "planned"
    assert payload["dry_run"] is True
    assert payload["candidate_run_id"] == latest.name
    assert payload["label"] == "stable"
    assert not (tmp_path / ".vibebench" / "baselines" / "stable.json").exists()
    assert {check["name"] for check in payload["checks"]} >= {
        "run_exists",
        "metrics_available",
        "manifest_consistent",
        "regression_policy",
    }


def test_baseline_promote_latest_writes_selected_label(tmp_path: Path) -> None:
    latest = write_run(tmp_path, "20260628_130000", metrics_payload(score=100))

    result = baseline_json(
        tmp_path,
        "--promote-latest",
        "--label",
        "stable",
        "--json",
    )

    baseline_path = tmp_path / ".vibebench" / "baselines" / "stable.json"
    stored = json.loads(baseline_path.read_text(encoding="utf-8"))
    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "promoted"
    assert payload["baseline_written"] is True
    assert stored["run_id"] == latest.name
    assert stored["label"] == "stable"
    assert stored["source"] == "promote-latest"


def test_baseline_promote_run_writes_explicit_run(tmp_path: Path) -> None:
    selected = write_run(tmp_path, "20260628_120000", metrics_payload(score=90))
    write_run(tmp_path, "20260628_130000", metrics_payload(score=100))

    result = baseline_json(
        tmp_path,
        "--promote-run",
        selected.name,
        "--label",
        "stable",
        "--json",
    )

    stored = json.loads(
        (tmp_path / ".vibebench" / "baselines" / "stable.json").read_text(
            encoding="utf-8"
        )
    )
    assert result.exit_code == 0
    assert json.loads(result.output)["candidate_run_id"] == selected.name
    assert stored["run_id"] == selected.name
    assert stored["source"] == "promote-run"


def test_baseline_promote_missing_run_fails(tmp_path: Path) -> None:
    write_run(tmp_path, "20260628_120000")

    result = baseline_json(
        tmp_path,
        "--promote-run",
        "missing",
        "--label",
        "stable",
        "--json",
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert payload["checks"][0]["name"] == "run_exists"
    assert payload["checks"][0]["status"] == "failed"
    assert not (tmp_path / ".vibebench" / "baselines" / "stable.json").exists()


def test_baseline_promote_missing_metrics_fails(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000")
    run_dir.joinpath("metrics.json").unlink()

    result = baseline_json(
        tmp_path,
        "--promote-run",
        run_dir.name,
        "--label",
        "stable",
        "--json",
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert any(check["name"] == "run_exists" for check in payload["checks"])
    assert not (tmp_path / ".vibebench" / "baselines" / "stable.json").exists()


def test_baseline_promote_requires_manifest_when_requested(tmp_path: Path) -> None:
    write_run(tmp_path, "20260628_120000")

    result = baseline_json(
        tmp_path,
        "--promote-latest",
        "--label",
        "stable",
        "--require-manifest",
        "--json",
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert any(
        check["name"] == "manifest_consistent" and check["status"] == "failed"
        for check in payload["checks"]
    )


def test_baseline_promote_requires_existing_baseline(tmp_path: Path) -> None:
    write_run(tmp_path, "20260628_120000")

    result = baseline_json(
        tmp_path,
        "--promote-latest",
        "--label",
        "stable",
        "--require-existing-baseline",
        "--json",
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert any(
        check["name"] == "regression_policy" and check["status"] == "failed"
        for check in payload["checks"]
    )


def test_baseline_promote_runs_regression_and_blocks_failure(
    tmp_path: Path,
) -> None:
    baseline = write_run(tmp_path, "20260628_120000", metrics_payload(score=100))
    candidate = write_run(tmp_path, "20260628_130000", metrics_payload(score=90))
    first = baseline_json(tmp_path, "--set-run", baseline.name, "--label", "stable")
    assert first.exit_code == 0

    result = baseline_json(
        tmp_path,
        "--promote-run",
        candidate.name,
        "--label",
        "stable",
        "--json",
    )

    payload = json.loads(result.output)
    stored = json.loads(
        (tmp_path / ".vibebench" / "baselines" / "stable.json").read_text(
            encoding="utf-8"
        )
    )
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert payload["regression_check"]["status"] == "failed"
    assert stored["run_id"] == baseline.name


def test_baseline_promote_allows_forced_regression_failure(
    tmp_path: Path,
) -> None:
    baseline = write_run(tmp_path, "20260628_120000", metrics_payload(score=100))
    candidate = write_run(tmp_path, "20260628_130000", metrics_payload(score=90))
    first = baseline_json(tmp_path, "--set-run", baseline.name, "--label", "stable")
    assert first.exit_code == 0

    result = baseline_json(
        tmp_path,
        "--promote-run",
        candidate.name,
        "--label",
        "stable",
        "--allow-regression-failure",
        "--json",
    )

    payload = json.loads(result.output)
    stored = json.loads(
        (tmp_path / ".vibebench" / "baselines" / "stable.json").read_text(
            encoding="utf-8"
        )
    )
    assert result.exit_code == 0
    assert payload["status"] == "promoted"
    assert payload["promotion_forced"] is True
    assert payload["regression_check"]["status"] == "failed"
    assert stored["run_id"] == candidate.name


def test_baseline_promote_json_stdout_is_pure(tmp_path: Path) -> None:
    write_run(tmp_path, "20260628_120000")

    result = baseline_json(tmp_path, "--promote-latest", "--label", "stable", "--json")

    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "promoted"
    assert "VibeBench baseline promotion" not in result.output


def test_baseline_promote_json_output_and_summary_output(tmp_path: Path) -> None:
    write_run(tmp_path, "20260628_120000")
    json_output = tmp_path / "promotion.json"
    summary_output = tmp_path / "promotion.md"

    result = baseline_json(
        tmp_path,
        "--promote-latest",
        "--label",
        "stable",
        "--json-output",
        str(json_output),
        "--summary-output",
        str(summary_output),
        "--json",
    )

    stdout_payload = json.loads(result.output)
    file_payload = json.loads(json_output.read_text(encoding="utf-8"))
    summary = summary_output.read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert stdout_payload["status"] == "promoted"
    assert file_payload["status"] == "promoted"
    assert summary.startswith("# VibeBench Baseline Promotion")
    assert "## Checks" in summary


def test_baseline_promote_uses_config_label_when_omitted(tmp_path: Path) -> None:
    config_dir = tmp_path / ".vibebench"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_dir.joinpath("config.yaml").write_text(
        """project:
  name: demo
checks:
  test:
    - pytest -q
regression:
  baseline_label: stable
""",
        encoding="utf-8",
    )
    latest = write_run(tmp_path, "20260628_120000")

    result = baseline_json(tmp_path, "--promote-latest", "--json")

    payload = json.loads(result.output)
    stored = json.loads(
        (tmp_path / ".vibebench" / "baselines" / "stable.json").read_text(
            encoding="utf-8"
        )
    )
    assert result.exit_code == 0
    assert payload["label"] == "stable"
    assert stored["run_id"] == latest.name


def test_baseline_promote_cli_label_overrides_config(tmp_path: Path) -> None:
    config_dir = tmp_path / ".vibebench"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_dir.joinpath("config.yaml").write_text(
        """project:
  name: demo
checks:
  test:
    - pytest -q
regression:
  baseline_label: stable
""",
        encoding="utf-8",
    )
    write_run(tmp_path, "20260628_120000")

    result = baseline_json(
        tmp_path,
        "--promote-latest",
        "--label",
        "candidate",
        "--json",
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["label"] == "candidate"
    assert (tmp_path / ".vibebench" / "baselines" / "candidate.json").exists()
    assert not (tmp_path / ".vibebench" / "baselines" / "stable.json").exists()
