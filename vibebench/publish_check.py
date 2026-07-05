"""Local-only publish readiness checks for VibeBench projects."""

from __future__ import annotations

import json
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vibebench.package_check import PackageReadinessResult, run_package_check
from vibebench.release_check import run_release_check
from vibebench.report import ReportError

PublishCheckStatus = Literal["passed", "warning", "failed"]


@dataclass(frozen=True)
class PublishReadinessCheck:
    """One publish readiness check."""

    name: str
    status: PublishCheckStatus
    message: str
    advice: str | None = None


@dataclass(frozen=True)
class PublishReadinessResult:
    """Complete publish readiness result."""

    project_root: Path
    package_version: str | None
    checks: list[PublishReadinessCheck]
    advice: bool = False

    @property
    def overall_status(self) -> str:
        """Return the overall publish readiness status."""
        statuses = {check.status for check in self.checks}
        if "failed" in statuses:
            return "failed"
        if "warning" in statuses:
            return "warning"
        return "ready"


def run_publish_check(
    project_root: Path,
    *,
    advice: bool = False,
) -> PublishReadinessResult:
    """Run local-only package publish readiness checks."""
    root = project_root.resolve()
    package_version = read_project_version(root)
    target_version = normalize_tag_version(package_version)

    base_package = run_package_check(root)
    build_package = run_package_check(root, build=True)

    checks = [
        working_tree_clean_check(root),
        package_version_check(package_version),
        release_notes_check(root, target_version),
        local_tag_check(root, target_version),
        remote_tag_check(root, target_version),
        package_check_result(base_package),
        package_build_check_result(build_package),
        release_check_result(root),
    ]

    return PublishReadinessResult(
        project_root=root,
        package_version=package_version,
        checks=checks,
        advice=advice,
    )


def publish_check_json_payload(result: PublishReadinessResult) -> dict[str, object]:
    """Return a JSON-safe publish readiness payload."""
    return {
        "overall_status": result.overall_status,
        "package_version": result.package_version,
        "project_root": str(result.project_root),
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "message": check.message,
                "advice": check.advice,
            }
            for check in result.checks
        ],
    }


def publish_check_json(result: PublishReadinessResult) -> str:
    """Return deterministic JSON for publish readiness."""
    return json.dumps(publish_check_json_payload(result), indent=2, sort_keys=True)


def write_publish_check_json(
    result: PublishReadinessResult,
    output_path: Path,
) -> Path:
    """Write publish readiness JSON to a selected path."""
    validate_output_path(output_path)
    output_path.write_text(publish_check_json(result) + "\n", encoding="utf-8")
    return output_path


def write_publish_check_summary(
    result: PublishReadinessResult,
    output_path: Path,
) -> Path:
    """Write publish readiness Markdown to a selected path."""
    validate_output_path(output_path)
    output_path.write_text(render_publish_check_markdown(result), encoding="utf-8")
    return output_path


