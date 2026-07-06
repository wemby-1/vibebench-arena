"""Evidence room package helpers for VibeBench Arena."""

import html
import json
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vibebench.proof import proof_payload, verify_proof_packet, write_proof_packet
from vibebench.site_check import BANNED_CLAIMS_OR_MARKERS
from vibebench.site_preview import verify_site_preview, write_site_preview

EVIDENCE_HTML = "evidence-room.html"
EVIDENCE_MARKDOWN = "evidence-room.md"
EVIDENCE_JSON = "evidence-room.json"
EVIDENCE_ZIP = "evidence-room.zip"
LANDING_HTML = "index.html"
REVIEW_HUB_HTML = "review-hub.html"
REVIEWER_GUIDE_MD = "reviewer-guide.md"
REVIEW_SCORECARD_HTML = "review-scorecard.html"
REVIEW_SCORECARD_MARKDOWN = "review-scorecard.md"
REVIEW_SCORECARD_JSON = "review-scorecard.json"
REVIEW_SCORECARD_VERSION = "vibebench.review-scorecard.v1"
TRUST_CENTER_HTML = "trust-center.html"
TRUST_CENTER_MARKDOWN = "trust-center.md"
PROOF_DIR = "proof-packet"
SITE_PREVIEW_DIR = "site-preview"
TOP_LEVEL_FILES = (
    LANDING_HTML,
    REVIEW_HUB_HTML,
    REVIEWER_GUIDE_MD,
    TRUST_CENTER_HTML,
    TRUST_CENTER_MARKDOWN,
    REVIEW_SCORECARD_HTML,
    REVIEW_SCORECARD_MARKDOWN,
    REVIEW_SCORECARD_JSON,
    EVIDENCE_HTML,
    EVIDENCE_MARKDOWN,
    EVIDENCE_JSON,
)
PROOF_FILES = (
    "proof.html",
    "proof.json",
    "proof.md",
    "proof-manifest.json",
    "proof.zip",
)
SITE_PREVIEW_FILES = (
    "index.html",
    "showcase.html",
    "site-check.json",
    "site-preview.md",
    "site-preview.zip",
)
REQUIRED_FILES = (
    *TOP_LEVEL_FILES,
    *(f"{PROOF_DIR}/{name}" for name in PROOF_FILES),
    *(f"{SITE_PREVIEW_DIR}/{name}" for name in SITE_PREVIEW_FILES),
)
COMMANDS = (
    "python3 -m vibebench proof --output-dir PATH --zip",
    "python3 -m vibebench site-preview --output-dir PATH --zip",
    "python3 -m vibebench evidence-room --output-dir PATH --zip",
    "python3 -m vibebench evidence-room --verify PATH",
)
PACKAGE_LINK_REWRITES = {
    'href="index.html"': 'href="site-preview/index.html"',
    'href="showcase.html"': 'href="site-preview/showcase.html"',
    'href="evaluate.md"': 'href="site-preview/evaluate.md"',
    'href="adoption.md"': 'href="site-preview/adoption.md"',
    'href="pages.md"': 'href="site-preview/pages.md"',
}
FORBIDDEN_LOCAL_PATHS = ("/tmp/", "/home/", "/data/code/")
FORBIDDEN_HTML = ("http://", "https://", "<script", "</script")
EXTRA_BANNED_MARKERS = (
    "fake customer",
    "fake funding",
    "fake revenue",
    "fake investor",
    "guaranteed funding",
    "guaranteed stars",
    "guaranteed secure",
    "market leader",
    "best in the world",
    "soc 2 certified",
    "iso 27001 certified",
    "audited by",
    "independently audited",
    "enterprise certified",
    "millions of users",
    "revenue",
    "unicorn",
)
FORBIDDEN_ZIP_PARTS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
FORBIDDEN_ZIP_PREFIXES = (
    ".vibebench/runs/",
    "build/",
    "dist/",
)


class EvidenceRoomError(Exception):
    """Raised when an evidence room cannot be written safely."""


def evidence_room_payload(
    *,
    root_label: str,
    output_dir: Path | None = None,
    zip_output: Path | None = None,
    status: str = "ready",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a stable evidence room payload without absolute local paths."""
    output_label = "PATH" if output_dir is not None else None
    zip_label = "PATH/evidence-room.zip" if zip_output is not None else None
    return {
        "status": status,
        "generated_at": generated_time(),
        "root": root_label,
        "output_dir": output_label,
        "zip_output": zip_label,
        "components": {
            "proof_packet": {
                "path": PROOF_DIR,
                "files": [f"{PROOF_DIR}/{name}" for name in PROOF_FILES],
            },
            "site_preview": {
                "path": SITE_PREVIEW_DIR,
                "files": [
                    f"{SITE_PREVIEW_DIR}/{name}" for name in SITE_PREVIEW_FILES
                ],
            },
        },
        "files": list(REQUIRED_FILES),
        "verification": {
            "status": "not-run",
            "summary": "Run python3 -m vibebench evidence-room --verify PATH.",
        },
        "commands": list(COMMANDS),
        "warnings": warnings or [],
    }


def write_evidence_room(
    *,
    project_root: Path,
    site_root: Path,
    root_label: str,
    output_dir: Path,
    create_zip: bool = False,
    zip_output: Path | None = None,
) -> dict[str, Any]:
    """Write an evidence room directory and optional zip archive."""
    output_dir.mkdir(parents=True, exist_ok=True)
    proof_dir = output_dir / PROOF_DIR
    site_preview_dir = output_dir / SITE_PREVIEW_DIR

    write_proof_packet(
        proof_payload(project_root),
        project_root=project_root,
        output_dir=proof_dir,
        create_zip=True,
    )
    write_site_preview(
        project_root=project_root,
        site_root=site_root,
        root_label=root_label,
        output_dir=site_preview_dir,
        create_zip=True,
    )

    nested_checks = [
        verify_proof_packet(proof_dir),
        verify_proof_packet(proof_dir / "proof.zip"),
        verify_site_preview(site_preview_dir),
        verify_site_preview(site_preview_dir / "site-preview.zip"),
    ]
    if not all(result["verified"] for result in nested_checks):
        raise EvidenceRoomError("Evidence room nested verification failed.")

    payload = evidence_room_payload(
        root_label=root_label,
        output_dir=output_dir,
        zip_output=zip_output,
        status="ready",
    )
    payload["verification"] = {
        "status": "passed",
        "summary": "Proof packet and static site preview verified.",
    }
    scorecard_payload = review_scorecard_payload(payload)
    output_dir.joinpath(EVIDENCE_JSON).write_text(
        evidence_room_json(payload) + "\n",
        encoding="utf-8",
    )
    output_dir.joinpath(EVIDENCE_MARKDOWN).write_text(
        evidence_room_markdown(payload),
        encoding="utf-8",
    )
    output_dir.joinpath(EVIDENCE_HTML).write_text(
        evidence_room_html(payload),
        encoding="utf-8",
    )
    output_dir.joinpath(LANDING_HTML).write_text(
        evidence_room_landing_html(payload),
        encoding="utf-8",
    )
    output_dir.joinpath(REVIEW_SCORECARD_JSON).write_text(
        evidence_room_json(scorecard_payload) + "\n",
        encoding="utf-8",
    )
    output_dir.joinpath(REVIEW_SCORECARD_MARKDOWN).write_text(
        review_scorecard_markdown(scorecard_payload),
        encoding="utf-8",
    )
    output_dir.joinpath(REVIEW_SCORECARD_HTML).write_text(
        review_scorecard_html(scorecard_payload),
        encoding="utf-8",
    )
    write_review_files(site_root, output_dir)
    write_trust_center_files(site_root, output_dir)

    written = {
        "output_dir": "PATH",
        "files": list(REQUIRED_FILES),
    }
    if create_zip or zip_output is not None:
        selected_zip = (
            zip_output if zip_output is not None else output_dir / EVIDENCE_ZIP
        )
        write_evidence_room_zip(output_dir, selected_zip)
        written["zip"] = "PATH/evidence-room.zip"
    payload["written"] = written
    return payload


def write_review_files(site_root: Path, output_dir: Path) -> None:
    """Copy package-safe review hub and reviewer guide files."""
    review_hub = read_required_site_file(site_root, REVIEW_HUB_HTML)
    for source, target in PACKAGE_LINK_REWRITES.items():
        review_hub = review_hub.replace(source, target)
    output_dir.joinpath(REVIEW_HUB_HTML).write_text(review_hub, encoding="utf-8")

    reviewer_guide = read_required_site_file(site_root, REVIEWER_GUIDE_MD)
    output_dir.joinpath(REVIEWER_GUIDE_MD).write_text(
        reviewer_guide,
        encoding="utf-8",
    )


def write_trust_center_files(site_root: Path, output_dir: Path) -> None:
    """Copy package-safe Trust Center files."""
    trust_html = read_required_site_file(site_root, TRUST_CENTER_HTML)
    output_dir.joinpath(TRUST_CENTER_HTML).write_text(
        trust_html,
        encoding="utf-8",
    )

    trust_markdown = read_required_site_file(site_root, TRUST_CENTER_MARKDOWN)
    trust_markdown = trust_markdown.replace(
        "/tmp/vibebench-evidence-room",
        "PATH",
    )
    output_dir.joinpath(TRUST_CENTER_MARKDOWN).write_text(
        trust_markdown,
        encoding="utf-8",
    )


def read_required_site_file(site_root: Path, name: str) -> str:
    """Read a required review file from the site root."""
    path = site_root / name
    if not path.is_file():
        raise EvidenceRoomError(f"Required site file is missing: {path}")
    return path.read_text(encoding="utf-8")


def write_zip_only_evidence_room(
    *,
    project_root: Path,
    site_root: Path,
    root_label: str,
    zip_output: Path,
) -> dict[str, Any]:
    """Write only an evidence room zip using a temporary directory."""
    with tempfile.TemporaryDirectory(prefix="vibebench-evidence-room-") as tmp:
        temp_dir = Path(tmp) / "evidence-room"
        return write_evidence_room(
            project_root=project_root,
            site_root=site_root,
            root_label=root_label,
            output_dir=temp_dir,
            create_zip=True,
            zip_output=zip_output,
        )


def write_evidence_room_zip(room_dir: Path, zip_path: Path) -> None:
    """Write an evidence room zip with safe relative names only."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(room_dir.rglob("*")):
            if not path.is_file() or path.resolve() == zip_path.resolve():
                continue
            if path.name == EVIDENCE_ZIP:
                continue
            relative_name = path.relative_to(room_dir).as_posix()
            if not safe_zip_name(relative_name):
                continue
            archive.write(path, arcname=relative_name)


def evidence_room_json(payload: dict[str, Any]) -> str:
    """Serialize evidence room JSON stably."""
    return json.dumps(payload, indent=2, sort_keys=True)


def write_evidence_room_json(payload: dict[str, Any], output: Path) -> None:
    """Write evidence room JSON to disk."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(evidence_room_json(payload) + "\n", encoding="utf-8")


def evidence_room_markdown(payload: dict[str, Any]) -> str:
    """Render the top-level evidence room Markdown."""
    lines = [
        "# VibeBench Evidence Room",
        "",
        f"- Generated time: {payload['generated_at']}",
        f"- Status: {payload['status']}",
        "",
        "## Start here",
        "",
        "- `index.html`",
        "- `review-hub.html`",
        "- `reviewer-guide.md`",
        "- `trust-center.html`",
        "- `trust-center.md`",
        "- `review-scorecard.html`",
        "- `review-scorecard.md`",
        "- `review-scorecard.json`",
        "",
        "## Proof packet",
        "",
        "- `proof-packet/proof.html`",
        "- `proof-packet/proof.json`",
        "- `proof-packet/proof.md`",
        "- `proof-packet/proof-manifest.json`",
        "- `proof-packet/proof.zip`",
        "",
        "## Static site preview",
        "",
        "- `site-preview/index.html`",
        "- `site-preview/showcase.html`",
        "- `site-preview/site-check.json`",
        "- `site-preview/site-preview.md`",
        "- `site-preview/site-preview.zip`",
        "",
        "## Local reproduction",
        "",
    ]
    lines.extend(f"- `{command}`" for command in COMMANDS[:3])
    lines.extend(
        [
            "",
            "## Verification",
            "",
            f"- `{COMMANDS[3]}`",
            "",
            "## What this does not claim",
            "",
            (
                "- No commercial outcome, adoption, benchmark dominance, or "
                "correctness promises."
            ),
            (
                "- No automatic publishing, releases, repository settings changes, "
                "or GitHub Pages enablement."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def evidence_room_html(payload: dict[str, Any]) -> str:
    """Render self-contained static evidence room HTML."""
    links = [
        "index.html",
        "review-hub.html",
        "reviewer-guide.md",
        "trust-center.html",
        "trust-center.md",
        "review-scorecard.html",
        "review-scorecard.md",
        "review-scorecard.json",
        "proof-packet/proof.html",
        "proof-packet/proof.json",
        "proof-packet/proof.md",
        "proof-packet/proof-manifest.json",
        "proof-packet/proof.zip",
        "site-preview/index.html",
        "site-preview/showcase.html",
        "site-preview/site-check.json",
        "site-preview/site-preview.md",
        "site-preview/site-preview.zip",
    ]
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            "  <title>VibeBench Evidence Room</title>",
            "  <style>",
            evidence_room_css(),
            "  </style>",
            "</head>",
            "<body>",
            '  <main class="page">',
            "    <header>",
            "      <h1>VibeBench Evidence Room</h1>",
            (
                "      <p>Local-first evidence package for reviewing VibeBench "
                "proof and static site preview artifacts.</p>"
            ),
            "    </header>",
            html_section(
                "Summary",
                [
                    ("Status", str(payload["status"])),
                    ("Generated time", str(payload["generated_at"])),
                    ("Root", str(payload["root"])),
                ],
            ),
            html_list_section("Included artifacts", links, link_items=True),
            html_list_section("Local reproduction", list(COMMANDS)),
            html_list_section(
                "What this does not claim",
                [
                    (
                        "No commercial outcome, adoption, benchmark dominance, "
                        "or correctness promises."
                    ),
                    (
                        "No automatic publishing, releases, repository settings "
                        "changes, or GitHub Pages enablement."
                    ),
                ],
            ),
            "  </main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def evidence_room_landing_html(payload: dict[str, Any]) -> str:
    """Render the self-opening evidence room landing page."""
    rows = [
        ("Evidence summary", "evidence-room.html"),
        ("Public review flow", "review-hub.html"),
        ("3-minute review path", "reviewer-guide.md"),
        ("Trust Center", "trust-center.html"),
        ("Reviewer scorecard", "review-scorecard.html"),
        ("Proof details", "proof-packet/proof.html"),
        ("Static site preview", "site-preview/index.html"),
    ]
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            "  <title>VibeBench Evidence Room Start</title>",
            "  <style>",
            evidence_room_css(),
            "  </style>",
            "</head>",
            "<body>",
            '  <main class="page">',
            "    <header>",
            "      <h1>Start here</h1>",
            (
                "      <p>This downloaded VibeBench evidence room is a "
                "local-first review package. Open the linked files directly "
                "from this folder to inspect the evidence.</p>"
            ),
            "    </header>",
            html_list_section(
                "What this package contains",
                [
                    "evidence-room.html summary",
                    "review-hub.html public review flow",
                    "reviewer-guide.md 3-minute review path",
                    "trust-center.html project-maintained safety documentation",
                    "trust-center.md Markdown trust notes",
                    "review-scorecard.html neutral checklist",
                    "review-scorecard.md Markdown checklist",
                    "review-scorecard.json machine-readable checklist",
                    "proof-packet/proof.html proof details",
                    "site-preview/index.html static site preview",
                    "evidence-room.json machine-readable summary",
                    "evidence-room.zip shareable archive",
                ],
            ),
            html_link_table_section("Open first", rows),
            html_list_section(
                "Trust Center",
                [
                    (
                        "Use trust-center.html or trust-center.md for "
                        "project-maintained safety, privacy, reproducibility, "
                        "and artifact-boundary notes."
                    ),
                    (
                        "The Trust Center is not a third-party audit or "
                        "compliance certification."
                    ),
                ],
            ),
            html_list_section(
                "Reviewer scorecard",
                [
                    (
                        "Use review-scorecard.html or review-scorecard.md as "
                        "a neutral checklist. It is a reviewer aid, not an "
                        "approval badge."
                    ),
                    "review-scorecard.json contains the same checklist structure.",
                ],
            ),
            html_list_section(
                "Verify this package",
                ["python3 -m vibebench evidence-room --verify PATH"],
            ),
            html_list_section(
                "Honest limits",
                [
                    (
                        "This package helps reviewers inspect evidence; it "
                        "does not replace human review or claim correctness."
                    ),
                    (
                        "It does not publish a site, change repository "
                        "settings, create releases, or upload packages."
                    ),
                ],
            ),
            "  </main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def review_scorecard_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a neutral reviewer scorecard payload."""
    return {
        "status": "ready",
        "project": "VibeBench Arena",
        "generated_at": payload["generated_at"],
        "scorecard_version": REVIEW_SCORECARD_VERSION,
        "sections": [
            scorecard_section(
                "Local reproducibility",
                "Check whether a reviewer can reproduce the package locally.",
                [
                    scorecard_check(
                        "evidence-room-verify",
                        "Verify the downloaded evidence room.",
                        "python3 -m vibebench evidence-room --verify PATH",
                        "Verifier exits successfully for an untampered package.",
                    ),
                    scorecard_check(
                        "dry-run-json",
                        "Inspect the planned local CI pipeline as JSON.",
                        "python3 -m vibebench ci --dry-run --json",
                        "JSON output is parseable and lists the planned steps.",
                    ),
                ],
            ),
            scorecard_section(
                "CI reproducibility",
                "Check whether CI-visible artifacts match the local review flow.",
                [
                    scorecard_check(
                        "ci-artifacts",
                        (
                            "Confirm proof, site preview, and evidence-room "
                            "artifacts exist."
                        ),
                        None,
                        "CI artifacts are downloadable and named consistently.",
                    ),
                    scorecard_check(
                        "ci-summary",
                        "Confirm the CI summary links reviewers to evidence.",
                        None,
                        "Summary lists the evidence room and related artifacts.",
                    ),
                ],
            ),
            scorecard_section(
                "Evidence-room artifact completeness",
                "Check whether the top-level package is self-opening.",
                [
                    scorecard_check(
                        "landing-page",
                        "Open index.html first.",
                        None,
                        "Landing page links to scorecard, proof, and site preview.",
                    ),
                    scorecard_check(
                        "scorecard-files",
                        "Confirm scorecard HTML, Markdown, and JSON exist.",
                        None,
                        (
                            "review-scorecard.html, review-scorecard.md, and "
                            "review-scorecard.json are present."
                        ),
                    ),
                ],
            ),
            scorecard_section(
                "Proof packet completeness",
                "Check whether the proof packet can stand on its own.",
                [
                    scorecard_check(
                        "proof-verify",
                        "Verify the nested proof packet.",
                        "python3 -m vibebench proof --verify PATH/proof-packet",
                        "Proof packet verification succeeds.",
                    ),
                    scorecard_check(
                        "proof-html",
                        "Open proof-packet/proof.html.",
                        None,
                        "Proof HTML is self-contained and readable.",
                    ),
                ],
            ),
            scorecard_section(
                "Static site preview completeness",
                "Check whether the public docs preview is packaged.",
                [
                    scorecard_check(
                        "site-preview-verify",
                        "Verify the nested static site preview.",
                        "python3 -m vibebench site-preview --verify PATH/site-preview",
                        "Site preview verification succeeds.",
                    ),
                    scorecard_check(
                        "site-check",
                        "Run the static site readiness check.",
                        "python3 -m vibebench site-check",
                        "Site check exits successfully.",
                    ),
                ],
            ),
            scorecard_section(
                "JSON output purity",
                "Check whether machine-readable commands stay parseable.",
                [
                    scorecard_check(
                        "evidence-room-json",
                        "Run evidence-room JSON output.",
                        "python3 -m vibebench evidence-room --json",
                        "Stdout is valid JSON with no human table text.",
                    ),
                    scorecard_check(
                        "ci-json",
                        "Run dry-run CI JSON output.",
                        "python3 -m vibebench ci --dry-run --json",
                        "Stdout is valid JSON with no human table text.",
                    ),
                ],
            ),
            scorecard_section(
                "Offline / local-first behavior",
                "Check whether the core review package works from local files.",
                [
                    scorecard_check(
                        "offline-files",
                        "Open package HTML files directly from disk.",
                        None,
                        "Core package files do not require remote assets.",
                    )
                ],
            ),
            scorecard_section(
                "Safety of generated static HTML",
                "Check whether generated HTML avoids unsafe publishing markers.",
                [
                    scorecard_check(
                        "static-html",
                        "Inspect generated package HTML.",
                        None,
                        (
                            "HTML contains no scripts, remote URLs, or "
                            "absolute local paths."
                        ),
                    )
                ],
            ),
            scorecard_section(
                "No fake traction or exaggerated claims",
                "Check whether the package stays factual.",
                [
                    scorecard_check(
                        "honest-claims",
                        "Review public-facing text for unsupported claims.",
                        None,
                        "Text avoids fake traction, endorsement, and dominance claims.",
                    )
                ],
            ),
            scorecard_section(
                "Adoption readiness",
                "Check whether a small team can pilot the workflow.",
                [
                    scorecard_check(
                        "pilot-path",
                        "Compare the adoption guide with local artifacts.",
                        None,
                        "Reviewer can identify a small, reversible pilot path.",
                    )
                ],
            ),
            scorecard_section(
                "Remaining risks / reviewer notes",
                "Capture open questions before adoption or external evaluation.",
                [
                    scorecard_check(
                        "reviewer-notes",
                        "Record questions, gaps, or follow-up checks.",
                        None,
                        "Reviewer notes are explicit rather than implied.",
                    )
                ],
            ),
        ],
    }


def scorecard_section(
    name: str,
    purpose: str,
    checks: list[dict[str, str | None]],
) -> dict[str, Any]:
    """Build one scorecard section."""
    return {"name": name, "purpose": purpose, "checks": checks}


def scorecard_check(
    check_id: str,
    label: str,
    command: str | None,
    expected: str,
) -> dict[str, str | None]:
    """Build one neutral scorecard check."""
    return {
        "id": check_id,
        "label": label,
        "command": command,
        "expected": expected,
        "reviewer_status": "not_reviewed",
    }


def review_scorecard_markdown(payload: dict[str, Any]) -> str:
    """Render the reviewer scorecard as Markdown."""
    lines = [
        "# VibeBench Arena Reviewer Scorecard",
        "",
        "## How to use this scorecard",
        "",
        (
            "Use this neutral checklist while inspecting a downloaded evidence "
            "room. Mark items only after you personally review the artifact or "
            "command output."
        ),
        "",
        "## Verification commands",
        "",
        "- `python3 -m vibebench evidence-room --verify PATH`",
        "- `python3 -m vibebench proof --verify PATH/proof-packet`",
        "- `python3 -m vibebench site-preview --verify PATH/site-preview`",
        "- `python3 -m vibebench site-check`",
        "- `python3 -m vibebench ci --dry-run --json`",
        "",
    ]
    for section in payload["sections"]:
        lines.extend(
            [
                f"## {section['name']}",
                "",
                str(section["purpose"]),
                "",
            ]
        )
        for item in section["checks"]:
            command = item.get("command")
            command_text = f" Command: `{command}`." if command else ""
            lines.append(
                f"- [ ] {item['label']}{command_text} "
                f"Expected: {item['expected']} "
                f"Status: `{item['reviewer_status']}`."
            )
        lines.append("")
    lines.extend(
        [
            "## Final reviewer notes",
            "",
            "- [ ] Notes recorded:",
            "",
        ]
    )
    return "\n".join(lines)


def review_scorecard_html(payload: dict[str, Any]) -> str:
    """Render the reviewer scorecard as static HTML."""
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            "  <title>VibeBench Arena Reviewer Scorecard</title>",
            "  <style>",
            evidence_room_css(),
            "  </style>",
            "</head>",
            "<body>",
            '  <main class="page">',
            "    <header>",
            "      <h1>VibeBench Arena Reviewer Scorecard</h1>",
            (
                "      <p>A neutral checklist for reviewing the downloaded "
                "evidence room without treating project claims as proof.</p>"
            ),
            "    </header>",
            html_list_section(
                "Open related evidence",
                [
                    "index.html",
                    "evidence-room.html",
                    "review-hub.html",
                    "reviewer-guide.md",
                    "proof-packet/proof.html",
                    "site-preview/index.html",
                ],
                link_items=True,
            ),
            html_list_section(
                "Verification commands",
                [
                    "python3 -m vibebench evidence-room --verify PATH",
                    "python3 -m vibebench proof --verify PATH/proof-packet",
                    "python3 -m vibebench site-preview --verify PATH/site-preview",
                    "python3 -m vibebench site-check",
                    "python3 -m vibebench ci --dry-run --json",
                ],
            ),
            *scorecard_html_sections(payload),
            "  </main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def scorecard_html_sections(payload: dict[str, Any]) -> list[str]:
    """Render scorecard sections as HTML fragments."""
    sections = []
    for section in payload["sections"]:
        lines = [
            "    <section>",
            f"      <h2>{escape(section['name'])}</h2>",
            f"      <p>{escape(section['purpose'])}</p>",
            "      <ul>",
        ]
        for item in section["checks"]:
            command = item.get("command")
            command_text = (
                f" Command: <code>{escape(command)}</code>." if command else ""
            )
            expected = html_sentence(item["expected"])
            lines.append(
                "        <li>"
                f"<strong>{html_sentence(item['label'])}</strong>"
                f"{command_text} Expected: {expected} "
                f"Status: <code>{escape(item['reviewer_status'])}</code>."
                "</li>"
            )
        lines.extend(["      </ul>", "    </section>"])
        sections.append("\n".join(lines))
    sections.append(
        "\n".join(
            [
                "    <section>",
                "      <h2>Final reviewer notes</h2>",
                "      <p>Record open questions, gaps, or follow-up checks.</p>",
                "    </section>",
            ]
        )
    )
    return sections


def html_sentence(value: object) -> str:
    """Escape a value and ensure it ends with one sentence mark."""
    text = str(value)
    suffix = "" if text.endswith((".", "!", "?")) else "."
    return escape(text + suffix)


def evidence_room_css() -> str:
    """Return inline CSS for evidence-room.html."""
    return """
    :root { color-scheme: light; }
    body {
      margin: 0;
      background: #f5f3ef;
      color: #20262d;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }
    .page { max-width: 980px; margin: 0 auto; padding: 40px 20px 56px; }
    header {
      border-bottom: 3px solid #2d6f6b;
      margin-bottom: 28px;
      padding-bottom: 18px;
    }
    h1, h2 { line-height: 1.2; margin: 0; }
    h1 { font-size: 2.25rem; }
    h2 { font-size: 1.25rem; margin-bottom: 12px; }
    header p { color: #52606b; font-size: 1.05rem; margin: 10px 0 0; }
    section {
      background: #ffffff;
      border: 1px solid #d7d0c7;
      border-radius: 8px;
      margin: 16px 0;
      padding: 18px;
    }
    dl {
      display: grid;
      grid-template-columns: minmax(140px, 200px) 1fr;
      gap: 8px 16px;
      margin: 0;
    }
    dt { color: #52606b; font-weight: 700; }
    dd { margin: 0; overflow-wrap: anywhere; }
    ul { margin: 0; padding-left: 1.25rem; }
    li + li { margin-top: 6px; }
    code {
      background: #eef1f4;
      border-radius: 4px;
      padding: 0.1rem 0.3rem;
      overflow-wrap: anywhere;
    }
    a { color: #295f87; font-weight: 700; }
    @media (max-width: 640px) {
      .page { padding: 24px 14px 40px; }
      h1 { font-size: 1.8rem; }
      dl { grid-template-columns: 1fr; }
    }
    """.strip()


def html_section(title: str, rows: list[tuple[str, str]]) -> str:
    """Render a section with escaped definition rows."""
    lines = [
        "    <section>",
        f"      <h2>{escape(title)}</h2>",
        "      <dl>",
    ]
    for key, value in rows:
        lines.append(f"        <dt>{escape(key)}</dt>")
        lines.append(f"        <dd>{escape(value)}</dd>")
    lines.extend(["      </dl>", "    </section>"])
    return "\n".join(lines)


def html_list_section(
    title: str,
    values: list[str],
    *,
    link_items: bool = False,
) -> str:
    """Render a section with escaped list values."""
    lines = [
        "    <section>",
        f"      <h2>{escape(title)}</h2>",
        "      <ul>",
    ]
    for value in values:
        if link_items:
            escaped = escape(value)
            lines.append(f'        <li><a href="{escaped}">{escaped}</a></li>')
        elif value.startswith("python3"):
            lines.append(f"        <li><code>{escape(value)}</code></li>")
        else:
            lines.append(f"        <li>{escape(value)}</li>")
    lines.extend(["      </ul>", "    </section>"])
    return "\n".join(lines)


def html_link_table_section(title: str, rows: list[tuple[str, str]]) -> str:
    """Render a section of relative package links."""
    lines = [
        "    <section>",
        f"      <h2>{escape(title)}</h2>",
        "      <dl>",
    ]
    for label, target in rows:
        escaped_target = escape(target)
        lines.append(f"        <dt>{escape(label)}</dt>")
        lines.append(
            f'        <dd><a href="{escaped_target}">{escaped_target}</a></dd>'
        )
    lines.extend(["      </dl>", "    </section>"])
    return "\n".join(lines)


def verify_evidence_room(target: Path) -> dict[str, Any]:
    """Verify an evidence room directory or zip archive."""
    if target.is_dir():
        return verify_evidence_room_directory(target)
    if target.is_file() and target.suffix == ".zip":
        return verify_evidence_room_zip(target)
    return verification_payload(
        target,
        target_type="missing",
        checks=[
            check("target_exists", False, "Target is not a directory or zip file.")
        ],
    )


def verify_evidence_room_directory(target: Path) -> dict[str, Any]:
    """Verify an evidence room directory."""
    available = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file()
    }
    checks = [
        required_files_check(available),
        valid_evidence_json_check(target / EVIDENCE_JSON),
        valid_scorecard_json_check(target / REVIEW_SCORECARD_JSON),
        top_level_safety_check(target),
        proof_component_check(target),
        site_preview_component_check(target),
        nested_zip_component_check(
            "proof_zip_verification",
            verify_proof_packet(target / PROOF_DIR / "proof.zip"),
        ),
        nested_zip_component_check(
            "site_preview_zip_verification",
            verify_site_preview(target / SITE_PREVIEW_DIR / "site-preview.zip"),
        ),
    ]
    return verification_payload(target, target_type="directory", checks=checks)


def verify_evidence_room_zip(target: Path) -> dict[str, Any]:
    """Verify an evidence room zip without trusting archive paths."""
    checks: list[dict[str, str]] = []
    try:
        with zipfile.ZipFile(target) as archive:
            names = archive.namelist()
            safe = all(safe_zip_name(name) for name in names)
            checks.append(
                check(
                    "zip_entry_names",
                    safe,
                    (
                        "Zip entries use safe relative names."
                        if safe
                        else "Zip contains unsafe entry names."
                    ),
                )
            )
            checks.append(required_files_check(set(names)))
            if safe:
                with tempfile.TemporaryDirectory(
                    prefix="vibebench-evidence-room-verify-"
                ) as tmp:
                    temp_dir = Path(tmp) / "room"
                    temp_dir.mkdir()
                    for name in names:
                        if safe_zip_name(name):
                            destination = temp_dir / name
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            destination.write_bytes(archive.read(name))
                    nested = verify_evidence_room_directory(temp_dir)
                    checks.extend(
                        prefixed_checks("zip_content", nested["checks"])
                    )
    except zipfile.BadZipFile:
        checks.append(check("valid_zip", False, "Target is not a valid zip file."))
    return verification_payload(target, target_type="zip", checks=checks)


def required_files_check(files: set[str]) -> dict[str, str]:
    """Check required evidence room files."""
    missing = [name for name in REQUIRED_FILES if name not in files]
    return check(
        "required_files",
        not missing,
        (
            "Required evidence room files are present."
            if not missing
            else "Missing required evidence room files: " + ", ".join(missing)
        ),
    )


