import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.pr_comment import generate_pr_comment
from vibebench.report import ReportError, find_latest_run

runner = CliRunner()


def sample_metrics(
    project_name: str = "demo-project",
    findings: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": project_name,
        "created_at": "2026-06-26T12:00:00Z",
        "overall_status": "passed",
        "score": 92,
        "risk_level": "low",
        "command_results": [
            {
                "group": "test",
                "command": "pytest -q",
                "exit_code": 0,
                "stdout": "ok",
                "stderr": "",
                "duration_seconds": 1.25,
                "status": "passed",
            }
        ],
        "diff_analysis": {
            "git_available": True,
            "changed_files": ["src/app.py"],
            "deleted_files": [],
            "added_files": [],
            "modified_files": ["src/app.py"],
            "renamed_files": [],
            "test_files_changed": ["tests/test_app.py"],
            "tests_deleted": ["tests/test_old.py"],
            "forbidden_paths_touched": [".env.local"],
            "secret_like_files_touched": ["config/token.txt"],
            "lockfiles_changed": ["package-lock.json"],
            "total_added_lines": 10,
            "total_deleted_lines": 2,
            "total_patch_lines": 12,
            "changed_file_count": 1,
            "warnings": [],
            "file_changes": [],
        },
        "risk_findings": findings
        if findings is not None
        else [
            {
                "severity": "warning",
                "code": "lockfiles_changed",
                "message": "Lockfiles changed.",
                "paths": ["package-lock.json"],
            }
        ],
        "summary": {
            "total_commands": 1,
            "passed_commands": 1,
            "failed_commands": 0,
            "total_findings": 1,
            "critical_findings": 0,
            "high_findings": 0,
            "warning_findings": 1,
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
    return run_dir


def test_pr_comment_generation_creates_markdown(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260626_120000")

    comment_path = generate_pr_comment(tmp_path, run_dir)

    assert comment_path == run_dir / "pr-comment.md"
    assert comment_path.exists()


def test_missing_runs_helpful_failure(tmp_path: Path) -> None:
    with pytest.raises(ReportError, match="Run 'vibebench check' first"):
        find_latest_run(tmp_path)

    result = runner.invoke(app, ["pr-comment", "--project-root", str(tmp_path)])
    assert result.exit_code == 1
    assert "No VibeBench runs found. Run 'vibebench check' first." in result.output


def test_generated_markdown_contains_expected_sections(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260626_120000")

    comment_path = generate_pr_comment(tmp_path, run_dir)
    markdown = comment_path.read_text(encoding="utf-8")

    assert "## VibeBench Check" in markdown
    assert "demo-project" in markdown
    assert "92" in markdown
    assert "🟢 low" in markdown
    assert "`pytest -q`" in markdown
    assert "Changed files" in markdown
    assert "Lockfiles changed" in markdown
    assert "Looks safe to review and ship" in markdown
    assert "Codex writes code. VibeBench verifies it." in markdown


def test_risk_findings_are_rendered(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260626_120000")

    comment_path = generate_pr_comment(tmp_path, run_dir)
    markdown = comment_path.read_text(encoding="utf-8")

    assert "**warning** `lockfiles_changed`" in markdown
    assert "`package-lock.json`" in markdown


def test_long_finding_list_is_capped(tmp_path: Path) -> None:
    findings = [
        {
            "severity": "warning",
            "code": f"finding_{index}",
            "message": f"Finding {index}",
            "paths": [f"path-{index}.txt"],
        }
        for index in range(12)
    ]
    run_dir = write_run(tmp_path, "20260626_120000", sample_metrics(findings=findings))

    comment_path = generate_pr_comment(tmp_path, run_dir)
    markdown = comment_path.read_text(encoding="utf-8")

    assert "finding_9" in markdown
    assert "finding_10" not in markdown
    assert "...and 2 more findings." in markdown


def test_run_dir_option_works(tmp_path: Path) -> None:
    first = write_run(tmp_path, "20260626_120000", sample_metrics("first-project"))
    second = write_run(tmp_path, "20260626_130000", sample_metrics("second-project"))

    result = runner.invoke(
        app,
        [
            "pr-comment",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(first),
        ],
    )

    assert result.exit_code == 0
    assert first.joinpath("pr-comment.md").exists()
    assert not second.joinpath("pr-comment.md").exists()
    assert "PR comment generated." in result.output


def test_failed_run_recommendation_says_do_not_ship(tmp_path: Path) -> None:
    metrics = sample_metrics()
    metrics["overall_status"] = "failed"
    metrics["score"] = 80
    run_dir = write_run(tmp_path, "20260626_120000", metrics)

    comment_path = generate_pr_comment(tmp_path, run_dir)
    markdown = comment_path.read_text(encoding="utf-8")

    assert "Do not ship until failures are resolved." in markdown
