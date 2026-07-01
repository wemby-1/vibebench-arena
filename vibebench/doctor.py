"""Project readiness diagnostics for VibeBench."""

from __future__ import annotations

import shlex
import shutil
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from vibebench.config import ConfigError, VibeBenchConfig, load_config
from vibebench.explain import find_latest_valid_run
from vibebench.gitdiff import is_git_repo
from vibebench.paths import config_dir, config_file
from vibebench.report import ReportError, load_metrics

DoctorStatus = Literal["passed", "warning", "failed"]

SHELL_TOKENS = {"&&", "||", "|", ";", ">", "<", "$(", "`"}


class DoctorCheck(BaseModel):
    """One doctor diagnostic row."""

    model_config = ConfigDict(extra="forbid")

    category: str
    status: DoctorStatus
    message: str
    advice: str | None = None


class DoctorResult(BaseModel):
    """Complete doctor diagnostic result."""

    model_config = ConfigDict(extra="forbid")

    project_root: Path
    checks: list[DoctorCheck]
    overall_status: DoctorStatus
    strict: bool = False
    advice: bool = False


def run_doctor(
    project_root: Path,
    *,
    strict: bool = False,
    advice: bool = False,
) -> DoctorResult:
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
        if strict:
            checks.extend(strict_checks(root))

    if advice:
        checks = [with_advice(check) for check in checks]

    overall_status: DoctorStatus = (
        "failed" if any(check.status == "failed" for check in checks) else "passed"
    )
    return DoctorResult(
        project_root=root,
        checks=checks,
        overall_status=overall_status,
        strict=strict,
        advice=advice,
    )


def doctor_json_payload(result: DoctorResult) -> dict[str, object]:
    """Return a deterministic JSON payload for doctor diagnostics."""
    return {
        "overall_status": result.overall_status,
        "strict": result.strict,
        "advice": result.advice,
        "project_root": str(result.project_root),
        "checks": [
            doctor_check_payload(check, include_advice=result.advice)
            for check in result.checks
        ],
    }


def doctor_check_payload(
    check: DoctorCheck,
    *,
    include_advice: bool,
) -> dict[str, object]:
    """Return a JSON-safe doctor check payload."""
    payload: dict[str, object] = {
        "name": check.category,
        "status": check.status,
        "message": check.message,
    }
    if include_advice and check.advice:
        payload["advice"] = check.advice
    return payload


def with_advice(check: DoctorCheck) -> DoctorCheck:
    """Attach concise advice to checks that need user attention."""
    if check.status == "passed":
        return check
    advice = advice_for_check(check)
    if not advice:
        return check
    return check.model_copy(update={"advice": advice})


def advice_for_check(check: DoctorCheck) -> str | None:
    """Return actionable advice for a failed or warning check."""
    advice_by_category = {
        "python": "Use Python 3.11 or newer.",
        "project_root": "Run VibeBench from an existing project directory.",
        "git": "Run inside a Git repository or initialize one with `git init`.",
        "config": (
            "Run `python -m vibebench init` or create `.vibebench/config.yaml`. "
            "Use `python -m vibebench config --validate` for invalid config."
        ),
        "configured_commands": (
            "Install missing tools or update `checks.test` and `checks.lint` "
            "in `.vibebench/config.yaml`."
        ),
        "runs_directory": "Ensure `.vibebench/runs/` is writable.",
        "strict_ci_workflow": (
            "Run `python -m vibebench init` or add `.github/workflows/ci.yml`."
        ),
        "strict_config": (
            "Run `python -m vibebench init` or `python -m vibebench config --validate`."
        ),
        "strict_runs_directory": "Run `python -m vibebench check`.",
        "strict_latest_run": "Run `python -m vibebench check`.",
        "strict_metrics": "Run `python -m vibebench check`.",
        "strict_manifest": "Run `python -m vibebench manifest`.",
        "strict_bundle": "Run `python -m vibebench bundle`.",
        "strict_report": "Run `python -m vibebench report`.",
    }
    return advice_by_category.get(check.category)




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


def strict_checks(project_root: Path) -> list[DoctorCheck]:
    """Run stronger release/CI readiness checks."""
    checks = [
        check_file_exists(
            "strict_ci_workflow",
            project_root / ".github" / "workflows" / "ci.yml",
            ".github/workflows/ci.yml exists",
        ),
    ]
    config_check, _ = check_config(project_root)
    checks.append(
        DoctorCheck(
            category="strict_config",
            status=config_check.status,
            message=config_check.message,
        )
    )

    runs_dir = config_dir(project_root) / "runs"
    if runs_dir.exists() and runs_dir.is_dir():
        checks.append(
            DoctorCheck(
                category="strict_runs_directory",
                status="passed",
                message=f"Run directory exists: {runs_dir}",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                category="strict_runs_directory",
                status="failed",
                message=f"Run directory does not exist: {runs_dir}",
            )
        )

    try:
        latest_run = find_latest_valid_run(project_root)
        load_metrics(latest_run)
    except (ReportError, OSError, ValueError) as exc:
        checks.append(
            DoctorCheck(
                category="strict_latest_run",
                status="failed",
                message=f"No readable latest VibeBench run: {exc}",
            )
        )
        return checks

    checks.append(
        DoctorCheck(
            category="strict_latest_run",
            status="passed",
            message=f"Latest valid run: {latest_run.name}",
        )
    )
    checks.extend(
        [
            check_file_exists(
                "strict_metrics",
                latest_run / "metrics.json",
                "latest run has metrics.json",
            ),
            check_file_exists(
                "strict_manifest",
                latest_run / "manifest.json",
                "latest run has manifest.json",
            ),
            check_file_exists(
                "strict_bundle",
                latest_run / "vibebench-bundle.zip",
                "latest run has vibebench-bundle.zip",
            ),
            check_file_exists(
                "strict_report",
                latest_run / "report" / "index.html",
                "latest run has report/index.html",
            ),
        ]
    )
    return checks


def check_file_exists(category: str, path: Path, success_message: str) -> DoctorCheck:
    """Return a doctor check for one required file."""
    if path.exists() and path.is_file():
        return DoctorCheck(
            category=category,
            status="passed",
            message=success_message,
        )
    return DoctorCheck(
        category=category,
        status="failed",
        message=f"Required file is missing: {path}",
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
