"""Project readiness diagnostics for VibeBench."""

from __future__ import annotations

import shlex
import shutil
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from vibebench.config import ConfigError, VibeBenchConfig, load_config
from vibebench.gitdiff import is_git_repo
from vibebench.paths import config_dir, config_file

DoctorStatus = Literal["passed", "warning", "failed"]

SHELL_TOKENS = {"&&", "||", "|", ";", ">", "<", "$(", "`"}


class DoctorCheck(BaseModel):
    """One doctor diagnostic row."""

    model_config = ConfigDict(extra="forbid")

    category: str
    status: DoctorStatus
    message: str


class DoctorResult(BaseModel):
    """Complete doctor diagnostic result."""

    model_config = ConfigDict(extra="forbid")

    project_root: Path
    checks: list[DoctorCheck]
    overall_status: DoctorStatus


def run_doctor(project_root: Path) -> DoctorResult:
    """Run readiness diagnostics without executing configured checks."""
    root = project_root.resolve()
    checks: list[DoctorCheck] = [
        check_python_version(),
        check_project_root(root),
    ]

    if root.exists() and root.is_dir():
        checks.append(check_git(root))
        config_check, config = check_config(root)
        checks.append(config_check)
        if config is not None:
            checks.append(check_configured_commands(config))
        checks.append(check_runs_directory(root))

    overall_status: DoctorStatus = (
        "failed" if any(check.status == "failed" for check in checks) else "passed"
    )
    return DoctorResult(
        project_root=root,
        checks=checks,
        overall_status=overall_status,
    )


def check_python_version() -> DoctorCheck:
    """Check that Python is new enough for VibeBench."""
    version = sys.version_info
    label = f"Python {version.major}.{version.minor}.{version.micro}"
    if version >= (3, 11):
        return DoctorCheck(category="python", status="passed", message=label)
    return DoctorCheck(
        category="python",
        status="failed",
        message=f"{label}; Python 3.11+ is required",
    )


def check_project_root(project_root: Path) -> DoctorCheck:
    """Check that the project root exists."""
    if project_root.exists() and project_root.is_dir():
        return DoctorCheck(
            category="project_root",
            status="passed",
            message=f"Project root found: {project_root}",
        )
    return DoctorCheck(
        category="project_root",
        status="failed",
        message=f"Project root does not exist: {project_root}",
    )


def check_git(project_root: Path) -> DoctorCheck:
    """Check that the project root is inside a Git repository."""
    if is_git_repo(project_root):
        return DoctorCheck(
            category="git",
            status="passed",
            message="Git repository detected",
        )
    return DoctorCheck(
        category="git",
        status="failed",
        message="Project root is not inside a Git repository",
    )


def check_config(project_root: Path) -> tuple[DoctorCheck, VibeBenchConfig | None]:
    """Check that VibeBench config exists and validates."""
    target = config_file(project_root)
    if not target.exists():
        return (
            DoctorCheck(
                category="config",
                status="failed",
                message="No .vibebench/config.yaml found. Run 'vibebench init' first.",
            ),
            None,
        )

    try:
        config = load_config(target)
    except ConfigError as exc:
        return (
            DoctorCheck(category="config", status="failed", message=str(exc)),
            None,
        )

    return (
        DoctorCheck(
            category="config",
            status="passed",
            message=".vibebench/config.yaml loaded",
        ),
        config,
    )


def check_configured_commands(config: VibeBenchConfig) -> DoctorCheck:
    """Check whether configured command executables are discoverable."""
    commands = [*config.checks.test, *config.checks.lint]
    if not commands:
        return DoctorCheck(
            category="configured_commands",
            status="warning",
            message="No test or lint commands configured",
        )

    warnings: list[str] = []
    failures: list[str] = []
    for command in commands:
        executable = first_executable(command)
        if executable is None:
            failures.append(f'empty command: "{command}"')
        elif is_shell_specific(command):
            warnings.append(f'shell-specific command: "{command}"')
        elif shutil.which(executable) is None:
            warnings.append(f'executable not found: "{executable}"')

    if failures:
        return DoctorCheck(
            category="configured_commands",
            status="failed",
            message="; ".join(failures),
        )
    if warnings:
        return DoctorCheck(
            category="configured_commands",
            status="warning",
            message="; ".join(warnings),
        )
    return DoctorCheck(
        category="configured_commands",
        status="passed",
        message=f"{len(commands)} configured command(s) appear runnable",
    )


def first_executable(command: str) -> str | None:
    """Return the first executable token from a configured command."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    if not parts:
        return None
    return parts[0]


def is_shell_specific(command: str) -> bool:
    """Return whether a command appears to rely on shell syntax."""
    return any(token in command for token in SHELL_TOKENS)


def check_runs_directory(project_root: Path) -> DoctorCheck:
    """Check that .vibebench/runs can be created and written."""
    runs_dir = config_dir(project_root) / "runs"
    try:
        runs_dir.mkdir(parents=True, exist_ok=True)
        probe = runs_dir / ".doctor-write-test"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return DoctorCheck(
            category="runs_directory",
            status="failed",
            message=f"Cannot write to {runs_dir}: {exc}",
        )
    return DoctorCheck(
        category="runs_directory",
        status="passed",
        message="writable",
    )
