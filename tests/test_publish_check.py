import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from vibebench import publish_check as publish_check_module
from vibebench.cli import app
from vibebench.package_check import (
    PackageBuildReadiness,
    PackageReadinessCheck,
    PackageReadinessResult,
)
from vibebench.publish_check import run_publish_check
from vibebench.release_check import ReleaseReadinessCheck, ReleaseReadinessResult

runner = CliRunner()


def write_publish_project(root: Path, *, release_notes: bool = True) -> None:
    """Write a small project with package-check-compatible metadata."""
    (root / "docs").mkdir(parents=True)
    (root / "vibebench_arena").mkdir()
    (root / "vibebench_arena" / "__init__.py").write_text("", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "README.zh-CN.md").write_text("# Demo\n", encoding="utf-8")
    (root / "LICENSE").write_text("Apache-2.0\n", encoding="utf-8")
    (root / "docs" / "quickstart.md").write_text("# Quickstart\n", encoding="utf-8")
    (root / "docs" / "github-actions.md").write_text("# Actions\n", encoding="utf-8")
    (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    if release_notes:
        (root / "RELEASE_NOTES_v0.3.0.md").write_text(
            "# Release\n",
            encoding="utf-8",
        )
    (root / "pyproject.toml").write_text(
        """
[project]
name = "vibebench-arena"
version = "0.3.0"
readme = "README.md"
requires-python = ">=3.11"
license = { file = "LICENSE" }

[project.scripts]
vibebench = "vibebench.cli:main"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def ready_package_result(root: Path, *, build: bool = False) -> PackageReadinessResult:
    build_result = None
    checks = [PackageReadinessCheck("package_check", "passed", "passed")]
    if build:
        build_result = PackageBuildReadiness(
            requested=True,
            status="passed",
            tool="fake local builder",
            tool_available=True,
            artifacts=["demo-0.3.0-py3-none-any.whl"],
            output_dir=None,
            message="Local build passed.",
        )
        checks.append(PackageReadinessCheck("build_readiness", "passed", "passed"))
    return PackageReadinessResult(
        project_root=root.resolve(),
        package_name="vibebench-arena",
        version="0.3.0",
        checks=checks,
        build=build_result,
    )


def ready_release_result(root: Path) -> ReleaseReadinessResult:
    return ReleaseReadinessResult(
        project_root=root.resolve(),
        checks=[ReleaseReadinessCheck("release_check", "passed", "passed")],
        latest_run_dir=None,
        latest_run_id=None,
    )


def fake_clean_git(
    project_root: Path,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    if args == ["status", "--porcelain"]:
        stdout = ""
    elif args[:2] == ["tag", "--list"]:
        stdout = f"{args[2]}\n"
    elif args[0] == "ls-remote":
        stdout = f"abc123\t{args[2]}\n"
    else:
        stdout = ""
    return subprocess.CompletedProcess(["git", *args], 0, stdout=stdout, stderr="")


def install_ready_mocks(monkeypatch) -> None:
    monkeypatch.setattr(publish_check_module, "git_inspect", fake_clean_git)
    monkeypatch.setattr(
        publish_check_module,
        "run_package_check",
        lambda root, build=False: ready_package_result(root, build=build),
    )
    monkeypatch.setattr(
        publish_check_module,
        "run_release_check",
        lambda root: ready_release_result(root),
    )


def test_publish_check_command_exists() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "publish-check" in result.output


def test_publish_check_json_is_valid_pure_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_publish_project(tmp_path)
    install_ready_mocks(monkeypatch)

    result = runner.invoke(
        app,
        ["publish-check", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["overall_status"] == "ready"
    assert payload["package_version"] == "0.3.0"
    assert payload["project_root"] == str(tmp_path.resolve())
    assert isinstance(payload["checks"], list)


def test_publish_check_reports_dirty_working_tree(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_publish_project(tmp_path)
    install_ready_mocks(monkeypatch)

    def fake_dirty_git(
        project_root: Path,
        args: list[str],
    ) -> subprocess.CompletedProcess[str]:
        if args == ["status", "--porcelain"]:
            return subprocess.CompletedProcess(
                ["git", *args],
                0,
                stdout=" M README.md\n",
                stderr="",
            )
        return fake_clean_git(project_root, args)

    monkeypatch.setattr(publish_check_module, "git_inspect", fake_dirty_git)

    result = run_publish_check(tmp_path)

    checks = {check.name: check for check in result.checks}
    assert result.overall_status == "warning"
    assert checks["working_tree_clean"].status == "warning"
    assert "uncommitted changes" in checks["working_tree_clean"].message


def test_publish_check_reports_missing_release_notes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_publish_project(tmp_path, release_notes=False)
    install_ready_mocks(monkeypatch)

    result = run_publish_check(tmp_path)

    checks = {check.name: check for check in result.checks}
    assert result.overall_status == "failed"
    assert checks["release_notes_file"].status == "failed"
    assert "RELEASE_NOTES_v0.3.0.md" in checks["release_notes_file"].message


def test_publish_check_reports_build_failure_without_installing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_publish_project(tmp_path)
    install_ready_mocks(monkeypatch)

    def fake_package_check(root: Path, build: bool = False) -> PackageReadinessResult:
        if not build:
            return ready_package_result(root)
        build_result = PackageBuildReadiness(
            requested=True,
            status="failed",
            tool=None,
            tool_available=False,
            artifacts=[],
            output_dir=None,
            message="No local build tool is available",
            advice="Install local build tooling manually.",
        )
        return PackageReadinessResult(
            project_root=root.resolve(),
            package_name="vibebench-arena",
            version="0.3.0",
            checks=[
                PackageReadinessCheck("package_check", "passed", "passed"),
                PackageReadinessCheck(
                    "build_readiness",
                    "failed",
                    build_result.message,
                    build_result.advice,
                ),
            ],
            build=build_result,
        )

    monkeypatch.setattr(publish_check_module, "run_package_check", fake_package_check)

    result = run_publish_check(tmp_path)

    checks = {check.name: check for check in result.checks}
    assert result.overall_status == "failed"
    assert checks["package_build"].status == "failed"
    assert "No local build tool" in checks["package_build"].message
    assert "Install local build tooling" in (checks["package_build"].advice or "")


def test_publish_check_successful_mocked_readiness_returns_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_publish_project(tmp_path)
    install_ready_mocks(monkeypatch)

    result = run_publish_check(tmp_path)

    assert result.overall_status == "ready"
    assert all(check.status == "passed" for check in result.checks)


def test_publish_check_advice_includes_advice_fields(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_publish_project(tmp_path)
    install_ready_mocks(monkeypatch)

    def fake_warning_git(
        project_root: Path,
        args: list[str],
    ) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["tag", "--list"]:
            return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")
        return fake_clean_git(project_root, args)

    monkeypatch.setattr(publish_check_module, "git_inspect", fake_warning_git)

    result = runner.invoke(
        app,
        [
            "publish-check",
            "--project-root",
            str(tmp_path),
            "--advice",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    checks = {check["name"]: check for check in payload["checks"]}
    assert result.exit_code == 0
    assert payload["overall_status"] == "warning"
    assert "advice" in checks["local_tag_exists"]
    assert checks["local_tag_exists"]["advice"]
