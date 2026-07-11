"""Deterministic v0.4.0 release-candidate evidence bundle."""

from __future__ import annotations

import filecmp
import hashlib
import json
import subprocess
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import yaml

from vibebench import __version__
from vibebench.release_check import (
    RELEASE_CANDIDATE_JSON,
    RELEASE_CANDIDATE_SUMMARY,
    TARGET_RELEASE_VERSION,
    ReleaseCandidateResult,
    release_candidate_json,
    release_candidate_markdown,
    run_release_candidate_check,
)
from vibebench.report import ReportError

RELEASE_BUNDLE_DIR = Path(".vibebench") / "release-candidates" / "v0.4.0"
RELEASE_BUNDLE_ARCHIVE = "release-candidate-bundle.zip"
RELEASE_PROVENANCE_JSON = "release-provenance.json"
RELEASE_WORKFLOW_VERIFICATION_JSON = "workflow-verification.json"
RELEASE_CHECKSUMS = "release-checksums.sha256"
CHECKSUM_ALGORITHM = "sha256"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZIP_FILE_MODE = 0o100644 << 16

SUPPORTING_FILES = [
    Path("RELEASE_NOTES_v0.4.0.md"),
    Path("docs") / "release-checklist-v0.4.0.md",
    Path("docs") / "github-action.md",
    Path("docs") / "marketplace-readiness.md",
    Path("action.yml"),
    Path("pyproject.toml"),
    Path("vibebench") / "__init__.py",
]

CORE_PAYLOAD_FILES = [
    Path(RELEASE_CANDIDATE_JSON),
    Path(RELEASE_CANDIDATE_SUMMARY),
    Path(RELEASE_WORKFLOW_VERIFICATION_JSON),
    Path(RELEASE_PROVENANCE_JSON),
]

CHECKSUM_PAYLOAD_FILES = [*CORE_PAYLOAD_FILES, *SUPPORTING_FILES]
ARCHIVE_PAYLOAD_FILES = [*CHECKSUM_PAYLOAD_FILES, Path(RELEASE_CHECKSUMS)]
OUTPUT_FILES = [*ARCHIVE_PAYLOAD_FILES, Path(RELEASE_BUNDLE_ARCHIVE)]

ReleaseBundleStatus = Literal["passed", "failed"]


@dataclass(frozen=True)
class ReleaseBundleCheck:
    """One release-bundle check result."""

    name: str
    status: ReleaseBundleStatus
    message: str


@dataclass(frozen=True)
class ReleaseBundleResult:
    """Release-candidate bundle command result."""

    project_root: Path
    output_dir: Path
    archive_path: Path
    target_version: str
    candidate: bool
    released: bool
    status: ReleaseBundleStatus
    checked: bool
    deterministic: bool
    files: list[str]
    archive_sha256: str | None
    checksums_valid: bool
    source_commit: str | None
    checks: list[ReleaseBundleCheck]


def build_release_candidate_bundle(
    project_root: Path,
    *,
    output_dir: Path | None = None,
    archive_output: Path | None = None,
    check: bool = False,
) -> ReleaseBundleResult:
    """Build or check the deterministic v0.4.0 candidate evidence bundle."""
    root = project_root.resolve()
    selected_output = (output_dir or root / RELEASE_BUNDLE_DIR).resolve()
    selected_archive = (
        archive_output.resolve()
        if archive_output is not None
        else selected_output / RELEASE_BUNDLE_ARCHIVE
    )
    if check:
        return check_release_candidate_bundle(
            root,
            selected_output,
            selected_archive,
        )

    validate_output_locations(selected_output, selected_archive)
    candidate = run_release_candidate_check(root)
    write_bundle_files(root, selected_output, selected_archive, candidate)
    return inspect_written_bundle(
        root,
        selected_output,
        selected_archive,
        checked=False,
    )


def check_release_candidate_bundle(
    project_root: Path,
    output_dir: Path,
    archive_path: Path,
) -> ReleaseBundleResult:
    """Check an existing bundle against a freshly generated temporary bundle."""
    checks: list[ReleaseBundleCheck] = []
    if not output_dir.exists():
        checks.append(
            failed("output_dir", f"Output directory is missing: {output_dir}")
        )
        return failed_result(project_root, output_dir, archive_path, checks)
    if not output_dir.is_dir():
        checks.append(
            failed("output_dir", f"Output path is not a directory: {output_dir}")
        )
        return failed_result(project_root, output_dir, archive_path, checks)

    with tempfile.TemporaryDirectory(prefix="vibebench-release-bundle-") as temp:
        expected_dir = Path(temp) / "candidate"
        expected_archive = expected_dir / RELEASE_BUNDLE_ARCHIVE
        candidate = run_release_candidate_check(project_root)
        write_bundle_files(project_root, expected_dir, expected_archive, candidate)
        checks.extend(compare_bundle_dirs(expected_dir, output_dir))
        checks.extend(compare_archive(expected_archive, archive_path))

    checks.extend(validate_existing_payload(output_dir, archive_path))
    status: ReleaseBundleStatus = (
        "passed" if all(check.status == "passed" for check in checks) else "failed"
    )
    inspected = inspect_written_bundle(
        project_root,
        output_dir,
        archive_path,
        checked=True,
        extra_checks=checks,
    )
    return ReleaseBundleResult(
        project_root=inspected.project_root,
        output_dir=inspected.output_dir,
        archive_path=inspected.archive_path,
        target_version=inspected.target_version,
        candidate=inspected.candidate,
        released=inspected.released,
        status=status,
        checked=True,
        deterministic=inspected.deterministic,
        files=inspected.files,
        archive_sha256=inspected.archive_sha256,
        checksums_valid=inspected.checksums_valid,
        source_commit=inspected.source_commit,
        checks=checks,
    )


def write_bundle_files(
    project_root: Path,
    output_dir: Path,
    archive_path: Path,
    result: ReleaseCandidateResult,
) -> None:
    """Write deterministic bundle files and archive."""
    validate_output_locations(output_dir, archive_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_text(output_dir / RELEASE_CANDIDATE_JSON, release_candidate_json(result))
    write_text(
        output_dir / RELEASE_CANDIDATE_SUMMARY,
        release_candidate_markdown(result),
    )
    write_json(
        output_dir / RELEASE_WORKFLOW_VERIFICATION_JSON,
        workflow_verification_payload(project_root),
    )
    write_supporting_files(project_root, output_dir)
    write_json(
        output_dir / RELEASE_PROVENANCE_JSON,
        provenance_payload(project_root, result),
    )
    write_text(output_dir / RELEASE_CHECKSUMS, checksum_manifest(output_dir))
    write_archive(output_dir, archive_path)


def workflow_verification_payload(project_root: Path) -> dict[str, object]:
    """Return structural workflow verification without remote run claims."""
    candidate_workflow = Path(".github") / "workflows" / "release-candidate.yml"
    action_smoke = Path(".github") / "workflows" / "action-smoke.yml"
    candidate_payload = read_yaml(project_root / candidate_workflow)
    smoke_payload = read_yaml(project_root / action_smoke)
    candidate_text = (project_root / candidate_workflow).read_text(encoding="utf-8")
    smoke_text = (project_root / action_smoke).read_text(encoding="utf-8")
    return {
        "schema_version": 1,
        "verification_type": "local_structural",
        "remote_hosted_status": "not_asserted",
        "candidate": True,
        "target_version": TARGET_RELEASE_VERSION,
        "released": False,
        "workflows": {
            candidate_workflow.as_posix(): {
                "exists": (project_root / candidate_workflow).is_file(),
                "permissions": candidate_payload.get("permissions"),
                "has_release_check_candidate": "release-check" in candidate_text
                and "--candidate" in candidate_text,
                "has_release_bundle_candidate": "release-bundle" in candidate_text
                and "--candidate" in candidate_text,
                "uploads_candidate_artifact": "vibebench-v0.4.0-release-candidate"
                in candidate_text,
                "forbidden_publication_commands": forbidden_publication_hits(
                    candidate_text
                ),
            },
            action_smoke.as_posix(): {
                "exists": (project_root / action_smoke).is_file(),
                "matrix_presets": smoke_payload.get("jobs", {})
                .get("action-smoke", {})
                .get("strategy", {})
                .get("matrix", {})
                .get("preset"),
                "forbidden_continue_on_error": "continue-on-error" in smoke_text,
            },
        },
    }


def provenance_payload(
    project_root: Path,
    result: ReleaseCandidateResult,
) -> dict[str, object]:
    """Return deterministic, portable release-candidate provenance."""
    pyproject = read_toml(project_root / "pyproject.toml")
    project = pyproject.get("project") if isinstance(pyproject, dict) else {}
    project = project if isinstance(project, dict) else {}
    package_version = str(project.get("version", ""))
    init_version = __version__
    source_commit = git_output(project_root, ["rev-parse", "HEAD"])
    return {
        "schema_version": 1,
        "project": str(project.get("name", "")),
        "package_version": package_version,
        "init_version": init_version,
        "target_version": result.target_version,
        "candidate": True,
        "released": result.released,
        "candidate_status": result.status,
        "source_commit": source_commit,
        "source_tree": git_tree_state(project_root),
        "package_metadata": {
            "pyproject_version": package_version,
            "init_version": init_version,
            "consistent": package_version == init_version == result.target_version,
        },
        "action_metadata": action_metadata(project_root),
        "workflow_paths": [
            ".github/workflows/release-candidate.yml",
            ".github/workflows/action-smoke.yml",
        ],
        "included_bundle_files": [path.as_posix() for path in ARCHIVE_PAYLOAD_FILES],
        "deterministic_build_policy": {
            "json": "sort_keys=True, indent=2, trailing_newline=True",
            "markdown": "derived from release-check candidate result",
            "checksums": "sha256 over sorted POSIX relative payload paths",
            "zip": "sorted members, timestamp 1980-01-01T00:00:00Z, mode 0644",
            "excluded_from_checksums": [
                RELEASE_CHECKSUMS,
                RELEASE_BUNDLE_ARCHIVE,
            ],
        },
        "archive_format": "zip",
        "archive_name": RELEASE_BUNDLE_ARCHIVE,
        "checksum_algorithm": CHECKSUM_ALGORITHM,
    }


def action_metadata(project_root: Path) -> dict[str, object]:
    """Return deterministic action metadata consistency evidence."""
    payload = read_yaml(project_root / "action.yml")
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    branding = (
        payload.get("branding") if isinstance(payload.get("branding"), dict) else {}
    )
    return {
        "name": payload.get("name"),
        "description_present": bool(payload.get("description")),
        "author_present": bool(payload.get("author")),
        "branding_icon": branding.get("icon"),
        "branding_color": branding.get("color"),
        "inputs": sorted(inputs),
        "outputs": sorted(outputs),
        "consistent": bool(payload.get("name"))
        and bool(payload.get("description"))
        and bool(payload.get("author"))
        and bool(branding.get("icon"))
        and bool(branding.get("color")),
    }


def write_supporting_files(project_root: Path, output_dir: Path) -> None:
    """Copy allowlisted supporting files into the bundle directory."""
    for relative in SUPPORTING_FILES:
        source = project_root / relative
        if not source.is_file() or source.is_symlink():
            raise ReportError(f"Required bundle source file is missing: {relative}")
        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())


def checksum_manifest(output_dir: Path) -> str:
    """Return a deterministic checksum manifest for payload files."""
    lines = []
    for relative in sorted(CHECKSUM_PAYLOAD_FILES, key=lambda item: item.as_posix()):
        digest = sha256_file(output_dir / relative)
        lines.append(f"{digest}  {relative.as_posix()}")
    return "\n".join(lines)