def valid_evidence_json_check(path: Path) -> dict[str, str]:
    """Check evidence-room.json is valid JSON."""
    return valid_json_file_check(path, "valid_json:evidence-room.json")


def valid_scorecard_json_check(path: Path) -> dict[str, str]:
    """Check review-scorecard.json is valid JSON."""
    return valid_json_file_check(path, "valid_json:review-scorecard.json")


def valid_json_file_check(path: Path, name: str) -> dict[str, str]:
    """Check a generated JSON file can be parsed."""
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return check(
            name,
            False,
            f"{path.name} is missing or invalid JSON.",
        )
    return check(
        name,
        True,
        f"{path.name} is valid JSON.",
    )


def top_level_safety_check(target: Path) -> dict[str, str]:
    """Check top-level generated files for unsafe content."""
    matches: list[str] = []
    for name in TOP_LEVEL_FILES:
        path = target / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        matches.extend(unsafe_text_matches(name, text))
    return check(
        "top_level_safety",
        not matches,
        (
            (
                "Top-level generated files avoid unsafe paths, scripts, remote "
                "URLs, and banned claims."
            )
            if not matches
            else "Unsafe top-level content found: " + "; ".join(matches)
        ),
    )


def proof_component_check(target: Path) -> dict[str, str]:
    """Run existing proof packet verification."""
    result = verify_proof_packet(target / PROOF_DIR)
    return nested_zip_component_check("proof_packet_verification", result)


