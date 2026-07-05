"""Local GitHub Release body export for VibeBench releases."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from vibebench.report import ReportError

STALE_RELEASE_BODY_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"Release Candidate",
        r"not been tagged",
        r"must not create the v[0-9]+\.[0-9]+\.[0-9]+ tag",
        r"must not create a GitHub Release",
        r"must not create.*GitHub Release",
    ]
]


@dataclass(frozen=True)
class ReleaseBodyCheck:
    """One release body validation check."""

    name: str
    status: str
    message: str


@dataclass(frozen=True)
class ReleaseBodyResult:
    """Release body export result."""

    version: str
    source_path: Path
    output_path: Path | None
    body: str | None
    checks: list[ReleaseBodyCheck]
    status: str


def export_release_body(
    project_root: Path,
    *,
    version: str,
    output_path: Path | None = None,
) -> ReleaseBodyResult:
    """Load and optionally write a local GitHub Release body."""
    normalized_version = normalize_release_version(version)
    source_path = project_root / f"RELEASE_NOTES_{normalized_version}.md"
    if not source_path.is_file():
        raise ReportError(f"Release notes file not found: {source_path}")
    body = source_path.read_text(encoding="utf-8")
    checks = validate_release_body(body, normalized_version)
    if output_path is not None:
        write_release_body(body, output_path)
    return ReleaseBodyResult(
        version=normalized_version,
        source_path=source_path,
        output_path=output_path,
        body=body,
        checks=checks,
        status=release_body_status(checks),
    )


def normalize_release_version(version: str) -> str:
    """Normalize a release version to vX.Y.Z."""
    value = version.strip()
    if not value:
        raise ReportError("Release version is required.")
    if not value.startswith("v"):
        value = f"v{value}"
    return value


def validate_release_body(body: str, version: str) -> list[ReleaseBodyCheck]:
    """Validate a release body for stale pre-release wording."""
    checks = [
        passed_check("body_non_empty", "Release body is not empty")
        if body.strip()
        else failed_check("body_non_empty", "Release body is empty")
    ]
    stale_matches = []
    for pattern in STALE_RELEASE_BODY_PATTERNS:
        if pattern.search(body):
            stale_matches.append(pattern.pattern)
    if stale_matches:
        checks.append(
            failed_check(
                "stale_release_candidate_wording",
                f"Release body for {version} contains stale release-candidate wording.",
            )
        )
    else:
        checks.append(
            passed_check(
                "stale_release_candidate_wording",
                f"Release body for {version} has no stale release-candidate wording.",
            )
        )
    return checks


def write_release_body(body: str, output_path: Path) -> Path:
    """Write a release body Markdown file."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"Release body output path is a directory: {output_path}")
    if not output_path.parent.exists():
        raise ReportError(
            f"Release body output parent does not exist: {output_path.parent}"
        )
    output_path.write_text(ensure_trailing_newline(body), encoding="utf-8")
    return output_path


def release_body_status(checks: list[ReleaseBodyCheck]) -> str:
    """Return passed or failed for validation checks."""
    if any(check.status == "failed" for check in checks):
        return "failed"
    return "passed"


def release_body_json(result: ReleaseBodyResult) -> str:
    """Return deterministic JSON for release body export."""
    return json.dumps(release_body_json_payload(result), indent=2, sort_keys=True)


def release_body_json_payload(result: ReleaseBodyResult) -> dict[str, object]:
    """Return a JSON-safe release body payload."""
    return {
        "body": result.body,
        "checks": [
            {"name": check.name, "status": check.status, "message": check.message}
            for check in result.checks
        ],
        "output_path": str(result.output_path) if result.output_path else None,
        "source_path": str(result.source_path),
        "status": result.status,
        "version": result.version,
    }


def ensure_trailing_newline(content: str) -> str:
    """Ensure Markdown content ends with a newline."""
    if content.endswith("\n"):
        return content
    return f"{content}\n"


def passed_check(name: str, message: str) -> ReleaseBodyCheck:
    """Build a passed check."""
    return ReleaseBodyCheck(name=name, status="passed", message=message)


def failed_check(name: str, message: str) -> ReleaseBodyCheck:
    """Build a failed check."""
    return ReleaseBodyCheck(name=name, status="failed", message=message)