def write_archive(output_dir: Path, archive_path: Path) -> None:
    """Write a deterministic release-candidate ZIP archive."""
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for relative in sorted(ARCHIVE_PAYLOAD_FILES, key=lambda item: item.as_posix()):
            validate_relative_path(relative.as_posix())
            info = zipfile.ZipInfo(relative.as_posix(), ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ZIP_FILE_MODE
            archive.writestr(info, (output_dir / relative).read_bytes())


def inspect_written_bundle(
    project_root: Path,
    output_dir: Path,
    archive_path: Path,
    *,
    checked: bool,
    extra_checks: list[ReleaseBundleCheck] | None = None,
) -> ReleaseBundleResult:
    """Inspect a written bundle and return command payload data."""
    checks = list(extra_checks or [])
    checks.extend(validate_existing_payload(output_dir, archive_path))
    status: ReleaseBundleStatus = (
        "passed" if all(check.status == "passed" for check in checks) else "failed"
    )
    archive_sha = sha256_file(archive_path) if archive_path.is_file() else None
    candidate_payload = read_json_or_none(output_dir / RELEASE_CANDIDATE_JSON) or {}
    provenance = read_json_or_none(output_dir / RELEASE_PROVENANCE_JSON) or {}
    return ReleaseBundleResult(
        project_root=project_root,
        output_dir=output_dir,
        archive_path=archive_path,
        target_version=str(
            candidate_payload.get("target_version", TARGET_RELEASE_VERSION)
        ),
        candidate=candidate_payload.get("candidate") is True,
        released=candidate_payload.get("released") is True,
        status=status,
        checked=checked,
        deterministic=True,
        files=[path.as_posix() for path in OUTPUT_FILES],
        archive_sha256=archive_sha,
        checksums_valid=verify_checksums(output_dir),
        source_commit=provenance.get("source_commit")
        if isinstance(provenance.get("source_commit"), str)
        else None,
        checks=checks or [passed("bundle", "Release-candidate bundle is current.")],
    )


def validate_existing_payload(
    output_dir: Path,
    archive_path: Path,
) -> list[ReleaseBundleCheck]:
    """Validate required files, JSON, checksums, and archive structure."""
    checks: list[ReleaseBundleCheck] = []
    for relative in OUTPUT_FILES:
        path = (
            archive_path
            if relative == Path(RELEASE_BUNDLE_ARCHIVE)
            else output_dir / relative
        )
        checks.append(
            passed(relative.as_posix(), "Required file exists.")
            if path.is_file() and not path.is_symlink()
            else failed(relative.as_posix(), "Required file is missing.")
        )
    checks.extend(validate_json_payloads(output_dir))
    checks.append(
        passed("checksums", "Checksum manifest is valid.")
        if verify_checksums(output_dir)
        else failed("checksums", "Checksum manifest is invalid.")
    )
    checks.extend(validate_archive(archive_path))
    return checks


def validate_json_payloads(output_dir: Path) -> list[ReleaseBundleCheck]:
    """Validate bundle JSON files and candidate fields."""
    checks: list[ReleaseBundleCheck] = []
    for relative in [
        Path(RELEASE_CANDIDATE_JSON),
        Path(RELEASE_WORKFLOW_VERIFICATION_JSON),
        Path(RELEASE_PROVENANCE_JSON),
    ]:
        try:
            payload = json.loads((output_dir / relative).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            checks.append(failed(relative.as_posix(), f"JSON is malformed: {exc}"))
            continue
        checks.append(passed(relative.as_posix(), "JSON parses."))
        if relative == Path(RELEASE_CANDIDATE_JSON):
            checks.extend(validate_candidate_payload(payload))
    return checks


def validate_candidate_payload(payload: dict[str, object]) -> list[ReleaseBundleCheck]:
    """Validate candidate JSON identity fields."""
    expectations = {
        "candidate": True,
        "target_version": TARGET_RELEASE_VERSION,
        "released": False,
        "status": "passed",
    }
    checks = []
    for key, expected in expectations.items():
        actual = payload.get(key)
        checks.append(
            passed(f"candidate.{key}", f"{key} matches expected value.")
            if actual == expected
            else failed(
                f"candidate.{key}",
                f"{key} mismatch: expected {expected!r}, found {actual!r}.",
            )
        )
    return checks


def validate_archive(archive_path: Path) -> list[ReleaseBundleCheck]:
    """Validate archive member safety and allowlist."""
    if not archive_path.is_file():
        return [failed("archive", "Archive is missing.")]
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            expected = [
                path.as_posix()
                for path in sorted(
                    ARCHIVE_PAYLOAD_FILES,
                    key=lambda item: item.as_posix(),
                )
            ]
            checks = [
                passed("archive.opens", "Archive opens."),
                passed("archive.members", "Archive members match allowlist.")
                if names == expected
                else failed(
                    "archive.members",
                    "Archive members differ from allowlist.",
                ),
            ]
            if len(names) != len(set(names)):
                checks.append(
                    failed("archive.duplicates", "Archive has duplicate members.")
                )
            else:
                checks.append(
                    passed(
                        "archive.duplicates",
                        "Archive has no duplicate members.",
                    )
                )
            for name in names:
                try:
                    validate_relative_path(name)
                except ReportError as exc:
                    checks.append(failed("archive.path", str(exc)))
            return checks
    except zipfile.BadZipFile as exc:
        return [failed("archive.opens", f"Archive is malformed: {exc}")]


def compare_bundle_dirs(
    expected_dir: Path,
    actual_dir: Path,
) -> list[ReleaseBundleCheck]:
    """Compare expected and actual output directories."""
    checks: list[ReleaseBundleCheck] = []
    expected = {path.as_posix() for path in OUTPUT_FILES}
    actual = {
        path.relative_to(actual_dir).as_posix()
        for path in actual_dir.rglob("*")
        if path.is_file()
    }
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing:
        checks.append(failed("files.missing", "Missing file(s): " + ", ".join(missing)))
    else:
        checks.append(passed("files.missing", "No expected files are missing."))
    if unexpected:
        checks.append(
            failed("files.unexpected", "Unexpected file(s): " + ", ".join(unexpected))
        )
    else:
        checks.append(passed("files.unexpected", "No unexpected files found."))

    for relative in sorted(expected & actual):
        if relative == RELEASE_BUNDLE_ARCHIVE:
            continue
        expected_path = expected_dir / relative
        actual_path = actual_dir / relative
        if not filecmp.cmp(expected_path, actual_path, shallow=False):
            checks.append(
                failed(
                    f"files.{relative}",
                    "File differs from expected bundle.",
                )
            )
    has_file_failure = any(
        check.name.startswith("files.") and check.status == "failed"
        for check in checks
    )
    if not has_file_failure:
        checks.append(
            passed("files.bytes", "Payload file bytes match expected bundle.")
        )
    return checks


def compare_archive(
    expected_archive: Path,
    actual_archive: Path,
) -> list[ReleaseBundleCheck]:
    """Compare expected and actual archive bytes."""
    if not actual_archive.is_file():
        return [failed("archive.bytes", "Archive is missing.")]
    return [
        passed("archive.bytes", "Archive bytes match expected bundle.")
        if filecmp.cmp(expected_archive, actual_archive, shallow=False)
        else failed("archive.bytes", "Archive bytes differ from expected bundle.")
    ]


def verify_checksums(output_dir: Path) -> bool:
    """Return whether release-checksums.sha256 matches payload files."""
    checksum_path = output_dir / RELEASE_CHECKSUMS
    if not checksum_path.is_file():
        return False
    try:
        lines = checksum_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    expected_paths = [
        path.as_posix()
        for path in sorted(CHECKSUM_PAYLOAD_FILES, key=lambda item: item.as_posix())
    ]
    seen: list[str] = []
    for line in lines:
        if "  " not in line:
            return False
        digest, relative = line.split("  ", 1)
        if len(digest) != 64:
            return False
        try:
            validate_relative_path(relative)
        except ReportError:
            return False
        if not (output_dir / relative).is_file():
            return False
        if sha256_file(output_dir / relative) != digest:
            return False
        seen.append(relative)
    return seen == expected_paths


def release_bundle_json_payload(result: ReleaseBundleResult) -> dict[str, object]:
    """Return deterministic JSON-safe release-bundle command payload."""
    return {
        "status": result.status,
        "candidate": result.candidate,
        "target_version": result.target_version,
        "released": result.released,
        "output_dir": str(result.output_dir),
        "archive_path": str(result.archive_path),
        "archive_sha256": result.archive_sha256,
        "deterministic": result.deterministic,
        "checked": result.checked,
        "files": result.files,
        "checksums_valid": result.checksums_valid,
        "source_commit": result.source_commit,
        "checks": [
            {"name": check.name, "status": check.status, "message": check.message}
            for check in result.checks
        ],
    }


def release_bundle_json(result: ReleaseBundleResult) -> str:
    """Return pretty deterministic JSON for release-bundle command output."""
    return json.dumps(release_bundle_json_payload(result), indent=2, sort_keys=True)


def write_release_bundle_json(result: ReleaseBundleResult, output_path: Path) -> Path:
    """Write release-bundle command JSON output."""
    validate_file_output_path(output_path)
    output_path.write_text(release_bundle_json(result) + "\n", encoding="utf-8")
    return output_path


def failed_result(
    project_root: Path,
    output_dir: Path,
    archive_path: Path,
    checks: list[ReleaseBundleCheck],
) -> ReleaseBundleResult:
    """Return a failed result before files can be inspected."""
    return ReleaseBundleResult(
        project_root=project_root,
        output_dir=output_dir,
        archive_path=archive_path,
        target_version=TARGET_RELEASE_VERSION,
        candidate=True,
        released=False,
        status="failed",
        checked=True,
        deterministic=True,
        files=[path.as_posix() for path in OUTPUT_FILES],
        archive_sha256=sha256_file(archive_path) if archive_path.is_file() else None,
        checksums_valid=False,
        source_commit=git_output(project_root, ["rev-parse", "HEAD"]),
        checks=checks,
    )


def write_json(path: Path, payload: dict[str, object]) -> None:
    """Write deterministic JSON with a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    """Write text with one trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")


def validate_output_locations(output_dir: Path, archive_path: Path) -> None:
    """Validate output directory and archive path before writing."""
    if output_dir.exists() and not output_dir.is_dir():
        raise ReportError(f"Output path is not a directory: {output_dir}")
    if archive_path.exists() and archive_path.is_dir():
        raise ReportError(f"Archive output path is a directory: {archive_path}")
    if not archive_path.parent.exists() and archive_path.parent != output_dir:
        raise ReportError(
            f"Archive output parent does not exist: {archive_path.parent}"
        )


def validate_file_output_path(output_path: Path) -> None:
    """Validate a JSON output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"JSON output path is a directory: {output_path}")
    if not output_path.parent.exists():
        raise ReportError(f"JSON output parent does not exist: {output_path.parent}")


def validate_relative_path(path: str) -> None:
    """Reject absolute, parent-traversing, or empty POSIX paths."""
    pure = PurePosixPath(path)
    if path.startswith("/") or pure.is_absolute() or not path:
        raise ReportError(f"Archive path is not relative: {path}")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ReportError(f"Archive path is unsafe: {path}")


def forbidden_publication_hits(text: str) -> list[str]:
    """Return forbidden release/publication snippets found in workflow text."""
    lower = text.lower()
    forbidden = [
        " gh ",
        "gh release",
        "git tag",
        "git push --tags",
        "twine upload",
        "hatch publish",
        "poetry publish",
        "softprops/action-gh-release",
        "ncipollo/release-action",
        "actions/create-release",
        "marketplace/actions/publish",
    ]
    return [item for item in forbidden if item in lower]


def read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML mapping."""
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReportError(f"Could not read {path}: {exc}") from exc
    return payload if isinstance(payload, dict) else {}


def read_toml(path: Path) -> dict[str, Any]:
    """Read a TOML mapping."""
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReportError(f"Could not read {path}: {exc}") from exc


def read_json_or_none(path: Path) -> dict[str, object] | None:
    """Read a JSON object, returning None on failure."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def git_output(project_root: Path, args: list[str]) -> str | None:
    """Return git output or None when unavailable."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def git_tree_state(project_root: Path) -> dict[str, object]:
    """Return deterministic source tree state without file contents."""
    porcelain = git_output(project_root, ["status", "--short"]) or ""
    changed = sorted(line[3:] for line in porcelain.splitlines() if len(line) >= 4)
    return {
        "git_available": (
            git_output(project_root, ["rev-parse", "--is-inside-work-tree"])
            == "true"
        ),
        "clean": not porcelain,
        "changed_files": changed,
    }


def sha256_file(path: Path) -> str:
    """Return SHA256 hex digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def passed(name: str, message: str) -> ReleaseBundleCheck:
    """Return a passing check."""
    return ReleaseBundleCheck(name, "passed", message)


def failed(name: str, message: str) -> ReleaseBundleCheck:
    """Return a failing check."""
    return ReleaseBundleCheck(name, "failed", message)
