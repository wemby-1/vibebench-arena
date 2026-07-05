"""Local proof packet helpers for VibeBench Arena."""

from __future__ import annotations

import hashlib
import html
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROOF_MARKDOWN = "proof.md"
PROOF_JSON = "proof.json"
PROOF_HTML = "proof.html"
PROOF_MANIFEST = "proof-manifest.json"
PROOF_ZIP = "proof.zip"
MANIFEST_CONTENT_FILES = [PROOF_MARKDOWN, PROOF_JSON, PROOF_HTML]
REQUIRED_PACKET_FILES = [PROOF_MARKDOWN, PROOF_JSON, PROOF_HTML, PROOF_MANIFEST]

RECOMMENDED_COMMANDS = [
    "python3 -m vibebench demo",
    "python3 -m vibebench demo --json",
    "python3 -m vibebench ci --dry-run --json",
    "python3 -m vibebench release-check",
    "python3 -m vibebench doctor --strict",
    "python3 -m vibebench proof --output-dir /tmp/vibebench-proof",
]

RECOMMENDED_DOCS = [
    "README.md",
    "docs/evaluate.md",
    "docs/adoption.md",
    "docs/demo.md",
    "docs/artifact-gallery.md",
    "docs/case-study.md",
    "docs/comparison.md",
    "docs/faq.md",
    "docs/product-strategy.md",
    "docs/commercial-potential.md",
    "docs/roadmap-public.md",
]

RECOMMENDED_ARTIFACTS = [
    "examples/showcase-artifacts/sample/README.md",
    "examples/showcase-artifacts/sample/ci-summary.md",
    "examples/showcase-artifacts/sample/ci-plan.json",
    "examples/showcase-artifacts/sample/artifact-inventory.json",
    "examples/showcase-artifacts/sample/compare-summary.md",
    "examples/showcase-artifacts/sample/release-audit-summary.md",
    "examples/showcase-artifacts/sample/manifest.json",
]

HONEST_LIMITS = [
    (
        "Does not promise star growth, funding outcomes, customer wins, "
        "or benchmark dominance."
    ),
    "Does not replace human code review, tests, CI, or release judgment.",
    "Does not automatically publish, deploy, tag, upload packages, or create releases.",
    "Does not require external services for the core local proof path.",
    "Keeps the proof packet local, inspectable, and explicit.",
]

NEXT_STEPS = [
    "Run the demo and JSON demo output.",
    "Preview the CI plan as JSON.",
    "Inspect the artifact gallery and case study.",
    "Generate a local proof packet under /tmp for sharing or review.",
    "Try VibeBench as a small pilot before expanding team use.",
]


class ProofError(Exception):
    """Raised when a proof packet cannot be written safely."""


def proof_payload(project_root: Path | None = None) -> dict[str, Any]:
    """Build the stable proof packet payload."""
    return {
        "status": "ready",
        "project": {
            "name": "VibeBench Arena",
            "kind": "Codex-first / vibe-coding quality console",
        },
        "summary": (
            "VibeBench Arena helps evaluate AI-assisted coding work by turning "
            "changes into inspectable local evidence."
        ),
        "positioning": {
            "codex_first": True,
            "vibe_coding": True,
            "quality_console": True,
            "description": (
                "A Codex-first / vibe-coding quality console for developers and "
                "teams evaluating AI-assisted coding workflows."
            ),
        },
        "local_first": {
            "enabled": True,
            "description": (
                "Core proof commands run from the repository checkout without a "
                "hosted service requirement."
            ),
        },
        "evidence_first": {
            "enabled": True,
            "description": (
                "Commands produce JSON, Markdown, summaries, and artifact paths "
                "that support local review."
            ),
        },
        "recommended_commands": RECOMMENDED_COMMANDS,
        "recommended_docs": RECOMMENDED_DOCS,
        "recommended_artifacts": RECOMMENDED_ARTIFACTS,
        "honest_limits": HONEST_LIMITS,
        "next_steps": NEXT_STEPS,
    }


