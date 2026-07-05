"""Local release audit artifact generation for VibeBench projects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, LargeZipFile, ZipFile, ZipInfo

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
RELEASE_AUDIT_ARCHIVE = "release-audit.zip"
RELEASE_AUDIT_REQUIRED_FILES = [
    "package-check.json",
    "package-check.md",
    "publish-check.json",
    "publish-check.md",
    "release-checklist.json",
    "release-checklist.md",
    RELEASE_AUDIT_JSON,
    RELEASE_AUDIT_SUMMARY,
]
RELEASE_AUDIT_JSON_FILES = [
    "package-check.json",
    "publish-check.json",
    "release-checklist.json",
    RELEASE_AUDIT_JSON,
]
RELEASE_AUDIT_MARKDOWN_FILES = [
    "package-check.md",
    "publish-check.md",
    "release-checklist.md",
    RELEASE_AUDIT_SUMMARY,
]
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
class ReleaseAuditArchive:
    """Release audit archive metadata."""

    requested: bool
    path: Path | None
    included_files: list[str]
    status: str


@dataclass(frozen=True)
class ReleaseAuditVerifyCheck:
    """One release audit verification check."""

    name: str
    status: str
    message: str


@dataclass(frozen=True)
class ReleaseAuditVerifyResult:
    """Release audit verification result."""

    target: Path
    target_type: str
    status: str
    checks: list[ReleaseAuditVerifyCheck]
    required_files: list[str]


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
    archive: ReleaseAuditArchive


def create_release_audit(
    project_root: Path,
    *,
    output_dir: Path | None = None,
    version: str | None = None,
    create_zip: bool = False,
    zip_output_path: Path | None = None,
    release_checklist_payload: dict[str, object],
) -> ReleaseAuditResult:
    """Create a local release audit directory and artifacts."""
    root = project_root.resolve()
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    selected_output_dir = resolve_output_dir(root, output_dir, generated_at)
    prepare_output_dir(selected_output_dir, create_parent=output_dir is None)
    archive_requested = create_zip or zip_output_path is not None
    selected_zip_path = resolve_zip_output_path(
        root,
        selected_output_dir,
        zip_output_path,
    )
    if archive_requested:
        prepare_zip_output_path(selected_zip_path)

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
    included_archive_files = sorted(RELEASE_AUDIT_REQUIRED_FILES)
    archive = ReleaseAuditArchive(
        requested=archive_requested,
        path=selected_zip_path if archive_requested else None,
        included_files=included_archive_files if archive_requested else [],
        status="created" if archive_requested else "not_requested",
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
        archive=archive,
    )
    write_release_audit_json(
        result,
        selected_output_dir / RELEASE_AUDIT_JSON,
    )
    write_release_audit_summary(
        result,
        selected_output_dir / RELEASE_AUDIT_SUMMARY,
    )
    if archive_requested:
        write_release_audit_archive(selected_zip_path, generated_files)
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


def resolve_zip_output_path(
    project_root: Path,
    output_dir: Path,
    zip_output_path: Path | None,
) -> Path:
    """Resolve the requested release audit zip path."""
    if zip_output_path is None:
        return output_dir / RELEASE_AUDIT_ARCHIVE
    if zip_output_path.is_absolute():
        return zip_output_path.resolve()
    return (project_root / zip_output_path).resolve()


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


def prepare_zip_output_path(output_path: Path) -> None:
    """Validate the requested zip output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(
            f"Release-audit zip output path is a directory: {output_path}"
        )
    if output_path.exists():
        raise ReportError(f"Release-audit zip output already exists: {output_path}")
    if not output_path.parent.exists():
        raise ReportError(
            f"Release-audit zip output parent does not exist: {output_path.parent}"
        )


def verify_release_audit(target: Path) -> ReleaseAuditVerifyResult:
    """Verify a release audit directory or zip archive."""
    selected_target = target.resolve()
    checks: list[ReleaseAuditVerifyCheck] = []
    if not selected_target.exists():
        checks.append(failed_check("target_exists", f"Path does not exist: {target}"))
        return release_audit_verify_result(selected_target, "unknown", checks)
    if selected_target.is_dir():
        verify_release_audit_directory(selected_target, checks)
        return release_audit_verify_result(selected_target, "directory", checks)
    if selected_target.is_file() and selected_target.suffix.lower() == ".zip":
        verify_release_audit_zip(selected_target, checks)
        return release_audit_verify_result(selected_target, "zip", checks)
    checks.append(
        failed_check(
            "target_type",
            f"Path is neither a release audit directory nor a .zip file: {target}",
        )
    )
    return release_audit_verify_result(selected_target, "unknown", checks)


def verify_release_audit_directory(
    target: Path,
    checks: list[ReleaseAuditVerifyCheck],
) -> None:
    """Verify a release audit directory."""
    for name in RELEASE_AUDIT_REQUIRED_FILES:
        file_path = target / name
        if file_path.is_file():
            checks.append(passed_check(f"required_file:{name}", f"Found {name}"))
        else:
            checks.append(failed_check(f"required_file:{name}", f"Missing {name}"))
    for name in RELEASE_AUDIT_JSON_FILES:
        file_path = target / name
        if file_path.is_file():
            verify_json_bytes(name, file_path.read_bytes(), checks)
    for name in RELEASE_AUDIT_MARKDOWN_FILES:
        file_path = target / name
        if file_path.is_file():
            verify_markdown_bytes(name, file_path.read_bytes(), checks)


