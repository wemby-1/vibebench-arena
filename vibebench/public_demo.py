"""Deterministic public demo portal generation."""

from __future__ import annotations

import filecmp
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from vibebench.artifacts import KNOWN_ARTIFACT_SPECS
from vibebench.explain import find_latest_valid_run
from vibebench.report import ReportError, load_metrics
from vibebench.share_check import run_share_check, share_check_payload

PUBLIC_DEMO_SCHEMA_VERSION = "vibebench.public-demo.v1"
INDEX_FILENAME = "index.html"
DEMO_JSON_FILENAME = "demo.json"
README_FILENAME = "README.md"
ARTIFACTS_DIR = "artifacts"
PUBLIC_PROOF_MARKER = "proof-packet-index.md"
REFERENCE_PROOF_REPRODUCTION_COMMAND = (
    "python3 scripts/build_public_proof_packet.py --check"
)

COPY_ALLOWLIST = {
    Path("README.md"),
    Path(PUBLIC_PROOF_MARKER),
    Path("metrics.json"),
    Path("manifest.json"),
    Path("artifact-inventory.json"),
    Path("config-check.json"),
    Path("config-check.md"),
    Path("workflow-check.json"),
    Path("workflow-check.md"),
    Path("preflight.json"),
    Path("preflight.md"),
    Path("release-check.json"),
    Path("release-check.md"),
    Path("adoption-ready.json"),
    Path("adoption-ready.md"),
    Path("github-step-summary.md"),
    Path("explain.md"),
    Path("gate-summary.md"),
    Path("report/index.html"),
    Path("evidence-room/index.html"),
    Path("evidence-room/review-hub.html"),
    Path("evidence-room/trust-center.html"),
    Path("evidence-room/security-questionnaire.html"),
    Path("evidence-room/security-questionnaire.md"),
    Path("evidence-room/review-scorecard.html"),
    Path("evidence-room/review-scorecard.md"),
    Path("evidence-room/review-scorecard.json"),
}

EVIDENCE_ORDER = [
    ("report", "Main report", Path("report/index.html")),
    ("manifest", "Manifest", Path("manifest.json")),
    ("bundle", "Bundle metadata", Path("vibebench-bundle.zip")),
    ("workflow_check", "Workflow check", Path("workflow-check.json")),
    ("preflight", "Preflight", Path("preflight.json")),
    ("adoption_ready", "Adoption readiness", Path("adoption-ready.json")),
    ("release_check", "Release check", Path("release-check.json")),
    ("doctor_readiness", "Doctor/readiness result", Path("adoption-ready.json")),
    ("evidence_room", "Evidence room", Path("evidence-room/index.html")),
    ("review_hub", "Review hub", Path("evidence-room/review-hub.html")),
    ("trust_center", "Trust center", Path("evidence-room/trust-center.html")),
    (
        "security_questionnaire",
        "Security questionnaire",
        Path("evidence-room/security-questionnaire.html"),
    ),
    ("scorecard", "Scorecard", Path("evidence-room/review-scorecard.json")),
    ("github_summary", "GitHub step summary", Path("github-step-summary.md")),
    ("config_check", "Config check", Path("config-check.json")),
    ("gate_summary", "Gate summary", Path("gate-summary.md")),
]

ARTIFACT_EXPLANATIONS = {
    "metrics.json": "Core status, score, command result, diff, and risk signals.",
    "manifest.json": "Inventory and checksums for known run artifacts.",
    "artifact-inventory.json": "Availability map for known evidence files.",
    "config-check.json": "Machine-readable configuration consistency checks.",
    "config-check.md": "Reviewer-readable configuration consistency summary.",
    "workflow-check.json": "Workflow readiness and policy checks.",
    "workflow-check.md": "Reviewer-readable workflow readiness summary.",
    "preflight.json": "Read-only adoption preflight result.",
    "preflight.md": "Reviewer-readable adoption preflight summary.",
    "release-check.json": "Local release-readiness evidence.",
    "release-check.md": "Reviewer-readable release-readiness summary.",
    "adoption-ready.json": "Compact adoption-readiness verdict.",
    "adoption-ready.md": "Reviewer-readable adoption-readiness verdict.",
    "github-step-summary.md": "GitHub Actions summary text captured for review.",
    "explain.md": "Short explanation of the run result and review signals.",
    "gate-summary.md": "Quality gate result summary.",
    "report/index.html": "Self-contained HTML report for the run.",
    "evidence-room/index.html": "Combined evidence-room landing page.",
    "evidence-room/review-hub.html": "Reviewer entry point for evidence inspection.",
    "evidence-room/trust-center.html": "Trust-boundary and non-claim documentation.",
    "evidence-room/security-questionnaire.html": (
        "Adopter-facing security questionnaire."
    ),
    "evidence-room/security-questionnaire.md": "Markdown security questionnaire.",
    "evidence-room/review-scorecard.html": "Reviewer scorecard.",
    "evidence-room/review-scorecard.md": "Markdown reviewer scorecard.",
    "evidence-room/review-scorecard.json": "Machine-readable reviewer scorecard.",
    "vibebench-bundle.zip": "Portable run artifact bundle metadata when present.",
}

FORBIDDEN_PUBLIC_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"/home/",
        r"/users/",
        r"/data/code/",
        r"/tmp/(?!vibebench-demo\b)",
        r"c:\\users\\",
        r"d:\\",
        r"\bghp_[A-Za-z0-9_]{20,}",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}",
        r"\bsk-[A-Za-z0-9_-]{20,}",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\b(?:authorization|api[_-]?key|token|secret|password)\s*[:=]",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    ]
]


class PublicDemoError(RuntimeError):
    """Raised when public-demo generation cannot continue safely."""


@dataclass(frozen=True)
class PublicDemoResult:
    """Result of generating or checking a public demo portal."""

    status: str
    source_type: str
    source_label: str
    output_label: str
    check: bool
    project: str
    overall_status: str
    score: int
    risk_level: str
    artifact_count: int
    available_artifact_count: int
    files: list[dict[str, object]]
    warnings: list[str]
    differences: list[str]


def generate_public_demo(
    *,
    project_root: Path,
    output_dir: Path,
    run_dir: Path | None = None,
    proof_packet: Path | None = None,
    check: bool = False,
) -> PublicDemoResult:
    """Generate or check a public demo portal."""
    root = project_root.resolve()
    source_type, source_dir = select_source(root, run_dir, proof_packet)
    selected_output = output_dir.resolve()
    validate_output_location(selected_output, source_dir)
    if selected_output.exists() and selected_output.is_file():
        raise PublicDemoError(f"Output path is a file: {output_dir}")
    if not selected_output.parent.exists():
        raise PublicDemoError(
            f"Output parent directory does not exist: {output_dir.parent}"
        )

    with tempfile.TemporaryDirectory(
        prefix="vibebench-public-demo-", dir=str(selected_output.parent)
    ) as temp:
        generated = Path(temp) / "generated"
        build_public_demo_tree(
            project_root=root,
            source_type=source_type,
            source_dir=source_dir,
            output_dir=generated,
        )
        if check:
            differences = compare_trees(generated, selected_output)
            metadata = public_demo_payload(
                project_root=root,
                source_type=source_type,
                source_dir=source_dir,
                output_dir=selected_output,
                check=True,
                differences=differences,
                status="passed" if not differences else "failed",
                warnings=load_generated_warnings(generated),
            )
            return result_from_payload(metadata)

        if selected_output.exists():
            shutil.rmtree(selected_output)
        shutil.copytree(generated, selected_output)
        metadata = public_demo_payload(
            project_root=root,
            source_type=source_type,
            source_dir=source_dir,
            output_dir=selected_output,
            check=False,
            differences=[],
            status="passed",
            warnings=[],
        )
        return result_from_payload(metadata)


def build_public_demo_tree(
    *,
    project_root: Path,
    source_type: str,
    source_dir: Path,
    output_dir: Path,
) -> None:
    """Build a demo portal in an empty directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    source = load_source_summary(project_root, source_type, source_dir)
    copied, copy_warnings = copy_safe_artifacts(source_dir, output_dir)
    artifacts = build_artifact_rows(source_dir, copied)
    evidence = build_evidence_rows(copied)
    warnings = [*source["warnings"], *copy_warnings]
    demo_payload = build_demo_json(
        source=source,
        artifacts=artifacts,
        evidence=evidence,
        warnings=warnings,
    )

    (output_dir / INDEX_FILENAME).write_text(
        clean_generated_text(render_index(demo_payload)),
        encoding="utf-8",
    )
    (output_dir / README_FILENAME).write_text(
        clean_generated_text(render_readme(demo_payload)),
        encoding="utf-8",
    )
    write_stable_demo_json(output_dir, demo_payload)
    scan_public_demo(output_dir)


def select_source(
    project_root: Path,
    run_dir: Path | None,
    proof_packet: Path | None,
) -> tuple[str, Path]:
    """Select and validate the public-demo source."""
    if run_dir is not None and proof_packet is not None:
        raise PublicDemoError("--run-dir and --proof-packet are mutually exclusive.")
    if proof_packet is not None:
        selected = resolve_cli_path(project_root, proof_packet)
        validate_proof_packet(selected)
        return "proof-packet", selected
    if run_dir is not None:
        selected = resolve_cli_path(project_root, run_dir)
        validate_run_source(selected)
        return "run", selected
    try:
        selected = find_latest_valid_run(project_root).resolve()
    except ReportError as exc:
        raise PublicDemoError(
            "No input supplied and no latest valid VibeBench run was found."
        ) from exc
    validate_run_source(selected)
    return "run", selected


def resolve_cli_path(project_root: Path, value: Path) -> Path:
    """Resolve a CLI path using the project root for relative paths."""
    return (value if value.is_absolute() else project_root / value).resolve()


def validate_output_location(output_dir: Path, source_dir: Path) -> None:
    """Reject output directories that would live inside the source evidence."""
    try:
        output_dir.relative_to(source_dir.resolve())
    except ValueError:
        return
    raise PublicDemoError(
        "Output directory must not be inside the selected run or proof packet."
    )


def validate_run_source(source_dir: Path) -> None:
    """Validate an ordinary run directory."""
    if not source_dir.exists():
        raise PublicDemoError(f"Run directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise PublicDemoError(f"Run path is not a directory: {source_dir}")
    try:
        metrics = load_metrics(source_dir)
    except json.JSONDecodeError as exc:
        raise PublicDemoError(
            f"metrics.json in {source_dir} is not valid JSON."
        ) from exc
    except ReportError as exc:
        raise PublicDemoError(str(exc)) from exc
    if not isinstance(metrics, dict):
        raise PublicDemoError(f"metrics.json in {source_dir} must contain an object.")


def validate_proof_packet(source_dir: Path) -> None:
    """Validate a curated proof packet directory."""
    if not source_dir.exists():
        raise PublicDemoError(f"Proof packet does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise PublicDemoError(f"Proof packet path is not a directory: {source_dir}")
    validate_run_source(source_dir)
    if not (source_dir / PUBLIC_PROOF_MARKER).is_file():
        raise PublicDemoError(
            "Proof packet is missing proof-packet-index.md; use --run-dir for "
            "ordinary run directories."
        )


def load_source_summary(
    project_root: Path,
    source_type: str,
    source_dir: Path,
) -> dict[str, Any]:
    """Load source metadata without exposing local paths."""
    metrics = load_metrics(source_dir)
    summary = as_dict(metrics.get("summary"))
    commands = [
        {
            "group": text(item.get("group"), "check"),
            "command": safe_command(text(item.get("command"), "")),
            "status": text(item.get("status"), "unknown"),
            "exit_code": item.get("exit_code"),
        }
        for item in as_list(metrics.get("command_results"))
        if isinstance(item, dict)
    ]
    findings = sorted(
        (
            {
                "severity": text(item.get("severity"), "info"),
                "code": text(item.get("code"), "finding"),
                "message": sanitize_text(text(item.get("message"), "")),
            }
            for item in as_list(metrics.get("risk_findings"))
            if isinstance(item, dict)
        ),
        key=lambda item: (item["severity"], item["code"], item["message"]),
    )
    try:
        source_label = source_dir.relative_to(project_root).as_posix()
    except ValueError:
        source_label = source_dir.name
    return {
        "schema_version": PUBLIC_DEMO_SCHEMA_VERSION,
        "source_type": source_type,
        "source": sanitize_path_label(source_label),
        "source_time": sanitize_text(text(metrics.get("created_at"), "")),
        "project": sanitize_text(text(metrics.get("project_name"), "Unknown project")),
        "overall_status": sanitize_text(
            text(metrics.get("overall_status"), "unknown")
        ),
        "score": int(metrics.get("score") or 0),
        "risk_level": sanitize_text(text(metrics.get("risk_level"), "unknown")),
        "quality_verdict": sanitize_text(
            verdict_for(text(metrics.get("overall_status"), "unknown"))
        ),
        "gate_result": gate_result(source_dir),
        "summary": {
            "total_commands": int(summary.get("total_commands") or len(commands)),
            "passed_commands": int(summary.get("passed_commands") or 0),
            "failed_commands": int(summary.get("failed_commands") or 0),
            "total_findings": int(summary.get("total_findings") or len(findings)),
        },
        "commands": commands,
        "findings": findings,
        "warnings": [],
    }


def gate_result(source_dir: Path) -> str:
    """Return a compact gate result from gate-summary.md when available."""
    gate = source_dir / "gate-summary.md"
    if not safe_source_file(source_dir, gate):
        return "unavailable"
    text_value = gate.read_text(encoding="utf-8", errors="replace")
    for line in text_value.splitlines():
        if "Gate:" in line or "Status:" in line:
            return sanitize_text(line.strip("- ").strip())
    return "available"


def copy_safe_artifacts(
    source_dir: Path,
    output_dir: Path,
) -> tuple[set[Path], list[str]]:
    """Copy explicit allowlisted artifacts that are safe for public browsing."""
    copied: set[Path] = set()
    warnings: list[str] = []
    target_root = output_dir / ARTIFACTS_DIR
    for relative in sorted(COPY_ALLOWLIST, key=lambda item: item.as_posix()):
        source = source_dir / relative
        if not source.exists():
            continue
        if not safe_source_file(source_dir, source):
            warnings.append(f"Omitted unsafe artifact path: {relative.as_posix()}")
            continue
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        try:
            scan_public_file(target, target_root)
        except PublicDemoError as exc:
            target.unlink(missing_ok=True)
            warnings.append(
                f"Omitted artifact that did not pass public safety scan: "
                f"{relative.as_posix()} ({exc})"
            )
            continue
        copied.add(relative)
    return copied, warnings


def safe_source_file(source_dir: Path, source: Path) -> bool:
    """Return whether source is a regular file inside source_dir."""
    if not source.is_file() or source.is_symlink():
        return False
    try:
        source.resolve().relative_to(source_dir.resolve())
    except ValueError:
        return False
    return True


def build_artifact_rows(source_dir: Path, copied: set[Path]) -> list[dict[str, object]]:
    """Build deterministic artifact explorer rows."""
    inventory_rows = collect_source_inventory(source_dir)
    seen: set[str] = set()
    rows: list[dict[str, object]] = []
    for item in inventory_rows:
        relative = normalize_artifact_relative_path(text(item.get("path"), ""))
        if not relative or relative in seen:
            continue
        seen.add(relative)
        relative_path = Path(relative)
        copied_path = relative_path in copied
        rows.append(
            artifact_row(
                name=text(item.get("name"), relative),
                relative=relative,
                available=bool(item.get("available")) and copied_path,
                source_available=bool(item.get("available")),
                size_bytes=item.get("size_bytes") if copied_path else None,
            )
        )
    for relative_path in sorted(copied, key=lambda item: item.as_posix()):
        relative = relative_path.as_posix()
        if relative in seen:
            continue
        rows.append(
            artifact_row(
                name=human_name(relative),
                relative=relative,
                available=True,
                source_available=True,
                size_bytes=None,
            )
        )
    rows.sort(key=lambda item: (not bool(item["available"]), str(item["path"])))
    target_root = Path(ARTIFACTS_DIR)
    for row in rows:
        if not row["available"]:
            continue
        relative = Path(str(row["path"]))
        _copied_path = target_root / relative
        source_path = source_dir / relative
        if source_path.is_file() and not source_path.is_symlink():
            row["size_bytes"] = source_path.stat().st_size
    return rows


def collect_source_inventory(source_dir: Path) -> list[dict[str, Any]]:
    """Collect inventory rows from manifest, inventory, or known artifact specs."""
    for filename in ("artifact-inventory.json", "manifest.json"):
        path = source_dir / filename
        if not path.is_file() or path.is_symlink():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        artifacts = payload.get("artifacts")
        if isinstance(artifacts, list):
            return [item for item in artifacts if isinstance(item, dict)]
    return [
        {
            "name": spec.name,
            "path": spec.relative_path.as_posix(),
            "available": (source_dir / spec.relative_path).is_file(),
            "size_bytes": (
                (source_dir / spec.relative_path).stat().st_size
                if (source_dir / spec.relative_path).is_file()
                else None
            ),
        }
        for spec in KNOWN_ARTIFACT_SPECS
    ]


def artifact_row(
    *,
    name: str,
    relative: str,
    available: bool,
    source_available: bool,
    size_bytes: object,
) -> dict[str, object]:
    """Build one artifact explorer row."""
    link = f"{ARTIFACTS_DIR}/{relative}" if available else None
    suffix = Path(relative).suffix.lower().lstrip(".") or "directory"
    return {
        "name": human_name(name),
        "path": relative,
        "available": available,
        "source_available": source_available,
        "file_type": suffix,
        "size_bytes": size_bytes if isinstance(size_bytes, int) else None,
        "link": link,
        "description": ARTIFACT_EXPLANATIONS.get(
            relative,
            "Known VibeBench artifact; inspect when available in the source evidence.",
        ),
    }


def normalize_artifact_relative_path(path_value: str) -> str:
    """Normalize manifest/inventory paths into source-relative paths."""
    value = sanitize_path_label(path_value)
    if not value:
        return ""
    marker = ".vibebench/runs/"
    if marker in value:
        tail = value.split(marker, 1)[1]
        parts = tail.split("/", 1)
        return parts[1] if len(parts) == 2 else ""
    if value.startswith("./"):
        value = value[2:]
    if value.startswith("/") or ".." in Path(value).parts:
        return ""
    return value


def build_evidence_rows(copied: set[Path]) -> list[dict[str, object]]:
    """Build deterministic evidence overview rows."""
    rows = []
    for key, title, relative in EVIDENCE_ORDER:
        available = relative in copied
        rows.append(
            {
                "id": key,
                "title": title,
                "available": available,
                "link": f"{ARTIFACTS_DIR}/{relative.as_posix()}" if available else None,
                "status": "available" if available else "unavailable optional evidence",
            }
        )
    return rows


def build_demo_json(
    *,
    source: dict[str, Any],
    artifacts: list[dict[str, object]],
    evidence: list[dict[str, object]],
    warnings: list[str],
) -> dict[str, Any]:
    """Build public-safe demo.json."""
    return {
        "schema_version": PUBLIC_DEMO_SCHEMA_VERSION,
        "status": "passed",
        "source_type": source["source_type"],
        "source": source["source"],
        "output_dir": ".",
        "check": False,
        "project": source["project"],
        "overall_status": source["overall_status"],
        "score": source["score"],
        "risk_level": source["risk_level"],
        "artifact_count": len(artifacts),
        "available_artifact_count": sum(1 for item in artifacts if item["available"]),
        "source_time": source["source_time"],
        "quality_verdict": source["quality_verdict"],
        "gate_result": source["gate_result"],
        "summary": source["summary"],
        "commands": source["commands"],
        "findings": source["findings"],
        "evidence": evidence,
        "artifacts": artifacts,
        "review_path": review_path(),
        "audiences": audience_views(),
        "reproduction": reproduction_commands(source["source_type"]),
        "trust_boundaries": trust_boundaries(),
        "warnings": sorted(sanitize_text(item) for item in warnings),
        "files": [],
        "differences": [],
    }


def public_demo_payload(
    *,
    project_root: Path,
    source_type: str,
    source_dir: Path,
    output_dir: Path,
    check: bool,
    differences: list[str],
    status: str,
    warnings: list[str],
) -> dict[str, Any]:
    """Build a command result payload from an existing generated tree."""
    demo_path = output_dir / DEMO_JSON_FILENAME
    if demo_path.is_file():
        payload = json.loads(demo_path.read_text(encoding="utf-8"))
    else:
        source = load_source_summary(project_root, source_type, source_dir)
        payload = build_demo_json(
            source=source,
            artifacts=[],
            evidence=build_evidence_rows(set()),
            warnings=warnings,
        )
    payload = dict(payload)
    payload["status"] = status
    payload["check"] = check
    payload["output_dir"] = output_label(project_root, output_dir)
    payload["files"] = file_listing(output_dir) if output_dir.exists() else []
    payload["differences"] = differences
    payload["warnings"] = sorted(set([*payload.get("warnings", []), *warnings]))
    return payload


def result_from_payload(payload: dict[str, Any]) -> PublicDemoResult:
    """Convert payload into a typed result."""
    return PublicDemoResult(
        status=text(payload.get("status"), "failed"),
        source_type=text(payload.get("source_type"), ""),
        source_label=text(payload.get("source"), ""),
        output_label=text(payload.get("output_dir"), ""),
        check=bool(payload.get("check")),
        project=text(payload.get("project"), ""),
        overall_status=text(payload.get("overall_status"), ""),
        score=int(payload.get("score") or 0),
        risk_level=text(payload.get("risk_level"), ""),
        artifact_count=int(payload.get("artifact_count") or 0),
        available_artifact_count=int(payload.get("available_artifact_count") or 0),
        files=[
            item
            for item in as_list(payload.get("files"))
            if isinstance(item, dict)
        ],
        warnings=[text(item, "") for item in as_list(payload.get("warnings"))],
        differences=[text(item, "") for item in as_list(payload.get("differences"))],
    )


def public_demo_json(result: PublicDemoResult) -> str:
    """Serialize a public-demo command result as stable JSON."""
    return json.dumps(public_demo_result_payload(result), indent=2, sort_keys=True)


def public_demo_result_payload(result: PublicDemoResult) -> dict[str, Any]:
    """Return command JSON for a public-demo result."""
    return {
        "status": result.status,
        "source_type": result.source_type,
        "source": result.source_label,
        "output_dir": result.output_label,
        "check": result.check,
        "project": result.project,
        "overall_status": result.overall_status,
        "score": result.score,
        "risk_level": result.risk_level,
        "artifact_count": result.artifact_count,
        "available_artifact_count": result.available_artifact_count,
        "files": result.files,
        "warnings": result.warnings,
        "differences": result.differences,
    }


def write_public_demo_json(result: PublicDemoResult, output_path: Path) -> None:
    """Write command JSON to a path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(public_demo_json(result) + "\n", encoding="utf-8")


