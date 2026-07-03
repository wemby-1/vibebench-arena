import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.package_check import run_package_check

runner = CliRunner()


def write_ready_project(
    root: Path,
    *,
    version: str = "0.2.0",
    readme: str = "README.md",
) -> None:
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "README.zh-CN.md").write_text("# Demo\n", encoding="utf-8")
    (root / "LICENSE").write_text("Apache-2.0\n", encoding="utf-8")
    (root / "docs" / "quickstart.md").write_text("# Quickstart\n", encoding="utf-8")
    (root / "docs" / "github-actions.md").write_text("# Actions\n", encoding="utf-8")
    (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        f"""
[project]
name = "vibebench-arena"
version = "{version}"
readme = "{readme}"
requires-python = ">=3.11"
license = {{ file = "LICENSE" }}

[project.scripts]
vibebench = "vibebench.cli:main"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_package_check_ready_project_passes(tmp_path: Path) -> None:
    write_ready_project(tmp_path)

    result = runner.invoke(app, ["package-check", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Package readiness" in result.stdout
    assert "ready" in result.stdout


def test_package_check_missing_pyproject_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["package-check", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "pyproject.toml is missing" in result.stdout


def test_package_check_version_mismatch_fails(tmp_path: Path) -> None:
    write_ready_project(tmp_path, version="9.9.9")

    result = run_package_check(tmp_path)

    assert result.status == "not-ready"
    version_check = next(
        check for check in result.checks if check.name == "version_match"
    )
    assert version_check.status == "failed"
    assert "does not match" in version_check.message


def test_package_check_missing_referenced_readme_fails(tmp_path: Path) -> None:
    write_ready_project(tmp_path, readme="MISSING.md")

    result = run_package_check(tmp_path)

    readme_check = next(check for check in result.checks if check.name == "readme")
    assert readme_check.status == "failed"
    assert "missing" in readme_check.message


def test_package_check_missing_license_fails(tmp_path: Path) -> None:
    write_ready_project(tmp_path)
    (tmp_path / "LICENSE").unlink()

    result = run_package_check(tmp_path)

    license_check = next(check for check in result.checks if check.name == "license")
    assert license_check.status == "failed"


def test_package_check_json_output_is_pure_json(tmp_path: Path) -> None:
    write_ready_project(tmp_path)

    result = runner.invoke(
        app,
        ["package-check", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready"
    assert payload["package_name"] == "vibebench-arena"
    assert payload["version"] == "0.2.0"
    assert isinstance(payload["checks"], list)


def test_package_check_advice_includes_advice_fields(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["package-check", "--project-root", str(tmp_path), "--json", "--advice"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    failed_checks = [
        check for check in payload["checks"] if check["status"] == "failed"
    ]
    assert failed_checks
    assert all("advice" in check for check in failed_checks)


def test_package_check_does_not_require_network(tmp_path: Path, monkeypatch) -> None:
    write_ready_project(tmp_path)

    def fail_network(*args, **kwargs):
        raise AssertionError("network should not be used")

    monkeypatch.setattr("urllib.request.urlopen", fail_network)

    result = runner.invoke(app, ["package-check", "--project-root", str(tmp_path)])

    assert result.exit_code == 0


def test_existing_pr_comment_help_still_works() -> None:
    result = runner.invoke(app, ["pr-comment", "--help"])

    assert result.exit_code == 0
    assert result.stdout
    assert "Usage" in result.stdout or "pr-comment" in result.stdout
