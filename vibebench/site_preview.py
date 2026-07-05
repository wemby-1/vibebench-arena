"""Static site preview packet helpers for VibeBench Arena."""

import json
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vibebench.site_check import (
    BANNED_CLAIMS_OR_MARKERS,
    HTML_FORBIDDEN_MARKERS,
    run_site_check,
    site_check_json,
)

PREVIEW_FILES = (
    "index.html",
    "showcase.html",
    "pages.md",
    "evaluate.md",
    "adoption.md",
    "demo.md",
    "product-strategy.md",
    "commercial-potential.md",
    "comparison.md",
    "faq.md",
)
SITE_CHECK_JSON = "site-check.json"
SITE_PREVIEW_MD = "site-preview.md"
SITE_PREVIEW_ZIP = "site-preview.zip"
GENERATED_FILES = (SITE_CHECK_JSON, SITE_PREVIEW_MD)
REQUIRED_PREVIEW_FILES = (*PREVIEW_FILES, *GENERATED_FILES)
HTML_PREVIEW_FILES = ("index.html", "showcase.html")
FORBIDDEN_LOCAL_PATHS = ("/tmp/", "/home/", "/data/code/")
FORBIDDEN_ZIP_PARTS = {".git", "__pycache__"}
PREVIEW_COMMAND = "python3 -m http.server 8000 --directory ."
DOCS_PREVIEW_COMMAND = "python3 -m http.server 8000 --directory docs"
READINESS_COMMAND = "python3 -m vibebench site-check"
PROOF_COMMAND = "python3 -m vibebench proof --output-dir PATH --zip"


class SitePreviewError(Exception):
    """Raised when a site preview cannot be written safely."""


def site_preview_payload(
    project_root: Path,
    *,
    site_root: Path,
    root_label: str,
    output_dir: Path | None = None,
    zip_output: Path | None = None,
) -> dict[str, Any]:
    """Build a deterministic static site preview payload."""
    site_check = run_site_check(site_root, root_label=root_label)
    output_label = output_dir.as_posix() if output_dir is not None else None
    zip_label = zip_output.as_posix() if zip_output is not None else None
    status = "ready" if site_check["status"] == "passed" else "failed"
    return {
        "status": status,
        "root": root_label,
        "project_root": project_root.as_posix(),
        "output_dir": output_label,
        "zip_output": zip_label,
        "included_files": list(REQUIRED_PREVIEW_FILES),
        "site_check": site_check,
        "commands": {
            "local_preview": PREVIEW_COMMAND,
            "docs_preview": DOCS_PREVIEW_COMMAND,
            "readiness": READINESS_COMMAND,
            "proof": PROOF_COMMAND,
        },
    }


def site_preview_json(payload: dict[str, Any]) -> str:
    """Serialize a static site preview payload as stable JSON."""
    return json.dumps(payload, indent=2, sort_keys=True)


