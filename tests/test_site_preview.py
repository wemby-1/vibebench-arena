import json
import shutil
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.site_preview import REQUIRED_PREVIEW_FILES

runner = CliRunner()


def copy_docs_site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    shutil.copytree(Path("docs"), site)
    return site


def test_site_preview_human_command_does_not_write_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "preview"

    result = runner.invoke(app, ["site-preview"])

    assert result.exit_code == 0
    assert "VibeBench site preview" in result.output
    assert "Status: ready" in result.output
    assert not output_dir.exists()


def test_site_preview_json_stdout_is_pure_json() -> None:
    result = runner.invoke(app, ["site-preview", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ready"
    assert payload["root"] == "docs"
    assert "VibeBench site preview" not in result.output


def test_site_preview_json_output_writes_valid_json(tmp_path: Path) -> None:
    output = tmp_path / "site-preview.json"

    result = runner.invoke(app, ["site-preview", "--json-output", str(output)])

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "ready"
    assert "Site preview JSON:" in result.output


def test_site_preview_json_with_json_output_keeps_stdout_pure(
    tmp_path: Path,
) -> None:
    output = tmp_path / "site-preview.json"

    result = runner.invoke(
        app,
        ["site-preview", "--json", "--json-output", str(output)],
    )

    assert result.exit_code == 0
    stdout_payload = json.loads(result.output)
    file_payload = json.loads(output.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    assert "Site preview JSON:" not in result.output


def test_site_preview_output_dir_writes_required_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "preview"

    result = runner.invoke(
        app,
        ["site-preview", "--output-dir", str(output_dir)],
    )

    assert result.exit_code == 0
    for relative_path in REQUIRED_PREVIEW_FILES:
        assert output_dir.joinpath(relative_path).is_file()


def test_site_preview_output_dir_writes_valid_site_check_json(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "preview"

    result = runner.invoke(
        app,
        ["site-preview", "--output-dir", str(output_dir)],
    )

    assert result.exit_code == 0
    payload = json.loads(output_dir.joinpath("site-check.json").read_text())
    assert payload["status"] == "passed"


def test_site_preview_output_dir_writes_summary_markdown(tmp_path: Path) -> None:
    output_dir = tmp_path / "preview"

    result = runner.invoke(
        app,
        ["site-preview", "--output-dir", str(output_dir)],
    )

    assert result.exit_code == 0
    markdown = output_dir.joinpath("site-preview.md").read_text(encoding="utf-8")
    assert markdown.startswith("# VibeBench Site Preview")
    assert "python3 -m http.server 8000 --directory ." in markdown
    assert "python3 -m vibebench site-check" in markdown
    assert "python3 -m vibebench proof --output-dir PATH --zip" in markdown


def test_site_preview_zip_creates_safe_relative_archive(tmp_path: Path) -> None:
    output_dir = tmp_path / "preview"

    result = runner.invoke(
        app,
        ["site-preview", "--output-dir", str(output_dir), "--zip"],
    )

    assert result.exit_code == 0
    archive_path = output_dir / "site-preview.zip"
    assert archive_path.is_file()
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    assert set(REQUIRED_PREVIEW_FILES) == names
    assert all(not Path(name).is_absolute() for name in names)
    assert all(".." not in Path(name).parts for name in names)
    assert ".vibebench/runs" not in "\n".join(names)


def test_site_preview_zip_output_writes_explicit_archive(tmp_path: Path) -> None:
    output_dir = tmp_path / "preview"
    archive_path = tmp_path / "preview.zip"

    result = runner.invoke(
        app,
        [
            "site-preview",
            "--output-dir",
            str(output_dir),
            "--zip-output",
            str(archive_path),
        ],
    )

    assert result.exit_code == 0
    assert archive_path.is_file()
    assert not output_dir.joinpath("site-preview.zip").exists()


def test_site_preview_verify_directory_passes(tmp_path: Path) -> None:
    output_dir = tmp_path / "preview"
    write_result = runner.invoke(
        app,
        ["site-preview", "--output-dir", str(output_dir), "--zip"],
    )

    result = runner.invoke(app, ["site-preview", "--verify", str(output_dir)])

    assert write_result.exit_code == 0
    assert result.exit_code == 0
    assert "verification passed" in result.output.lower()


def test_site_preview_verify_zip_passes(tmp_path: Path) -> None:
    output_dir = tmp_path / "preview"
    write_result = runner.invoke(
        app,
        ["site-preview", "--output-dir", str(output_dir), "--zip"],
    )

    result = runner.invoke(
        app,
        ["site-preview", "--verify", str(output_dir / "site-preview.zip")],
    )

    assert write_result.exit_code == 0
    assert result.exit_code == 0
    assert "verification passed" in result.output.lower()


def test_site_preview_verify_json_outputs_valid_payload(tmp_path: Path) -> None:
    output_dir = tmp_path / "preview"
    runner.invoke(app, ["site-preview", "--output-dir", str(output_dir), "--zip"])

    result = runner.invoke(
        app,
        ["site-preview", "--verify", str(output_dir / "site-preview.zip"), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["verified"] is True
    assert payload["target_type"] == "zip"
    assert "verification passed" not in result.output.lower()


def test_site_preview_verify_fails_for_missing_required_file(tmp_path: Path) -> None:
    output_dir = tmp_path / "preview"
    runner.invoke(app, ["site-preview", "--output-dir", str(output_dir)])
    output_dir.joinpath("index.html").unlink()

    result = runner.invoke(app, ["site-preview", "--verify", str(output_dir)])

    assert result.exit_code == 1
    assert "Missing required preview files: index.html" in result.output


def test_site_preview_verify_fails_for_unsafe_local_path(tmp_path: Path) -> None:
    output_dir = tmp_path / "preview"
    runner.invoke(app, ["site-preview", "--output-dir", str(output_dir)])
    index = output_dir / "index.html"
    index.write_text(
        index.read_text(encoding="utf-8") + "\n/data/code/example",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["site-preview", "--verify", str(output_dir)])

    assert result.exit_code == 1
    assert "/data/code/" in result.output


def test_site_preview_verify_fails_for_remote_url_in_html(tmp_path: Path) -> None:
    output_dir = tmp_path / "preview"
    runner.invoke(app, ["site-preview", "--output-dir", str(output_dir)])
    index = output_dir / "index.html"
    index.write_text(
        index.read_text(encoding="utf-8") + '\n<a href="https://example.test">x</a>',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["site-preview", "--verify", str(output_dir)])

    assert result.exit_code == 1
    assert "https://" in result.output


def test_site_preview_verify_fails_for_script_tags(tmp_path: Path) -> None:
    output_dir = tmp_path / "preview"
    runner.invoke(app, ["site-preview", "--output-dir", str(output_dir)])
    showcase = output_dir / "showcase.html"
    showcase.write_text(
        showcase.read_text(encoding="utf-8") + "\n<script></script>",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["site-preview", "--verify", str(output_dir)])

    assert result.exit_code == 1
    assert "<script" in result.output


def test_site_preview_custom_root_is_copied(tmp_path: Path) -> None:
    site = copy_docs_site(tmp_path)
    output_dir = tmp_path / "preview"

    result = runner.invoke(
        app,
        [
            "site-preview",
            "--root",
            str(site),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert output_dir.joinpath("index.html").read_text(encoding="utf-8") == (
        site / "index.html"
    ).read_text(encoding="utf-8")


def test_site_preview_does_not_copy_vibebench_runs(tmp_path: Path) -> None:
    site = copy_docs_site(tmp_path)
    site.joinpath(".vibebench", "runs", "demo").mkdir(parents=True)
    site.joinpath(".vibebench", "runs", "demo", "metrics.json").write_text(
        "{}",
        encoding="utf-8",
    )
    output_dir = tmp_path / "preview"

    result = runner.invoke(
        app,
        [
            "site-preview",
            "--root",
            str(site),
            "--output-dir",
            str(output_dir),
            "--zip",
        ],
    )

    assert result.exit_code == 0
    assert not output_dir.joinpath(".vibebench").exists()
    with zipfile.ZipFile(output_dir / "site-preview.zip") as archive:
        assert all(".vibebench/runs" not in name for name in archive.namelist())