def proof_json(payload: dict[str, Any]) -> str:
    """Serialize a proof payload as sorted, pretty JSON."""
    return json.dumps(payload, indent=2, sort_keys=True)


def proof_markdown(payload: dict[str, Any]) -> str:
    """Render a GitHub-readable proof packet summary."""
    lines = [
        "# VibeBench Proof Packet",
        "",
        str(payload["summary"]),
        "",
        "VibeBench Arena is a Codex-first / vibe-coding quality console. It is "
        "local-first, evidence-first, and built to support audit-friendly review "
        "of AI-assisted coding workflows.",
        "",
        "## 5-minute Evaluation Path",
        "",
        "- Read `README.md` and `docs/evaluate.md`.",
        "- Run `python3 -m vibebench demo`.",
        "- Run `python3 -m vibebench demo --json`.",
        "- Run `python3 -m vibebench ci --dry-run --json`.",
        "- Inspect `docs/artifact-gallery.md` and `docs/case-study.md`.",
        "",
        "## Local Commands",
        "",
    ]
    lines.extend(f"- `{command}`" for command in payload["recommended_commands"])
    lines.extend(
        [
            "",
            "## Artifact Inspection Path",
            "",
        ]
    )
    lines.extend(f"- `{artifact}`" for artifact in payload["recommended_artifacts"])
    lines.extend(
        [
            "",
            "## Adoption Path",
            "",
            "- Read `docs/adoption.md`.",
            "- Use one small repo, one maintainer, and one AI coding workflow.",
            "- Inspect artifacts before expanding team use.",
            "- Treat the packet as review support, not automatic approval.",
            "",
            "## Honest Limitations / Non-claims",
            "",
        ]
    )
    lines.extend(f"- {limit}" for limit in payload["honest_limits"])
    lines.extend(
        [
            "",
            "## Relevant Docs",
            "",
        ]
    )
    lines.extend(f"- [{doc}]({doc})" for doc in payload["recommended_docs"])
    return "\n".join(lines) + "\n"