def write_public_demo_summary(result: PublicDemoResult, output_path: Path) -> None:
    """Write a concise Markdown public-demo summary."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(public_demo_summary_markdown(result), encoding="utf-8")


def public_demo_summary_markdown(result: PublicDemoResult) -> str:
    """Render a concise Markdown public-demo summary."""
    lines = [
        "# VibeBench Public Demo",
        "",
        f"- Project: `{result.project}`",
        f"- Result: `{result.overall_status}`",
        f"- Score/risk: `{result.score}` / `{result.risk_level}`",
        f"- Source type: `{result.source_type}`",
        f"- Source: `{result.source_label}`",
        f"- Output: `{result.output_label}`",
        "",
        "## Generated Files",
        "",
    ]
    for item in result.files:
        lines.append(f"- `{item['path']}` ({item['size_bytes']} bytes)")
    if not result.files:
        lines.append("- No generated files were inspected.")
    lines.extend(
        [
            "",
            "## Major Evidence Links",
            "",
            "- `index.html`",
            "- `demo.json`",
            "- `README.md`",
            "",
            "## Warnings",
            "",
        ]
    )
    if result.warnings:
        lines.extend(f"- {item}" for item in result.warnings)
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Reproduction",
            "",
            f"- `{REFERENCE_PROOF_REPRODUCTION_COMMAND}`",
            "",
        ]
    )
    return "\n".join(lines)


def render_index(payload: dict[str, Any]) -> str:
    """Render the self-contained public demo HTML."""
    project = escape(text(payload.get("project"), "Unknown project"))
    status = escape(text(payload.get("overall_status"), "unknown"))
    score = escape(str(payload.get("score", 0)))
    risk = escape(text(payload.get("risk_level"), "unknown"))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{project} - VibeBench Public Demo</title>
  <style>
{styles()}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <p class="eyebrow">VibeBench Public Demo</p>
      <h1>{project}</h1>
      <p class="lede">{hero_value_proposition()}</p>
      <div class="scorebar">
        <div><span>Overall status</span><strong>{status}</strong></div>
        <div><span>Score</span><strong>{score}</strong></div>
        <div><span>Risk level</span><strong>{risk}</strong></div>
      </div>
      <div class="claims">
        <p><strong>What this evidence proves:</strong> {evidence_proves()}</p>
        <p><strong>What this does not prove:</strong> {evidence_does_not_prove()}</p>
      </div>
    </section>
    {reviewer_summary(payload)}
    {evidence_overview(payload)}
    {artifact_explorer(payload)}
    {review_path_section(payload)}
    {audience_section(payload)}
    {reproduction_section(payload)}
    {trust_section(payload)}
  </main>
</body>
</html>
"""


