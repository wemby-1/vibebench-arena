import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.gh_summary import generate_github_summary
from vibebench.report import ReportError, find_latest_run

runner = CliRunner()


def sample_metrics(project_name: str = "demo-project") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": project_name,
        "created_at": "2026-06-27T12:00:00Z",
        "overall_status": "failed",
        "score": 64,
        "risk_level": "high",
        "command_results": [
            {
                "group": "test",
                "command": "pytest -q",
                "exit_code": 0,
                "stdout": "ok",
                "stderr": "",
                "duration_seconds": 1.25,
                "status": "passed",
            },
            {
                "group": "lint",
                "command": "ruff check .",
                "exit_code": 1,
                "stdout": "",
                "stderr": "lint failed",
                "duration_seconds": 0.5,
                "status": "failed",
            },
        ],
        "diff_analysis": {
            "git_available": True,
            "changed_files": ["src/app.py", ".env.local"],
            "deleted_files": ["tests/test_old.py"],
            "added_files": [".env.local"],
            "modified_files": ["src/app.py"],
            "renamed_files": [],
            "test_files_changed": ["tests/test_old.py"],
            "tests_deleted": ["tests/test_old.py"],
            "forbidden_paths_touched": [".env.local"],
            "secret_like_files_touched": ["secrets/config.json"],
            "lockfiles_changed": ["package-lock.json"],
            "total_added_lines": 10,
            "total_deleted_lines": 3,
            "total_patch_lines": 13,
            "changed_file_count": 2,
            "warnings": [],
            "file_changes": [],
        },
        "risk_findings": [
            {
                "severity": "critical",
                "code": "forbidden_paths_touched",
                "message": "Forbidden paths were touched.",
                "paths": [".env.local"],
            }
        ],
        "summary": {
            "total_commands": 2,
            "passed_commands": 1,
            "failed_commands": 1,
            "total_findings": 1,
            "critical_findings": 1,
            "high_findings": 0,
            "warning_findings": 0,
            "info_findings": 0,
        },
        "run_dir": "",
        "metrics_path": "",
        "log_path": "",
    }


