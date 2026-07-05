import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

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
    "release-body.json",
    "release-body.md",
    "release-audit.json",
    "release-audit.md",
}
MANIFEST_FILE = "release-audit-manifest.json"
EXPECTED_GENERATED_FILES = EXPECTED_FILES | {MANIFEST_FILE}


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
    assert {path.name for path in output_dir.iterdir()} == EXPECTED_GENERATED_FILES


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
    assert payload["archive"] == {
        "included_files": [],
        "path": None,
        "requested": False,
        "status": "not_requested",
    }
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


def test_release_audit_includes_release_body_outputs(
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

    body_markdown = output_dir.joinpath("release-body.md").read_text(
        encoding="utf-8"
    )
    body_json = json.loads(output_dir.joinpath("release-body.json").read_text())
    assert result.exit_code == 0
    assert body_markdown == "# Release\n"
    assert body_json["version"] == "v0.3.0"
    assert body_json["status"] == "passed"


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
    assert generated == EXPECTED_GENERATED_FILES


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


def test_release_audit_zip_creates_expected_archive(
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
            "--zip",
        ],
    )

    zip_path = output_dir / "release-audit.zip"
    assert result.exit_code == 0
    assert zip_path.is_file()
    with ZipFile(zip_path) as archive:
        names = archive.namelist()
    assert set(names) == EXPECTED_GENERATED_FILES
    assert all(not name.startswith("/") for name in names)
    assert all(".." not in Path(name).parts for name in names)
    assert all(len(Path(name).parts) == 1 for name in names)


def test_release_audit_zip_includes_release_body_outputs(
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
            "--zip",
        ],
    )

    assert result.exit_code == 0
    with ZipFile(output_dir / "release-audit.zip") as archive:
        assert "release-body.md" in archive.namelist()
        assert "release-body.json" in archive.namelist()


def test_release_audit_zip_output_writes_requested_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    zip_path = tmp_path / "requested-release-audit.zip"

    result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--zip-output",
            str(zip_path),
        ],
    )

    assert result.exit_code == 0
    assert zip_path.is_file()
    assert not output_dir.joinpath("release-audit.zip").exists()


def test_release_audit_json_zip_stdout_is_pure_json(
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
            "--zip",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["archive"]["requested"] is True
    assert payload["archive"]["status"] == "created"
    assert payload["archive"]["path"] == str(output_dir / "release-audit.zip")


def test_release_audit_json_records_archive_metadata(
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
            "--zip",
        ],
    )

    payload = json.loads(output_dir.joinpath("release-audit.json").read_text())
    assert result.exit_code == 0
    assert payload["archive"] == {
        "included_files": sorted(EXPECTED_GENERATED_FILES),
        "path": str(output_dir / "release-audit.zip"),
        "requested": True,
        "status": "created",
    }


def test_release_audit_markdown_mentions_archive(
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
            "--zip",
        ],
    )

    markdown = output_dir.joinpath("release-audit.md").read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert "## Archive" in markdown
    assert str(output_dir / "release-audit.zip") in markdown


def test_release_audit_missing_zip_output_parent_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    zip_path = tmp_path / "missing" / "release-audit.zip"

    result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--zip-output",
            str(zip_path),
        ],
    )

    assert result.exit_code == 1
    assert "zip output parent does not exist" in result.output


def test_release_audit_zip_output_directory_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    zip_path = tmp_path / "zip-dir"
    zip_path.mkdir()

    result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--zip-output",
            str(zip_path),
        ],
    )

    assert result.exit_code == 1
    assert "zip output path is a directory" in result.output


def test_release_audit_default_does_not_create_archive(
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
    assert result.exit_code == 0
    assert not output_dir.joinpath("release-audit.zip").exists()
    assert payload["archive"]["requested"] is False
    assert payload["archive"]["status"] == "not_requested"


def test_release_audit_verify_generated_directory_passes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    result = runner.invoke(app, ["release-audit", "--verify", str(output_dir)])

    assert create_result.exit_code == 0
    assert result.exit_code == 0
    assert "Release audit verification: passed" in result.output


def test_release_audit_verify_generated_zip_passes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--zip",
        ],
    )

    result = runner.invoke(
        app,
        ["release-audit", "--verify", str(output_dir / "release-audit.zip")],
    )

    assert create_result.exit_code == 0
    assert result.exit_code == 0
    assert "Release audit verification: passed" in result.output


def test_release_audit_verify_json_stdout_is_pure_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    result = runner.invoke(
        app,
        ["release-audit", "--verify", str(output_dir), "--json"],
    )

    payload = json.loads(result.output)
    assert create_result.exit_code == 0
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert payload["target_type"] == "directory"
    assert set(payload["required_files"]) == EXPECTED_FILES


def test_release_audit_verify_missing_release_body_markdown_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    output_dir.joinpath("release-body.md").unlink()

    result = runner.invoke(app, ["release-audit", "--verify", str(output_dir)])

    assert create_result.exit_code == 0
    assert result.exit_code == 1
    assert "Missing release-body.md" in result.output


def test_release_audit_verify_missing_required_file_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    output_dir.joinpath("publish-check.md").unlink()

    result = runner.invoke(app, ["release-audit", "--verify", str(output_dir)])

    assert create_result.exit_code == 0
    assert result.exit_code == 1
    assert "Missing publish-check.md" in result.output


