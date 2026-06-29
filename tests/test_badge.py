import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.badge import badge_color, badge_url, generate_badge
from vibebench.cli import app

runner = CliRunner()


def sample_metrics(
    *,
    status: str = "passed",
    score: int = 100,
    risk: str = "low",
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": "demo-project",
        "created_at": "2026-06-29T12:00:00Z",
        "overall_status": status,
        "score": score,
        "risk_level": risk,
        "command_results": [],
        "diff_analysis": {"git_available": True, "changed_file_count": 0},
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


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_badge_writes_default_badge_json_for_valid_run(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)

    result = runner.invoke(app, ["badge", "--project-root", str(tmp_path)])

    badge_path = run_dir / "badge.json"
    assert result.exit_code == 0
    assert badge_path.exists()
    assert read_json(badge_path) == {
        "schemaVersion": 1,
        "label": "VibeBench",
        "message": "100 low",
        "color": "brightgreen",
    }
    assert "Badge generated" in result.output


def test_badge_run_dir_option_works(tmp_path: Path) -> None:
    first = write_run(tmp_path, "20260629_120000", metrics=sample_metrics(score=82))
    second = write_run(tmp_path, "20260629_130000", metrics=sample_metrics(score=100))

    result = runner.invoke(
        app,
        ["badge", "--project-root", str(tmp_path), "--run-dir", str(first)],
    )

    assert result.exit_code == 0
    assert read_json(first / "badge.json")["message"] == "82 low"
    assert not second.joinpath("badge.json").exists()


def test_badge_output_option_works(tmp_path: Path) -> None:
    write_run(tmp_path)
    output_path = tmp_path / "custom-badge.json"

    result = runner.invoke(
        app,
        [
            "badge",
            "--project-root",
            str(tmp_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    assert read_json(output_path)["message"] == "100 low"


def test_badge_label_option_works(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        ["badge", "--project-root", str(tmp_path), "--label", "Quality"],
    )

    assert result.exit_code == 0
    assert read_json(run_dir / "badge.json")["label"] == "Quality"



def test_badge_markdown_format_creates_badge_md(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        ["badge", "--project-root", str(tmp_path), "--format", "markdown"],
    )

    badge_path = run_dir / "badge.md"
    assert result.exit_code == 0
    assert badge_path.exists()
    assert badge_path.read_text(encoding="utf-8") == (
        "![VibeBench](https://img.shields.io/badge/VibeBench-100%20low-brightgreen)\n"
    )


def test_badge_url_format_creates_badge_url_txt(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        ["badge", "--project-root", str(tmp_path), "--format", "url"],
    )

    badge_path = run_dir / "badge-url.txt"
    assert result.exit_code == 0
    assert badge_path.exists()
    assert badge_path.read_text(encoding="utf-8") == (
        "https://img.shields.io/badge/VibeBench-100%20low-brightgreen\n"
    )


def test_badge_url_encoding_uses_percent_twenty_for_spaces() -> None:
    url = badge_url(
        {
            "label": "Vibe Score",
            "message": "failed high",
            "color": "bright green",
        }
    )

    assert url == (
        "https://img.shields.io/badge/"
        "Vibe%20Score-failed%20high-bright%20green"
    )
    assert "+" not in url


def test_badge_label_affects_markdown_and_url(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)

    markdown = runner.invoke(
        app,
        [
            "badge",
            "--project-root",
            str(tmp_path),
            "--format",
            "markdown",
            "--label",
            "VibeScore",
        ],
    )
    url = runner.invoke(
        app,
        [
            "badge",
            "--project-root",
            str(tmp_path),
            "--format",
            "url",
            "--label",
            "Vibe Score",
        ],
    )

    assert markdown.exit_code == 0
    assert url.exit_code == 0
    assert run_dir.joinpath("badge.md").read_text(encoding="utf-8").startswith(
        "![VibeScore]"
    )
    assert "Vibe%20Score" in run_dir.joinpath("badge-url.txt").read_text(
        encoding="utf-8"
    )


def test_badge_output_works_for_markdown_and_url(tmp_path: Path) -> None:
    write_run(tmp_path)
    markdown_path = tmp_path / "custom.md"
    url_path = tmp_path / "custom-url.txt"

    markdown = runner.invoke(
        app,
        [
            "badge",
            "--project-root",
            str(tmp_path),
            "--format",
            "markdown",
            "--output",
            str(markdown_path),
        ],
    )
    url = runner.invoke(
        app,
        [
            "badge",
            "--project-root",
            str(tmp_path),
            "--format",
            "url",
            "--output",
            str(url_path),
        ],
    )

    assert markdown.exit_code == 0
    assert url.exit_code == 0
    assert markdown_path.read_text(encoding="utf-8").startswith("![VibeBench]")
    assert url_path.read_text(encoding="utf-8").startswith(
        "https://img.shields.io/badge/"
    )


def test_invalid_badge_format_fails_clearly(tmp_path: Path) -> None:
    write_run(tmp_path)

    result = runner.invoke(
        app,
        ["badge", "--project-root", str(tmp_path), "--format", "svg"],
    )

    assert result.exit_code == 1
    assert "Unsupported badge format" in result.output

def test_badge_color_mapping() -> None:
    assert badge_color(status="passed", score=95, risk="low") == "brightgreen"
    assert badge_color(status="passed", score=82, risk="medium") == "green"
    assert badge_color(status="passed", score=82, risk="unknown") == "yellow"
    assert badge_color(status="failed", score=100, risk="low") == "red"
    assert badge_color(status="passed", score=100, risk="high") == "red"
    assert badge_color(status="passed", score=100, risk="critical") == "red"
    assert badge_color(status="passed", score=79, risk="low") == "red"


def test_missing_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260629_120000"
    run_dir.mkdir(parents=True)

    result = runner.invoke(
        app,
        ["badge", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 1
    assert "No metrics.json found" in result.output


def test_corrupt_metrics_fails_clearly(tmp_path: Path) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "20260629_120000"
    run_dir.mkdir(parents=True)
    run_dir.joinpath("metrics.json").write_text("{not-json", encoding="utf-8")

    result = runner.invoke(
        app,
        ["badge", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 1
    assert "not valid JSON" in result.output


def test_invalid_output_parent_fails_clearly(tmp_path: Path) -> None:
    write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "badge",
            "--project-root",
            str(tmp_path),
            "--output",
            str(tmp_path / "missing" / "badge.json"),
        ],
    )

    assert result.exit_code == 1
    assert "Output parent directory does not exist" in result.output


def test_generate_badge_returns_result(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, metrics=sample_metrics(status="failed", risk="high"))

    result = generate_badge(tmp_path, run_dir)

    assert result.message == "failed high"
    assert result.color == "red"
    assert result.output_path == run_dir / "badge.json"