def hero_value_proposition() -> str:
    """Return the portal value proposition."""
    return (
        "A deterministic, local-first evidence portal for reviewing VibeBench "
        "quality signals."
    )


def evidence_proves() -> str:
    """Return the positive evidence boundary."""
    return (
        "the supplied VibeBench run or proof packet contains reproducible "
        "quality, readiness, artifact, and review signals summarized here."
    )


def evidence_does_not_prove() -> str:
    """Return the negative evidence boundary."""
    return (
        "it does not independently prove security, replace human review, "
        "certify compliance, or claim adoption, revenue, funding, customers, "
        "or product-market fit."
    )


def reviewer_summary(payload: dict[str, Any]) -> str:
    """Render reviewer summary HTML."""
    summary = as_dict(payload.get("summary"))
    commands = as_list(payload.get("commands"))
    findings = as_list(payload.get("findings"))
    command_rows = "".join(
        f"<li><code>{escape(text(item.get('group'), 'check'))}</code> "
        f"{escape(text(item.get('status'), 'unknown'))}: "
        f"{escape(text(item.get('command'), ''))}</li>"
        for item in commands
        if isinstance(item, dict)
    )
    finding_rows = "".join(
        f"<li>{escape(text(item.get('severity'), 'info'))}: "
        f"{escape(text(item.get('message'), ''))}</li>"
        for item in findings
        if isinstance(item, dict)
    ) or "<li>No risk findings were reported in the supplied evidence.</li>"
    return f"""
    <section class="panel" id="reviewer-summary">
      <h2>Reviewer Summary</h2>
      <div class="grid">
        {summary_tile("Source", source_label(payload))}
        {summary_tile("Source time", text(payload.get("source_time"), "unavailable"))}
        {summary_tile("Quality verdict", text(payload.get("quality_verdict")))}
        {summary_tile("Gate result", text(payload.get("gate_result")))}
      </div>
      <p>{command_count_sentence(summary)}</p>
      <h3>Command/check summary</h3>
      <ul>{command_rows}</ul>
      <h3>Key findings</h3>
      <ul>{finding_rows}</ul>
    </section>
"""


