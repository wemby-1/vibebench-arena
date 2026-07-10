"""Local pre-sharing scanner for generated review packages."""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = {".html", ".md", ".json", ".txt", ".yml", ".yaml", ".toml"}
IGNORED_REPORT_FILES = {"share-check.json", "share-check.md"}
MAX_SNIPPET_LENGTH = 120
REMOTE_URL_RE = re.compile(r"https?://[^\s\"'<>)]*", re.IGNORECASE)
REMOTE_SCRIPT_RE = re.compile(
    r"<script\b[^>]*\bsrc\s*=\s*[\"']https?://",
    re.IGNORECASE,
)
REMOTE_STYLESHEET_RE = re.compile(
    r"<link\b[^>]*\bhref\s*=\s*[\"']https?://",
    re.IGNORECASE,
)
REMOTE_IMAGE_RE = re.compile(
    r"<img\b[^>]*\bsrc\s*=\s*[\"']https?://",
    re.IGNORECASE,
)
IFRAME_RE = re.compile(r"<iframe\b", re.IGNORECASE)
SCRIPT_TAG_RE = re.compile(r"<script\b", re.IGNORECASE)
GITHUB_TOKEN_RE = re.compile(
    r"\b(?:ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})"
)
OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")
AWS_ACCESS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
SECRET_ASSIGNMENT_RE = re.compile(
    r"\b(?:OPENAI_API_KEY|GITHUB_TOKEN|AWS_SECRET_ACCESS_KEY)\s*=\s*[^\s#]+",
    re.IGNORECASE,
)
PASSWORD_ASSIGNMENT_RE = re.compile(
    r"\bpassword\s*[:=]\s*[^\s#]+",
    re.IGNORECASE,
)
PRIVATE_KEY_MARKERS = (
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
)
POSITIVE_CLAIM_MARKERS = {
    "soc 2 certified": "SOC 2 certified",
    "iso 27001 certified": "ISO 27001 certified",
    "independently audited": "independently audited",
    "audited by": "audited by",
    "guaranteed secure": "guaranteed secure",
    "enterprise certified": "enterprise certified",
    "millions of users": "millions of users",
    "revenue": "revenue",
    "funding guaranteed": "funding guaranteed",
    "unicorn": "unicorn",
}
NON_CLAIM_ALLOWLIST = (
    "not claiming soc 2 certification",
    "not claiming iso 27001 certification",
    "not a third-party audit",
    "not independently audited",
    "no fake traction claims",
    "not a claim of revenue",
    "does not claim",
    "does not prove product-market fit",
    "does not prove product-market fit, revenue",
    "or claim adoption, revenue",
    "proof of traction, revenue",
    "does not enable github pages automatically or claim",
    "should not invent",
    "not invent",
    "fake revenue",
)


class ShareCheckError(Exception):
    """Raised when share-check cannot inspect a target."""


@dataclass(frozen=True)
class ShareCheckFinding:
    """One share-check finding."""

    severity: str
    code: str
    file: str
    line: int | None
    message: str
    snippet: str | None


@dataclass(frozen=True)
class ScannedFile:
    """Text file selected for scanning."""

    path: str
    text: str


@dataclass(frozen=True)
class ShareCheckResult:
    """Result of a share-check scan."""

    status: str
    target: str
    target_type: str
    strict: bool
    checked_files: list[str]
    findings: list[ShareCheckFinding]


def run_share_check(
    target: Path,
    *,
    strict: bool = False,
    allow_remote_urls: bool = False,
    allow_example_temp_paths: bool = False,
    target_label: str | None = None,
) -> ShareCheckResult:
    """Scan a directory, zip, or single text artifact before sharing."""
    selected_target = target.resolve()
    if not selected_target.exists():
        raise ShareCheckError(f"Share-check target does not exist: {target}")

    findings: list[ShareCheckFinding] = []
    if selected_target.is_dir():
        target_type = "directory"
        scanned_files = list(scan_directory(selected_target))
    elif selected_target.is_file() and selected_target.suffix.lower() == ".zip":
        target_type = "zip"
        scanned_files = list(scan_zip(selected_target, findings))
    elif selected_target.is_file():
        target_type = "file"
        scanned_files = [scan_file(selected_target)]
    else:
        target_type = "missing"
        raise ShareCheckError(
            "Share-check target must be a directory, zip file, or text artifact."
        )

    for scanned_file in scanned_files:
        findings.extend(
            scan_text(
                scanned_file.path,
                scanned_file.text,
                allow_remote_urls=allow_remote_urls,
                allow_example_temp_paths=allow_example_temp_paths,
            )
        )

    status = status_from_findings(findings, strict=strict)
    return ShareCheckResult(
        status=status,
        target=target_label if target_label is not None else str(selected_target),
        target_type=target_type,
        strict=strict,
        checked_files=[item.path for item in scanned_files],
        findings=findings,
    )


