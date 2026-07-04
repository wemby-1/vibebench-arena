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
    created_at: str = "2026-07-04T00:00:00Z",
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": "demo",
        "created_at": created_at,
        "overall_status": status,
        "score": score,
        "risk_level": risk,
        "command_results": [],
        "summary": {
            "total_commands": 0,
            "passed_commands": 0,
            "failed_commands": 0,
            "total_findings": 0,
        },
        "diff_analysis": {
            "changed_file_count": 0,
            "total_patch_lines": 0,
        },
        "risk_findings": [],
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


def test_run_index_default_output(tmp_path: Path) -> None:
    write_run(tmp_path, "20260704_100000", metrics(score=90, risk="medium"))
    latest = write_run(tmp_path, "20260704_110000")
    latest.joinpath("report").mkdir()
    latest.joinpath("report", "index.html").write_text("<html></html>\n")

    result = runner.invoke(app, ["run-index", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "VibeBench Run Index" in result.output

    json_result = runner.invoke(
        app, ["run-index", "--project-root", str(tmp_path), "--json"]
    )
    payload = json.loads(json_result.output)
    assert payload["runs"][0]["run_id"] == "20260704_110000"
    assert payload["runs"][1]["run_id"] == "20260704_100000"


def test_run_index_json_output_is_pure_json(tmp_path: Path) -> None:
    write_run(tmp_path, "20260704_110000")

    result = runner.invoke(
        app,
        ["run-index", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["total_runs_seen"] == 1
    assert payload["runs"][0]["run_id"] == "20260704_110000"
    assert payload["runs"][0]["metrics_available"] is True


def test_run_index_limit_and_runs_dir(tmp_path: Path) -> None:
    runs_dir = tmp_path / "custom-runs"
    write_run(tmp_path, "unused")
    for index in range(3):
        run_dir = runs_dir / f"20260704_11000{index}"
        run_dir.mkdir(parents=True)
        run_dir.joinpath("metrics.json").write_text(json.dumps(metrics(score=index)))

    result = runner.invoke(
        app,
        [
            "run-index",
            "--project-root",
            str(tmp_path),
            "--runs-dir",
            str(runs_dir),
            "--limit",
            "2",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["limit"] == 2
    assert payload["total_runs_seen"] == 3
    assert len(payload["runs"]) == 2


def test_run_index_write_json(tmp_path: Path) -> None:
    write_run(tmp_path, "20260704_110000")
    output_path = tmp_path / "run-index.json"

    result = runner.invoke(
        app,
        [
            "run-index",
            "--project-root",
            str(tmp_path),
            "--write-json",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["runs"][0]["run_id"] == "20260704_110000"


def test_run_index_write_summary(tmp_path: Path) -> None:
    write_run(tmp_path, "20260704_110000")
    output_path = tmp_path / "run-index.md"

    result = runner.invoke(
        app,
        [
            "run-index",
            "--project-root",
            str(tmp_path),
            "--write-summary",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    markdown = output_path.read_text(encoding="utf-8")
    assert "# VibeBench Run Index" in markdown
    assert "20260704_110000 (latest)" in markdown


def test_run_index_json_with_write_json_keeps_stdout_pure(tmp_path: Path) -> None:
    write_run(tmp_path, "20260704_110000")
    output_path = tmp_path / "run-index.json"

    result = runner.invoke(
        app,
        [
            "run-index",
            "--project-root",
            str(tmp_path),
            "--json",
            "--write-json",
            str(output_path),
        ],
    )

    stdout_payload = json.loads(result.output)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert stdout_payload == file_payload


def test_run_index_partial_and_corrupt_runs_do_not_crash(tmp_path: Path) -> None:
    write_run(tmp_path, "20260704_100000")
    partial = tmp_path / ".vibebench" / "runs" / "20260704_110000"
    partial.mkdir(parents=True)
    corrupt = tmp_path / ".vibebench" / "runs" / "20260704_120000"
    corrupt.mkdir(parents=True)
    corrupt.joinpath("metrics.json").write_text("{nope", encoding="utf-8")

    result = runner.invoke(
        app,
        ["run-index", "--project-root", str(tmp_path), "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    rows = {row["run_id"]: row for row in payload["runs"]}
    assert rows["20260704_120000"]["status"] == "invalid"
    assert "unreadable" in rows["20260704_120000"]["message"]
    assert rows["20260704_110000"]["status"] == "unknown"
    assert rows["20260704_110000"]["message"] == "metrics.json missing"


def test_run_index_missing_runs_dir_is_empty(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["run-index", "--project-root", str(tmp_path), "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "empty"
    assert payload["runs"] == []