def write_site_preview_json(payload: dict[str, Any], output: Path) -> None:
    """Write a static site preview JSON payload."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(site_preview_json(payload) + "\n", encoding="utf-8")


def write_site_preview(
    *,
    project_root: Path,
    site_root: Path,
    root_label: str,
    output_dir: Path,
    create_zip: bool = False,
    zip_output: Path | None = None,
) -> dict[str, Any]:
    """Write a static site preview directory and optional zip archive."""
    payload = site_preview_payload(
        project_root,
        site_root=site_root,
        root_label=root_label,
        output_dir=output_dir,
        zip_output=zip_output,
    )
    if payload["status"] != "ready":
        raise SitePreviewError("Static site readiness check failed.")

    output_dir.mkdir(parents=True, exist_ok=True)
    for relative_path in PREVIEW_FILES:
        source = site_root / relative_path
        if not source.is_file():
            raise SitePreviewError(f"Missing preview source file: {relative_path}")
        shutil.copyfile(source, output_dir / relative_path)

    output_dir.joinpath(SITE_CHECK_JSON).write_text(
        site_check_json(payload["site_check"]) + "\n",
        encoding="utf-8",
    )
    output_dir.joinpath(SITE_PREVIEW_MD).write_text(
        site_preview_markdown(payload),
        encoding="utf-8",
    )

    written = {
        "output_dir": output_dir.as_posix(),
        "files": list(REQUIRED_PREVIEW_FILES),
    }
    if create_zip or zip_output is not None:
        selected_zip = (
            zip_output if zip_output is not None else output_dir / SITE_PREVIEW_ZIP
        )
        write_site_preview_zip(output_dir, selected_zip)
        written["zip"] = selected_zip.as_posix()
        payload["zip_output"] = selected_zip.as_posix()
    payload["written"] = written
    return payload


def write_site_preview_zip(preview_dir: Path, zip_path: Path) -> None:
    """Write a zip archive with safe relative preview file names."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path in REQUIRED_PREVIEW_FILES:
            source = preview_dir / relative_path
            if not source.is_file():
                raise SitePreviewError(f"Missing preview file for zip: {relative_path}")
            archive.write(source, arcname=relative_path)


