"""Compare two VibeBench runs and write a Markdown summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from vibebench.paths import config_dir
from vibebench.report import ReportError

Verdict = Literal["improved", "stable", "regressed"]

RISK_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

RECOMMENDATIONS: dict[Verdict, str] = {
    "improved": "Quality improved compared with the previous run.",
    "stable": "Quality is stable compared with the previous run.",
    "regressed": (
        "Review carefully before shipping; this run regressed against the "
        "previous run."
    ),
}


class CompareMetric(BaseModel):
    """One metric row in a VibeBench run comparison."""

    model_config = ConfigDict(extra="forbid")

    name: str
    base: str
    current: str
    delta: str


class RunSnapshot(BaseModel):
    """Small comparable snapshot of one metrics.json payload."""

    model_config = ConfigDict(extra="forbid")

    run_dir: Path
    overall_status: str
    score: int
    risk_level: str
    command_count: int
    passed_command_count: int
    failed_command_count: int
    changed_files: int
    added_lines: int
    deleted_lines: int
    patch_lines: int
    risk_findings_count: int


class CompareResult(BaseModel):
    """Structured result for comparing two VibeBench runs."""

    model_config = ConfigDict(extra="forbid")

    base_run: Path
    current_run: Path
    verdict: Verdict
    score_delta: int
    risk_delta: str
    metrics: list[CompareMetric]
    recommendation: str
    output_path: Path


def find_comparable_runs(project_root: Path) -> list[Path]:
    """Return run directories that contain metrics.json, sorted by name."""
    runs_dir = config_dir(project_root) / "runs"
    if not runs_dir.exists():
        return []
    return sorted(
        path
        for path in runs_dir.iterdir()
        if path.is_dir() and (path / "metrics.json").exists()
    )


def load_run_snapshot(run_dir: Path) -> RunSnapshot:
    """Load comparable values from a run directory."""
    metrics_path = run_dir / "metrics.json"
    if not run_dir.exists() or not run_dir.is_dir():
        raise ReportError(f"Run directory does not exist: {run_dir}")
    if not metrics_path.exists():
        raise ReportError(f"No metrics.json found in {run_dir}.")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    summary = as_dict(metrics.get("summary"))
    diff = as_dict(metrics.get("diff_analysis"))
    findings = as_list(metrics.get("risk_findings"))
    commands = as_list(metrics.get("command_results"))

    return RunSnapshot(
        run_dir=run_dir,
        overall_status=text(metrics.get("overall_status", "unknown")),
        score=as_int(metrics.get("score")),
        risk_level=text(metrics.get("risk_level", "unknown")),
        command_count=as_int(summary.get("total_commands"), len(commands)),
        passed_command_count=as_int(summary.get("passed_commands")),
        failed_command_count=as_int(summary.get("failed_commands")),
        changed_files=as_int(diff.get("changed_file_count")),
        added_lines=as_int(diff.get("total_added_lines")),
        deleted_lines=as_int(diff.get("total_deleted_lines")),
        patch_lines=as_int(diff.get("total_patch_lines")),
        risk_findings_count=as_int(summary.get("total_findings"), len(findings)),
    )


def compare_runs(
    project_root: Path,
    current_run: Path | None = None,
    base_run: Path | None = None,
) -> CompareResult:
    """Compare two runs, write compare.md, and return the result."""
    root = project_root.resolve()
    selected_base, selected_current = select_runs(root, current_run, base_run)
    base = load_run_snapshot(selected_base)
    current = load_run_snapshot(selected_current)
    verdict = verdict_for(base, current)
    score_delta = current.score - base.score
    risk_delta = format_risk_delta(base.risk_level, current.risk_level)
    output_path = current.run_dir / "compare.md"

    result = CompareResult(
        base_run=base.run_dir,
        current_run=current.run_dir,
        verdict=verdict,
        score_delta=score_delta,
        risk_delta=risk_delta,
        metrics=metric_rows(base, current),
        recommendation=RECOMMENDATIONS[verdict],
        output_path=output_path,
    )
    output_path.write_text(render_markdown(result), encoding="utf-8")
    return result


def select_runs(
    project_root: Path,
    current_run: Path | None,
    base_run: Path | None,
) -> tuple[Path, Path]:
    """Select base and current run directories."""
    if current_run is not None or base_run is not None:
        if current_run is None or base_run is None:
            raise ReportError(
                "Provide both --base-run and --current-run, or neither."
            )
        return (
            resolve_run(project_root, base_run),
            resolve_run(project_root, current_run),
        )

    runs = find_comparable_runs(project_root)
    if len(runs) < 2:
        raise ReportError(
            "Need at least two VibeBench runs with metrics.json. "
            "Run 'vibebench check' at least twice or provide explicit run dirs."
        )
    return runs[-2], runs[-1]


def resolve_run(project_root: Path, run_dir: Path) -> Path:
    """Resolve a run directory relative to the project root."""
    return (run_dir if run_dir.is_absolute() else project_root / run_dir).resolve()


def verdict_for(base: RunSnapshot, current: RunSnapshot) -> Verdict:
    """Return the comparison verdict."""
    if (
        current.score < base.score
        or risk_rank(current.risk_level) > risk_rank(base.risk_level)
        or current.failed_command_count > base.failed_command_count
        or current.risk_findings_count > base.risk_findings_count
    ):
        return "regressed"
    if current.score > base.score and risk_rank(current.risk_level) <= risk_rank(
        base.risk_level
    ):
        return "improved"
    return "stable"


def metric_rows(base: RunSnapshot, current: RunSnapshot) -> list[CompareMetric]:
    """Build table rows for comparable metrics."""
    return [
        text_metric("Overall status", base.overall_status, current.overall_status),
        number_metric("VibeScore", base.score, current.score),
        text_metric("Risk level", base.risk_level, current.risk_level),
        number_metric("Command count", base.command_count, current.command_count),
        number_metric(
            "Passed command count",
            base.passed_command_count,
            current.passed_command_count,
        ),
        number_metric(
            "Failed command count",
            base.failed_command_count,
            current.failed_command_count,
        ),
        number_metric("Changed files", base.changed_files, current.changed_files),
        number_metric("Added lines", base.added_lines, current.added_lines),
        number_metric("Deleted lines", base.deleted_lines, current.deleted_lines),
        number_metric("Patch lines", base.patch_lines, current.patch_lines),
        number_metric(
            "Risk findings count",
            base.risk_findings_count,
            current.risk_findings_count,
        ),
    ]


def number_metric(name: str, base: int, current: int) -> CompareMetric:
    """Build a numeric metric row."""
    return CompareMetric(
        name=name,
        base=str(base),
        current=str(current),
        delta=format_number_delta(current - base),
    )


def text_metric(name: str, base: str, current: str) -> CompareMetric:
    """Build a text metric row."""
    delta = "unchanged" if base == current else f"{base} -> {current}"
    return CompareMetric(name=name, base=base, current=current, delta=delta)


def render_markdown(result: CompareResult) -> str:
    """Render compare.md."""
    lines = [
        "# VibeBench Compare",
        "",
        f"- Base run: `{result.base_run}`",
        f"- Current run: `{result.current_run}`",
        f"- Verdict: **{result.verdict}**",
        f"- Score delta: `{format_number_delta(result.score_delta)}`",
        f"- Risk delta: `{result.risk_delta}`",
        "",
        "| Metric | Base | Current | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for metric in result.metrics:
        lines.append(
            "| "
            f"{escape_markdown(metric.name)} | "
            f"{escape_markdown(metric.base)} | "
            f"{escape_markdown(metric.current)} | "
            f"{escape_markdown(metric.delta)} |"
        )
    lines.extend(["", f"Recommendation: {result.recommendation}", ""])
    return "\n".join(lines)


def format_risk_delta(base: str, current: str) -> str:
    """Format risk movement between two runs."""
    return "unchanged" if base == current else f"{base} -> {current}"


def risk_rank(value: str) -> int:
    """Return a safe comparable rank for risk level."""
    return RISK_ORDER.get(value.lower(), len(RISK_ORDER))


def format_number_delta(value: int) -> str:
    """Format a signed numeric delta."""
    if value > 0:
        return f"+{value}"
    return str(value)


def as_dict(value: object) -> dict[str, Any]:
    """Return value as a dict if possible."""
    return value if isinstance(value, dict) else {}


def as_list(value: object) -> list[Any]:
    """Return value as a list if possible."""
    return value if isinstance(value, list) else []


def as_int(value: object, default: int = 0) -> int:
    """Coerce a dynamic JSON value to int safely."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def text(value: object) -> str:
    """Convert a dynamic JSON value to text."""
    if value is None:
        return ""
    return str(value)


def escape_markdown(value: str) -> str:
    """Escape table-sensitive Markdown characters."""
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")
