import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

runner = CliRunner()


def sample_metrics() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": "demo-project",
        "created_at": "2026-07-01T12:00:00Z",
        "overall_status": "passed",
        "score": 100,
        "risk_level": "low",
        "command_results": [],
        "diff_analysis": {
            "changed_file_count": 2,
            "total_patch_lines": 14,
        },
        "risk_findings": [{"severity": "info", "code": "test", "message": "x"}],
        "summary": {
            "total_commands": 0,
            "passed_commands": 0,
            "failed_commands": 0,
            "total_findings": 1,
        },
    }


def write_run(
    project_root: Path,
    name: str = "20260701_120000",
    *,
    metrics: dict[str, object] | None = None,
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    run_dir.joinpath("metrics.json").write_text(
        json.dumps(metrics or sample_metrics(), indent=2),
        encoding="utf-8",
    )
    run_dir.joinpath("check.log").write_text("ok\n", encoding="utf-8")
    return run_dir


def read_manifest(run_dir: Path) -> dict[str, object]:
    return json.loads(run_dir.joinpath("manifest.json").read_text(encoding="utf-8"))


def artifact_by_name(payload: dict[str, object], name: str) -> dict[str, object]:
    artifacts = payload["artifacts"]
    assert isinstance(artifacts, list)
    return next(
        item
        for item in artifacts
        if isinstance(item, dict) and item["name"] == name
    )


def test_manifest_writes_latest_run(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_110000")
    latest = write_run(tmp_path, "20260701_120000")

    result = runner.invoke(app, ["manifest", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Manifest written" in result.output
    payload = read_manifest(latest)
    assert payload["schema_version"] == "vibebench.manifest.v1"
    assert payload["run_id"] == latest.name
    assert payload["project"] == "demo-project"
    assert payload["status"] == "passed"
    assert payload["score"] == 100
    assert payload["risk_level"] == "low"
    assert payload["findings_count"] == 1
    assert payload["changed_files"] == 2
    assert payload["patch_lines"] == 14


def test_manifest_run_dir_option(tmp_path: Path) -> None:
    first = write_run(tmp_path, "20260701_110000")
    write_run(tmp_path, "20260701_120000")

    result = runner.invoke(
        app,
        ["manifest", "--project-root", str(tmp_path), "--run-dir", str(first)],
    )

    assert result.exit_code == 0
    assert first.joinpath("manifest.json").exists()


def test_manifest_output_option(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    output = tmp_path / "manifest-output.json"

    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8"))["run_id"] == run_dir.name


def test_manifest_contains_artifact_entries_and_itself(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        ["manifest", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 0
    payload = read_manifest(run_dir)
    metrics = artifact_by_name(payload, "metrics.json")
    manifest = artifact_by_name(payload, "manifest.json")
    assert metrics["available"] is True
    assert isinstance(metrics["size_bytes"], int)
    assert manifest["available"] is True
    assert isinstance(manifest["size_bytes"], int)
    assert manifest["size_bytes"] > 0


def test_manifest_corrupt_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260701_120000"
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text("{nope", encoding="utf-8")

    result = runner.invoke(
        app,
        ["manifest", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 1
    assert "not valid JSON" in result.output


def test_manifest_invalid_run_dir_fails_clearly(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(tmp_path / "missing"),
        ],
    )

    assert result.exit_code == 1
    assert "Run directory does not exist" in result.output


def test_manifest_invalid_output_parent_fails_clearly(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    output = tmp_path / "missing" / "manifest.json"

    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    assert "Output parent directory does not exist" in result.output
