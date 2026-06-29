import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

runner = CliRunner()


def sample_metrics(project_name: str = "demo-project") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": project_name,
        "created_at": "2026-06-29T12:00:00Z",
        "overall_status": "passed",
        "score": 95,
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
            "changed_file_count": 2,
            "total_added_lines": 10,
            "total_deleted_lines": 3,
            "total_patch_lines": 13,
            "tests_deleted": ["tests/test_old.py"],
            "forbidden_paths_touched": [".env.local"],
            "secret_like_files_touched": ["secrets/config.json"],
            "lockfiles_changed": ["package-lock.json"],
        },
        "risk_findings": [
            {
                "severity": "warning",
                "code": "lockfiles_changed",
                "message": "Lockfile changed.",
                "paths": ["package-lock.json"],
            }
        ],
        "summary": {
            "total_commands": 1,
            "passed_commands": 1,
            "failed_commands": 0,
            "total_findings": 1,
        },
    }


def write_run(
    project_root: Path,
    name: str = "20260629_120000",
    *,
    metrics: dict[str, object] | None = None,
    artifacts: bool = True,
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    run_dir.joinpath("metrics.json").write_text(
        json.dumps(metrics or sample_metrics(), indent=2),
        encoding="utf-8",
    )
    if artifacts:
        run_dir.joinpath("check.log").write_text("log\n", encoding="utf-8")
        report_dir = run_dir / "report"
        report_dir.mkdir()
        report_dir.joinpath("index.html").write_text(
            "<html></html>\n",
            encoding="utf-8",
        )
        run_dir.joinpath("pr-comment.md").write_text("comment\n", encoding="utf-8")
        run_dir.joinpath("github-step-summary.md").write_text(
            "summary\n",
            encoding="utf-8",
        )
        run_dir.joinpath("gate-summary.md").write_text("gate\n", encoding="utf-8")
        run_dir.joinpath("explain.md").write_text("explain\n", encoding="utf-8")
        run_dir.joinpath("vibebench-bundle.zip").write_text("zip\n", encoding="utf-8")
        run_dir.joinpath("compare.md").write_text("compare\n", encoding="utf-8")
    return run_dir


def parse_json_output(output: str) -> dict[str, object]:
    return json.loads(output)


def test_export_prints_valid_json_to_stdout_by_default(tmp_path: Path) -> None:
    write_run(tmp_path)

    result = runner.invoke(app, ["export", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    payload = parse_json_output(result.output)
    assert payload["schema_version"] == "vibebench.export.v1"
    assert payload["project"] == "demo-project"


def test_export_pretty_produces_indented_json(tmp_path: Path) -> None:
    write_run(tmp_path)

    result = runner.invoke(app, ["export", "--project-root", str(tmp_path), "--pretty"])

    assert result.exit_code == 0
    assert result.output.startswith("{\n")
    assert '  "schema_version": "vibebench.export.v1"' in result.output


def test_export_output_writes_json_to_file(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    output_path = tmp_path / "export.json"

    result = runner.invoke(
        app,
        [
            "export",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Export written" in result.output
    assert json.loads(output_path.read_text(encoding="utf-8"))["run_id"] == run_dir.name


def test_export_markdown_prints_markdown(tmp_path: Path) -> None:
    write_run(tmp_path)

    result = runner.invoke(
        app,
        ["export", "--project-root", str(tmp_path), "--format", "markdown"],
    )

    assert result.exit_code == 0
    assert result.output.startswith("# VibeBench Export")
    assert "| test | `pytest -q` | passed | 0 | 1.250s |" in result.output


def test_export_markdown_output_writes_file(tmp_path: Path) -> None:
    write_run(tmp_path)
    output_path = tmp_path / "export.md"

    result = runner.invoke(
        app,
        [
            "export",
            "--project-root",
            str(tmp_path),
            "--format",
            "markdown",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.read_text(encoding="utf-8").startswith("# VibeBench Export")


def test_export_includes_required_top_level_json_keys(tmp_path: Path) -> None:
    write_run(tmp_path)

    result = runner.invoke(app, ["export", "--project-root", str(tmp_path)])
    payload = parse_json_output(result.output)

    assert set(payload) >= {
        "schema_version",
        "run_id",
        "created_at",
        "project",
        "overall_status",
        "score",
        "risk_level",
        "command_results",
        "git_diff_risk",
        "risk_findings",
        "artifacts",
    }
    assert payload["command_results"] == [
        {
            "group": "test",
            "command": "pytest -q",
            "status": "passed",
            "exit_code": 0,
            "duration_seconds": 1.25,
        }
    ]
    assert payload["git_diff_risk"] == {
        "changed_files": 2,
        "added_lines": 10,
        "deleted_lines": 3,
        "patch_lines": 13,
        "tests_deleted": ["tests/test_old.py"],
        "forbidden_paths_touched": [".env.local"],
        "secret_like_files_touched": ["secrets/config.json"],
        "lockfiles_changed": ["package-lock.json"],
        "risk_findings_count": 1,
    }


def test_export_includes_expected_artifact_booleans(tmp_path: Path) -> None:
    write_run(tmp_path, artifacts=True)

    result = runner.invoke(app, ["export", "--project-root", str(tmp_path)])
    artifacts = parse_json_output(result.output)["artifacts"]

    assert artifacts == {
        "metrics_json": True,
        "check_log": True,
        "html_report": True,
        "pr_comment": True,
        "github_summary": True,
        "gate_summary": True,
        "explain": True,
        "bundle_zip": True,
        "compare": True,
    }


def test_export_corrupt_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260629_120000"
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text("{not-json", encoding="utf-8")

    result = runner.invoke(app, ["export", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "not valid JSON" in result.output


def test_export_missing_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260629_120000"
    run_dir.mkdir(parents=True)

    result = runner.invoke(
        app,
        ["export", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 1
    assert "No metrics.json found" in result.output


def test_export_invalid_format_fails_clearly(tmp_path: Path) -> None:
    write_run(tmp_path)

    result = runner.invoke(
        app,
        ["export", "--project-root", str(tmp_path), "--format", "xml"],
    )

    assert result.exit_code == 1
    assert "Unsupported export format" in result.output


def test_export_missing_output_parent_fails_clearly(tmp_path: Path) -> None:
    write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "export",
            "--project-root",
            str(tmp_path),
            "--output",
            str(tmp_path / "missing" / "export.json"),
        ],
    )

    assert result.exit_code == 1
    assert "Output parent directory does not exist" in result.output


def test_export_run_dir_option_works(tmp_path: Path) -> None:
    first = write_run(tmp_path, "20260629_120000", metrics=sample_metrics("first"))
    write_run(tmp_path, "20260629_130000", metrics=sample_metrics("second"))

    result = runner.invoke(
        app,
        ["export", "--project-root", str(tmp_path), "--run-dir", str(first)],
    )

    assert result.exit_code == 0
    assert parse_json_output(result.output)["project"] == "first"
