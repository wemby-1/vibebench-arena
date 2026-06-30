import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

runner = CliRunner()


def sample_metrics(
    *,
    project_name: str = "demo-project",
    status: str = "passed",
    score: int = 100,
    risk: str = "low",
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": project_name,
        "created_at": "2026-06-29T12:00:00Z",
        "overall_status": status,
        "score": score,
        "risk_level": risk,
        "command_results": [],
        "diff_analysis": {
            "git_available": True,
            "changed_file_count": 3,
            "total_patch_lines": 44,
        },
        "risk_findings": [
            {
                "severity": "info",
                "code": "test_files_changed",
                "message": "Test files changed.",
                "paths": ["tests/test_app.py"],
            }
        ],
        "summary": {
            "total_commands": 0,
            "passed_commands": 0,
            "failed_commands": 0,
            "total_findings": 1,
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


def test_default_status_block_writes_status_block_md(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)

    result = runner.invoke(app, ["status-block", "--project-root", str(tmp_path)])

    output = run_dir / "status-block.md"
    assert result.exit_code == 0
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert content.startswith("## VibeBench Status\n")
    assert "- Overall status: passed" in content
    assert "- VibeScore: 100" in content
    assert "- Risk level: low" in content
    assert "- Changed files: 3" in content
    assert "- Patch lines: 44" in content
    assert "- Risk findings: 1" in content
    assert "- Generated at: 2026-06-29T12:00:00Z" in content


def test_run_dir_selects_specific_run(tmp_path: Path) -> None:
    first = write_run(tmp_path, "20260629_120000", metrics=sample_metrics(score=82))
    second = write_run(tmp_path, "20260629_130000", metrics=sample_metrics(score=100))

    result = runner.invoke(
        app,
        ["status-block", "--project-root", str(tmp_path), "--run-dir", str(first)],
    )

    assert result.exit_code == 0
    assert "VibeScore: 82" in first.joinpath("status-block.md").read_text(
        encoding="utf-8"
    )
    assert not second.joinpath("status-block.md").exists()


def test_output_writes_exact_requested_path(tmp_path: Path) -> None:
    write_run(tmp_path)
    output = tmp_path / "README-status.md"

    result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert output.exists()
    default_output = (
        tmp_path / ".vibebench" / "runs" / "20260629_120000" / "status-block.md"
    )
    assert not default_output.exists()


def test_invalid_output_parent_fails_clearly(tmp_path: Path) -> None:
    write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--output",
            str(tmp_path / "missing" / "status-block.md"),
        ],
    )

    assert result.exit_code == 1
    assert "Output parent directory does not exist" in result.output


def test_custom_title_is_used(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        ["status-block", "--project-root", str(tmp_path), "--title", "Project Quality"],
    )

    assert result.exit_code == 0
    assert run_dir.joinpath("status-block.md").read_text(encoding="utf-8").startswith(
        "## Project Quality\n"
    )