def source_label(payload: dict[str, Any]) -> str:
    """Return a compact source label."""
    return f"{text(payload.get('source_type'))}: {text(payload.get('source'))}"


def summary_tile(label: str, value: str) -> str:
    """Render one reviewer-summary tile."""
    return (
        "<p>"
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(value)}</strong>"
        "</p>"
    )


def command_count_sentence(summary: dict[str, Any]) -> str:
    """Return the command count sentence."""
    return (
        f"Commands: {summary.get('passed_commands', 0)} passed, "
        f"{summary.get('failed_commands', 0)} failed, "
        f"{summary.get('total_commands', 0)} total."
    )


def evidence_overview(payload: dict[str, Any]) -> str:
    """Render evidence overview HTML."""
    rows = []
    for item in as_list(payload.get("evidence")):
        if not isinstance(item, dict):
            continue
        title = escape(text(item.get("title")))
        status = escape(text(item.get("status")))
        link = item.get("link")
        value = (
            f'<a href="{escape(text(link))}">open</a>'
            if isinstance(link, str)
            else "unavailable"
        )
        rows.append(f"<tr><td>{title}</td><td>{status}</td><td>{value}</td></tr>")
    return f"""
    <section class="panel" id="evidence-overview">
      <h2>Evidence Overview</h2>
      <table>
        <thead><tr><th>Evidence</th><th>Status</th><th>Link</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
"""


def artifact_explorer(payload: dict[str, Any]) -> str:
    """Render artifact explorer HTML."""
    rows = []
    for item in as_list(payload.get("artifacts")):
        if not isinstance(item, dict):
            continue
        link = item.get("link")
        link_html = (
            f'<a href="{escape(text(link))}">{escape(text(item.get("path")))}</a>'
            if isinstance(link, str)
            else escape(text(item.get("path")))
        )
        rows.append(
            "<tr>"
            f"<td>{escape(text(item.get('name')))}</td>"
            f"<td>{'available' if item.get('available') else 'unavailable'}</td>"
            f"<td>{escape(text(item.get('file_type')))}</td>"
            f"<td>{escape(format_size(item.get('size_bytes')))}</td>"
            f"<td>{link_html}</td>"
            f"<td>{escape(text(item.get('description')))}</td>"
            "</tr>"
        )
    return f"""
    <section class="panel" id="artifact-explorer">
      <h2>Artifact Explorer</h2>
      <table>
        <thead>
          <tr>
            <th>Name</th><th>Availability</th><th>Type</th>
            <th>Size</th><th>Path</th><th>Demonstrates</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
"""


def review_path_section(payload: dict[str, Any]) -> str:
    """Render five-minute review path."""
    rows = "".join(f"<li>{escape(text(item))}</li>" for item in payload["review_path"])
    return f"""
    <section class="panel" id="five-minute-review-path">
      <h2>Five-Minute Review Path</h2>
      <ol>{rows}</ol>
    </section>
"""


def audience_section(payload: dict[str, Any]) -> str:
    """Render audience views."""
    rows = "".join(
        "<article>"
        f"<h3>{escape(text(item.get('audience')))}</h3>"
        f"<p>{escape(text(item.get('framing')))}</p>"
        "</article>"
        for item in payload["audiences"]
    )
    return f"""
    <section class="panel" id="audience-views">
      <h2>Audience Views</h2>
      <div class="audiences">{rows}</div>
    </section>
"""


def reproduction_section(payload: dict[str, Any]) -> str:
    """Render reproduction commands."""
    commands = "".join(
        f"<li><code>{escape(text(item))}</code></li>"
        for item in payload["reproduction"]
    )
    return f"""
    <section class="panel" id="reproduction">
      <h2>Reproduction</h2>
      <p>
        Run these from the repository root when using the committed reference
        proof packet.
      </p>
      <ul>{commands}</ul>
    </section>
"""


def trust_section(payload: dict[str, Any]) -> str:
    """Render non-claims and trust boundaries."""
    rows = "".join(
        f"<li>{escape(text(item))}</li>"
        for item in payload["trust_boundaries"]
    )
    warnings = "".join(
        f"<li>{escape(text(item))}</li>" for item in payload["warnings"]
    )
    warning_block = f"<h3>Warnings</h3><ul>{warnings}</ul>" if warnings else ""
    return f"""
    <section class="panel" id="non-claims-and-trust-boundaries">
      <h2>Non-Claims and Trust Boundaries</h2>
      <ul>{rows}</ul>
      {warning_block}
    </section>
"""


