import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

runner = CliRunner()


def write_release_notes(
    root: Path,
    version: str = "v0.3.0",
    body: str | None = None,
) -> Path:
    """Write release notes for release-body tests."""
    content = body or "# VibeBench Arena v0.3.0\n\nStable release notes.\n"
    path = root / f"RELEASE_NOTES_{version}.md"
    path.write_text(content, encoding="utf-8")
    return path


def test_release_body_accepts_prefixed_version(tmp_path: Path) -> None:
    write_release_notes(tmp_path, "v0.3.0")

    result = runner.invoke(
        app,
        [
            "release-body",
            "--project-root",
            str(tmp_path),
            "--version",
            "v0.3.0",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["version"] == "v0.3.0"
    assert payload["source_path"].endswith("RELEASE_NOTES_v0.3.0.md")


def test_release_body_accepts_unprefixed_version(tmp_path: Path) -> None:
    write_release_notes(tmp_path, "v0.3.0")

    result = runner.invoke(
        app,
        [
            "release-body",
            "--project-root",
            str(tmp_path),
            "--version",
            "0.3.0",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["version"] == "v0.3.0"


def test_release_body_missing_notes_fails_clearly(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["release-body", "--project-root", str(tmp_path), "--version", "v0.3.0"],
    )

    assert result.exit_code == 1
    assert "Release notes file not found" in result.output


def test_release_body_default_prints_markdown(tmp_path: Path) -> None:
    body = "# Release\n\nCopy me.\n"
    write_release_notes(tmp_path, body=body)

    result = runner.invoke(
        app,
        ["release-body", "--project-root", str(tmp_path), "--version", "v0.3.0"],
    )

    assert result.exit_code == 0
    assert result.output == body


def test_release_body_output_writes_trailing_newline(tmp_path: Path) -> None:
    write_release_notes(tmp_path, body="# Release\n\nNo final newline.")
    output_path = tmp_path / "release-body.md"

    result = runner.invoke(
        app,
        [
            "release-body",
            "--project-root",
            str(tmp_path),
            "--version",
            "v0.3.0",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_release_body_invalid_parent_fails(tmp_path: Path) -> None:
    write_release_notes(tmp_path)
    output_path = tmp_path / "missing" / "release-body.md"

    result = runner.invoke(
        app,
        [
            "release-body",
            "--project-root",
            str(tmp_path),
            "--version",
            "v0.3.0",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 1
    assert "output parent does not exist" in result.output


def test_release_body_directory_output_fails(tmp_path: Path) -> None:
    write_release_notes(tmp_path)

    result = runner.invoke(
        app,
        [
            "release-body",
            "--project-root",
            str(tmp_path),
            "--version",
            "v0.3.0",
            "--output",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert "output path is a directory" in result.output


def test_release_body_check_passes_for_clean_notes(tmp_path: Path) -> None:
    write_release_notes(tmp_path, body="# Release\n\nStable release.\n")

    result = runner.invoke(
        app,
        [
            "release-body",
            "--project-root",
            str(tmp_path),
            "--version",
            "v0.3.0",
            "--check",
        ],
    )

    assert result.exit_code == 0
    assert "Release body check: passed" in result.output


def test_release_body_check_fails_for_release_candidate_wording(tmp_path: Path) -> None:
    write_release_notes(
        tmp_path,
        body="# Release Candidate\n\nThis must not create a GitHub Release.\n",
    )

    result = runner.invoke(
        app,
        [
            "release-body",
            "--project-root",
            str(tmp_path),
            "--version",
            "v0.3.0",
            "--check",
        ],
    )

    assert result.exit_code == 1
    assert "stale release-candidate wording" in result.output


def test_release_body_json_is_pure_json(tmp_path: Path) -> None:
    write_release_notes(tmp_path)

    result = runner.invoke(
        app,
        [
            "release-body",
            "--project-root",
            str(tmp_path),
            "--version",
            "v0.3.0",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert payload["body"].startswith("# VibeBench Arena")


def test_release_body_json_output_writes_file_and_stdout_json(tmp_path: Path) -> None:
    write_release_notes(tmp_path)
    output_path = tmp_path / "release-body.md"

    result = runner.invoke(
        app,
        [
            "release-body",
            "--project-root",
            str(tmp_path),
            "--version",
            "v0.3.0",
            "--json",
            "--output",
            str(output_path),
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["output_path"] == str(output_path)
    assert output_path.is_file()


def test_release_body_has_no_publish_or_github_side_effects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_release_notes(tmp_path)

    def fail_subprocess(*args, **kwargs):
        raise AssertionError("release-body must not run subprocess commands")

    monkeypatch.setattr(subprocess, "run", fail_subprocess)

    result = runner.invoke(
        app,
        [
            "release-body",
            "--project-root",
            str(tmp_path),
            "--version",
            "v0.3.0",
            "--check",
        ],
    )

    assert result.exit_code == 0