def test_badge_md_is_embedded_when_present(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    run_dir.joinpath("badge.md").write_text("![Quality](https://example.test/badge)\n")

    result = runner.invoke(app, ["status-block", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    content = run_dir.joinpath("status-block.md").read_text(encoding="utf-8")
    assert "![Quality](https://example.test/badge)" in content


def test_badge_url_fallback_is_used_when_badge_md_absent(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    run_dir.joinpath("badge-url.txt").write_text("https://example.test/badge\n")

    result = runner.invoke(app, ["status-block", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    content = run_dir.joinpath("status-block.md").read_text(encoding="utf-8")
    assert "![VibeBench](https://example.test/badge)" in content


def test_no_include_badge_omits_badge(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    run_dir.joinpath("badge.md").write_text("![Quality](https://example.test/badge)\n")

    result = runner.invoke(
        app,
        ["status-block", "--project-root", str(tmp_path), "--no-include-badge"],
    )

    assert result.exit_code == 0
    content = run_dir.joinpath("status-block.md").read_text(encoding="utf-8")
    assert "![Quality]" not in content


def test_artifact_list_includes_only_existing_artifacts(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    report_dir = run_dir / "report"
    report_dir.mkdir()
    report_dir.joinpath("index.html").write_text("<html></html>\n", encoding="utf-8")
    run_dir.joinpath("export.json").write_text("{}\n", encoding="utf-8")
    run_dir.joinpath("badge.json").write_text("{}\n", encoding="utf-8")

    result = runner.invoke(app, ["status-block", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    content = run_dir.joinpath("status-block.md").read_text(encoding="utf-8")
    assert "Artifacts:" in content
    assert "- report/index.html" in content
    assert "- export.json" in content
    assert "- badge.json" in content
    assert "- pr-comment.md" not in content


def test_no_include_artifacts_omits_artifact_section(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    run_dir.joinpath("export.json").write_text("{}\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["status-block", "--project-root", str(tmp_path), "--no-include-artifacts"],
    )

    assert result.exit_code == 0
    content = run_dir.joinpath("status-block.md").read_text(encoding="utf-8")
    assert "Artifacts:" not in content
    assert "- export.json" not in content


def test_symlink_run_directory_is_rejected(tmp_path: Path) -> None:
    real_run = write_run(tmp_path, "20260629_120000")
    symlink_run = tmp_path / ".vibebench" / "runs" / "20260629_130000"
    symlink_run.symlink_to(real_run, target_is_directory=True)

    result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(symlink_run),
        ],
    )

    assert result.exit_code == 1
    assert "must not be a symlink" in result.output


STATUS_START = "<!-- VIBEBENCH_STATUS_START -->"
STATUS_END = "<!-- VIBEBENCH_STATUS_END -->"


def write_readme(path: Path, block: str = "old block\n") -> None:
    path.write_text(
        f"# Demo\n\nBefore\n\n{STATUS_START}\n{block}{STATUS_END}\n\nAfter\n",
        encoding="utf-8",
    )


def test_write_readme_replaces_only_content_between_markers(tmp_path: Path) -> None:
    write_run(tmp_path)
    readme = tmp_path / "README.md"
    write_readme(readme)

    result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--readme",
            str(readme),
            "--write-readme",
        ],
    )

    content = readme.read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert content.startswith("# Demo\n\nBefore\n\n")
    assert content.endswith("\nAfter\n")
    assert STATUS_START in content
    assert STATUS_END in content
    assert "old block" not in content
    assert "## VibeBench Status" in content
    assert "- VibeScore: 100" in content


def test_write_readme_is_idempotent(tmp_path: Path) -> None:
    write_run(tmp_path)
    readme = tmp_path / "README.md"
    write_readme(readme)
    args = [
        "status-block",
        "--project-root",
        str(tmp_path),
        "--readme",
        str(readme),
        "--write-readme",
    ]

    first = runner.invoke(app, args)
    first_content = readme.read_text(encoding="utf-8")
    second = runner.invoke(app, args)
    second_content = readme.read_text(encoding="utf-8")

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert first_content == second_content
    assert "already current" in second.output


def test_check_readme_passes_when_block_is_current(tmp_path: Path) -> None:
    write_run(tmp_path)
    readme = tmp_path / "README.md"
    write_readme(readme)
    write_result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--readme",
            str(readme),
            "--write-readme",
        ],
    )

    check_result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--readme",
            str(readme),
            "--check-readme",
        ],
    )

    assert write_result.exit_code == 0
    assert check_result.exit_code == 0
    assert "current" in check_result.output


def test_check_readme_fails_when_block_is_stale(tmp_path: Path) -> None:
    write_run(tmp_path)
    readme = tmp_path / "README.md"
    write_readme(readme, block="stale\n")

    result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--readme",
            str(readme),
            "--check-readme",
        ],
    )

    assert result.exit_code == 1
    assert "stale" in result.output
    assert "stale\n" in readme.read_text(encoding="utf-8")


def test_missing_readme_file_fails_clearly(tmp_path: Path) -> None:
    write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--readme",
            str(tmp_path / "README.md"),
            "--write-readme",
        ],
    )

    assert result.exit_code == 1
    assert "README file does not exist" in result.output


def test_missing_start_marker_fails_clearly(tmp_path: Path) -> None:
    write_run(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(f"# Demo\n\n{STATUS_END}\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--readme",
            str(readme),
            "--write-readme",
        ],
    )

    assert result.exit_code == 1
    assert "Missing <!-- VIBEBENCH_STATUS_START -->" in result.output


def test_missing_end_marker_fails_clearly(tmp_path: Path) -> None:
    write_run(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(f"# Demo\n\n{STATUS_START}\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--readme",
            str(readme),
            "--write-readme",
        ],
    )

    assert result.exit_code == 1
    assert "Missing <!-- VIBEBENCH_STATUS_END -->" in result.output


def test_end_marker_before_start_marker_fails_clearly(tmp_path: Path) -> None:
    write_run(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(f"# Demo\n\n{STATUS_END}\n{STATUS_START}\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--readme",
            str(readme),
            "--write-readme",
        ],
    )

    assert result.exit_code == 1
    assert "appears before" in result.output


def test_write_and_check_readme_together_fail_clearly(tmp_path: Path) -> None:
    write_run(tmp_path)
    readme = tmp_path / "README.md"
    write_readme(readme)

    result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--readme",
            str(readme),
            "--write-readme",
            "--check-readme",
        ],
    )

    assert result.exit_code == 1
    assert "cannot be used together" in result.output


def test_readme_action_without_readme_fails_clearly(tmp_path: Path) -> None:
    write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--write-readme",
        ],
    )

    assert result.exit_code == 1
    assert "--readme is required" in result.output


def test_multiple_readme_paths_are_updated(tmp_path: Path) -> None:
    write_run(tmp_path)
    readme = tmp_path / "README.md"
    readme_cn = tmp_path / "README.zh-CN.md"
    write_readme(readme)
    write_readme(readme_cn)

    result = runner.invoke(
        app,
        [
            "status-block",
            "--project-root",
            str(tmp_path),
            "--readme",
            str(readme),
            "--readme",
            str(readme_cn),
            "--write-readme",
        ],
    )

    assert result.exit_code == 0
    assert "## VibeBench Status" in readme.read_text(encoding="utf-8")
    assert "## VibeBench Status" in readme_cn.read_text(encoding="utf-8")
