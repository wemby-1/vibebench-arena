import json
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from vibebench.bundle import create_bundle
from vibebench.cli import app

runner = CliRunner()


def sample_metrics(project_name: str = "demo-project") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": project_name,
        "created_at": "2026-06-29T12:00:00Z",
        "overall_status": "passed",
        "score": 100,
        "risk_level": "low",
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
    full: bool = True,
    metrics: dict[str, object] | None = None,
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = metrics or sample_metrics()
    (run_dir / "metrics.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    if full:
        (run_dir / "check.log").write_text("check log\n", encoding="utf-8")
        report_dir = run_dir / "report"
        report_dir.mkdir()
        (report_dir / "index.html").write_text("<html></html>\n", encoding="utf-8")
        (report_dir / "style.css").write_text("body {}\n", encoding="utf-8")
        (run_dir / "pr-comment.md").write_text("comment\n", encoding="utf-8")
        (run_dir / "github-step-summary.md").write_text(
            "summary\n",
            encoding="utf-8",
        )
        (run_dir / "gate-summary.md").write_text("gate\n", encoding="utf-8")
        (run_dir / "explain.md").write_text("explain\n", encoding="utf-8")
        (run_dir / "export.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "badge.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "badge.md").write_text("![badge](url)\n", encoding="utf-8")
        (run_dir / "badge-url.txt").write_text("url\n", encoding="utf-8")
        (run_dir / "status-block.md").write_text("status\n", encoding="utf-8")
        (run_dir / "trend.md").write_text("trend\n", encoding="utf-8")
        (run_dir / "trend.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "run-index.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "run-index.md").write_text("run index\n", encoding="utf-8")
        (run_dir / "config-check.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "config-check.md").write_text("config check\n", encoding="utf-8")
        (run_dir / "package-check.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "package-check.md").write_text("package check\n", encoding="utf-8")
        (run_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "compare.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "compare.md").write_text("compare\n", encoding="utf-8")
        (run_dir / "metrics-check.json").write_text(
            '{"status":"passed"}\n',
            encoding="utf-8",
        )
        (run_dir / "metrics-check.md").write_text(
            "# VibeBench Metrics Check\n",
            encoding="utf-8",
        )
        (run_dir / "metrics-diff.json").write_text(
            '{"status":"passed"}\n',
            encoding="utf-8",
        )
        (run_dir / "metrics-diff.md").write_text(
            "# VibeBench Metrics Diff\n",
            encoding="utf-8",
        )
        (run_dir / "regression-check.json").write_text(
            '{"status":"passed"}\n',
            encoding="utf-8",
        )
        (run_dir / "regression-check.md").write_text(
            "# VibeBench Regression Check\n",
            encoding="utf-8",
        )
        evidence_dir = run_dir / "evidence-room"
        evidence_dir.mkdir()
        (evidence_dir / "index.html").write_text(
            "<html></html>\n",
            encoding="utf-8",
        )
        (evidence_dir / "review-hub.html").write_text(
            "<html></html>\n",
            encoding="utf-8",
        )
        (evidence_dir / "reviewer-guide.md").write_text(
            "guide\n",
            encoding="utf-8",
        )
        (evidence_dir / "trust-center.html").write_text(
            "<html></html>\n",
            encoding="utf-8",
        )
        (evidence_dir / "trust-center.md").write_text(
            "trust\n",
            encoding="utf-8",
        )
        (evidence_dir / "security-questionnaire.html").write_text(
            "<html></html>\n",
            encoding="utf-8",
        )
        (evidence_dir / "security-questionnaire.md").write_text(
            "questionnaire\n",
            encoding="utf-8",
        )
        (evidence_dir / "review-scorecard.html").write_text(
            "<html></html>\n",
            encoding="utf-8",
        )
        (evidence_dir / "review-scorecard.md").write_text(
            "scorecard\n",
            encoding="utf-8",
        )
        (evidence_dir / "review-scorecard.json").write_text(
            "{}\n",
            encoding="utf-8",
        )
        (evidence_dir / "share-check.json").write_text(
            '{"status":"passed"}\n',
            encoding="utf-8",
        )
        (evidence_dir / "share-check.md").write_text(
            "local pre-sharing aid; not a security certification; "
            "not a third-party audit; not a guarantee\n",
            encoding="utf-8",
        )
        (evidence_dir / "evidence-room.html").write_text(
            "<html></html>\n",
            encoding="utf-8",
        )
        (evidence_dir / "evidence-room.json").write_text("{}\n", encoding="utf-8")
        (evidence_dir / "evidence-room.md").write_text("evidence\n", encoding="utf-8")
        (evidence_dir / "evidence-room.zip").write_text("zip\n", encoding="utf-8")
    return run_dir


def zip_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return sorted(archive.namelist())


def test_latest_run_bundle_is_created(tmp_path: Path) -> None:
    write_run(tmp_path, "20260629_120000")
    latest = write_run(tmp_path, "20260629_130000")

    result = create_bundle(tmp_path)

    assert result.run_dir == latest.resolve()
    assert result.output_path == latest / "vibebench-bundle.zip"
    names = zip_names(result.output_path)
    assert "metrics.json" in names
    assert "check.log" in names
    assert "report/index.html" in names
    assert "export.json" in names
    assert "badge.json" in names
    assert "badge.md" in names
    assert "badge-url.txt" in names
    assert "status-block.md" in names
    assert "trend.md" in names
    assert "trend.json" in names
    assert "run-index.json" in names
    assert "run-index.md" in names
    assert "config-check.json" in names
    assert "config-check.md" in names
    assert "package-check.json" in names
    assert "package-check.md" in names
    assert "manifest.json" in names
    assert "compare.json" in names
    assert "compare.md" in names
    assert "metrics-check.json" in names
    assert "metrics-check.md" in names
    assert "metrics-diff.json" in names
    assert "metrics-diff.md" in names
    assert "regression-check.json" in names
    assert "regression-check.md" in names
    assert "evidence-room/index.html" in names
    assert "evidence-room/review-hub.html" in names
    assert "evidence-room/reviewer-guide.md" in names
    assert "evidence-room/trust-center.html" in names
    assert "evidence-room/trust-center.md" in names
    assert "evidence-room/security-questionnaire.html" in names
    assert "evidence-room/security-questionnaire.md" in names
    assert "evidence-room/review-scorecard.html" in names
    assert "evidence-room/review-scorecard.md" in names
    assert "evidence-room/review-scorecard.json" in names
    assert "evidence-room/share-check.json" in names
    assert "evidence-room/share-check.md" in names
    assert "evidence-room/evidence-room.html" in names
    assert "evidence-room/evidence-room.json" in names
    assert "evidence-room/evidence-room.md" in names
    assert "evidence-room/evidence-room.zip" in names
    assert "vibebench-bundle.zip" not in names


def test_run_dir_option_works(tmp_path: Path) -> None:
    first = write_run(tmp_path, "20260629_120000")
    second = write_run(tmp_path, "20260629_130000")

    result = runner.invoke(
        app,
        [
            "bundle",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(first),
        ],
    )

    assert result.exit_code == 0
    assert first.joinpath("vibebench-bundle.zip").exists()
    assert not second.joinpath("vibebench-bundle.zip").exists()
    assert "VibeBench bundle" in result.output


def test_bundle_command_refreshes_existing_manifest(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260629_120000")
    manifest = runner.invoke(
        app,
        ["manifest", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    result = runner.invoke(
        app,
        ["bundle", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )
    check = runner.invoke(
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

    assert manifest.exit_code == 0
    assert result.exit_code == 0
    assert check.exit_code == 0


def test_output_writes_custom_path(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260629_120000")
    output_path = tmp_path / "bundle.zip"

    result = runner.invoke(
        app,
        [
            "bundle",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    assert "metrics.json" in zip_names(output_path)


def test_missing_optional_artifacts_are_skipped_non_strict(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260629_120000", full=False)

    result = create_bundle(tmp_path, run_dir)

    assert result.output_path.exists()
    assert Path("check.log") in result.skipped_files
    assert zip_names(result.output_path) == ["metrics.json"]


def test_missing_optional_artifacts_fail_in_strict_mode(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260629_120000", full=False)

    result = runner.invoke(
        app,
        [
            "bundle",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--strict",
        ],
    )

    assert result.exit_code == 1
    assert "Missing expected artifact" in result.output
    assert "check.log" in result.output


def test_missing_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260629_120000"
    run_dir.mkdir(parents=True)

    result = runner.invoke(
        app,
        ["bundle", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 1
    assert "No metrics.json found" in result.output


def test_corrupt_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260629_120000"
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text("{not json", encoding="utf-8")

    result = runner.invoke(
        app,
        ["bundle", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 1
    assert "not valid JSON" in result.output


def test_symlink_files_and_dirs_are_not_followed(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260629_120000")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    run_dir.joinpath("linked.txt").symlink_to(outside)
    linked_dir = run_dir / "report" / "linked-dir"
    linked_dir.symlink_to(tmp_path, target_is_directory=True)

    result = create_bundle(tmp_path, run_dir, include_report_assets=True)

    names = zip_names(result.output_path)
    assert "linked.txt" not in names
    assert "report/linked-dir/outside.txt" not in names


def test_output_zip_does_not_include_itself(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260629_120000")
    output_path = run_dir / "vibebench-bundle.zip"
    output_path.write_text("old zip placeholder", encoding="utf-8")

    result = create_bundle(tmp_path, run_dir)

    assert "vibebench-bundle.zip" not in zip_names(result.output_path)


def test_include_report_assets_includes_nested_report_files(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260629_120000")
    asset_dir = run_dir / "report" / "assets"
    asset_dir.mkdir()
    asset_dir.joinpath("preview.css").write_text(".x {}\n", encoding="utf-8")

    result = create_bundle(tmp_path, run_dir, include_report_assets=True)

    names = zip_names(result.output_path)
    assert "report/index.html" in names
    assert "report/assets/preview.css" in names


def test_invalid_output_parent_fails_clearly(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260629_120000")
    output_path = tmp_path / "missing" / "bundle.zip"

    result = runner.invoke(
        app,
        [
            "bundle",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 1
    assert "Output parent directory does not exist" in result.output
