"""README status block generation for VibeBench runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibebench.explain import find_latest_valid_run
from vibebench.pr_comment import as_dict, as_list, text
from vibebench.report import ReportError, load_metrics

STATUS_BLOCK_FILENAME = "status-block.md"
DEFAULT_STATUS_TITLE = "VibeBench Status"

STATUS_ARTIFACTS = [
    Path("report") / "index.html",
    Path("pr-comment.md"),
    Path("explain.md"),
    Path("gate-summary.md"),
    Path("export.json"),
    Path("badge.json"),
    Path("badge.md"),
    Path("badge-url.txt"),
    Path("vibebench-bundle.zip"),
]


@dataclass(frozen=True)
class StatusBlockResult:
    """Result of generating a README status block."""

    run_dir: Path
    run_id: str
    output_path: Path
    title: str
    include_badge: bool
    include_artifacts: bool


def generate_status_block(
    project_root: Path,
    run_dir: Path | None = None,
    output_path: Path | None = None,
    *,
    title: str = DEFAULT_STATUS_TITLE,
    include_badge: bool = True,
    include_artifacts: bool = True,
) -> StatusBlockResult:
    """Generate a copy-pasteable README status block."""
    if run_dir is not None:
        validate_run_dir(run_dir)
        selected_run_dir = run_dir.resolve()
    else:
        selected_run_dir = find_latest_valid_run(project_root).resolve()

    try:
        metrics = load_metrics(selected_run_dir)
    except json.JSONDecodeError as exc:
        message = f"metrics.json in {selected_run_dir} is not valid JSON."
        raise ReportError(message) from exc

    selected_output = (
        output_path or selected_run_dir / STATUS_BLOCK_FILENAME
    ).resolve()
    validate_output_path(selected_output)
    selected_output.write_text(
        render_status_block(
            metrics,
            selected_run_dir,
            title=title,
            include_badge=include_badge,
            include_artifacts=include_artifacts,
        ),
        encoding="utf-8",
    )
    return StatusBlockResult(
        run_dir=selected_run_dir,
        run_id=selected_run_dir.name,
        output_path=selected_output,
        title=title,
        include_badge=include_badge,
        include_artifacts=include_artifacts,
    )


def validate_run_dir(run_dir: Path) -> None:
    """Validate an explicitly selected run directory."""
    if run_dir.is_symlink():
        raise ReportError(f"Run directory must not be a symlink: {run_dir}")
    if not run_dir.exists():
        raise ReportError(f"Run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise ReportError(f"Run path is not a directory: {run_dir}")


def validate_output_path(output_path: Path) -> None:
    """Validate a status block output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"Output path is a directory: {output_path}")
    if not output_path.parent.exists():
        message = f"Output parent directory does not exist: {output_path.parent}"
        raise ReportError(message)


def render_status_block(
    metrics: dict[str, Any],
    run_dir: Path,
    *,
    title: str,
    include_badge: bool,
    include_artifacts: bool,
) -> str:
    """Render status block Markdown."""
    diff = as_dict(metrics.get("diff_analysis"))
    findings = as_list(metrics.get("risk_findings"))
    lines = [
        f"## {markdown_text(title)}",
        "",
    ]

    badge_line = badge_markdown(run_dir) if include_badge else None
    if badge_line:
        lines.extend([badge_line, ""])

    lines.extend(
        [
            "- Overall status: "
            f"{markdown_text(metrics.get('overall_status', 'unknown'))}",
            f"- VibeScore: {markdown_text(metrics.get('score', 0))}",
            f"- Risk level: {markdown_text(metrics.get('risk_level', 'unknown'))}",
            f"- Changed files: {markdown_text(diff.get('changed_file_count', 0))}",
            f"- Patch lines: {markdown_text(diff.get('total_patch_lines', 0))}",
            f"- Risk findings: {len(findings)}",
            f"- Generated at: {markdown_text(metrics.get('created_at', ''))}",
            "",
        ]
    )

    if include_artifacts:
        artifacts = existing_artifacts(run_dir)
        if artifacts:
            lines.extend(["Artifacts:"])
            lines.extend(f"- {artifact.as_posix()}" for artifact in artifacts)
            lines.append("")

    return "\n".join(lines)


def badge_markdown(run_dir: Path) -> str | None:
    """Return badge Markdown if a badge artifact is available."""
    badge_md = run_dir / "badge.md"
    if badge_md.is_file() and not badge_md.is_symlink():
        first_line = badge_md.read_text(encoding="utf-8").splitlines()
        return first_line[0] if first_line else None

    badge_url = run_dir / "badge-url.txt"
    if badge_url.is_file() and not badge_url.is_symlink():
        first_line = badge_url.read_text(encoding="utf-8").splitlines()
        if first_line:
            return f"![VibeBench]({first_line[0]})"
    return None


def existing_artifacts(run_dir: Path) -> list[Path]:
    """Return existing standard artifacts relative to the run directory."""
    artifacts = []
    for relative_path in STATUS_ARTIFACTS:
        artifact_path = run_dir / relative_path
        if artifact_path.is_file() and not artifact_path.is_symlink():
            artifacts.append(relative_path)
    return artifacts


def markdown_text(value: object) -> str:
    """Return text safe for a Markdown bullet line."""
    return text(value).replace("\n", " ")
