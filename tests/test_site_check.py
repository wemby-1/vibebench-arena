import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

runner = CliRunner()


def copy_docs_site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    shutil.copytree(Path("docs"), site)
    return site


def run_site_check(root: Path) -> object:
    return runner.invoke(app, ["site-check", "--root", str(root)])


def test_site_check_default_passes_on_current_docs_site() -> None:
    result = runner.invoke(app, ["site-check"])

    assert result.exit_code == 0
    assert "Status: passed" in result.output
    assert "index.html, showcase.html, pages.md" in result.output


def test_site_check_json_output_is_pure_valid_json() -> None:
    result = runner.invoke(app, ["site-check", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "passed"
    assert payload["root"] == "docs"
    assert payload["checked_files"] == ["index.html", "showcase.html", "pages.md"]
    assert "VibeBench site check" not in result.output


def test_site_check_json_output_file_writes_valid_json(tmp_path: Path) -> None:
    output = tmp_path / "site-check.json"

    result = runner.invoke(app, ["site-check", "--json-output", str(output)])

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert "Site check JSON:" in result.output


def test_site_check_missing_required_file_fails(tmp_path: Path) -> None:
    site = copy_docs_site(tmp_path)
    site.joinpath("pages.md").unlink()

    result = run_site_check(site)

    assert result.exit_code == 1
    assert "required_files" in result.output
    assert "pages.md" in result.output


def test_site_check_forbidden_remote_url_or_script_marker_fails(
    tmp_path: Path,
) -> None:
    site = copy_docs_site(tmp_path)
    index = site / "index.html"
    index.write_text(
        index.read_text(encoding="utf-8") + '\n<a href="https://example.test">x</a>',
        encoding="utf-8",
    )

    result = run_site_check(site)

    assert result.exit_code == 1
    assert "html_safety" in result.output
    assert "https://" in result.output


def test_site_check_forbidden_absolute_local_path_fails(tmp_path: Path) -> None:
    site = copy_docs_site(tmp_path)
    showcase = site / "showcase.html"
    showcase.write_text(
        showcase.read_text(encoding="utf-8") + "\n/data/code/example",
        encoding="utf-8",
    )

    result = run_site_check(site)

    assert result.exit_code == 1
    assert "html_safety" in result.output
    assert "/data/code/" in result.output


def test_site_check_banned_claim_or_sensitive_marker_fails(tmp_path: Path) -> None:
    site = copy_docs_site(tmp_path)
    pages = site / "pages.md"
    pages.write_text(
        pages.read_text(encoding="utf-8") + "\nGuaranteed funding is not claimed.",
        encoding="utf-8",
    )

    result = run_site_check(site)

    assert result.exit_code == 1
    assert "claims_and_sensitive_markers" in result.output
    assert "guaranteed funding" in result.output.lower()


def test_site_check_missing_required_content_fails(tmp_path: Path) -> None:
    site = copy_docs_site(tmp_path)
    index = site / "index.html"
    index.write_text(
        index.read_text(encoding="utf-8").replace("VibeBench Arena", "VibeBench"),
        encoding="utf-8",
    )

    result = run_site_check(site)

    assert result.exit_code == 1
    assert "required_content" in result.output
    assert "VibeBench Arena" in result.output


def test_site_check_broken_local_relative_link_fails(tmp_path: Path) -> None:
    site = copy_docs_site(tmp_path)
    index = site / "index.html"
    index.write_text(
        index.read_text(encoding="utf-8") + '\n<a href="missing.md">Missing</a>',
        encoding="utf-8",
    )

    result = run_site_check(site)

    assert result.exit_code == 1
    assert "relative_links" in result.output
    assert "missing.md" in result.output


def test_site_check_root_option_works_on_copied_site(tmp_path: Path) -> None:
    site = copy_docs_site(tmp_path)

    result = runner.invoke(app, ["site-check", "--root", str(site), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "passed"
    assert payload["root"] == site.as_posix()
