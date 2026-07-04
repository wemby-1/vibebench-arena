"""Release readiness checks for VibeBench projects."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vibebench.artifacts import collect_artifact_inventory
from vibebench.config import ConfigError, load_effective_config
from vibebench.config_check import config_check_payload, config_consistency_checks
from vibebench.doctor import run_doctor
from vibebench.explain import find_latest_valid_run
from vibebench.manifest import check_manifest
from vibebench.package_check import run_package_check
from vibebench.paths import config_file
from vibebench.report import ReportError
from vibebench.run_index import build_run_index

RELEASE_CHECK_JSON = "release-check.json"
RELEASE_CHECK_SUMMARY = "release-check.md"

ReleaseCheckStatus = Literal["passed", "failed"]


@dataclass(frozen=True)
class ReleaseReadinessCheck:
    """One release readiness check."""

    name: str
    status: ReleaseCheckStatus
    message: str


@dataclass(frozen=True)
class ReleaseReadinessResult:
    """Complete release readiness result."""

    project_root: Path
    checks: list[ReleaseReadinessCheck]
    latest_run_dir: Path | None
    latest_run_id: str | None

    @property
    def ready(self) -> bool:
        """Return whether every readiness check passed."""
        return all(check.status == "passed" for check in self.checks)

    @property
    def status(self) -> str:
        """Return the release readiness status string."""
        return "ready" if self.ready else "not-ready"


def run_release_check(project_root: Path) -> ReleaseReadinessResult:
    """Run release readiness checks without modifying project files."""
    root = project_root.resolve()
    latest_run_dir: Path | None = None
    latest_run_id: str | None = None

    checks = [
        check_config_consistency(root),
        check_package_readiness(root),
        check_doctor_strict(root),
    ]

    latest_check, latest_run_dir = check_latest_run(root)
    checks.append(latest_check)
    if latest_run_dir is not None:
        latest_run_id = latest_run_dir.name

    checks.append(check_manifest_consistency(root, latest_run_dir))
    checks.append(check_artifact_inventory(root, latest_run_dir))
    checks.append(check_run_index(root))
    checks.append(check_ci_plan())
    checks.append(check_git_diff_whitespace(root))

    return ReleaseReadinessResult(
        project_root=root,
        checks=checks,
        latest_run_dir=latest_run_dir,
        latest_run_id=latest_run_id,
    )


def check_config_consistency(project_root: Path) -> ReleaseReadinessCheck:
    """Run config load and consistency diagnostics."""
    try:
        result = load_effective_config(config_file(project_root))
        checks = config_consistency_checks(result)
        payload = config_check_payload(result, checks)
    except ConfigError as exc:
        return ReleaseReadinessCheck("config", "failed", str(exc))

    status = "passed" if payload["overall_status"] == "passed" else "failed"
    failed = [check for check in checks if check["status"] == "failed"]
    message = (
        "Config consistency check passed"
        if not failed
        else "; ".join(check["message"] for check in failed)
    )
    return ReleaseReadinessCheck("config", status, message)


def check_package_readiness(project_root: Path) -> ReleaseReadinessCheck:
    """Run package metadata and install readiness diagnostics."""
    result = run_package_check(project_root)
    if result.ready:
        return ReleaseReadinessCheck(
            "package_check",
            "passed",
            "Package readiness check passed",
        )
    failed = [check for check in result.checks if check.status == "failed"]
    message = "; ".join(f"{check.name}: {check.message}" for check in failed)
    return ReleaseReadinessCheck(
        "package_check",
        "failed",
        message or "Package readiness check failed",
    )


def check_doctor_strict(project_root: Path) -> ReleaseReadinessCheck:
    """Run strict doctor diagnostics."""
    result = run_doctor(project_root, strict=True)
    if result.overall_status == "passed":
        return ReleaseReadinessCheck("doctor_strict", "passed", "Strict doctor passed")
    failed = [check for check in result.checks if check.status == "failed"]
    message = "; ".join(f"{check.category}: {check.message}" for check in failed)
    return ReleaseReadinessCheck("doctor_strict", "failed", message)


def check_latest_run(project_root: Path) -> tuple[ReleaseReadinessCheck, Path | None]:
    """Find the latest valid run."""
    try:
        run_dir = find_latest_valid_run(project_root)
    except ReportError as exc:
        return ReleaseReadinessCheck("latest_run", "failed", str(exc)), None
    return (
        ReleaseReadinessCheck(
            "latest_run",
            "passed",
            f"Latest valid run: {run_dir.name}",
        ),
        run_dir,
    )


def check_manifest_consistency(
    project_root: Path,
    latest_run_dir: Path | None,
) -> ReleaseReadinessCheck:
    """Check latest run manifest consistency."""
    if latest_run_dir is None:
        return ReleaseReadinessCheck(
            "manifest",
            "failed",
            "No latest run available for manifest check",
        )
    try:
        result = check_manifest(project_root, latest_run_dir)
    except ReportError as exc:
        return ReleaseReadinessCheck("manifest", "failed", str(exc))
    if result.passed:
        return ReleaseReadinessCheck("manifest", "passed", "Manifest is consistent")
    return ReleaseReadinessCheck(
        "manifest",
        "failed",
        "; ".join(result.differences[:3]),
    )


def check_artifact_inventory(
    project_root: Path,
    latest_run_dir: Path | None,
) -> ReleaseReadinessCheck:
    """Check that artifact inventory can be generated."""
    if latest_run_dir is None:
        return ReleaseReadinessCheck(
            "artifacts",
            "failed",
            "No latest run available for artifact inventory",
        )
    try:
        result = collect_artifact_inventory(project_root, latest_run_dir)
    except ReportError as exc:
        return ReleaseReadinessCheck("artifacts", "failed", str(exc))
    available = sum(1 for artifact in result.artifacts if artifact.available)
    return ReleaseReadinessCheck(
        "artifacts",
        "passed",
        f"Artifact inventory generated ({available} available)",
    )


def check_run_index(project_root: Path) -> ReleaseReadinessCheck:
    """Check that a useful run index can be generated."""
    try:
        result = build_run_index(project_root)
    except ReportError as exc:
        return ReleaseReadinessCheck("run_index", "failed", str(exc))
    return ReleaseReadinessCheck(
        "run_index",
        "passed",
        (
            f"Run index generated ({len(result.runs)} indexed, "
            f"{result.total_runs_seen} seen)"
        ),
    )


def check_ci_plan() -> ReleaseReadinessCheck:
    """Check that a dry-run CI plan can be produced."""
    from vibebench.ci import plan_ci_pipeline

    result = plan_ci_pipeline()
    if result.dry_run and result.steps:
        return ReleaseReadinessCheck("ci_plan", "passed", "CI dry-run plan produced")
    return ReleaseReadinessCheck("ci_plan", "failed", "CI dry-run plan was empty")


def check_git_diff_whitespace(project_root: Path) -> ReleaseReadinessCheck:
    """Run git diff --check as a whitespace/readiness check."""
    try:
        completed = subprocess.run(
            ["git", "diff", "--check"],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return ReleaseReadinessCheck("git_diff_check", "failed", str(exc))
    if completed.returncode == 0:
        return ReleaseReadinessCheck(
            "git_diff_check",
            "passed",
            "git diff --check passed",
        )
    message = (
        completed.stdout or completed.stderr or "git diff --check failed"
    ).strip()
    return ReleaseReadinessCheck("git_diff_check", "failed", message)


def release_check_json_payload(result: ReleaseReadinessResult) -> dict[str, object]:
    """Return a deterministic JSON-safe release readiness payload."""
    return {
        "status": result.status,
        "project_root": str(result.project_root),
        "latest_run_dir": str(result.latest_run_dir) if result.latest_run_dir else None,
        "latest_run_id": result.latest_run_id,
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "message": check.message,
            }
            for check in result.checks
        ],
    }


def release_check_json(result: ReleaseReadinessResult) -> str:
    """Return pretty deterministic JSON for release readiness."""
    return json.dumps(release_check_json_payload(result), indent=2, sort_keys=True)


def release_check_markdown(result: ReleaseReadinessResult) -> str:
    """Render a human-readable Markdown release readiness summary."""
    lines = [
        "# VibeBench Release Check",
        "",
        f"- Project root: `{escape_markdown(result.project_root)}`",
        f"- Status: `{escape_markdown(result.status)}`",
        f"- Latest run: `{escape_markdown(result.latest_run_id or 'none')}`",
        "",
        "| Check | Status | Message |",
        "| --- | --- | --- |",
    ]
    for check in result.checks:
        lines.append(
            "| "
            f"{escape_markdown(check.name)} | "
            f"{escape_markdown(check.status)} | "
            f"{escape_markdown(check.message)} |"
        )
    return "\n".join(lines) + "\n"


def write_release_check_json(
    result: ReleaseReadinessResult,
    output_path: Path,
) -> Path:
    """Write release readiness JSON to a selected path."""
    validate_output_path(output_path)
    output_path.write_text(release_check_json(result) + "\n", encoding="utf-8")
    return output_path


def write_release_check_summary(
    result: ReleaseReadinessResult,
    output_path: Path,
) -> Path:
    """Write release readiness Markdown to a selected path."""
    validate_output_path(output_path)
    output_path.write_text(release_check_markdown(result), encoding="utf-8")
    return output_path


def validate_output_path(output_path: Path) -> None:
    """Validate a requested release check artifact output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"Output path is a directory: {output_path}")
    if not output_path.parent.exists():
        message = f"Output parent directory does not exist: {output_path.parent}"
        raise ReportError(message)


def escape_markdown(value: object) -> str:
    """Escape Markdown table-sensitive characters."""
    return str(value).replace("|", "\\|").replace("\n", " ")
