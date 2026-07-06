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
    created_at: str = "2026-07-01T00:00:00Z",
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

def test_latest_selects_latest_valid_run(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(score=90))
    write_run(tmp_path, "20260701_110000", metrics(score=95, risk="medium"))

    result = runner.invoke(app, ["latest", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "20260701_110000" in result.output
    assert "VibeScore: 95" in result.output
    assert "Risk: medium" in result.output

def test_latest_empty_runs_dir_fails_clearly(tmp_path: Path) -> None:
    (tmp_path / ".vibebench" / "runs").mkdir(parents=True)

    result = runner.invoke(app, ["latest", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "No valid VibeBench runs found" in result.output

def test_latest_skips_corrupt_newer_run(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_100000", metrics(score=90))
    corrupt = tmp_path / ".vibebench" / "runs" / "20260701_110000"
    corrupt.mkdir(parents=True)
    corrupt.joinpath("metrics.json").write_text("{nope", encoding="utf-8")

    result = runner.invoke(app, ["latest", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "20260701_100000" in result.output
    assert "Skipped corrupt runs: 1" in result.output

def test_latest_all_corrupt_runs_fail_clearly(tmp_path: Path) -> None:
    corrupt = tmp_path / ".vibebench" / "runs" / "20260701_110000"
    corrupt.mkdir(parents=True)
    corrupt.joinpath("metrics.json").write_text("{nope", encoding="utf-8")

    result = runner.invoke(app, ["latest", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "all metrics.json files were unreadable" in result.output

def test_latest_json_output_shape(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260701_110000", metrics(score=95))
    run_dir.joinpath("check.log").write_text("log\n", encoding="utf-8")

    result = runner.invoke(app, ["latest", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["run_id"] == "20260701_110000"
    assert payload["status"] == "passed"
    assert payload["score"] == 95
    assert payload["risk"] == "low"
    assert payload["created_at"] == "2026-07-01T00:00:00Z"
    artifacts = {item["name"]: item for item in payload["artifacts"]}
    assert artifacts["metrics.json"]["available"] is True
    assert artifacts["check.log"]["available"] is True

def test_latest_runs_dir_option(tmp_path: Path) -> None:
    runs_dir = tmp_path / "custom-runs"
    run_dir = runs_dir / "20260701_110000"
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text(json.dumps(metrics(score=77)))

    result = runner.invoke(
        app,
        ["latest", "--project-root", str(tmp_path), "--runs-dir", str(runs_dir)],
    )

    assert result.exit_code == 0
    assert "20260701_110000" in result.output
    assert "VibeScore: 77" in result.output

def test_latest_artifact_available(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260701_110000")
    run_dir.joinpath("check.log").write_text("log\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["latest", "--project-root", str(tmp_path), "--artifact", "check-log"],
    )

    assert result.exit_code == 0
    assert "check.log" in result.output
    assert "available" in result.output
    assert "metrics.json" not in result.output

def test_latest_artifact_unavailable(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_110000")

    result = runner.invoke(
        app,
        ["latest", "--project-root", str(tmp_path), "--artifact", "bundle"],
    )

    assert result.exit_code == 0
    assert "vibebench-bundle.zip" in result.output
    assert "missing" in result.output

def test_latest_run_index_artifact_path_only(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260701_110000")
    run_dir.joinpath("run-index.json").write_text("{}\n", encoding="utf-8")
    run_dir.joinpath("run-index.md").write_text("run index\n", encoding="utf-8")

    json_result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "run-index-json",
            "--path-only",
        ],
    )
    md_result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "run-index-md",
            "--path-only",
        ],
    )

    assert json_result.exit_code == 0
    assert "run-index.json" in json_result.output
    assert md_result.exit_code == 0
    assert "run-index.md" in md_result.output


def test_latest_compare_artifact_path_only(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260701_110000")
    run_dir.joinpath("compare.json").write_text("{}\n", encoding="utf-8")
    run_dir.joinpath("compare.md").write_text("compare\n", encoding="utf-8")

    json_result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "compare-json",
            "--path-only",
        ],
    )
    md_result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "compare-md",
            "--path-only",
        ],
    )

    assert json_result.exit_code == 0
    assert "compare.json" in json_result.output
    assert md_result.exit_code == 0
    assert "compare.md" in md_result.output


def test_latest_package_check_artifact_path_only(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260701_110000")
    run_dir.joinpath("package-check.json").write_text("{}\n", encoding="utf-8")
    run_dir.joinpath("package-check.md").write_text("package\n", encoding="utf-8")

    json_result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "package-check-json",
            "--path-only",
        ],
    )
    md_result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "package-check-md",
            "--path-only",
        ],
    )

    assert json_result.exit_code == 0
    assert "package-check.json" in json_result.output
    assert md_result.exit_code == 0
    assert "package-check.md" in md_result.output


def test_latest_unknown_artifact_fails_clearly(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_110000")

    result = runner.invoke(
        app,
        ["latest", "--project-root", str(tmp_path), "--artifact", "nope"],
    )

    assert result.exit_code == 1
    assert "Unknown artifact 'nope'" in result.output
    assert "check-log" in result.output

def test_latest_path_only_success(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260701_110000")
    run_dir.joinpath("check.log").write_text("log\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "check-log",
            "--path-only",
        ],
    )

    assert result.exit_code == 0
    assert result.output.strip() == ".vibebench/runs/20260701_110000/check.log"

def test_latest_path_only_requires_artifact(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_110000")

    result = runner.invoke(
        app,
        ["latest", "--project-root", str(tmp_path), "--path-only"],
    )

    assert result.exit_code == 1
    assert "--path-only requires --artifact" in result.output

def test_latest_path_only_fails_when_artifact_unavailable(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_110000")

    result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "bundle",
            "--path-only",
        ],
    )

    assert result.exit_code == 1
    assert "unavailable" in result.output

def test_latest_all_paths_prints_only_available_artifact_paths(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260701_110000")
    run_dir.joinpath("check.log").write_text("log\n", encoding="utf-8")
    report_dir = run_dir / "report"
    report_dir.mkdir()
    report_dir.joinpath("index.html").write_text("<html></html>\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["latest", "--project-root", str(tmp_path), "--all-paths"],
    )

    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert "metrics: .vibebench/runs/20260701_110000/metrics.json" in lines
    assert "check-log: .vibebench/runs/20260701_110000/check.log" in lines
    assert "report: .vibebench/runs/20260701_110000/report/index.html" in lines

def test_latest_all_paths_omits_unavailable_artifacts(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_110000")

    result = runner.invoke(
        app,
        ["latest", "--project-root", str(tmp_path), "--all-paths"],
    )

    assert result.exit_code == 0
    assert "metrics:" in result.output
    assert "bundle:" not in result.output
    assert "report:" not in result.output

def test_latest_all_paths_json_output_shape(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260701_110000")
    run_dir.joinpath("check.log").write_text("log\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["latest", "--project-root", str(tmp_path), "--all-paths", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["run_id"] == "20260701_110000"
    paths = {item["name"]: item for item in payload["paths"]}
    assert paths["metrics"]["path"] == ".vibebench/runs/20260701_110000/metrics.json"
    assert paths["check-log"]["size_bytes"] == 4
    assert "bundle" not in paths

def test_latest_all_paths_rejects_artifact(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_110000")

    result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--all-paths",
            "--artifact",
            "metrics",
        ],
    )

    assert result.exit_code == 1
    assert "--all-paths cannot be combined with --artifact" in result.output

def test_latest_all_paths_rejects_path_only(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_110000")

    result = runner.invoke(
        app,
        ["latest", "--project-root", str(tmp_path), "--all-paths", "--path-only"],
    )

    assert result.exit_code == 1
    assert "--all-paths cannot be combined with --path-only" in result.output

def test_latest_artifact_path_only_still_works_with_all_paths_added(
    tmp_path: Path,
) -> None:
    run_dir = write_run(tmp_path, "20260701_110000")
    run_dir.joinpath("check.log").write_text("log\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "check-log",
            "--path-only",
        ],
    )

    assert result.exit_code == 0
    assert result.output.strip() == ".vibebench/runs/20260701_110000/check.log"

def test_latest_json_output_remains_full_inventory(tmp_path: Path) -> None:
    write_run(tmp_path, "20260701_110000")

    result = runner.invoke(app, ["latest", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "artifacts" in payload
    assert "paths" not in payload
    assert any(item["available"] is False for item in payload["artifacts"])

def test_latest_manifest_path_only(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260701_110000")
    run_dir.joinpath("manifest.json").write_text("{}\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "manifest",
            "--path-only",
        ],
    )

    assert result.exit_code == 0
    assert result.output.strip() == ".vibebench/runs/20260701_110000/manifest.json"

def test_latest_artifact_supports_config_check_alias(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260701_110000", metrics(score=95))
    run_dir.joinpath("config-check.json").write_text("{}\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "config-check-json",
            "--path-only",
        ],
    )

    assert result.exit_code == 0
    assert result.output.strip().endswith("config-check.json")


def test_latest_artifact_supports_security_questionnaire_aliases(
    tmp_path: Path,
) -> None:
    run_dir = write_run(tmp_path, "20260701_110000")
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

    html_result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "evidence-room-security-questionnaire-html",
            "--path-only",
        ],
    )
    md_result = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "evidence-room-security-questionnaire-md",
            "--path-only",
        ],
    )

    assert html_result.exit_code == 0
    assert html_result.output.strip().endswith(
        "evidence-room/security-questionnaire.html"
    )
    assert md_result.exit_code == 0
    assert md_result.output.strip().endswith("evidence-room/security-questionnaire.md")
