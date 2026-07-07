import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

runner = CliRunner()


def sample_metrics() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": "demo-project",
        "created_at": "2026-06-30T12:00:00Z",
        "overall_status": "passed",
        "score": 100,
        "risk_level": "low",
        "command_results": [],
        "summary": {
            "total_commands": 0,
            "passed_commands": 0,
            "failed_commands": 0,
        },
    }


def write_run(
    project_root: Path,
    name: str = "20260630_120000",
    *,
    metrics: dict[str, object] | None = None,
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / name
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text(
        json.dumps(metrics or sample_metrics()),
        encoding="utf-8",
    )
    return run_dir


def test_default_latest_run_artifact_listing(tmp_path: Path) -> None:
    old_run = write_run(tmp_path, "20260630_110000")
    latest_run = write_run(tmp_path, "20260630_120000")
    latest_run.joinpath("check.log").write_text("ok\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["run_id"] == latest_run.name
    assert payload["run_id"] != old_run.name
    artifacts = {item["name"]: item for item in payload["artifacts"]}
    assert artifacts["metrics.json"]["available"] is True
    assert artifacts["check.log"]["available"] is True
    assert artifacts["pr-comment.md"]["available"] is False
    assert "trend.md" in artifacts
    assert "trend.json" in artifacts
    assert "manifest.json" in artifacts
    assert "config-check.json" in artifacts
    assert "config-check.md" in artifacts
    assert "package-check.json" in artifacts
    assert "package-check.md" in artifacts
    assert "run-index.json" in artifacts
    assert "run-index.md" in artifacts
    assert "compare.json" in artifacts
    assert "compare.md" in artifacts
    assert "metrics-check-json" in artifacts
    assert "metrics-check-md" in artifacts
    assert "metrics-diff-json" in artifacts
    assert "metrics-diff-md" in artifacts
    assert "project-scan-json" in artifacts
    assert "project-scan-md" in artifacts
    assert "onboard-json" in artifacts
    assert "onboard-md" in artifacts
    assert "workflow-template-json" in artifacts
    assert "workflow-template-md" in artifacts
    assert "workflow-template-yml" in artifacts
    assert "workflow-check-json" in artifacts
    assert "workflow-check-md" in artifacts
    assert "regression-check-json" in artifacts
    assert "regression-check-md" in artifacts
    assert "evidence-room-security-questionnaire-html" in artifacts
    assert "evidence-room-security-questionnaire-md" in artifacts
    assert "evidence-room-share-check-json" in artifacts
    assert "evidence-room-share-check-md" in artifacts


def test_explicit_run_dir_is_used(tmp_path: Path) -> None:
    first = write_run(tmp_path, "20260630_110000")
    write_run(tmp_path, "20260630_120000")

    result = runner.invoke(
        app,
        [
            "artifacts",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(first),
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["run_id"] == first.name


def test_missing_run_directory_fails_clearly(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "artifacts",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(tmp_path / "missing"),
        ],
    )

    assert result.exit_code == 1
    assert "Run directory does not exist" in result.output


def test_missing_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260630_120000"
    run_dir.mkdir(parents=True)

    result = runner.invoke(
        app,
        [
            "artifacts",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
        ],
    )

    assert result.exit_code == 1
    assert "No metrics.json found" in result.output


def test_corrupt_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260630_120000"
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text("{nope", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "artifacts",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
        ],
    )

    assert result.exit_code == 1
    assert "not valid JSON" in result.output


def test_table_output_lists_artifacts(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    report_dir = run_dir / "report"
    report_dir.mkdir()
    report_dir.joinpath("index.html").write_text("<html></html>\n", encoding="utf-8")

    result = runner.invoke(app, ["artifacts", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "VibeBench artifacts" in result.output
    assert "metrics.json" in result.output
    assert "available" in result.output


def test_available_and_missing_artifacts_are_detected(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    report_dir = run_dir / "report"
    report_dir.mkdir()
    report_dir.joinpath("index.html").write_text("<html></html>\n", encoding="utf-8")
    evidence_dir = run_dir / "evidence-room"
    evidence_dir.mkdir()
    evidence_dir.joinpath("security-questionnaire.html").write_text(
        "<html></html>\n",
        encoding="utf-8",
    )
    evidence_dir.joinpath("security-questionnaire.md").write_text(
        "questionnaire\n",
        encoding="utf-8",
    )
    evidence_dir.joinpath("share-check.json").write_text(
        '{"status":"passed"}\n',
        encoding="utf-8",
    )
    evidence_dir.joinpath("share-check.md").write_text(
        "local pre-sharing aid; not a security certification; "
        "not a third-party audit; not a guarantee\n",
        encoding="utf-8",
    )
    run_dir.joinpath("metrics-check.json").write_text(
        '{"status":"passed"}\n',
        encoding="utf-8",
    )
    run_dir.joinpath("metrics-check.md").write_text(
        "# VibeBench Metrics Check\n",
        encoding="utf-8",
    )
    run_dir.joinpath("metrics-diff.json").write_text(
        '{"status":"passed"}\n',
        encoding="utf-8",
    )
    run_dir.joinpath("metrics-diff.md").write_text(
        "# VibeBench Metrics Diff\n",
        encoding="utf-8",
    )
    run_dir.joinpath("project-scan.json").write_text(
        '{"status":"ready"}\n',
        encoding="utf-8",
    )
    run_dir.joinpath("project-scan.md").write_text(
        "# VibeBench Project Scan\n",
        encoding="utf-8",
    )
    run_dir.joinpath("onboard.json").write_text(
        '{"status":"ready"}\n',
        encoding="utf-8",
    )
    run_dir.joinpath("onboard.md").write_text(
        "# VibeBench Onboarding Plan\n",
        encoding="utf-8",
    )
    run_dir.joinpath("workflow-check.json").write_text(
        '{"status":"passed"}\n',
        encoding="utf-8",
    )
    run_dir.joinpath("workflow-check.md").write_text(
        "# VibeBench Workflow Check\n",
        encoding="utf-8",
    )
    run_dir.joinpath("regression-check.json").write_text(
        '{"status":"passed"}\n',
        encoding="utf-8",
    )
    run_dir.joinpath("regression-check.md").write_text(
        "# VibeBench Regression Check\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    artifacts = {item["name"]: item for item in json.loads(result.output)["artifacts"]}
    assert artifacts["report/index.html"]["available"] is True
    assert artifacts["pr-comment.md"]["available"] is False
    assert artifacts["evidence-room-security-questionnaire-html"]["available"] is True
    assert artifacts["evidence-room-security-questionnaire-md"]["available"] is True
    assert artifacts["evidence-room-share-check-json"]["available"] is True
    assert artifacts["evidence-room-share-check-md"]["available"] is True
    assert artifacts["metrics-check-json"]["available"] is True
    assert artifacts["metrics-check-md"]["available"] is True
    assert artifacts["metrics-diff-json"]["available"] is True
    assert artifacts["metrics-diff-md"]["available"] is True
    assert artifacts["project-scan-json"]["available"] is True
    assert artifacts["project-scan-md"]["available"] is True
    assert artifacts["onboard-json"]["available"] is True
    assert artifacts["onboard-md"]["available"] is True
    assert artifacts["regression-check-json"]["available"] is True
    assert artifacts["regression-check-md"]["available"] is True


def test_only_available_hides_missing_artifacts(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    run_dir.joinpath("check.log").write_text("ok\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "artifacts",
            "--project-root",
            str(tmp_path),
            "--only-available",
            "--json",
        ],
    )

    assert result.exit_code == 0
    names = {item["name"] for item in json.loads(result.output)["artifacts"]}
    assert "metrics.json" in names
    assert "check.log" in names
    assert "pr-comment.md" not in names


def test_strict_fails_when_optional_artifacts_are_missing(tmp_path: Path) -> None:
    write_run(tmp_path)

    result = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--strict"],
    )

    assert result.exit_code == 1
    assert "Missing expected artifact" in result.output
    assert "check.log" in result.output


def test_json_output_is_valid_and_stable(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    run_dir.joinpath("check.log").write_text("ok\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["run_id"] == "20260630_120000"
    assert payload["run_dir"] == str(run_dir.resolve())
    artifacts = payload["artifacts"]
    metrics = next(item for item in artifacts if item["name"] == "metrics.json")
    assert metrics["path"].endswith(".vibebench/runs/20260630_120000/metrics.json")
    assert metrics["available"] is True
    assert isinstance(metrics["size_bytes"], int)
    missing = next(item for item in artifacts if item["name"] == "pr-comment.md")
    assert missing["available"] is False
    assert missing["size_bytes"] is None


def test_pinned_baseline_state_is_not_listed_as_run_artifact(tmp_path: Path) -> None:
    write_run(tmp_path)
    baseline_dir = tmp_path / ".vibebench" / "baselines"
    baseline_dir.mkdir(parents=True)
    baseline_dir.joinpath("stable.json").write_text('{"run_id":"demo"}\n')

    result = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )

    payload = json.loads(result.output)
    artifact_names = {item["name"] for item in payload["artifacts"]}
    artifact_paths = {item["path"] for item in payload["artifacts"]}
    assert result.exit_code == 0
    assert "stable.json" not in artifact_names
    assert all(".vibebench/baselines" not in path for path in artifact_paths)
