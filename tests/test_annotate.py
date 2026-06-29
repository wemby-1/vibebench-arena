import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.annotate import generate_annotations
from vibebench.cli import app

runner = CliRunner()


def finding(
    severity: str,
    code: str = "demo_finding",
    message: str = "Something happened.",
    paths: list[str] | None = None,
) -> dict[str, object]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "paths": paths or ["src/app.py"],
    }


def sample_metrics(
    *,
    findings: list[dict[str, object]] | None = None,
    command_failed: bool = False,
) -> dict[str, object]:
    command_status = "failed" if command_failed else "passed"
    exit_code = 2 if command_failed else 0
    return {
        "schema_version": "1.0",
        "project_name": "demo-project",
        "created_at": "2026-06-29T12:00:00Z",
        "overall_status": "failed" if command_failed else "passed",
        "score": 60 if command_failed else 100,
        "risk_level": "high" if command_failed else "low",
        "command_results": [
            {
                "group": "test",
                "command": "pytest -q",
                "exit_code": exit_code,
                "stdout": "",
                "stderr": "failed" if command_failed else "",
                "duration_seconds": 1.0,
                "status": command_status,
            }
        ],
        "diff_analysis": {"git_available": True, "changed_file_count": 0},
        "risk_findings": findings or [],
        "summary": {
            "total_commands": 1,
            "passed_commands": 0 if command_failed else 1,
            "failed_commands": 1 if command_failed else 0,
            "total_findings": len(findings or []),
        },
    }


def write_run(
    project_root: Path,
    name: str = "20260629_120000",
    *,
    metrics: dict[str, object] | None = None,
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    run_dir.joinpath("metrics.json").write_text(
        json.dumps(metrics or sample_metrics(), indent=2),
        encoding="utf-8",
    )
    return run_dir


def test_no_findings_or_failures_exits_zero_with_friendly_message(
    tmp_path: Path,
) -> None:
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        ["annotate", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 0
    assert "No VibeBench annotations to emit." in result.output
    assert "::" not in result.output


def test_warning_finding_produces_github_warning(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, metrics=sample_metrics(findings=[finding("warning")]))

    result = generate_annotations(tmp_path, run_dir)

    assert "::warning" in result.output
    assert "demo_finding" in result.output


def test_high_and_critical_findings_produce_github_errors(tmp_path: Path) -> None:
    run_dir = write_run(
        tmp_path,
        metrics=sample_metrics(
            findings=[
                finding("high", "high_code"),
                finding("critical", "critical_code"),
            ]
        ),
    )

    result = generate_annotations(tmp_path, run_dir)

    assert result.output.count("::error") == 2
    assert "high_code" in result.output
    assert "critical_code" in result.output


def test_info_finding_is_suppressed_by_default(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, metrics=sample_metrics(findings=[finding("info")]))

    result = generate_annotations(tmp_path, run_dir)

    assert result.annotations == []
    assert "No VibeBench annotations" in result.output


def test_info_finding_appears_when_min_severity_allows_it(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, metrics=sample_metrics(findings=[finding("info")]))

    result = generate_annotations(tmp_path, run_dir, min_severity="info")

    assert "::notice" in result.output


def test_command_failure_produces_error(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, metrics=sample_metrics(command_failed=True))

    result = generate_annotations(tmp_path, run_dir)

    assert "::error" in result.output
    assert "pytest -q failed with exit code 2" in result.output


def test_no_github_actions_prints_plain_text(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, metrics=sample_metrics(findings=[finding("warning")]))

    result = runner.invoke(
        app,
        [
            "annotate",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--no-github-actions",
        ],
    )

    assert result.exit_code == 0
    assert "WARNING:" in result.output
    assert "::warning" not in result.output


def test_github_workflow_command_escaping(tmp_path: Path) -> None:
    run_dir = write_run(
        tmp_path,
        metrics=sample_metrics(
            findings=[
                finding(
                    "warning",
                    code="code:with,chars",
                    message="100% bad\nnext\rline: value, more",
                    paths=["src/a:b,c.py"],
                )
            ]
        ),
    )

    result = generate_annotations(tmp_path, run_dir)

    assert "100%25 bad%0Anext%0Dline%3A value%2C more" in result.output
    assert "code%3Awith%2Cchars" in result.output
    assert "src/a%3Ab%2Cc.py" in result.output


def test_invalid_min_severity_fails_clearly(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "annotate",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--min-severity",
            "bad",
        ],
    )

    assert result.exit_code == 1
    assert "Invalid min severity" in result.output


def test_missing_run_dir_fails_clearly(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "annotate",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(tmp_path / "missing"),
        ],
    )

    assert result.exit_code == 1
    assert "Run directory does not exist" in result.output


def test_missing_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260629_120000"
    run_dir.mkdir(parents=True)

    result = runner.invoke(
        app,
        [
            "annotate",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
        ],
    )

    assert result.exit_code == 1
    assert "metrics.json" in result.output


def test_corrupt_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260629_120000"
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text("{not-json", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "annotate",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
        ],
    )

    assert result.exit_code == 1
    assert "not valid JSON" in result.output

def test_run_dir_option_works(tmp_path: Path) -> None:
    first = write_run(tmp_path, "20260629_120000")
    second = write_run(
        tmp_path,
        "20260629_130000",
        metrics=sample_metrics(findings=[finding("warning", "second")]),
    )

    result = runner.invoke(
        app,
        ["annotate", "--project-root", str(tmp_path), "--run-dir", str(first)],
    )

    assert result.exit_code == 0
    assert "second" not in result.output
    assert second.exists()
