import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from vibebench import release_audit as release_audit_module
from vibebench.cli import app
from vibebench.package_check import PackageReadinessCheck, PackageReadinessResult
from vibebench.publish_check import PublishReadinessResult

runner = CliRunner()


EXPECTED_FILES = {
    "package-check.json",
    "package-check.md",
    "publish-check.json",
    "publish-check.md",
    "release-checklist.json",
    "release-checklist.md",
    "release-audit.json",
    "release-audit.md",
}


def write_audit_project(root: Path, *, version: str = "0.3.0") -> None:
    """Write minimal project metadata for release-audit tests."""
    root.joinpath("pyproject.toml").write_text(
        f"""
[project]
name = "vibebench-arena"
version = "{version}"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    root.joinpath(f"RELEASE_NOTES_v{version}.md").write_text(
        "# Release\n",
        encoding="utf-8",
    )


def install_release_audit_mocks(monkeypatch) -> None:
    """Avoid expensive checks and network-ish git inspection in audit tests."""
    package_result = PackageReadinessResult(
        project_root=Path(".").resolve(),
        package_name="vibebench-arena",
        version="0.3.0",
        checks=[
            PackageReadinessCheck(
                name="package_check",
                status="passed",
                message="passed",
            )
        ],
        advice=True,
    )
    publish_result = PublishReadinessResult(
        project_root=Path(".").resolve(),
        package_version="0.3.0",
        checks=[],
        advice=True,
    )
    monkeypatch.setattr(
        release_audit_module,
        "run_package_check",
        lambda root, advice=True, build=True: package_result,
    )
    monkeypatch.setattr(
        release_audit_module,
        "run_publish_check",
        lambda root, advice=True: publish_result,
    )
    monkeypatch.setattr(
        "vibebench.cli.run_package_check",
        lambda root: SimpleNamespace(ready=True),
    )
    monkeypatch.setattr(
        "vibebench.cli.run_release_check",
        lambda root: SimpleNamespace(ready=True),
    )
    monkeypatch.setattr(
        "vibebench.cli.run_doctor",
        lambda root, strict, advice: SimpleNamespace(overall_status="passed"),
    )

    def fake_git(root: Path, args: list[str]) -> SimpleNamespace:
        if args == ["status", "--porcelain"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[:2] == ["tag", "--list"]:
            return SimpleNamespace(returncode=0, stdout=f"{args[2]}\n", stderr="")
        if args[:2] == ["ls-remote", "origin"]:
            return SimpleNamespace(
                returncode=0,
                stdout=f"abc123\t{args[2]}\n",
                stderr="",
            )
        return SimpleNamespace(returncode=1, stdout="", stderr="unexpected git args")

    monkeypatch.setattr("vibebench.cli.release_checklist_git", fake_git)


def test_release_audit_creates_expected_files(tmp_path: Path, monkeypatch) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"

    result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert {path.name for path in output_dir.iterdir()} == EXPECTED_FILES


def test_release_audit_json_stdout_is_pure_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)

    result = runner.invoke(
        app,
        ["release-audit", "--project-root", str(tmp_path), "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "warning"
    assert payload["version"] == "v0.3.0"
    assert set(payload["safety_notes"]) >= {
        "No tag is created.",
        "No GitHub Release is created.",
    }


def test_release_audit_version_records_requested_version(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    tmp_path.joinpath("RELEASE_NOTES_v0.4.0.md").write_text(
        "# Release\n",
        encoding="utf-8",
    )
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"

    result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--version",
            "v0.4.0",
            "--output-dir",
            str(output_dir),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    written = json.loads(output_dir.joinpath("release-audit.json").read_text())
    assert result.exit_code == 0
    assert payload["version"] == "v0.4.0"
    assert written["version"] == "v0.4.0"


def test_release_audit_output_dir_writes_into_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "selected-audit"

    result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert output_dir.joinpath("release-audit.json").is_file()
    assert output_dir.joinpath("release-audit.md").is_file()


def test_release_audit_markdown_includes_title_and_safety(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"

    result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    markdown = output_dir.joinpath("release-audit.md").read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert "# VibeBench Release Audit" in markdown
    assert "No tag is created" in markdown
    assert "No GitHub Release is created" in markdown
    assert "No package publish or upload is performed" in markdown
    assert "No version bump is performed" in markdown


def test_release_audit_json_includes_generated_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"

    result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    payload = json.loads(output_dir.joinpath("release-audit.json").read_text())
    generated = {item["name"] for item in payload["generated_files"]}
    assert result.exit_code == 0
    assert generated == EXPECTED_FILES


def test_release_audit_invalid_output_parent_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "missing" / "audit"

    result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 1
    assert "output parent does not exist" in result.output


def test_release_audit_output_path_file_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_path = tmp_path / "audit-file"
    output_path.write_text("existing", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_path),
        ],
    )

    assert result.exit_code == 1
    assert "output path is a file" in result.output
