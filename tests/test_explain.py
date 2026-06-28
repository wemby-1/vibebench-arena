import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.explain import generate_explanation

runner = CliRunner()


def sample_metrics(
    *,
    status: str = "passed",
    score: int = 100,
    risk: str = "low",
    command_status: str = "passed",
    findings: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    exit_code = 0 if command_status == "passed" else 2
    findings = findings if findings is not None else []
    return {
        "schema_version": "1.0",
        "project_name": "demo-project",
        "created_at": "2026-06-28T12:00:00Z",
        "overall_status": status,
        "score": score,
        "risk_level": risk,
        "command_results": [
            {
                "group": "test",
                "command": "pytest -q",
                "exit_code": exit_code,
                "stdout": "ok" if command_status == "passed" else "",
                "stderr": "failed" if command_status == "failed" else "",
                "duration_seconds": 1.25,
                "status": command_status,
            }
        ],
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
            "total_patch_lines": 0,
            "changed_file_count": 0,
            "warnings": [],
            "file_changes": [],
        },
        "risk_findings": findings,
        "summary": {
            "total_commands": 1,
            "passed_commands": 1 if command_status == "passed" else 0,
            "failed_commands": 0 if command_status == "passed" else 1,
            "total_findings": len(findings),
            "critical_findings": finding_count(findings, "critical"),
            "high_findings": finding_count(findings, "high"),
            "warning_findings": finding_count(findings, "warning"),
            "info_findings": finding_count(findings, "info"),
        },
        "run_dir": "",
        "metrics_path": "",
        "log_path": "",
    }


def finding_count(findings: list[dict[str, object]], severity: str) -> int:
    """Count findings with a severity."""
    return sum(1 for item in findings if item.get("severity") == severity)


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


def test_passing_run_without_findings_generates_explanation(
    tmp_path: Path,
) -> None:
    run_dir = write_run(tmp_path, "20260628_120000")

    result = generate_explanation(tmp_path, run_dir)

    assert result.output_path == run_dir / "explain.md"
    markdown = result.output_path.read_text(encoding="utf-8")
    assert "# VibeBench Explanation" in markdown
    assert "demo-project" in markdown
    assert "No risk findings detected." in markdown
    assert "`explain.md` (available)" in markdown
    assert "looks safe to review and ship" in markdown


def test_failed_command_explanation_points_to_check_log(tmp_path: Path) -> None:
    metrics = sample_metrics(
        status="failed",
        score=60,
        risk="high",
        command_status="failed",
    )
    run_dir = write_run(tmp_path, "20260628_120000", metrics)

    result = generate_explanation(tmp_path, run_dir)
    markdown = result.markdown

    assert "`pytest -q`" in markdown
    assert "failed with exit code 2" in markdown
    assert "Inspect `check.log`" in markdown
    assert "rerun the command locally" in markdown


def test_known_risk_finding_explanation(tmp_path: Path) -> None:
    finding = {
        "severity": "critical",
        "code": "forbidden_paths_touched",
        "message": "Forbidden paths were touched.",
        "paths": [".env.local"],
    }
    run_dir = write_run(tmp_path, "20260628_120000", sample_metrics(findings=[finding]))

    result = generate_explanation(tmp_path, run_dir)

    assert "Protected or sensitive paths changed" in result.markdown
    assert "`.env.local`" in result.markdown


def test_unknown_risk_finding_does_not_crash(tmp_path: Path) -> None:
    finding = {
        "severity": "warning",
        "code": "surprise_signal",
        "message": "Something unusual happened.",
        "paths": ["src/app.py"],
    }
    run_dir = write_run(tmp_path, "20260628_120000", sample_metrics(findings=[finding]))

    result = generate_explanation(tmp_path, run_dir)

    assert "surprise_signal" in result.markdown
    assert "Review this finding and affected paths carefully" in result.markdown


def test_run_dir_option_works(tmp_path: Path) -> None:
    first = write_run(tmp_path, "20260628_120000")
    second = write_run(tmp_path, "20260628_130000")

    result = runner.invoke(
        app,
        [
            "explain",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(first),
        ],
    )

    assert result.exit_code == 0
    assert first.joinpath("explain.md").exists()
    assert not second.joinpath("explain.md").exists()
    assert "VibeBench explain" in result.output


def test_output_option_writes_custom_path(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000")
    output_path = tmp_path / "custom" / "explanation.md"

    result = runner.invoke(
        app,
        [
            "explain",
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
    assert "# VibeBench Explanation" in output_path.read_text(encoding="utf-8")


def test_no_write_does_not_create_explain_md(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260628_120000")

    result = runner.invoke(
        app,
        [
            "explain",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--no-write",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("explain.md").exists()
    assert "Explanation was not written" in result.output
    assert "# VibeBench Explanation" in result.output


def test_missing_runs_fail_clearly(tmp_path: Path) -> None:
    result = runner.invoke(app, ["explain", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "Run 'vibebench check' first" in result.output


def test_corrupt_metrics_fail_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260628_120000"
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text("{not json", encoding="utf-8")

    result = runner.invoke(
        app,
        ["explain", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 1
    assert "not valid JSON" in result.output
