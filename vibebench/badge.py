"""Shields.io-compatible badge artifact generation for VibeBench runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibebench.explain import find_latest_valid_run
from vibebench.pr_comment import text
from vibebench.report import ReportError, load_metrics

BADGE_FILENAME = "badge.json"
DEFAULT_BADGE_LABEL = "VibeBench"


@dataclass(frozen=True)
class BadgeResult:
    """Result of generating a VibeBench badge artifact."""

    run_dir: Path
    run_id: str
    output_path: Path
    label: str
    message: str
    color: str


def generate_badge(
    project_root: Path,
    run_dir: Path | None = None,
    output_path: Path | None = None,
    *,
    label: str = DEFAULT_BADGE_LABEL,
) -> BadgeResult:
    """Generate a Shields.io endpoint badge JSON artifact."""
    selected_run_dir = (run_dir or find_latest_valid_run(project_root)).resolve()
    if run_dir is not None:
        validate_run_dir(selected_run_dir)

    try:
        metrics = load_metrics(selected_run_dir)
    except json.JSONDecodeError as exc:
        message = f"metrics.json in {selected_run_dir} is not valid JSON."
        raise ReportError(message) from exc

    selected_output = (output_path or selected_run_dir / BADGE_FILENAME).resolve()
    validate_output_path(selected_output)

    badge = badge_payload(metrics, label=label)
    selected_output.write_text(
        json.dumps(badge, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return BadgeResult(
        run_dir=selected_run_dir,
        run_id=selected_run_dir.name,
        output_path=selected_output,
        label=text(badge["label"]),
        message=text(badge["message"]),
        color=text(badge["color"]),
    )


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