def write_run(
    project_root: Path,
    name: str,
    metrics: dict[str, object] | None = None,
    with_artifacts: bool = True,
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = metrics or sample_metrics()
    payload["run_dir"] = str(run_dir)
    payload["metrics_path"] = str(run_dir / "metrics.json")
    payload["log_path"] = str(run_dir / "check.log")
    (run_dir / "metrics.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    if with_artifacts:
        (run_dir / "check.log").write_text("check log\n", encoding="utf-8")
        report_dir = run_dir / "report"
        report_dir.mkdir()
        (report_dir / "index.html").write_text("<html></html>\n", encoding="utf-8")
        (run_dir / "pr-comment.md").write_text("comment\n", encoding="utf-8")
        (run_dir / "explain.md").write_text("explain\n", encoding="utf-8")
        (run_dir / "vibebench-bundle.zip").write_text("zip\n", encoding="utf-8")
        (run_dir / "export.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "badge.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "badge.md").write_text("![badge](url)\n", encoding="utf-8")
        (run_dir / "status-block.md").write_text("status\n", encoding="utf-8")
        (run_dir / "trend.md").write_text("trend\n", encoding="utf-8")
        (run_dir / "trend.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "run-index.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "run-index.md").write_text("run index\n", encoding="utf-8")
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
        (run_dir / "project-scan.json").write_text(
            '{"status":"ready"}\n',
            encoding="utf-8",
        )
        (run_dir / "project-scan.md").write_text(
            "# VibeBench Project Scan\n",
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
        (run_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "package-check.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "package-check.md").write_text("package\n", encoding="utf-8")
        (run_dir / "release-check.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "release-check.md").write_text("release\n", encoding="utf-8")
        (run_dir / "gate-summary.md").write_text("gate\n", encoding="utf-8")
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


def test_gh_summary_writes_to_github_step_summary_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = write_run(tmp_path, "20260627_120000")
    output_path = tmp_path / "step-summary.md"
    output_path.write_text("existing\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(output_path))

    result_path = generate_github_summary(tmp_path, run_dir)

    content = output_path.read_text(encoding="utf-8")
    assert result_path == output_path
    assert content.startswith("existing\n# VibeBench Summary")
    assert "demo-project" in content
    assert "64" in content
    assert "forbidden_paths_touched" in content


def test_gh_summary_writes_to_run_dir_when_env_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    run_dir = write_run(tmp_path, "20260627_120000")

    output_path = generate_github_summary(tmp_path, run_dir)

    assert output_path == run_dir / "github-step-summary.md"
    assert output_path.exists()


def test_run_dir_option_works(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    first = write_run(tmp_path, "20260627_120000", sample_metrics("first-project"))
    second = write_run(tmp_path, "20260627_130000", sample_metrics("second-project"))

    result = runner.invoke(
        app,
        [
            "gh-summary",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(first),
        ],
    )

    assert result.exit_code == 0
    assert first.joinpath("github-step-summary.md").exists()
    assert not second.joinpath("github-step-summary.md").exists()
    assert "GitHub step summary written." in result.output


def test_missing_runs_helpful_failure(tmp_path: Path) -> None:
    with pytest.raises(ReportError, match="Run 'vibebench check' first"):
        find_latest_run(tmp_path)

    result = runner.invoke(app, ["gh-summary", "--project-root", str(tmp_path)])
    assert result.exit_code == 1
    assert "No VibeBench runs found. Run 'vibebench check' first." in result.output


def test_summary_contains_key_sections_and_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    run_dir = write_run(tmp_path, "20260627_120000")

    output_path = generate_github_summary(tmp_path, run_dir)
    markdown = output_path.read_text(encoding="utf-8")

    assert "# VibeBench Summary" in markdown
    assert "**VibeScore:** 64" in markdown
    assert "🟠 high" in markdown
    assert "| test | `pytest -q` | ✅ passed | 0 | 1.250s |" in markdown
    assert "| lint | `ruff check .` | ❌ failed | 1 | 0.500s |" in markdown
    assert "**Changed files:** 2" in markdown
    assert "**Risk findings:** 1" in markdown
    assert "**critical** `forbidden_paths_touched`" in markdown
    assert "`metrics.json` (available)" in markdown
    assert "`check.log` (available)" in markdown
    assert "`report/index.html` (available)" in markdown
    assert "`pr-comment.md` (available)" in markdown
    assert "`explain.md` (available)" in markdown
    assert "`vibebench-bundle.zip` (available)" in markdown
    assert "`export.json` (available)" in markdown
    assert "`badge.json` (available)" in markdown
    assert "`badge.md` (available)" in markdown
    assert "`status-block.md` (available)" in markdown
    assert "`trend.md` (available)" in markdown
    assert "`trend.json` (available)" in markdown
    assert "`run-index.json` (available)" in markdown
    assert "`run-index.md` (available)" in markdown
    assert "`compare.json` (available)" in markdown
    assert "`compare.md` (available)" in markdown
    assert "`metrics-check.json` (available)" in markdown
    assert "`metrics-check.md` (available)" in markdown
    assert "`metrics-diff.json` (available)" in markdown
    assert "`metrics-diff.md` (available)" in markdown
    assert "`project-scan.json` (available)" in markdown
    assert "`project-scan.md` (available)" in markdown
    assert "`regression-check.json` (available)" in markdown
    assert "`regression-check.md` (available)" in markdown
    assert "`evidence-room/index.html` (available)" in markdown
    assert "`evidence-room/review-hub.html` (available)" in markdown
    assert "`evidence-room/reviewer-guide.md` (available)" in markdown
    assert "`evidence-room/trust-center.html` (available)" in markdown
    assert "`evidence-room/trust-center.md` (available)" in markdown
    assert "`evidence-room/security-questionnaire.html` (available)" in markdown
    assert "`evidence-room/security-questionnaire.md` (available)" in markdown
    assert "`evidence-room/review-scorecard.html` (available)" in markdown
    assert "`evidence-room/review-scorecard.md` (available)" in markdown
    assert "`evidence-room/review-scorecard.json` (available)" in markdown
    assert "`evidence-room/share-check.json` (available)" in markdown
    assert "`evidence-room/share-check.md` (available)" in markdown
    assert "`evidence-room/evidence-room.html` (available)" in markdown
    assert "`evidence-room/evidence-room.json` (available)" in markdown
    assert "`evidence-room/evidence-room.md` (available)" in markdown
    assert "`evidence-room/evidence-room.zip` (available)" in markdown
    assert "`manifest.json` (available)" in markdown
    assert "`package-check.json` (available)" in markdown
    assert "`package-check.md` (available)" in markdown
    assert "`release-check.json` (available)" in markdown
    assert "`release-check.md` (available)" in markdown
    assert "`gate-summary.md` (available)" in markdown
    assert "Codex writes code. VibeBench verifies it." in markdown