def render_readme(payload: dict[str, Any]) -> str:
    """Render portal README."""
    return f"""# VibeBench Public Demo

Project: `{payload['project']}`

Result: `{payload['overall_status']}` with score `{payload['score']}` and
risk `{payload['risk_level']}`.

Open `index.html` directly in a browser. The portal is self-contained and does
not require a server, CDN, external JavaScript, external CSS, remote fonts,
analytics, or network access.

## Review Path

{markdown_list(payload['review_path'])}

## Reproduction

```bash
{REFERENCE_PROOF_REPRODUCTION_COMMAND}
```

## Boundaries

{markdown_list(payload['trust_boundaries'])}
"""


def styles() -> str:
    """Return embedded CSS."""
    return """
:root {
  color-scheme: light;
  --bg: #f7f8fa;
  --ink: #1d2733;
  --muted: #5d6878;
  --panel: #fff;
  --line: #d9dfe8;
  --accent: #12665a;
  --warn: #9a5b00;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
  line-height: 1.5;
}
main {
  width: min(1180px, calc(100% - 40px));
  margin: 0 auto;
  padding: 28px 0;
}
.hero, .panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
}
.hero { padding: 32px; background: #173b35; color: white; }
.eyebrow {
  margin: 0 0 8px;
  color: #b8d8d2;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0;
}
h1 {
  margin: 0;
  font-size: clamp(30px, 5vw, 56px);
  line-height: 1.05;
  letter-spacing: 0;
}
h2 { margin: 0 0 16px; font-size: 24px; letter-spacing: 0; }
h3 { margin: 18px 0 8px; font-size: 17px; letter-spacing: 0; }
.lede { max-width: 760px; color: #e6f2ef; font-size: 18px; }
.scorebar {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 24px 0;
}
.scorebar div {
  background: rgba(255,255,255,.1);
  border: 1px solid rgba(255,255,255,.22);
  border-radius: 8px;
  padding: 16px;
}
span { display: block; color: var(--muted); font-size: 13px; font-weight: 650; }
.scorebar span { color: #cfe6e1; }
strong { display: block; font-size: 24px; }
.claims { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.claims p {
  margin: 0;
  padding: 14px;
  border-radius: 8px;
  background: rgba(255,255,255,.08);
}
.panel { margin-top: 18px; padding: 24px; overflow-x: auto; }
.grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.grid p { margin: 0; padding: 14px; border: 1px solid var(--line); border-radius: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td {
  padding: 10px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}
th {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0;
}
a { color: var(--accent); font-weight: 650; }
code {
  background: #eef2f6;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 1px 5px;
  color: #263545;
}
.audiences {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}
article { border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
article h3 { margin-top: 0; }
@media (max-width: 860px) {
  .scorebar, .claims, .grid, .audiences { grid-template-columns: 1fr; }
  main { width: min(100% - 24px, 1180px); }
  .hero, .panel { padding: 18px; }
}
"""


def review_path() -> list[str]:
    """Return the fixed five-minute review path."""
    return [
        "Verify the overall result, score, and risk level.",
        "Inspect workflow and adoption readiness evidence.",
        "Inspect findings and command results.",
        "Open the main report when it is available and safe to include.",
        "Review trust boundaries and non-claims.",
        "Reproduce the committed proof packet before relying on it externally.",
    ]


def audience_views() -> list[dict[str, str]]:
    """Return fixed audience framing."""
    return [
        {
            "audience": "Maintainer",
            "framing": (
                "Use the portal to decide what changed, what passed, and which "
                "review artifacts deserve attention before merge or release."
            ),
        },
        {
            "audience": "Engineering reviewer",
            "framing": (
                "Start with command results, findings, workflow checks, and the "
                "report; treat the score as a pointer into evidence, not as a "
                "substitute for review."
            ),
        },
        {
            "audience": "Adopter",
            "framing": (
                "Use readiness, preflight, release-check, and trust-boundary "
                "evidence to decide whether the workflow matches your "
                "evaluation needs."
            ),
        },
        {
            "audience": "Security/procurement reviewer",
            "framing": (
                "Inspect the questionnaire and trust-center evidence when "
                "present; this portal is not a security certification or "
                "compliance audit."
            ),
        },
        {
            "audience": "Investor or diligence reviewer",
            "framing": (
                "Use the artifact trail to evaluate product discipline and "
                "reproducibility without treating it as proof of traction, "
                "revenue, customers, or funding."
            ),
        },
    ]


def reproduction_commands(source_type: str) -> list[str]:
    """Return deterministic reproduction commands."""
    commands = [
        (
            "python3 -m vibebench public-demo --proof-packet "
            "examples/showcase-artifacts/public-proof --output-dir "
            "/tmp/vibebench-demo"
        ),
        (
            "python3 -m vibebench public-demo --proof-packet "
            "examples/showcase-artifacts/public-proof --output-dir "
            "/tmp/vibebench-demo --check"
        ),
    ]
    if source_type == "proof-packet":
        commands.insert(0, REFERENCE_PROOF_REPRODUCTION_COMMAND)
    return commands


def trust_boundaries() -> list[str]:
    """Return required non-claims."""
    return [
        "The portal summarizes the supplied VibeBench evidence.",
        "It does not independently prove security.",
        "It does not replace human code review.",
        "It does not certify regulatory compliance.",
        "It does not prove product-market fit, revenue, customer adoption, or funding.",
        "It should not fabricate users, customers, benchmarks, or commercial traction.",
    ]


