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
        item for item in artifacts if isinstance(item, dict) and item["name"] == name
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
    run_dir.joinpath("preflight.json").write_text(
        '{"status":"ready"}\n',
        encoding="utf-8",
    )
    run_dir.joinpath("preflight.md").write_text(
        "# VibeBench Preflight\n",
        encoding="utf-8",
    )
    run_dir.joinpath("workflow-template.json").write_text(
        '{"status":"planned"}\n',
        encoding="utf-8",
    )
    run_dir.joinpath("workflow-template.md").write_text(
        "# VibeBench Workflow Template\n",
        encoding="utf-8",
    )
    run_dir.joinpath("workflow-template.yml").write_text(
        "name: VibeBench\n",
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
    assert (
        artifact_by_name(payload, "evidence-room-security-questionnaire-html")[
            "available"
        ]
        is True
    )
    assert (
        artifact_by_name(payload, "evidence-room-security-questionnaire-md")[
            "available"
        ]
        is True
    )
    assert (
        artifact_by_name(payload, "evidence-room-share-check-json")["available"] is True
    )
    assert (
        artifact_by_name(payload, "evidence-room-share-check-md")["available"] is True
    )
    assert artifact_by_name(payload, "metrics-check-json")["available"] is True
    assert artifact_by_name(payload, "metrics-check-md")["available"] is True
    assert artifact_by_name(payload, "metrics-diff-json")["available"] is True
    assert artifact_by_name(payload, "metrics-diff-md")["available"] is True
    assert artifact_by_name(payload, "project-scan-json")["available"] is True
    assert artifact_by_name(payload, "project-scan-md")["available"] is True
    assert artifact_by_name(payload, "onboard-json")["available"] is True
    assert artifact_by_name(payload, "onboard-md")["available"] is True
    assert artifact_by_name(payload, "preflight-json")["available"] is True
    assert artifact_by_name(payload, "preflight-md")["available"] is True
    assert artifact_by_name(payload, "workflow-template-json")["available"] is True
    assert artifact_by_name(payload, "workflow-template-md")["available"] is True
    assert artifact_by_name(payload, "workflow-template-yml")["available"] is True
    assert artifact_by_name(payload, "workflow-check-json")["available"] is True
    assert artifact_by_name(payload, "workflow-check-md")["available"] is True
    assert artifact_by_name(payload, "regression-check-json")["available"] is True
    assert artifact_by_name(payload, "regression-check-md")["available"] is True


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


def write_manifest(project_root: Path, run_dir: Path) -> dict[str, object]:
    result = runner.invoke(
        app,
        ["manifest", "--project-root", str(project_root), "--run-dir", str(run_dir)],
    )
    assert result.exit_code == 0
    return read_manifest(run_dir)


def overwrite_manifest(run_dir: Path, payload: dict[str, object]) -> None:
    run_dir.joinpath("manifest.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def test_manifest_check_passes_after_writing(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    write_manifest(tmp_path, run_dir)

    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--check",
        ],
    )

    assert result.exit_code == 0
    assert "Manifest is consistent" in result.output


def test_manifest_check_run_dir_option_passes(tmp_path: Path) -> None:
    first = write_run(tmp_path, "20260701_110000")
    write_run(tmp_path, "20260701_120000")
    write_manifest(tmp_path, first)

    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(first),
            "--check",
        ],
    )

    assert result.exit_code == 0
    assert first.name in result.output or "Manifest is consistent" in result.output


def test_manifest_check_output_uses_custom_manifest_without_rewriting(
    tmp_path: Path,
) -> None:
    run_dir = write_run(tmp_path)
    custom_manifest = tmp_path / "custom-manifest.json"
    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--output",
            str(custom_manifest),
        ],
    )
    assert result.exit_code == 0
    before = custom_manifest.read_text(encoding="utf-8")

    check = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--output",
            str(custom_manifest),
            "--check",
        ],
    )

    assert check.exit_code == 0
    assert custom_manifest.read_text(encoding="utf-8") == before


def test_manifest_check_missing_manifest_fails_clearly(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--check",
        ],
    )

    assert result.exit_code == 1
    assert "No manifest.json found" in result.output


def test_manifest_check_corrupt_manifest_fails_clearly(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    run_dir.joinpath("manifest.json").write_text("{nope", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--check",
        ],
    )

    assert result.exit_code == 1
    assert "not valid JSON" in result.output


def test_manifest_check_corrupt_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    write_manifest(tmp_path, run_dir)
    run_dir.joinpath("metrics.json").write_text("{nope", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--check",
        ],
    )

    assert result.exit_code == 1
    assert "metrics.json" in result.output
    assert "not valid JSON" in result.output


def test_manifest_check_changed_artifact_availability_fails(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    write_manifest(tmp_path, run_dir)
    run_dir.joinpath("check.log").unlink()

    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--check",
        ],
    )

    assert result.exit_code == 1
    assert "artifact check.log available" in result.output


def test_manifest_check_changed_artifact_size_fails(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    write_manifest(tmp_path, run_dir)
    run_dir.joinpath("check.log").write_text("changed size\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--check",
        ],
    )

    assert result.exit_code == 1
    assert "artifact check.log size_bytes" in result.output


def test_manifest_check_missing_artifact_entry_fails(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    payload = write_manifest(tmp_path, run_dir)
    artifacts = payload["artifacts"]
    assert isinstance(artifacts, list)
    payload["artifacts"] = [
        item
        for item in artifacts
        if isinstance(item, dict) and item["name"] != "check.log"
    ]
    overwrite_manifest(run_dir, payload)

    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--check",
        ],
    )

    assert result.exit_code == 1
    assert "artifact check.log: missing entry" in result.output


def test_manifest_check_allows_missing_unavailable_new_artifact_entry(
    tmp_path: Path,
) -> None:
    run_dir = write_run(tmp_path)
    payload = write_manifest(tmp_path, run_dir)
    artifacts = payload["artifacts"]
    assert isinstance(artifacts, list)
    payload["artifacts"] = [
        item
        for item in artifacts
        if isinstance(item, dict) and item["name"] != "run-index.json"
    ]
    overwrite_manifest(run_dir, payload)

    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--check",
        ],
    )

    assert result.exit_code == 0
    assert "Manifest is consistent" in result.output


def test_manifest_check_mismatched_run_id_and_score_fail(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    payload = write_manifest(tmp_path, run_dir)
    payload["run_id"] = "wrong-run"
    payload["score"] = 12
    overwrite_manifest(run_dir, payload)

    result = runner.invoke(
        app,
        [
            "manifest",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--check",
        ],
    )

    assert result.exit_code == 1
    assert "run_id" in result.output
    assert "score" in result.output