def proof_html(payload: dict[str, Any]) -> str:
    """Render a self-contained static HTML proof packet report."""
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    project = payload.get("project") if isinstance(payload.get("project"), dict) else {}
    positioning = (
        payload.get("positioning")
        if isinstance(payload.get("positioning"), dict)
        else {}
    )
    local_first = (
        payload.get("local_first")
        if isinstance(payload.get("local_first"), dict)
        else {}
    )
    evidence_first = (
        payload.get("evidence_first")
        if isinstance(payload.get("evidence_first"), dict)
        else {}
    )

    commands = list_items(payload.get("recommended_commands"))
    docs = list_items(payload.get("recommended_docs"))
    artifacts = list_items(payload.get("recommended_artifacts"))
    limits = list_items(payload.get("honest_limits"))
    next_steps = list_items(payload.get("next_steps"))

    summary_rows = [
        ("status", payload.get("status", "")),
        ("project", project.get("name", "")),
        ("generated time", generated_at),
        ("risk / status", "local-first, evidence-first proof packet"),
        ("artifact / check summary", artifact_check_summary(artifacts, commands)),
    ]
    if commands:
        summary_rows.insert(4, ("command used", neutralize_local_paths(commands[-1])))

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            "  <title>VibeBench Proof Packet</title>",
            "  <style>",
            css_text(),
            "  </style>",
            "</head>",
            "<body>",
            '  <main class="page">',
            "    <header>",
            "      <h1>VibeBench Proof Packet</h1>",
            (
                "      <p>Codex-first / vibe-coding quality evidence for "
                "local AI-assisted development.</p>"
            ),
            "    </header>",
            section_html("Summary", definition_list(summary_rows)),
            section_html(
                "CI dry-run / plan evidence",
                bullet_list(
                    [command for command in commands if "ci --dry-run" in command]
                )
                or paragraph("No CI dry-run command is present in this proof payload."),
            ),
            section_html(
                "Release readiness evidence",
                bullet_list(
                    [command for command in commands if "release-check" in command]
                    + [doc for doc in docs if "release" in doc or "evaluate" in doc]
                )
                or paragraph(
                    "No release readiness evidence is present in this proof payload."
                ),
            ),
            section_html(
                "Doctor / strict readiness evidence",
                bullet_list(
                    [command for command in commands if "doctor --strict" in command]
                )
                or paragraph(
                    "No strict doctor command is present in this proof payload."
                ),
            ),
            section_html(
                "Artifact or proof packet outputs",
                bullet_list(
                    artifacts + [command for command in commands if "proof" in command]
                )
                or paragraph("No artifact outputs are present in this proof payload."),
            ),
            section_html(
                "Verification / checksum status",
                bullet_list(
                    [
                        (
                            "proof-manifest.json records relative packet files "
                            "and checksums."
                        ),
                        (
                            "proof verification validates required files and "
                            "manifest checksums."
                        ),
                    ]
                ),
            ),
            section_html(
                "Local and Evidence-First Notes",
                bullet_list(
                    [
                        value
                        for value in [
                            positioning.get("description", ""),
                            local_first.get("description", ""),
                            evidence_first.get("description", ""),
                        ]
                        if value
                    ]
                ),
            ),
            section_html("Honest Limitations / Non-claims", bullet_list(limits)),
            section_html("Next Steps", bullet_list(next_steps)),
            "  </main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def css_text() -> str:
    """Return inline CSS for the self-contained proof report."""
    return """
    :root { color-scheme: light; }
    body {
      margin: 0;
      background: #f6f7f9;
      color: #20242a;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }
    .page {
      max-width: 980px;
      margin: 0 auto;
      padding: 40px 20px 56px;
    }
    header {
      border-bottom: 3px solid #2f6f73;
      margin-bottom: 28px;
      padding-bottom: 18px;
    }
    h1, h2 { line-height: 1.2; margin: 0; }
    h1 { font-size: 2.25rem; }
    h2 { font-size: 1.25rem; margin-bottom: 12px; }
    header p { color: #49515a; font-size: 1.05rem; margin: 10px 0 0; }
    section {
      background: #ffffff;
      border: 1px solid #d8dde3;
      border-radius: 8px;
      margin: 16px 0;
      padding: 18px;
    }
    dl {
      display: grid;
      grid-template-columns: minmax(140px, 220px) 1fr;
      gap: 8px 16px;
      margin: 0;
    }
    dt { color: #49515a; font-weight: 700; }
    dd { margin: 0; overflow-wrap: anywhere; }
    ul { margin: 0; padding-left: 1.25rem; }
    li + li { margin-top: 6px; }
    code {
      background: #eef1f4;
      border-radius: 4px;
      padding: 0.1rem 0.3rem;
      white-space: normal;
      overflow-wrap: anywhere;
    }
    @media (max-width: 640px) {
      .page { padding: 24px 14px 40px; }
      h1 { font-size: 1.8rem; }
      dl { grid-template-columns: 1fr; }
      dt { margin-top: 8px; }
    }
    """.strip()


def section_html(title: str, body: str) -> str:
    """Render an escaped section title with already escaped body HTML."""
    return f"    <section>\n      <h2>{escape_text(title)}</h2>\n{body}\n    </section>"


def definition_list(rows: list[tuple[str, object]]) -> str:
    """Render escaped key-value rows."""
    items: list[str] = ["      <dl>"]
    for key, value in rows:
        items.append(f"        <dt>{escape_text(key)}</dt>")
        items.append(f"        <dd>{inline_code_or_text(value)}</dd>")
    items.append("      </dl>")
    return "\n".join(items)


def bullet_list(values: list[object]) -> str:
    """Render escaped list values, returning an empty string when no values exist."""
    if not values:
        return ""
    items = ["      <ul>"]
    for value in values:
        items.append(f"        <li>{inline_code_or_text(value)}</li>")
    items.append("      </ul>")
    return "\n".join(items)


