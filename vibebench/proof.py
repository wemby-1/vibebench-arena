"""Local proof packet helpers for VibeBench Arena."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROOF_MARKDOWN = "proof.md"
PROOF_JSON = "proof.json"

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
) -> dict[str, Path]:
    """Write proof packet files and return written paths."""
    root = project_root.resolve()
    written: dict[str, Path] = {}

    if output_dir is not None:
        target_dir = resolve_output_path(root, output_dir)
        if target_dir.exists() and not target_dir.is_dir():
            raise ProofError(f"Output path exists as a file: {target_dir}")
        target_dir.mkdir(parents=True, exist_ok=True)
        written["summary"] = target_dir / PROOF_MARKDOWN
        written["json"] = target_dir / PROOF_JSON

    if summary_output is not None:
        summary_path = resolve_output_path(root, summary_output)
        ensure_output_file(summary_path)
        written["summary"] = summary_path

    if json_output is not None:
        json_path = resolve_output_path(root, json_output)
        ensure_output_file(json_path)
        written["json"] = json_path

    if "summary" in written:
        written["summary"].write_text(proof_markdown(payload), encoding="utf-8")
    if "json" in written:
        written["json"].write_text(proof_json(payload) + "\n", encoding="utf-8")

    return written


def ensure_output_file(output_path: Path) -> None:
    """Validate an explicit output file path."""
    if output_path.exists() and output_path.is_dir():
        raise ProofError(f"Output path exists as a directory: {output_path}")
    if not output_path.parent.exists():
        message = f"Output parent directory does not exist: {output_path.parent}"
        raise ProofError(message)