def verify_release_audit_zip(
    target: Path,
    checks: list[ReleaseAuditVerifyCheck],
) -> None:
    """Verify a release audit zip without extracting it."""
    try:
        with ZipFile(target) as archive:
            names = archive.namelist()
            file_names = {name for name in names if not name.endswith("/")}
            verify_zip_entry_safety(names, checks)
            for name in RELEASE_AUDIT_REQUIRED_FILES:
                if name in file_names:
                    checks.append(
                        passed_check(f"required_file:{name}", f"Found {name}")
                    )
                else:
                    checks.append(
                        failed_check(f"required_file:{name}", f"Missing {name}")
                    )
            for name in RELEASE_AUDIT_JSON_FILES:
                if name in file_names:
                    verify_json_bytes(name, archive.read(name), checks)
            for name in RELEASE_AUDIT_MARKDOWN_FILES:
                if name in file_names:
                    verify_markdown_bytes(name, archive.read(name), checks)
    except (OSError, BadZipFile, LargeZipFile) as exc:
        checks.append(failed_check("zip_read", f"Unable to read zip archive: {exc}"))


def verify_zip_entry_safety(
    names: list[str],
    checks: list[ReleaseAuditVerifyCheck],
) -> None:
    """Verify zip entries are safe relative names."""
    unsafe_entries = sorted(name for name in names if is_unsafe_zip_entry(name))
    if unsafe_entries:
        checks.append(
            failed_check(
                "zip_safety",
                f"Unsafe zip entries: {', '.join(unsafe_entries)}",
            )
        )
    else:
        checks.append(passed_check("zip_safety", "Zip entries are safe"))


def is_unsafe_zip_entry(name: str) -> bool:
    """Return whether a zip entry name is unsafe."""
    return not name or name.startswith("/") or ".." in Path(name).parts


def verify_json_bytes(
    name: str,
    content: bytes,
    checks: list[ReleaseAuditVerifyCheck],
) -> None:
    """Verify JSON bytes parse successfully."""
    try:
        json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        checks.append(failed_check(f"json:{name}", f"Invalid JSON in {name}: {exc}"))
    else:
        checks.append(passed_check(f"json:{name}", f"Valid JSON in {name}"))


def verify_markdown_bytes(
    name: str,
    content: bytes,
    checks: list[ReleaseAuditVerifyCheck],
) -> None:
    """Verify Markdown bytes are non-empty text."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        checks.append(
            failed_check(f"markdown:{name}", f"Invalid UTF-8 in {name}: {exc}")
        )
        return
    if text.strip():
        checks.append(passed_check(f"markdown:{name}", f"Non-empty Markdown in {name}"))
    else:
        checks.append(failed_check(f"markdown:{name}", f"Empty Markdown in {name}"))


def release_audit_verify_result(
    target: Path,
    target_type: str,
    checks: list[ReleaseAuditVerifyCheck],
) -> ReleaseAuditVerifyResult:
    """Build a verification result from checks."""
    status = "failed" if any(check.status == "failed" for check in checks) else "passed"
    return ReleaseAuditVerifyResult(
        target=target,
        target_type=target_type,
        status=status,
        checks=checks,
        required_files=list(RELEASE_AUDIT_REQUIRED_FILES),
    )


def passed_check(name: str, message: str) -> ReleaseAuditVerifyCheck:
    """Build a passed verification check."""
    return ReleaseAuditVerifyCheck(name=name, status="passed", message=message)


def failed_check(name: str, message: str) -> ReleaseAuditVerifyCheck:
    """Build a failed verification check."""
    return ReleaseAuditVerifyCheck(name=name, status="failed", message=message)


def release_audit_verify_json_payload(
    result: ReleaseAuditVerifyResult,
) -> dict[str, object]:
    """Return a JSON-safe release audit verification payload."""
    return {
        "checks": [
            {"name": check.name, "status": check.status, "message": check.message}
            for check in result.checks
        ],
        "required_files": result.required_files,
        "status": result.status,
        "target": str(result.target),
        "target_type": result.target_type,
    }


def release_audit_verify_json(result: ReleaseAuditVerifyResult) -> str:
    """Return deterministic JSON for release audit verification."""
    return json.dumps(
        release_audit_verify_json_payload(result),
        indent=2,
        sort_keys=True,
    )


def release_audit_json_payload(result: ReleaseAuditResult) -> dict[str, object]:
    """Return a JSON-safe release audit payload."""
    archive_path = None
    if result.archive.path is not None:
        archive_path = str(result.archive.path)
    return {
        "archive": {
            "included_files": result.archive.included_files,
            "path": archive_path,
            "requested": result.archive.requested,
            "status": result.archive.status,
        },
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


def write_release_audit_archive(
    output_path: Path,
    generated_files: list[ReleaseAuditFile],
) -> Path:
    """Write a zip archive containing only generated release audit files."""
    files_by_name = {item.name: item.path for item in generated_files}
    try:
        with ZipFile(output_path, mode="x") as archive:
            for name in sorted(files_by_name):
                zip_info = ZipInfo(name)
                zip_info.date_time = (1980, 1, 1, 0, 0, 0)
                zip_info.compress_type = ZIP_DEFLATED
                zip_info.external_attr = 0o100644 << 16
                archive.writestr(zip_info, files_by_name[name].read_bytes())
    except (OSError, BadZipFile, LargeZipFile) as exc:
        raise ReportError(f"Failed to create release-audit zip: {exc}") from exc
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
            "## Archive",
            "",
        ]
    )
    if result.archive.requested:
        lines.extend(
            [
                f"- Status: `{markdown_cell(result.archive.status)}`",
                f"- Path: `{markdown_cell(result.archive.path)}`",
                "",
                "| Included file |",
                "| --- |",
            ]
        )
        lines.extend(
            f"| {markdown_cell(name)} |" for name in result.archive.included_files
        )
        lines.append("")
    else:
        lines.extend(["- Not requested.", ""])
    lines.extend(
        [
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