def validate_output_path(output_path: Path) -> None:
    """Validate a requested publish-check output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"Publish-check output path is a directory: {output_path}")
    if not output_path.parent.exists():
        raise ReportError(
            f"Publish-check output parent does not exist: {output_path.parent}"
        )


def render_publish_check_markdown(result: PublishReadinessResult) -> str:
    """Render a concise Markdown publish readiness summary."""
    lines = [
        "# VibeBench Publish Check",
        "",
        f"- Project root: `{markdown_cell(result.project_root)}`",
        f"- Package version: `{markdown_cell(result.package_version or 'unknown')}`",
        f"- Overall status: `{markdown_cell(result.overall_status)}`",
        "",
        "| Check | Status | Message | Advice |",
        "| --- | --- | --- | --- |",
    ]
    for check in result.checks:
        lines.append(
            "| "
            f"{markdown_cell(check.name)} | "
            f"{markdown_cell(check.status)} | "
            f"{markdown_cell(check.message)} | "
            f"{markdown_cell(check.advice or '')} |"
        )
    lines.extend(
        [
            "",
            "## Local-Only Safety",
            "",
            "- No package upload is performed.",
            "- No publishing is performed.",
            "- No tag or release is created.",
            "- No version bump is performed.",
            "",
        ]
    )
    return "\n".join(lines)


def markdown_cell(value: object) -> str:
    """Escape Markdown table-sensitive content."""
    return str(value).replace("|", "\\|").replace("\n", " ")


def read_project_version(project_root: Path) -> str | None:
    """Read project.version from pyproject.toml."""
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.is_file():
        return None
    try:
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    project = payload.get("project")
    if not isinstance(project, dict):
        return None
    version = project.get("version")
    return version if isinstance(version, str) and version.strip() else None


def normalize_tag_version(package_version: str | None) -> str:
    """Return the expected version tag name."""
    if not package_version:
        return "unknown"
    stripped = package_version.strip()
    if not stripped:
        return "unknown"
    return stripped if stripped.startswith("v") else f"v{stripped}"


def git_inspect(
    project_root: Path,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    """Run a read-only git inspection command."""
    command = ["git", *args]
    try:
        return subprocess.run(
            command,
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr=str(exc))


def working_tree_clean_check(project_root: Path) -> PublishReadinessCheck:
    """Check whether the git working tree is clean."""
    result = git_inspect(project_root, ["status", "--porcelain"])
    if result.returncode != 0:
        return failed(
            "working_tree_clean",
            "Could not inspect working tree status.",
            "Run git status and resolve repository errors before publishing.",
        )
    if result.stdout.strip():
        return warning(
            "working_tree_clean",
            "Working tree has uncommitted changes.",
            "Commit or discard local changes before publishing.",
        )
    return passed("working_tree_clean", "Working tree is clean.")


def package_version_check(package_version: str | None) -> PublishReadinessCheck:
    """Check package metadata version availability."""
    if package_version:
        return passed(
            "package_metadata_version",
            f"Package metadata version is {package_version}.",
        )
    return failed(
        "package_metadata_version",
        "Package metadata version was not found.",
        "Set project.version in pyproject.toml before publishing.",
    )


def release_notes_check(
    project_root: Path,
    target_version: str,
) -> PublishReadinessCheck:
    """Check whether release notes exist for the package version."""
    notes_path = project_root / f"RELEASE_NOTES_{target_version}.md"
    if notes_path.is_file():
        return passed(
            "release_notes_file",
            f"Release notes found: {notes_path.name}.",
        )
    return failed(
        "release_notes_file",
        f"Release notes missing: {notes_path.name}.",
        "Create release notes for the package version before publishing.",
    )


def local_tag_check(project_root: Path, target_version: str) -> PublishReadinessCheck:
    """Check whether the expected version tag exists locally."""
    if target_version == "unknown":
        return warning(
            "local_tag_exists",
            "Local tag could not be checked because package version is unknown.",
            "Set project.version, then create the matching tag after verification.",
        )
    result = git_inspect(project_root, ["tag", "--list", target_version])
    if result.returncode != 0:
        return warning(
            "local_tag_exists",
            "Could not inspect local tags.",
            "Run git tag --list locally before publishing.",
        )
    if result.stdout.strip() == target_version:
        return passed("local_tag_exists", f"Local tag exists: {target_version}.")
    return warning(
        "local_tag_exists",
        f"Local tag does not exist yet: {target_version}.",
        "Create the matching tag only after final verification passes.",
    )


def remote_tag_check(project_root: Path, target_version: str) -> PublishReadinessCheck:
    """Check whether the expected version tag exists on origin when possible."""
    if target_version == "unknown":
        return warning(
            "remote_tag_exists",
            "Remote tag could not be checked because package version is unknown.",
            "Set project.version, then push the matching tag after verification.",
        )
    result = git_inspect(
        project_root,
        ["ls-remote", "origin", f"refs/tags/{target_version}"],
    )
    if result.returncode != 0:
        return warning(
            "remote_tag_exists",
            "Could not inspect remote tag through git.",
            "Check network access and run git ls-remote origin manually.",
        )
    if result.stdout.strip():
        return passed("remote_tag_exists", f"Remote tag exists: {target_version}.")
    return warning(
        "remote_tag_exists",
        f"Remote tag does not exist yet: {target_version}.",
        "Push the matching tag only after final verification passes.",
    )


def package_check_result(result: PackageReadinessResult) -> PublishReadinessCheck:
    """Convert package-check result into a publish readiness check."""
    if result.ready:
        return passed("package_check", "package-check passed.")
    failed_checks = [check for check in result.checks if check.status == "failed"]
    message = "; ".join(f"{check.name}: {check.message}" for check in failed_checks)
    return failed(
        "package_check",
        message or "package-check did not pass.",
        "Run python -m vibebench package-check and address reported issues.",
    )


def package_build_check_result(
    result: PackageReadinessResult,
) -> PublishReadinessCheck:
    """Convert package-check --build result into a publish readiness check."""
    build = result.build
    if build is not None and build.status == "passed":
        artifacts = ", ".join(build.artifacts) if build.artifacts else "artifact"
        return passed(
            "package_build",
            f"package-check --build passed with {build.tool}: {artifacts}.",
        )
    message = build.message if build is not None else "Build readiness was not run."
    advice = (
        build.advice
        if build is not None and build.advice
        else "Run python -m vibebench package-check --build and address issues."
    )
    return failed("package_build", message, advice)


def release_check_result(project_root: Path) -> PublishReadinessCheck:
    """Convert release-check result into a publish readiness check."""
    result = run_release_check(project_root)
    if result.ready:
        return passed("release_check", "release-check passed.")
    failed_checks = [check for check in result.checks if check.status == "failed"]
    message = "; ".join(f"{check.name}: {check.message}" for check in failed_checks)
    return failed(
        "release_check",
        message or "release-check did not pass.",
        "Run python -m vibebench release-check and address reported issues.",
    )


def passed(name: str, message: str) -> PublishReadinessCheck:
    """Build a passing publish readiness check."""
    return PublishReadinessCheck(name=name, status="passed", message=message)


def warning(
    name: str,
    message: str,
    advice: str,
) -> PublishReadinessCheck:
    """Build a warning publish readiness check."""
    return PublishReadinessCheck(
        name=name,
        status="warning",
        message=message,
        advice=advice,
    )


def failed(
    name: str,
    message: str,
    advice: str,
) -> PublishReadinessCheck:
    """Build a failing publish readiness check."""
    return PublishReadinessCheck(
        name=name,
        status="failed",
        message=message,
        advice=advice,
    )