def scan_file(path: Path) -> ScannedFile:
    """Collect one text/static artifact file."""
    if not should_scan_path(path.name):
        raise ShareCheckError(
            "Share-check file target must use a supported text/static suffix."
        )
    data = path.read_bytes()
    if is_probably_binary(data):
        raise ShareCheckError("Share-check file target appears to be binary.")
    return ScannedFile(path.name, decode_text(data))


def scan_directory(root: Path) -> list[ScannedFile]:
    """Collect text/static files from a directory recursively."""
    files: list[ScannedFile] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if ignored_report_path(relative) or not should_scan_path(path.name):
            continue
        data = path.read_bytes()
        if is_probably_binary(data):
            continue
        files.append(ScannedFile(relative, decode_text(data)))
    return files


def scan_zip(zip_path: Path, findings: list[ShareCheckFinding]) -> list[ScannedFile]:
    """Collect text/static files from a zip without extracting to the repo."""
    files: list[ScannedFile] = []
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for info in sorted(archive.infolist(), key=lambda item: item.filename):
                name = info.filename
                if name.endswith("/"):
                    continue
                if not safe_zip_name(name):
                    findings.append(
                        ShareCheckFinding(
                            severity="error",
                            code="unsafe_zip_path",
                            file=name,
                            line=None,
                            message="Zip entry path is not a safe relative path.",
                            snippet=None,
                        )
                    )
                    continue
                if ignored_report_path(name):
                    continue
                if not should_scan_path(name):
                    continue
                data = archive.read(info)
                if is_probably_binary(data):
                    continue
                files.append(ScannedFile(name, decode_text(data)))
    except zipfile.BadZipFile as exc:
        message = f"Share-check target is not a valid zip file: {zip_path}"
        raise ShareCheckError(message) from exc
    return files


def should_scan_path(name: str) -> bool:
    """Return whether a file path should be scanned as a text artifact."""
    return Path(name).suffix.lower() in TEXT_SUFFIXES


def ignored_report_path(name: str) -> bool:
    """Return whether a path is a generated share-check report."""
    return Path(name).name in IGNORED_REPORT_FILES


def is_probably_binary(data: bytes) -> bool:
    """Return whether bytes look like an obvious binary file."""
    if not data:
        return False
    if b"\x00" in data[:4096]:
        return True
    return False


def decode_text(data: bytes) -> str:
    """Decode artifact text conservatively."""
    return data.decode("utf-8", errors="replace")


def safe_zip_name(name: str) -> bool:
    """Return whether a zip member name is safe to inspect."""
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    if re.match(r"^[A-Za-z]:", name):
        return False
    if name.startswith("/") or name.endswith("/"):
        return False
    return True


def scan_text(
    file_path: str,
    text: str,
    *,
    allow_remote_urls: bool,
    allow_example_temp_paths: bool,
) -> list[ShareCheckFinding]:
    """Scan one text artifact."""
    findings: list[ShareCheckFinding] = []
    for index, line in enumerate(text.splitlines(), start=1):
        findings.extend(scan_html_markers(file_path, index, line))
        findings.extend(
            scan_remote_urls(
                file_path,
                index,
                line,
                allow_remote_urls=allow_remote_urls,
            )
        )
        findings.extend(
            scan_absolute_paths(
                file_path,
                index,
                line,
                allow_example_temp_paths=allow_example_temp_paths,
            )
        )
        findings.extend(scan_secrets(file_path, index, line))
        findings.extend(scan_claims(file_path, index, line))
    return findings


def scan_html_markers(
    file_path: str,
    line_number: int,
    line: str,
) -> list[ShareCheckFinding]:
    """Scan HTML-specific unsafe markers."""
    suffix = Path(file_path).suffix.lower()
    if suffix != ".html":
        return []
    checks = [
        (SCRIPT_TAG_RE, "html_script_tag", "Static HTML contains a script tag."),
        (REMOTE_SCRIPT_RE, "html_remote_script", "Static HTML loads a remote script."),
        (
            REMOTE_STYLESHEET_RE,
            "html_remote_stylesheet",
            "Static HTML loads a remote stylesheet.",
        ),
        (REMOTE_IMAGE_RE, "html_remote_image", "Static HTML loads a remote image."),
        (IFRAME_RE, "html_iframe", "Static HTML contains an iframe tag."),
    ]
    findings: list[ShareCheckFinding] = []
    for pattern, code, message in checks:
        if pattern.search(line):
            findings.append(
                finding("error", code, file_path, line_number, message, line)
            )
    return findings