def paragraph(value: object) -> str:
    """Render one escaped paragraph."""
    return f"      <p>{escape_text(value)}</p>"


def inline_code_or_text(value: object) -> str:
    """Render command-like values as escaped inline code."""
    text = neutralize_local_paths(str(value))
    escaped = escape_text(text)
    if text.startswith("python") or text.endswith(".json") or text.endswith(".md"):
        return f"<code>{escaped}</code>"
    return escaped


def escape_text(value: object) -> str:
    """Escape dynamic text for safe HTML output."""
    return html.escape(str(value), quote=True)


def list_items(value: object) -> list[str]:
    """Return a list of string items from a payload value."""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def neutralize_local_paths(value: str) -> str:
    """Avoid exposing absolute local paths in the HTML report."""
    return value.replace("/tmp/vibebench-proof", "PATH")


def artifact_check_summary(artifacts: list[str], commands: list[str]) -> str:
    """Summarize available artifact and command evidence."""
    return f"{len(artifacts)} artifact path(s), {len(commands)} recommended command(s)"


def proof_manifest(
    payload: dict[str, Any],
    content: dict[str, bytes],
) -> dict[str, Any]:
    """Build a manifest for proof packet content files."""
    return {
        "status": "ready",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "project": payload["project"],
        "files": [
            file_manifest(name, content[name]) for name in MANIFEST_CONTENT_FILES
        ],
        "notes": [
            "Manifest paths are relative to the proof packet root.",
            "Checksums cover proof.md, proof.json, and proof.html.",
            "Verification also requires proof-manifest.json to be present and valid.",
        ],
    }


def proof_manifest_json(manifest: dict[str, Any]) -> str:
    """Serialize a proof manifest as sorted, pretty JSON."""
    return json.dumps(manifest, indent=2, sort_keys=True)