def site_preview_markdown(payload: dict[str, Any]) -> str:
    """Render a compact human-readable static site preview summary."""
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    lines = [
        "# VibeBench Site Preview",
        "",
        f"- Generated time: {generated_at}",
        f"- Status: {payload['status']}",
        "",
        "## Included files",
        "",
    ]
    lines.extend(f"- `{relative_path}`" for relative_path in REQUIRED_PREVIEW_FILES)
    lines.extend(
        [
            "",
            "## Commands",
            "",
            f"- Local preview: `{PREVIEW_COMMAND}`",
            f"- Original docs preview: `{DOCS_PREVIEW_COMMAND}`",
            f"- Readiness: `{READINESS_COMMAND}`",
            f"- Proof packet: `{PROOF_COMMAND}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_zip_only_preview(
    *,
    project_root: Path,
    site_root: Path,
    root_label: str,
    zip_output: Path,
) -> dict[str, Any]:
    """Write only a static site preview zip using a temporary directory."""
    with tempfile.TemporaryDirectory(prefix="vibebench-site-preview-") as tmp:
        temp_dir = Path(tmp) / "site-preview"
        return write_site_preview(
            project_root=project_root,
            site_root=site_root,
            root_label=root_label,
            output_dir=temp_dir,
            create_zip=True,
            zip_output=zip_output,
        )


def verify_site_preview(target: Path) -> dict[str, Any]:
    """Verify a static site preview directory or zip archive."""
    target_path = target
    if target_path.is_dir():
        return _verify_preview_directory(target_path)
    if target_path.is_file() and target_path.suffix == ".zip":
        return _verify_preview_zip(target_path)
    return _verification_payload(
        target_path,
        target_type="missing",
        checks=[
            _check("target_exists", False, "Target is not a directory or zip file."),
        ],
    )


def site_preview_verification_json(payload: dict[str, Any]) -> str:
    """Serialize a site preview verification payload as stable JSON."""
    return json.dumps(payload, indent=2, sort_keys=True)


def _verify_preview_directory(target: Path) -> dict[str, Any]:
    available_files = {
        relative_path
        for relative_path in REQUIRED_PREVIEW_FILES
        if (target / relative_path).is_file()
    }
    checks = [
        _check_required_preview_files(available_files),
        _check_valid_site_check_json(target / SITE_CHECK_JSON),
        _check_directory_safety(target),
    ]
    return _verification_payload(target, target_type="directory", checks=checks)


def _verify_preview_zip(target: Path) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    try:
        with zipfile.ZipFile(target) as archive:
            names = archive.namelist()
            safe_names = all(_safe_zip_name(name) for name in names)
            checks.append(
                _check(
                    "zip_entry_names",
                    safe_names,
                    (
                        "Zip entries use safe relative names."
                        if safe_names
                        else "Zip contains unsafe entry names."
                    ),
                )
            )
            name_set = set(names)
            checks.append(_check_required_preview_files(name_set))
            site_check_valid = _zip_json_valid(archive, SITE_CHECK_JSON)
            checks.append(
                _check(
                    "valid_json:site-check.json",
                    site_check_valid,
                    (
                        "site-check.json is valid JSON."
                        if site_check_valid
                        else "site-check.json is missing or invalid JSON."
                    ),
                )
            )
            checks.append(_check_zip_safety(archive, names))
    except zipfile.BadZipFile:
        checks.append(_check("valid_zip", False, "Target is not a valid zip file."))
    return _verification_payload(target, target_type="zip", checks=checks)


def _verification_payload(
    target: Path,
    *,
    target_type: str,
    checks: list[dict[str, str]],
) -> dict[str, Any]:
    verified = all(check["status"] == "passed" for check in checks)
    return {
        "status": "passed" if verified else "failed",
        "verified": verified,
        "target": target.as_posix(),
        "target_type": target_type,
        "checks": checks,
    }


def _check_required_preview_files(files: set[str]) -> dict[str, str]:
    missing = [
        relative_path
        for relative_path in REQUIRED_PREVIEW_FILES
        if relative_path not in files
    ]
    return _check(
        "required_files",
        not missing,
        (
            "Required preview files are present."
            if not missing
            else "Missing required preview files: " + ", ".join(missing)
        ),
    )


def _check_valid_site_check_json(path: Path) -> dict[str, str]:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _check(
            "valid_json:site-check.json",
            False,
            "site-check.json is missing or invalid JSON.",
        )
    return _check(
        "valid_json:site-check.json",
        True,
        "site-check.json is valid JSON.",
    )


def _check_directory_safety(target: Path) -> dict[str, str]:
    matches: list[str] = []
    for relative_path in REQUIRED_PREVIEW_FILES:
        path = target / relative_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        matches.extend(_unsafe_text_matches(relative_path, text))
    return _check(
        "preview_safety",
        not matches,
        (
            "Preview files avoid unsafe paths, remote URLs, scripts, and banned claims."
            if not matches
            else "Unsafe preview content found: " + "; ".join(matches)
        ),
    )


def _check_zip_safety(
    archive: zipfile.ZipFile,
    names: list[str],
) -> dict[str, str]:
    matches: list[str] = []
    for name in names:
        if name not in REQUIRED_PREVIEW_FILES:
            continue
        try:
            text = archive.read(name).decode("utf-8", errors="replace")
        except KeyError:
            continue
        matches.extend(_unsafe_text_matches(name, text))
    return _check(
        "preview_safety",
        not matches,
        (
            "Preview files avoid unsafe paths, remote URLs, scripts, and banned claims."
            if not matches
            else "Unsafe preview content found: " + "; ".join(matches)
        ),
    )


def _unsafe_text_matches(relative_path: str, text: str) -> list[str]:
    lowered = text.lower()
    matches: list[str] = []
    if relative_path in HTML_PREVIEW_FILES:
        for marker in HTML_FORBIDDEN_MARKERS:
            if marker in lowered:
                matches.append(f"{relative_path}: {marker}")
        for marker in FORBIDDEN_LOCAL_PATHS:
            if marker in lowered:
                matches.append(f"{relative_path}: {marker}")
    for marker in BANNED_CLAIMS_OR_MARKERS:
        if marker in lowered:
            matches.append(f"{relative_path}: {marker}")
    return matches


def _zip_json_valid(archive: zipfile.ZipFile, name: str) -> bool:
    try:
        json.loads(archive.read(name).decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return True


def _safe_zip_name(name: str) -> bool:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    if any(part in FORBIDDEN_ZIP_PARTS for part in path.parts):
        return False
    if name.startswith(".vibebench/runs/") or name.startswith("/"):
        return False
    return name in REQUIRED_PREVIEW_FILES


def _check(name: str, passed: bool, message: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "message": message,
    }