def scan_remote_urls(
    file_path: str,
    line_number: int,
    line: str,
    *,
    allow_remote_urls: bool,
) -> list[ShareCheckFinding]:
    """Scan remote URLs."""
    if not REMOTE_URL_RE.search(line):
        return []
    severity = "warning" if allow_remote_urls else "error"
    message = (
        "Remote URL is present and should be reviewed before sharing."
        if allow_remote_urls
        else "Remote URL is present in a shareable artifact."
    )
    return [
        finding(
            severity,
            "remote_url",
            file_path,
            line_number,
            message,
            line,
        )
    ]


def scan_absolute_paths(
    file_path: str,
    line_number: int,
    line: str,
    *,
    allow_example_temp_paths: bool,
) -> list[ShareCheckFinding]:
    """Scan absolute local paths."""
    lowered = line.lower()
    markers = [
        ("/home/", "absolute_home_path"),
        ("/users/", "absolute_users_path"),
        ("/data/code/", "absolute_data_code_path"),
        ("c:\\users\\", "absolute_windows_user_path"),
        ("d:\\", "absolute_windows_drive_path"),
    ]
    findings: list[ShareCheckFinding] = []
    for marker, code in markers:
        if marker in lowered:
            findings.append(
                finding(
                    "error",
                    code,
                    file_path,
                    line_number,
                    "Personal or machine-local absolute path is present.",
                    line,
                )
            )

    if "/tmp/" in lowered and not allowed_tmp_example(
        line,
        allow_example_temp_paths=allow_example_temp_paths,
    ):
        findings.append(
            finding(
                "error",
                "absolute_tmp_path",
                file_path,
                line_number,
                "Temporary absolute path should be reviewed before sharing.",
                line,
            )
        )
    return findings


def allowed_tmp_example(line: str, *, allow_example_temp_paths: bool) -> bool:
    """Return whether a /tmp path is a documented VibeBench example."""
    lowered = line.lower()
    return "/tmp/vibebench-" in lowered


def scan_secrets(
    file_path: str,
    line_number: int,
    line: str,
) -> list[ShareCheckFinding]:
    """Scan high-confidence secret markers."""
    checks = [
        (GITHUB_TOKEN_RE, "github_token", "GitHub token-like value is present."),
        (OPENAI_KEY_RE, "openai_api_key", "OpenAI key-like value is present."),
        (AWS_ACCESS_KEY_RE, "aws_access_key", "AWS access key-like value is present."),
        (
            SECRET_ASSIGNMENT_RE,
            "secret_assignment",
            "Secret environment assignment is present.",
        ),
        (
            PASSWORD_ASSIGNMENT_RE,
            "password_assignment",
            "Password assignment is present.",
        ),
    ]
    findings: list[ShareCheckFinding] = []
    for pattern, code, message in checks:
        if pattern.search(line):
            findings.append(
                finding("error", code, file_path, line_number, message, line)
            )
    for marker in PRIVATE_KEY_MARKERS:
        if marker in line:
            findings.append(
                finding(
                    "error",
                    "private_key_block",
                    file_path,
                    line_number,
                    "Private key block marker is present.",
                    line,
                )
            )
    return findings


def scan_claims(
    file_path: str,
    line_number: int,
    line: str,
) -> list[ShareCheckFinding]:
    """Scan fake positive trust/compliance/traction claims."""
    lowered = line.lower()
    if any(allowed in lowered for allowed in NON_CLAIM_ALLOWLIST):
        return []
    findings: list[ShareCheckFinding] = []
    for marker, display in POSITIVE_CLAIM_MARKERS.items():
        if marker in lowered:
            findings.append(
                finding(
                    "error",
                    "fake_trust_claim",
                    file_path,
                    line_number,
                    f"Positive unsupported claim found: {display}.",
                    line,
                )
            )
    return findings