def file_manifest(name: str, content: bytes) -> dict[str, Any]:
    """Build one file entry for the proof manifest."""
    return {
        "name": name,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def resolve_output_path(project_root: Path, output_path: Path) -> Path:
    """Resolve an output path relative to the project root."""
    if output_path.is_absolute():
        return output_path.resolve()
    return (project_root / output_path).resolve()


def write_proof_packet(
    payload: dict[str, Any],
    *,
    project_root: Path,
    output_dir: Path | None = None,
    json_output: Path | None = None,
    summary_output: Path | None = None,
    html_output: Path | None = None,
    create_zip: bool = False,
    zip_output: Path | None = None,
) -> dict[str, Path]:
    """Write proof packet files and return written paths."""
    root = project_root.resolve()
    written: dict[str, Path] = {}
    packet_dir: Path | None = None

    summary_text = proof_markdown(payload)
    json_text = proof_json(payload) + "\n"
    html_text = proof_html(payload)
    packet_content = {
        PROOF_MARKDOWN: summary_text.encode("utf-8"),
        PROOF_JSON: json_text.encode("utf-8"),
        PROOF_HTML: html_text.encode("utf-8"),
    }
    manifest_text = proof_manifest_json(proof_manifest(payload, packet_content)) + "\n"

    if output_dir is not None:
        packet_dir = resolve_output_path(root, output_dir)
        if packet_dir.exists() and not packet_dir.is_dir():
            raise ProofError(f"Output path exists as a file: {packet_dir}")
        packet_dir.mkdir(parents=True, exist_ok=True)
        written["summary"] = packet_dir / PROOF_MARKDOWN
        written["json"] = packet_dir / PROOF_JSON
        written["html"] = packet_dir / PROOF_HTML
        written["manifest"] = packet_dir / PROOF_MANIFEST

    if summary_output is not None:
        summary_path = resolve_output_path(root, summary_output)
        ensure_output_file(summary_path)
        written["summary"] = summary_path

    if json_output is not None:
        json_path = resolve_output_path(root, json_output)
        ensure_output_file(json_path)
        written["json"] = json_path

    if html_output is not None:
        html_path = resolve_output_path(root, html_output)
        ensure_output_file(html_path)
        written["html"] = html_path

    if create_zip or zip_output is not None:
        if packet_dir is None:
            message = "--zip requires --output-dir so packet files can be built."
            raise ProofError(message)
        zip_path = resolve_zip_output(root, packet_dir, zip_output)
        written["zip"] = zip_path

    if "summary" in written:
        written["summary"].write_text(summary_text, encoding="utf-8")
    if "json" in written:
        written["json"].write_text(json_text, encoding="utf-8")
    if "html" in written:
        written["html"].write_text(html_text, encoding="utf-8")
    if "manifest" in written:
        written["manifest"].write_text(manifest_text, encoding="utf-8")
    if "zip" in written and packet_dir is not None:
        write_proof_zip(packet_dir, written["zip"])

    return written


def resolve_zip_output(
    project_root: Path,
    packet_dir: Path,
    zip_output: Path | None,
) -> Path:
    """Resolve and validate the archive output path."""
    zip_path = packet_dir / PROOF_ZIP
    if zip_output is not None:
        zip_path = resolve_output_path(project_root, zip_output)
        ensure_output_file(zip_path)
    elif zip_path.exists() and zip_path.is_dir():
        raise ProofError(f"Output path exists as a directory: {zip_path}")
    return zip_path


def write_proof_zip(packet_dir: Path, zip_path: Path) -> None:
    """Write a proof archive with relative file names only."""
    if not zip_path.parent.exists():
        zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        zip_path, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for name in REQUIRED_PACKET_FILES:
            archive.write(packet_dir / name, arcname=name)


def ensure_output_file(output_path: Path) -> None:
    """Validate an explicit output file path."""
    if output_path.exists() and output_path.is_dir():
        raise ProofError(f"Output path exists as a directory: {output_path}")
    if not output_path.parent.exists():
        message = f"Output parent directory does not exist: {output_path.parent}"
        raise ProofError(message)


def verify_proof_packet(target: Path) -> dict[str, Any]:
    """Verify a proof packet directory or zip archive."""
    selected = target.resolve()
    if selected.is_dir():
        return verify_packet_bytes(
            load_directory_packet(selected),
            target_label=selected.name,
            target_type="directory",
        )
    if selected.is_file():
        return verify_packet_bytes(
            load_zip_packet(selected),
            target_label=selected.name,
            target_type="zip",
        )
    return verification_result(
        target_label=selected.name or str(target),
        target_type="missing",
        checks=[failed_check("target_exists", "Verification target does not exist.")],
        files=[],
        errors=["Verification target does not exist."],
    )


def load_directory_packet(target: Path) -> dict[str, bytes]:
    """Load packet files from a directory."""
    files: dict[str, bytes] = {}
    for name in REQUIRED_PACKET_FILES:
        path = target / name
        if path.is_file():
            files[name] = path.read_bytes()
    return files


def load_zip_packet(target: Path) -> dict[str, bytes]:
    """Load packet files from a zip archive without extracting local paths."""
    files: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(target) as archive:
            for name in archive.namelist():
                if Path(name).is_absolute() or ".." in Path(name).parts:
                    continue
                if name in REQUIRED_PACKET_FILES:
                    files[name] = archive.read(name)
    except zipfile.BadZipFile:
        return files
    return files


def verify_packet_bytes(
    packet_files: dict[str, bytes],
    *,
    target_label: str,
    target_type: str,
) -> dict[str, Any]:
    """Verify loaded proof packet bytes."""
    checks: list[dict[str, str]] = []
    errors: list[str] = []

    missing = [name for name in REQUIRED_PACKET_FILES if name not in packet_files]
    if missing:
        message = "Missing required file(s): " + ", ".join(missing)
        checks.append(failed_check("required_files", message))
        errors.append(message)
        return verification_result(
            target_label=target_label,
            target_type=target_type,
            checks=checks,
            files=[],
            errors=errors,
        )
    checks.append(passed_check("required_files", "Required proof files are present."))

    proof_json_payload = load_json_check(
        packet_files[PROOF_JSON],
        name=PROOF_JSON,
        checks=checks,
        errors=errors,
    )
    manifest_payload = load_json_check(
        packet_files[PROOF_MANIFEST],
        name=PROOF_MANIFEST,
        checks=checks,
        errors=errors,
    )
    if proof_json_payload is None or manifest_payload is None:
        return verification_result(
            target_label=target_label,
            target_type=target_type,
            checks=checks,
            files=[],
            errors=errors,
        )

    manifest_files = manifest_payload.get("files")
    if not isinstance(manifest_files, list):
        message = "Manifest files field is missing or invalid."
        checks.append(failed_check("manifest_files", message))
        errors.append(message)
        return verification_result(
            target_label=target_label,
            target_type=target_type,
            checks=checks,
            files=[],
            errors=errors,
        )

    manifest_by_name = {
        str(item.get("name")): item
        for item in manifest_files
        if isinstance(item, dict) and "name" in item
    }
    listed = set(manifest_by_name)
    expected = set(MANIFEST_CONTENT_FILES)
    if listed != expected:
        message = "Manifest must list proof.md, proof.json, and proof.html."
        checks.append(failed_check("manifest_expected_files", message))
        errors.append(message)
    else:
        checks.append(
            passed_check(
                "manifest_expected_files",
                "Manifest lists expected proof content files.",
            )
        )

    verified_files: list[dict[str, Any]] = []
    for name in MANIFEST_CONTENT_FILES:
        item = manifest_by_name.get(name)
        if not isinstance(item, dict):
            continue
        content = packet_files[name]
        actual_size = len(content)
        actual_sha = hashlib.sha256(content).hexdigest()
        expected_size = item.get("size_bytes")
        expected_sha = item.get("sha256")
        file_status = "passed"
        if expected_size != actual_size or expected_sha != actual_sha:
            file_status = "failed"
            message = f"Checksum or size mismatch for {name}."
            checks.append(failed_check(f"file_integrity:{name}", message))
            errors.append(message)
        else:
            checks.append(
                passed_check(f"file_integrity:{name}", f"{name} matches manifest.")
            )
        verified_files.append(
            {
                "name": name,
                "status": file_status,
                "size_bytes": actual_size,
                "sha256": actual_sha,
            }
        )

    return verification_result(
        target_label=target_label,
        target_type=target_type,
        checks=checks,
        files=verified_files,
        errors=errors,
    )


def load_json_check(
    content: bytes,
    *,
    name: str,
    checks: list[dict[str, str]],
    errors: list[str],
) -> dict[str, Any] | None:
    """Load JSON and record a verification check."""
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        message = f"{name} is not valid JSON."
        checks.append(failed_check(f"valid_json:{name}", message))
        errors.append(message)
        return None
    if not isinstance(payload, dict):
        message = f"{name} must contain a JSON object."
        checks.append(failed_check(f"valid_json:{name}", message))
        errors.append(message)
        return None
    checks.append(passed_check(f"valid_json:{name}", f"{name} is valid JSON."))
    return payload


def verification_result(
    *,
    target_label: str,
    target_type: str,
    checks: list[dict[str, str]],
    files: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    """Build a stable verification result."""
    verified = not errors and all(check["status"] == "passed" for check in checks)
    return {
        "status": "passed" if verified else "failed",
        "verified": verified,
        "target": target_label,
        "target_type": target_type,
        "checks": checks,
        "files": files,
        "errors": errors,
    }


def verification_json(result: dict[str, Any]) -> str:
    """Serialize verification output as sorted, pretty JSON."""
    return json.dumps(result, indent=2, sort_keys=True)


def passed_check(name: str, message: str) -> dict[str, str]:
    """Build a passed verification check."""
    return {"name": name, "status": "passed", "message": message}


def failed_check(name: str, message: str) -> dict[str, str]:
    """Build a failed verification check."""
    return {"name": name, "status": "failed", "message": message}