def site_preview_component_check(target: Path) -> dict[str, str]:
    """Run existing site preview verification."""
    result = verify_site_preview(target / SITE_PREVIEW_DIR)
    return nested_zip_component_check("site_preview_verification", result)


def nested_zip_component_check(name: str, result: dict[str, Any]) -> dict[str, str]:
    """Convert a nested verification payload into one check."""
    verified = bool(result.get("verified"))
    return check(
        name,
        verified,
        (
            f"{name} passed."
            if verified
            else f"{name} failed: {nested_verification_message(result)}"
        ),
    )


def nested_verification_message(result: dict[str, Any]) -> str:
    """Summarize nested verification failures."""
    errors = result.get("errors")
    if isinstance(errors, list) and errors:
        return "; ".join(str(item) for item in errors)
    failed = [
        str(item.get("message"))
        for item in result.get("checks", [])
        if isinstance(item, dict) and item.get("status") == "failed"
    ]
    return "; ".join(failed) if failed else "verification failed"


def unsafe_text_matches(name: str, text: str) -> list[str]:
    """Find unsafe generated top-level content markers."""
    lowered = text.lower()
    matches: list[str] = []
    for marker in FORBIDDEN_LOCAL_PATHS:
        if marker in lowered:
            matches.append(f"{name}: {marker}")
    for marker in FORBIDDEN_HTML:
        if marker in lowered:
            matches.append(f"{name}: {marker}")
    for marker in BANNED_CLAIMS_OR_MARKERS:
        if marker in lowered:
            matches.append(f"{name}: {marker}")
    for marker in EXTRA_BANNED_MARKERS:
        if marker in lowered:
            matches.append(f"{name}: {marker}")
    return matches