def finding(
    severity: str,
    code: str,
    file_path: str,
    line_number: int | None,
    message: str,
    line: str | None,
) -> ShareCheckFinding:
    """Build a finding with a short sanitized snippet."""
    return ShareCheckFinding(
        severity=severity,
        code=code,
        file=file_path,
        line=line_number,
        message=message,
        snippet=snippet(line),
    )


def snippet(line: str | None) -> str | None:
    """Return a short single-line snippet."""
    if line is None:
        return None
    cleaned = " ".join(line.strip().split())
    if not cleaned:
        return None
    if len(cleaned) > MAX_SNIPPET_LENGTH:
        return cleaned[: MAX_SNIPPET_LENGTH - 3] + "..."
    return cleaned


def status_from_findings(
    findings: list[ShareCheckFinding],
    *,
    strict: bool,
) -> str:
    """Return passed or failed for a finding set."""
    if any(item.severity == "error" for item in findings):
        return "failed"
    if strict and any(item.severity == "warning" for item in findings):
        return "failed"
    return "passed"


def share_check_payload(result: ShareCheckResult) -> dict[str, Any]:
    """Return deterministic JSON-ready share-check payload."""
    summary = share_check_summary(result.findings, len(result.checked_files))
    return {
        "status": result.status,
        "target": result.target,
        "target_type": result.target_type,
        "strict": result.strict,
        "checked_files": result.checked_files,
        "summary": summary,
        "findings": [
            {
                "severity": item.severity,
                "code": item.code,
                "file": item.file,
                "line": item.line,
                "message": item.message,
                "snippet": item.snippet,
            }
            for item in result.findings
        ],
    }


def share_check_summary(
    findings: list[ShareCheckFinding],
    checked_file_count: int,
) -> dict[str, int]:
    """Return finding counts."""
    return {
        "checked_file_count": checked_file_count,
        "finding_count": len(findings),
        "error_count": sum(1 for item in findings if item.severity == "error"),
        "warning_count": sum(1 for item in findings if item.severity == "warning"),
        "info_count": sum(1 for item in findings if item.severity == "info"),
    }


def share_check_json(result: ShareCheckResult) -> str:
    """Serialize share-check result as stable JSON."""
    return json.dumps(share_check_payload(result), indent=2, sort_keys=True)


def write_share_check_json(result: ShareCheckResult, output: Path) -> None:
    """Write share-check JSON to a path."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(share_check_json(result) + "\n", encoding="utf-8")


def share_check_markdown(result: ShareCheckResult) -> str:
    """Render a human-readable Markdown share-check report."""
    summary = share_check_summary(result.findings, len(result.checked_files))
    lines = [
        "# VibeBench Share Check",
        "",
        f"- Target: `{result.target}`",
        f"- Target type: `{result.target_type}`",
        f"- Status: `{result.status}`",
        f"- Strict mode: `{str(result.strict).lower()}`",
        f"- Checked files: {summary['checked_file_count']}",
        f"- Findings: {summary['finding_count']}",
        f"- Errors: {summary['error_count']}",
        f"- Warnings: {summary['warning_count']}",
        f"- Info: {summary['info_count']}",
        "",
    ]
    if result.findings:
        lines.extend(
            [
                "## Findings",
                "",
                "| Severity | Code | File | Line | Message |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for item in result.findings:
            line = "" if item.line is None else str(item.line)
            lines.append(
                "| "
                f"{markdown_cell(item.severity)} | "
                f"{markdown_cell(item.code)} | "
                f"{markdown_cell(item.file)} | "
                f"{markdown_cell(line)} | "
                f"{markdown_cell(item.message)} |"
            )
        lines.append("")
    else:
        lines.extend(["## Findings", "", "No findings.", ""])

    lines.extend(
        [
            "## Remediation Guidance",
            "",
            (
                "Review errors before sharing. Remove scripts, remote assets, "
                "personal paths, credential-like values, private key material, and "
                "unsupported trust or traction claims from generated packages."
            ),
            "",
            "## Scope",
            "",
            "- This is a local pre-sharing aid.",
            "- It is not a security certification.",
            "- It is not a third-party audit.",
            "- It is not a guarantee.",
            "- Users should still manually review artifacts before publishing.",
            "",
        ]
    )
    return "\n".join(lines)


def write_share_check_markdown(result: ShareCheckResult, output: Path) -> None:
    """Write share-check Markdown to a path."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(share_check_markdown(result), encoding="utf-8")


def markdown_cell(value: object) -> str:
    """Escape a value for a compact Markdown table cell."""
    return str(value).replace("|", "\\|").replace("\n", " ")