def compare_trees(generated: Path, output_dir: Path) -> list[str]:
    """Compare generated tree with an existing output tree."""
    if not output_dir.exists():
        return [f"missing output directory: {output_dir.name}"]
    expected = file_set(generated)
    actual = file_set(output_dir)
    differences: list[str] = []
    for relative in sorted(expected - actual):
        differences.append(f"missing: {relative}")
    for relative in sorted(actual - expected):
        differences.append(f"added: {relative}")
    for relative in sorted(expected & actual):
        if not filecmp.cmp(generated / relative, output_dir / relative, shallow=False):
            differences.append(f"changed: {relative}")
    return differences


def file_set(root: Path) -> set[str]:
    """Return all regular file paths below root."""
    if not root.exists():
        return set()
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def file_listing(root: Path) -> list[dict[str, object]]:
    """Return deterministic generated file listing."""
    return [
        {"path": relative, "size_bytes": (root / relative).stat().st_size}
        for relative in sorted(file_set(root))
    ]


def load_generated_warnings(generated: Path) -> list[str]:
    """Load warnings from generated demo.json."""
    path = generated / DEMO_JSON_FILENAME
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [text(item, "") for item in as_list(payload.get("warnings"))]


def scan_public_demo(output_dir: Path) -> None:
    """Run conservative scans over generated public-demo files."""
    result = run_share_check(
        output_dir,
        strict=True,
        allow_remote_urls=False,
        allow_example_temp_paths=True,
        target_label="public-demo",
    )
    if result.status != "passed":
        payload = share_check_payload(result)
        findings = payload.get("findings", [])
        detail = "; ".join(
            f"{item.get('file')}: {item.get('code')}"
            for item in findings[:5]
            if isinstance(item, dict)
        )
        raise PublicDemoError(f"generated portal failed leak scan: {detail}")
    for relative in sorted(file_set(output_dir)):
        scan_public_file(output_dir / relative, output_dir)


def scan_public_file(path: Path, root: Path) -> None:
    """Scan one generated/copied public file."""
    if path.suffix.lower() not in {".html", ".md", ".json", ".txt", ".yml", ".yaml"}:
        return
    text_value = path.read_text(encoding="utf-8", errors="replace")
    for pattern in FORBIDDEN_PUBLIC_PATTERNS:
        if pattern.search(text_value):
            relative = path.relative_to(root).as_posix()
            raise PublicDemoError(f"{relative} matches unsafe public pattern")


def output_label(project_root: Path, output_dir: Path) -> str:
    """Return a public-safe output label."""
    try:
        return output_dir.resolve().relative_to(project_root).as_posix()
    except ValueError:
        if output_dir.is_absolute():
            return output_dir.name
        return output_dir.as_posix()


def write_stable_demo_json(output_dir: Path, payload: dict[str, Any]) -> None:
    """Write demo.json with a stable self file listing."""
    demo_path = output_dir / DEMO_JSON_FILENAME
    previous_text = ""
    for _ in range(8):
        payload["files"] = file_listing(output_dir)
        text_value = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        demo_path.write_text(text_value, encoding="utf-8")
        if text_value == previous_text:
            return
        previous_text = text_value


def safe_command(value: str) -> str:
    """Sanitize command text for public output."""
    return sanitize_text(value.replace("\\", "/"))


def sanitize_text(value: str) -> str:
    """Remove machine-local path fragments from display text."""
    cleaned = value
    cleaned = re.sub(r"/home/[^\\s`'\"<>)]*", "<local-path>", cleaned)
    cleaned = re.sub(r"/Users/[^\\s`'\"<>)]*", "<local-path>", cleaned)
    cleaned = re.sub(r"/data/code/[^\\s`'\"<>)]*", "<local-path>", cleaned)
    cleaned = re.sub(
        r"/tmp/(?!vibebench-demo\\b)[^\\s`'\"<>)]*",
        "<temp-path>",
        cleaned,
    )
    cleaned = re.sub(r"[A-Za-z]:\\\\Users\\\\[^\\s`'\"<>)]*", "<local-path>", cleaned)
    return cleaned


def sanitize_path_label(value: str) -> str:
    """Return a safe relative path-like label."""
    return sanitize_text(value).replace("\\", "/").lstrip("/")


def verdict_for(status: str) -> str:
    """Return a compact quality verdict."""
    return "ready for evidence review" if status == "passed" else "needs attention"


def human_name(value: str) -> str:
    """Return a human-readable artifact name."""
    stem = value.replace("-", " ").replace("_", " ").replace("/", " / ")
    return stem


def format_size(value: object) -> str:
    """Format an optional size."""
    if not isinstance(value, int):
        return "n/a"
    return f"{value} bytes"


def markdown_list(items: list[Any]) -> str:
    """Render Markdown list items."""
    return "\n".join(f"- {item}" for item in items)


def clean_generated_text(value: str) -> str:
    """Strip trailing whitespace while preserving final newline."""
    return "\n".join(line.rstrip() for line in value.splitlines()) + "\n"


def text(value: object, default: str = "") -> str:
    """Return a stable string."""
    if value is None:
        return default
    return str(value)


def as_dict(value: object) -> dict[str, Any]:
    """Return a dict or empty dict."""
    return value if isinstance(value, dict) else {}


def as_list(value: object) -> list[Any]:
    """Return a list or empty list."""
    return value if isinstance(value, list) else []
