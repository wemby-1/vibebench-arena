import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.report import ReportError, find_latest_run, generate_report

runner = CliRunner()


def sample_metrics(project_name: str = "demo-project") -> dict[str, object]:
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
            "tests_deleted": [],
            "forbidden_paths_touched": [],
            "secret_like_files_touched": [],
            "lockfiles_changed": ["package-lock.json"],
            "total_added_lines": 10,
            "total_deleted_lines": 2,
            "total_patch_lines": 12,
            "changed_file_count": 1,
            "warnings": [],
            "file_changes": [],
        },
        "risk_findings": [
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
    (run_dir / "check.log").write_text("check log\n", encoding="utf-8")
    return run_dir


def test_latest_run_detection(tmp_path: Path) -> None:
    write_run(tmp_path, "20260626_120000")
    latest = write_run(tmp_path, "20260626_130000")

    assert find_latest_run(tmp_path) == latest


def test_missing_runs_helpful_failure(tmp_path: Path) -> None:
    with pytest.raises(ReportError, match="Run 'vibebench check' first"):
        find_latest_run(tmp_path)

    result = runner.invoke(app, ["report", "--project-root", str(tmp_path)])
    assert result.exit_code == 1
    assert "No VibeBench runs found. Run 'vibebench check' first." in result.output


def test_report_generation_creates_index_html(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260626_120000")

    report_path = generate_report(tmp_path, run_dir)

    assert report_path == run_dir / "report" / "index.html"
    assert report_path.exists()


def test_generated_html_contains_key_metrics(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260626_120000")

    report_path = generate_report(tmp_path, run_dir)
    html = report_path.read_text(encoding="utf-8")

    assert "demo-project" in html
    assert "92" in html
    assert "low" in html
    assert "pytest -q" in html
    assert "lockfiles_changed" in html


def test_html_escaping_works(tmp_path: Path) -> None:
    metrics = sample_metrics(project_name="<script>alert(1)</script>")
    metrics["command_results"][0]["command"] = "echo <script>bad</script>"
    metrics["risk_findings"][0]["message"] = "unsafe <script>bad</script>"
    metrics["risk_findings"][0]["paths"] = ["<script>.env</script>"]
    run_dir = write_run(tmp_path, "20260626_120000", metrics)

    report_path = generate_report(tmp_path, run_dir)
    html = report_path.read_text(encoding="utf-8")

    assert "<script>alert(1)</script>" not in html
    assert "echo <script>bad</script>" not in html
    assert "unsafe <script>bad</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "echo &lt;script&gt;bad&lt;/script&gt;" in html