def safe_zip_name(name: str) -> bool:
    """Return whether a zip member name is safe for evidence rooms."""
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    if any(part in FORBIDDEN_ZIP_PARTS for part in path.parts):
        return False
    if any(name.startswith(prefix) for prefix in FORBIDDEN_ZIP_PREFIXES):
        return False
    if name.startswith("/") or name.endswith("/"):
        return False
    return True


def prefixed_checks(prefix: str, checks: object) -> list[dict[str, str]]:
    """Prefix nested checks for zip verification output."""
    if not isinstance(checks, list):
        return [check(f"{prefix}:checks", False, "Nested checks are invalid.")]
    result: list[dict[str, str]] = []
    for item in checks:
        if not isinstance(item, dict):
            continue
        result.append(
            check(
                f"{prefix}:{item.get('name', 'check')}",
                item.get("status") == "passed",
                str(item.get("message", "")),
            )
        )
    return result


def verification_payload(
    target: Path,
    *,
    target_type: str,
    checks: list[dict[str, str]],
) -> dict[str, Any]:
    """Build evidence room verification payload."""
    verified = all(item["status"] == "passed" for item in checks)
    return {
        "status": "passed" if verified else "failed",
        "verified": verified,
        "target": target.name or target.as_posix(),
        "target_type": target_type,
        "checks": checks,
    }


def evidence_room_verification_json(payload: dict[str, Any]) -> str:
    """Serialize evidence room verification as stable JSON."""
    return json.dumps(payload, indent=2, sort_keys=True)


def check(name: str, passed: bool, message: str) -> dict[str, str]:
    """Build a verification check."""
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "message": message,
    }


def generated_time() -> str:
    """Return a compact UTC generated timestamp."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def escape(value: object) -> str:
    """Escape dynamic text for HTML."""
    return html.escape(str(value), quote=True)
