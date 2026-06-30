import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

runner = CliRunner()


def metrics(
    *,
    status: str = "passed",
    score: int = 100,
    risk: str = "low",
    findings: int = 0,
    changed_files: int = 0,
    patch_lines: int = 0,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": "demo",
        "created_at": "2026-06-30T12:00:00Z",
        "overall_status": status,
        "score": score,
        "risk_level": risk,
        "command_results": [],
        "summary": {
            "total_commands": 0,
            "passed_commands": 0,
            "failed_commands": 0,
            "total_findings": findings,
        },
        "diff_analysis": {
            "changed_file_count": changed_files,
            "total_patch_lines": patch_lines,
        },
        "risk_findings": [
            {
                "severity": "warning",
                "code": f"finding_{index}",
                "message": "Finding",
                "paths": [],
            }
            for index in range(findings)
        ],
    }


def write_run(
    project_root: Path,
    run_id: str,
    payload: dict[str, object] | None = None,
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / run_id
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text(
        json.dumps(payload or metrics()),
        encoding="utf-8",
    )
    return run_dir


def parse_json_output(output: str) -> dict[str, object]:
    return json.loads(output)


def test_trend_lists_recent_runs_newest_first(tmp_path: Path) -> None:
    write_run(tmp_path, "20260630_110000", metrics(score=90, changed_files=1))
    write_run(tmp_path, "20260630_120000", metrics(score=95, changed_files=2))

    result = runner.invoke(app, ["trend", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "VibeBench trend" in result.output
    assert result.output.index("20260630_120000") < result.output.index(
        "20260630_110000"
    )
    assert "improved" in result.output


def test_trend_json_output_is_deterministic(tmp_path: Path) -> None:
    write_run(tmp_path, "20260630_110000", metrics(score=80, findings=2))
    write_run(tmp_path, "20260630_120000", metrics(score=90, findings=1))

    result = runner.invoke(
        app,
        ["trend", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    payload = parse_json_output(result.output)
    assert payload["limit"] == 10
    assert payload["valid_run_count"] == 2
    assert payload["skipped_run_count"] == 0
    assert payload["runs"][0]["run_id"] == "20260630_120000"
    assert payload["runs"][0]["score"] == 90
    assert payload["runs"][0]["risk_findings_count"] == 1
    assert payload["summary"]["latest_score"] == 90
    assert payload["summary"]["oldest_score"] == 80
    assert payload["summary"]["score_delta"] == 10
    assert payload["verdict"] == "improved"


def test_limit_controls_valid_runs_considered(tmp_path: Path) -> None:
    write_run(tmp_path, "20260630_100000", metrics(score=60))
    write_run(tmp_path, "20260630_110000", metrics(score=70))
    write_run(tmp_path, "20260630_120000", metrics(score=80))

    result = runner.invoke(
        app,
        ["trend", "--project-root", str(tmp_path), "--limit", "2", "--json"],
    )

    assert result.exit_code == 0
    payload = parse_json_output(result.output)
    assert payload["valid_run_count"] == 2
    assert [run["run_id"] for run in payload["runs"]] == [
        "20260630_120000",
        "20260630_110000",
    ]


def test_runs_dir_option_works(tmp_path: Path) -> None:
    runs_dir = tmp_path / "custom-runs"
    run_dir = runs_dir / "20260630_120000"
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text(json.dumps(metrics(score=77)))

    result = runner.invoke(
        app,
        [
            "trend",
            "--project-root",
            str(tmp_path),
            "--runs-dir",
            str(runs_dir),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = parse_json_output(result.output)
    assert payload["runs_dir"] == str(runs_dir.resolve())
    assert payload["runs"][0]["score"] == 77


def test_empty_runs_directory_exits_zero_with_message(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".vibebench" / "runs"
    runs_dir.mkdir(parents=True)

    result = runner.invoke(app, ["trend", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "No valid VibeBench runs found" in result.output


def test_single_run_reports_trend_needs_two_runs(tmp_path: Path) -> None:
    write_run(tmp_path, "20260630_120000", metrics(score=88))

    result = runner.invoke(app, ["trend", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Trend needs at least two valid runs" in result.output
    assert "20260630_120000" in result.output


def test_corrupt_run_is_skipped_when_valid_runs_exist(tmp_path: Path) -> None:
    write_run(tmp_path, "20260630_110000", metrics(score=90))
    corrupt = tmp_path / ".vibebench" / "runs" / "20260630_120000"
    corrupt.mkdir(parents=True)
    corrupt.joinpath("metrics.json").write_text("{nope", encoding="utf-8")

    result = runner.invoke(
        app,
        ["trend", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    payload = parse_json_output(result.output)
    assert payload["valid_run_count"] == 1
    assert payload["skipped_run_count"] == 1


def test_all_corrupt_runs_fail_clearly(tmp_path: Path) -> None:
    corrupt = tmp_path / ".vibebench" / "runs" / "20260630_120000"
    corrupt.mkdir(parents=True)
    corrupt.joinpath("metrics.json").write_text("{nope", encoding="utf-8")

    result = runner.invoke(app, ["trend", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "No valid VibeBench runs found" in result.output


def test_regressed_verdict_when_score_drops(tmp_path: Path) -> None:
    write_run(tmp_path, "20260630_110000", metrics(score=95))
    write_run(tmp_path, "20260630_120000", metrics(score=89))

    result = runner.invoke(
        app,
        ["trend", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    assert parse_json_output(result.output)["verdict"] == "regressed"


def test_regressed_verdict_when_risk_worsens(tmp_path: Path) -> None:
    write_run(tmp_path, "20260630_110000", metrics(score=90, risk="low"))
    write_run(tmp_path, "20260630_120000", metrics(score=90, risk="high"))

    result = runner.invoke(
        app,
        ["trend", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    assert parse_json_output(result.output)["verdict"] == "regressed"


def test_improved_verdict_when_findings_drop(tmp_path: Path) -> None:
    write_run(tmp_path, "20260630_110000", metrics(score=90, findings=3))
    write_run(tmp_path, "20260630_120000", metrics(score=90, findings=1))

    result = runner.invoke(
        app,
        ["trend", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    assert parse_json_output(result.output)["verdict"] == "improved"


def test_stable_verdict_for_small_score_change(tmp_path: Path) -> None:
    write_run(tmp_path, "20260630_110000", metrics(score=90))
    write_run(tmp_path, "20260630_120000", metrics(score=94))

    result = runner.invoke(
        app,
        ["trend", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    assert parse_json_output(result.output)["verdict"] == "stable"


def test_invalid_limit_fails_clearly(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["trend", "--project-root", str(tmp_path), "--limit", "0"],
    )

    assert result.exit_code == 1
    assert "--limit must be greater than 0" in result.output
