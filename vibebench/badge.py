"""Shields.io-compatible badge artifact generation for VibeBench runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from vibebench.explain import find_latest_valid_run
from vibebench.pr_comment import text
from vibebench.report import ReportError, load_metrics

BADGE_JSON_FILENAME = "badge.json"
BADGE_MARKDOWN_FILENAME = "badge.md"
BADGE_URL_FILENAME = "badge-url.txt"
DEFAULT_BADGE_LABEL = "VibeBench"
SHIELDS_STATIC_BADGE_BASE_URL = "https://img.shields.io/badge"
BadgeFormat = Literal["json", "markdown", "url"]


@dataclass(frozen=True)
class BadgeResult:
    """Result of generating a VibeBench badge artifact."""

    run_dir: Path
    run_id: str
    output_path: Path
    label: str
    message: str
    color: str
    format: str


def generate_badge(
    project_root: Path,
    run_dir: Path | None = None,
    output_path: Path | None = None,
    *,
    label: str = DEFAULT_BADGE_LABEL,
    badge_format: str = "json",
) -> BadgeResult:
    """Generate a Shields.io-compatible badge artifact."""
    validate_badge_format(badge_format)
    selected_run_dir = (run_dir or find_latest_valid_run(project_root)).resolve()
    if run_dir is not None:
        validate_run_dir(selected_run_dir)

    try:
        metrics = load_metrics(selected_run_dir)
    except json.JSONDecodeError as exc:
        message = f"metrics.json in {selected_run_dir} is not valid JSON."
        raise ReportError(message) from exc

    selected_output = (
        output_path or selected_run_dir / default_badge_filename(badge_format)
    ).resolve()
    validate_output_path(selected_output)

    badge = badge_payload(metrics, label=label)
    content = render_badge_content(badge, badge_format)
    selected_output.write_text(content, encoding="utf-8")
    return BadgeResult(
        run_dir=selected_run_dir,
        run_id=selected_run_dir.name,
        output_path=selected_output,
        label=text(badge["label"]),
        message=text(badge["message"]),
        color=text(badge["color"]),
        format=badge_format,
    )


def generate_ci_badges(project_root: Path, run_dir: Path | None = None) -> Path:
    """Generate the default CI badge artifacts and return badge.json."""
    selected_run_dir = (run_dir or find_latest_valid_run(project_root)).resolve()
    json_result = generate_badge(project_root, selected_run_dir, badge_format="json")
    generate_badge(project_root, selected_run_dir, badge_format="markdown")
    return json_result.output_path


def validate_badge_format(value: str) -> None:
    """Validate a badge output format."""
    if value not in {"json", "markdown", "url"}:
        message = "Unsupported badge format. Expected one of: json, markdown, url."
        raise ReportError(message)


def default_badge_filename(badge_format: str) -> str:
    """Return the default output filename for a badge format."""
    if badge_format == "markdown":
        return BADGE_MARKDOWN_FILENAME
    if badge_format == "url":
        return BADGE_URL_FILENAME
    return BADGE_JSON_FILENAME


def validate_run_dir(run_dir: Path) -> None:
    """Validate an explicitly selected run directory."""
    if not run_dir.exists():
        raise ReportError(f"Run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise ReportError(f"Run path is not a directory: {run_dir}")


def validate_output_path(output_path: Path) -> None:
    """Validate a badge output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"Output path is a directory: {output_path}")
    if not output_path.parent.exists():
        message = f"Output parent directory does not exist: {output_path.parent}"
        raise ReportError(message)


def badge_payload(metrics: dict[str, Any], *, label: str) -> dict[str, Any]:
    """Build a Shields.io endpoint JSON payload."""
    status = text(metrics.get("overall_status", "unknown"))
    risk = text(metrics.get("risk_level", "unknown"))
    score = score_value(metrics.get("score", 0))
    return {
        "schemaVersion": 1,
        "label": label,
        "message": badge_message(status=status, score=score, risk=risk),
        "color": badge_color(status=status, score=score, risk=risk),
    }


def render_badge_content(badge: dict[str, Any], badge_format: str) -> str:
    """Render badge content for the selected format."""
    if badge_format == "markdown":
        label = text(badge["label"])
        return f"![{label}]({badge_url(badge)})\n"
    if badge_format == "url":
        return f"{badge_url(badge)}\n"
    return json.dumps(badge, indent=2, ensure_ascii=False) + "\n"


def badge_url(badge: dict[str, Any]) -> str:
    """Return a deterministic Shields static badge URL."""
    label = quote(text(badge["label"]), safe="")
    message = quote(text(badge["message"]), safe="")
    color = quote(text(badge["color"]), safe="")
    return f"{SHIELDS_STATIC_BADGE_BASE_URL}/{label}-{message}-{color}"


def badge_message(*, status: str, score: int, risk: str) -> str:
    """Return the badge message."""
    if status != "passed":
        return f"failed {risk}"
    return f"{score} {risk}"


def badge_color(*, status: str, score: int, risk: str) -> str:
    """Return a deterministic badge color."""
    if status != "passed" or risk in {"high", "critical"} or score < 80:
        return "red"
    if score >= 90 and risk == "low":
        return "brightgreen"
    if score >= 80 and risk in {"low", "medium"}:
        return "green"
    return "yellow"


def score_value(value: Any) -> int:
    """Convert a score metric to int safely."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
