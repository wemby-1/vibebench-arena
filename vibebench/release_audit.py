"""Local release audit artifact generation for VibeBench projects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from vibebench.package_check import (
    run_package_check,
    write_package_check_json,
    write_package_check_summary,
)
from vibebench.publish_check import (
    run_publish_check,
    write_publish_check_json,
    write_publish_check_summary,
)
from vibebench.report import ReportError

RELEASE_AUDIT_JSON = "release-audit.json"
RELEASE_AUDIT_SUMMARY = "release-audit.md"
SAFETY_NOTES = [
    "No tag is created.",
    "No GitHub Release is created.",
    "No package publish or upload is performed.",
    "No version bump is performed.",
]


@dataclass(frozen=True)
class ReleaseAuditFile:
    """One generated release audit file."""

    name: str
    path: Path
    kind: str


@dataclass(frozen=True)
class ReleaseAuditResult:
    """Complete release audit result."""

    project_root: Path
    output_dir: Path
    version: str
    generated_at: str
    status: str
    files: list[ReleaseAuditFile]
    package_status: str
    publish_status: str
    release_checklist_status: str


def create_release_audit(
    project_root: Path,
    *,
    output_dir: Path | None = None,
    version: str | None = None,
    release_checklist_payload: dict[str, object],
) -> ReleaseAuditResult:
    """Create a local release audit directory and artifacts."""
    root = project_root.resolve()
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    selected_output_dir = resolve_output_dir(root, output_dir, generated_at)
    prepare_output_dir(selected_output_dir, create_parent=output_dir is None)

    package_result = run_package_check(root, advice=True, build=True)
    publish_result = run_publish_check(root, advice=True)
    selected_version = (
        version
        or value_as_str(release_checklist_payload.get("target_version"))
        or value_as_str(release_checklist_payload.get("package_version"))
        or "unknown"
    )

    generated_files: list[ReleaseAuditFile] = []
    generated_files.append(
        generated_file(
            "package-check.json",
            write_package_check_json(
                package_result,
                selected_output_dir / "package-check.json",
            ),
            "json",
        )
    )
    generated_files.append(
        generated_file(
            "package-check.md",
            write_package_check_summary(
                package_result,
                selected_output_dir / "package-check.md",
            ),
            "markdown",
        )
    )
    generated_files.append(
        generated_file(
            "publish-check.json",
            write_publish_check_json(
                publish_result,
                selected_output_dir / "publish-check.json",
            ),
            "json",
        )
    )
    generated_files.append(
        generated_file(
            "publish-check.md",
            write_publish_check_summary(
                publish_result,
                selected_output_dir / "publish-check.md",
            ),
            "markdown",
        )
    )
    generated_files.append(
        generated_file(
            "release-checklist.json",
            write_json_payload(
                release_checklist_payload,
                selected_output_dir / "release-checklist.json",
            ),
            "json",
        )
    )
    generated_files.append(
        generated_file(
            "release-checklist.md",
            write_text(
                render_release_checklist_markdown(release_checklist_payload),
                selected_output_dir / "release-checklist.md",
            ),
            "markdown",
        )
    )

    generated_files.append(
        generated_file(
            RELEASE_AUDIT_JSON,
            selected_output_dir / RELEASE_AUDIT_JSON,
            "json",
        )
    )
    generated_files.append(
        generated_file(
            RELEASE_AUDIT_SUMMARY,
            selected_output_dir / RELEASE_AUDIT_SUMMARY,
            "markdown",
        )
    )

    result = ReleaseAuditResult(
        project_root=root,
        output_dir=selected_output_dir,
        version=selected_version,
        generated_at=generated_at,
        status=overall_status(
            package_result.status,
            publish_result.overall_status,
            value_as_str(release_checklist_payload.get("overall_status")) or "unknown",
        ),
        files=generated_files,
        package_status=package_result.status,
        publish_status=publish_result.overall_status,
        release_checklist_status=(
            value_as_str(release_checklist_payload.get("overall_status")) or "unknown"
        ),
    )
    write_release_audit_json(
        result,
        selected_output_dir / RELEASE_AUDIT_JSON,
    )
    write_release_audit_summary(
        result,
        selected_output_dir / RELEASE_AUDIT_SUMMARY,
    )
    return result

def resolve_output_dir(
    project_root: Path,
    output_dir: Path | None,
    generated_at: str,
) -> Path:
    """Resolve the selected audit output directory."""
    if output_dir is not None:
        if output_dir.is_absolute():
            return output_dir.resolve()
        return (project_root / output_dir).resolve()
    stamp = generated_at.replace("-", "").replace(":", "").replace("+00:00", "Z")
    return (project_root / ".vibebench" / "release-audits" / stamp).resolve()


def prepare_output_dir(output_dir: Path, *, create_parent: bool = False) -> None:
    """Create or validate the audit output directory."""
    if output_dir.exists() and output_dir.is_file():
        raise ReportError(f"Release-audit output path is a file: {output_dir}")
    if output_dir.exists():
        raise ReportError(
            f"Release-audit output directory already exists: {output_dir}"
        )
    if create_parent:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
    if not output_dir.parent.exists():
        raise ReportError(
            f"Release-audit output parent does not exist: {output_dir.parent}"
        )
    output_dir.mkdir()


def release_audit_json_payload(result: ReleaseAuditResult) -> dict[str, object]:
    """Return a JSON-safe release audit payload."""
    return {
        "generated_at": result.generated_at,
        "generated_files": [
            {"name": item.name, "path": str(item.path), "kind": item.kind}
            for item in result.files
        ],
        "output_dir": str(result.output_dir),
        "project_root": str(result.project_root),
        "safety_notes": SAFETY_NOTES,
        "status": result.status,
        "summary": {
            "package_check": result.package_status,
            "publish_check": result.publish_status,
            "release_checklist": result.release_checklist_status,
        },
        "version": result.version,
    }


def release_audit_json(result: ReleaseAuditResult) -> str:
    """Return deterministic JSON for a release audit result."""
    return json.dumps(release_audit_json_payload(result), indent=2, sort_keys=True)


def write_release_audit_json(result: ReleaseAuditResult, output_path: Path) -> Path:
    """Write release audit JSON."""
    output_path.write_text(release_audit_json(result) + "\n", encoding="utf-8")
    return output_path


def write_release_audit_summary(result: ReleaseAuditResult, output_path: Path) -> Path:
    """Write release audit Markdown."""
    output_path.write_text(render_release_audit_markdown(result), encoding="utf-8")
    return output_path


def render_release_audit_markdown(result: ReleaseAuditResult) -> str:
    """Render a concise release audit Markdown summary."""
    lines = [
        "# VibeBench Release Audit",
        "",
        f"- Version: `{markdown_cell(result.version)}`",
        f"- Generated at: `{markdown_cell(result.generated_at)}`",
        f"- Output directory: `{markdown_cell(result.output_dir)}`",
        f"- Status: `{markdown_cell(result.status)}`",
        "",
        "## Generated Files",
        "",
        "| File | Kind | Path |",
        "| --- | --- | --- |",
    ]
    for item in result.files:
        lines.append(
            "| "
            f"{markdown_cell(item.name)} | "
            f"{markdown_cell(item.kind)} | "
            f"{markdown_cell(item.path)} |"
        )
    lines.extend(
        [
            "",
            "## Status Summary",
            "",
            "| Check | Status |",
            "| --- | --- |",
            f"| Package check | {markdown_cell(result.package_status)} |",
            f"| Publish check | {markdown_cell(result.publish_status)} |",
            f"| Release checklist | {markdown_cell(result.release_checklist_status)} |",
            "",
            "## Safety Notes",
            "",
        ]
    )
    lines.extend(f"- {note}" for note in SAFETY_NOTES)
    lines.append("")
    return "\n".join(lines)


def render_release_checklist_markdown(payload: dict[str, object]) -> str:
    """Render release checklist Markdown for the audit folder."""
    lines = [
        "# VibeBench Release Checklist",
        "",
        f"- Version: `{markdown_cell(payload.get('target_version', 'unknown'))}`",
        (
            "- Overall status: "
            f"`{markdown_cell(payload.get('overall_status', 'unknown'))}`"
        ),
        "",
        "| Item | Status | Message |",
        "| --- | --- | --- |",
    ]
    checks = payload.get("checks", [])
    if isinstance(checks, list):
        for check in checks:
            if isinstance(check, dict):
                lines.append(
                    "| "
                    f"{markdown_cell(check.get('name', ''))} | "
                    f"{markdown_cell(check.get('status', ''))} | "
                    f"{markdown_cell(check.get('message', ''))} |"
                )
    lines.extend(["", "## Safety Note", ""])
    lines.extend(f"- {note}" for note in SAFETY_NOTES)
    lines.append("")
    return "\n".join(lines)


def write_json_payload(payload: dict[str, object], output_path: Path) -> Path:
    """Write a deterministic JSON payload."""
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_text(content: str, output_path: Path) -> Path:
    """Write text content."""
    output_path.write_text(content, encoding="utf-8")
    return output_path


def generated_file(name: str, path: Path, kind: str) -> ReleaseAuditFile:
    """Build one generated file entry."""
    return ReleaseAuditFile(name=name, path=path, kind=kind)


def overall_status(
    package_status: str,
    publish_status: str,
    checklist_status: str,
) -> str:
    """Summarize audit status."""
    statuses = {package_status, publish_status, checklist_status}
    if "failed" in statuses or "not-ready" in statuses:
        return "failed"
    if "warning" in statuses or "unknown" in statuses:
        return "warning"
    return "ready"


def value_as_str(value: object) -> str | None:
    """Return a non-empty string value."""
    if isinstance(value, str) and value.strip():
        return value
    return None


def markdown_cell(value: object) -> str:
    """Escape Markdown table-sensitive content."""
    return str(value).replace("|", "\\|").replace("\n", " ")