def test_release_audit_verify_invalid_json_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    output_dir.joinpath("package-check.json").write_text("{", encoding="utf-8")

    result = runner.invoke(app, ["release-audit", "--verify", str(output_dir)])

    assert create_result.exit_code == 0
    assert result.exit_code == 1
    assert "Invalid JSON in package-check.json" in result.output


def test_release_audit_verify_empty_markdown_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    output_dir.joinpath("release-audit.md").write_text("", encoding="utf-8")

    result = runner.invoke(app, ["release-audit", "--verify", str(output_dir)])

    assert create_result.exit_code == 0
    assert result.exit_code == 1
    assert "Empty Markdown in release-audit.md" in result.output


def test_release_audit_verify_unsafe_zip_entry_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--zip",
        ],
    )
    with ZipFile(output_dir / "release-audit.zip", "a") as archive:
        archive.writestr("../unsafe.txt", "bad")

    result = runner.invoke(
        app,
        ["release-audit", "--verify", str(output_dir / "release-audit.zip")],
    )

    assert create_result.exit_code == 0
    assert result.exit_code == 1
    assert "Unsafe zip entries" in result.output
    assert "../unsafe.txt" in result.output


def test_release_audit_verify_nonexistent_path_fails(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-audit"

    result = runner.invoke(app, ["release-audit", "--verify", str(missing)])

    assert result.exit_code == 1
    assert "Path does not exist" in result.output


def test_release_audit_verify_plain_file_fails(
    tmp_path: Path,
) -> None:
    target = tmp_path / "release-audit.txt"
    target.write_text("not an audit", encoding="utf-8")

    result = runner.invoke(app, ["release-audit", "--verify", str(target)])

    assert result.exit_code == 1
    assert "neither a release audit directory nor a .zip file" in result.output


def test_release_audit_directory_includes_manifest(
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

    assert result.exit_code == 0
    assert output_dir.joinpath(MANIFEST_FILE).is_file()


def test_release_audit_zip_includes_manifest(
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
            "--zip",
        ],
    )

    assert result.exit_code == 0
    with ZipFile(output_dir / "release-audit.zip") as archive:
        assert MANIFEST_FILE in archive.namelist()


def test_release_audit_manifest_records_size_and_sha256(
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

    payload = json.loads(output_dir.joinpath(MANIFEST_FILE).read_text())
    files = {entry["path"]: entry for entry in payload["files"]}
    assert result.exit_code == 0
    assert payload["schema_version"] == 1
    assert payload["artifact"] == "release-audit"
    assert set(files) == EXPECTED_FILES
    assert "release-body.md" in files
    assert "release-body.json" in files
    for entry in files.values():
        assert isinstance(entry["size_bytes"], int)
        assert entry["size_bytes"] > 0
        assert isinstance(entry["sha256"], str)
        assert len(entry["sha256"]) == 64
        assert entry["sha256"] == entry["sha256"].lower()


def test_release_audit_verify_modified_release_body_json_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    output_dir.joinpath("release-body.json").write_text(
        "{}\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["release-audit", "--verify", str(output_dir)])

    assert create_result.exit_code == 0
    assert result.exit_code == 1
    assert "Manifest size mismatch for release-body.json" in result.output
    assert "Manifest sha256 mismatch for release-body.json" in result.output


def test_release_audit_verify_manifest_detects_modified_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    output_dir.joinpath("package-check.md").write_text("changed", encoding="utf-8")

    result = runner.invoke(app, ["release-audit", "--verify", str(output_dir)])

    assert create_result.exit_code == 0
    assert result.exit_code == 1
    assert "Manifest size mismatch for package-check.md" in result.output
    assert "Manifest sha256 mismatch for package-check.md" in result.output


def test_release_audit_verify_manifest_detects_bad_sha256(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    manifest_path = output_dir / MANIFEST_FILE
    payload = json.loads(manifest_path.read_text())
    payload["files"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    result = runner.invoke(app, ["release-audit", "--verify", str(output_dir)])

    assert create_result.exit_code == 0
    assert result.exit_code == 1
    assert "Manifest sha256 mismatch" in result.output


def test_release_audit_verify_manifest_rejects_unsafe_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    manifest_path = output_dir / MANIFEST_FILE
    payload = json.loads(manifest_path.read_text())
    payload["files"].append(
        {"path": "../bad.txt", "size_bytes": 1, "sha256": "0" * 64}
    )
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    result = runner.invoke(app, ["release-audit", "--verify", str(output_dir)])

    assert create_result.exit_code == 0
    assert result.exit_code == 1
    assert "Unsafe manifest path: ../bad.txt" in result.output


def test_release_audit_verify_accepts_old_audit_without_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    output_dir.joinpath(MANIFEST_FILE).unlink()

    result = runner.invoke(app, ["release-audit", "--verify", str(output_dir)])

    assert create_result.exit_code == 0
    assert result.exit_code == 0
    assert "Release audit verification: passed" in result.output


def test_release_audit_verify_zip_with_manifest_passes_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_audit_project(tmp_path)
    install_release_audit_mocks(monkeypatch)
    output_dir = tmp_path / "audit"
    create_result = runner.invoke(
        app,
        [
            "release-audit",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--zip",
        ],
    )

    result = runner.invoke(
        app,
        [
            "release-audit",
            "--verify",
            str(output_dir / "release-audit.zip"),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert create_result.exit_code == 0
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert any(check["name"] == "manifest_json" for check in payload["checks"])
