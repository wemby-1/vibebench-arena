"""GitHub Actions annotation rendering for VibeBench runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from vibebench.explain import find_latest_valid_run
from vibebench.pr_comment import as_dict, as_list, text
from vibebench.report import ReportError, load_metrics

Severity = Literal["info", "warning", "high", "critical"]

SEVERITY_ORDER: dict[str, int] = {
    "info": 0,
    "warning": 1,
    "high": 2,
    "critical": 3,
}


@dataclass(frozen=True)
class Annotation:
    """One rendered VibeBench annotation."""

    level: str
    title: str
    message: str
    paths: list[str]


@dataclass(frozen=True)
class AnnotationResult:
    """Result of rendering annotations for a run."""

    run_dir: Path
    annotations: list[Annotation]
    output: str


def generate_annotations(
    project_root: Path,
    run_dir: Path | None = None,
    *,
    min_severity: str = "warning",
    github_actions: bool = True,
) -> AnnotationResult:
    """Generate GitHub Actions or plain-text annotations for a run."""
    validate_min_severity(min_severity)
    selected_run_dir = (run_dir or find_latest_valid_run(project_root)).resolve()
    if run_dir is not None:
        validate_run_dir(selected_run_dir)
    try:
        metrics = load_metrics(selected_run_dir)
    except json.JSONDecodeError as exc:
        message = f"metrics.json in {selected_run_dir} is not valid JSON."
        raise ReportError(message) from exc

    annotations = collect_annotations(metrics, min_severity=min_severity)
    output = render_annotations(annotations, github_actions=github_actions)
    return AnnotationResult(
        run_dir=selected_run_dir,
        annotations=annotations,
        output=output,
    )


def validate_run_dir(run_dir: Path) -> None:
    """Validate an explicitly selected run directory."""
    if not run_dir.exists():
        raise ReportError(f"Run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise ReportError(f"Run path is not a directory: {run_dir}")


def validate_min_severity(value: str) -> None:
    """Validate a minimum severity value."""
    if value not in SEVERITY_ORDER:
        allowed = ", ".join(SEVERITY_ORDER)
        message = f"Invalid min severity '{value}'. Expected one of: {allowed}."
        raise ReportError(message)


def collect_annotations(
    metrics: dict[str, Any],
    *,
    min_severity: str,
) -> list[Annotation]:
    """Collect annotations from risk findings and command failures."""
    annotations: list[Annotation] = []
    min_rank = SEVERITY_ORDER[min_severity]

    for finding in as_list(metrics.get("risk_findings")):
        item = as_dict(finding)
        severity = text(item.get("severity", "info"))
        if SEVERITY_ORDER.get(severity, -1) < min_rank:
            continue
        annotations.append(
            Annotation(
                level=level_for_finding(severity),
                title=f"VibeBench {severity}: {text(item.get('code', 'unknown'))}",
                message=text(item.get("message", "")),
                paths=[text(path) for path in as_list(item.get("paths"))],
            )
        )

    for command in as_list(metrics.get("command_results")):
        item = as_dict(command)
        if text(item.get("status", "")) == "passed":
            continue
        command_text = text(item.get("command", ""))
        exit_code = text(item.get("exit_code", ""))
        annotations.append(
            Annotation(
                level="error",
                title="VibeBench command failed",
                message=f"{command_text} failed with exit code {exit_code}",
                paths=[],
            )
        )

    return annotations


def level_for_finding(severity: str) -> str:
    """Map VibeBench finding severity to GitHub annotation level."""
    if severity == "info":
        return "notice"
    if severity == "warning":
        return "warning"
    return "error"


def render_annotations(
    annotations: list[Annotation],
    *,
    github_actions: bool,
) -> str:
    """Render annotations."""
    if not annotations:
        return "No VibeBench annotations to emit."

    lines = []
    for annotation in annotations:
        if github_actions:
            lines.append(render_github_annotation(annotation))
        else:
            path_text = ", ".join(annotation.paths) if annotation.paths else "no paths"
            lines.append(
                f"{annotation.level.upper()}: {annotation.title}: "
                f"{annotation.message} ({path_text})"
            )
    return "\n".join(lines)


def render_github_annotation(annotation: Annotation) -> str:
    """Render one GitHub workflow command annotation."""
    properties = [f"title={escape_property(annotation.title)}"]
    if annotation.paths:
        properties.append(f"file={escape_property(annotation.paths[0])}")
    return (
        f"::{annotation.level} {','.join(properties)}::"
        f"{escape_message(annotation.message)}"
    )


def escape_property(value: str) -> str:
    """Escape a GitHub workflow command property value."""
    return escape_common(value).replace(":", "%3A").replace(",", "%2C")


def escape_message(value: str) -> str:
    """Escape a GitHub workflow command message value."""
    return escape_common(value).replace(":", "%3A").replace(",", "%2C")


def escape_common(value: str) -> str:
    """Escape characters required by GitHub workflow commands."""
    return (
        value.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )
