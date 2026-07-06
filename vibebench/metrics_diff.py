"""Compare numeric metrics between two VibeBench runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from vibebench.baseline import BaselineMetadata, show_pinned_baseline
from vibebench.compare import find_valid_runs, resolve_run
from vibebench.metrics_check import evaluate_metrics_run, risk_value_for_level
from vibebench.report import ReportError, load_metrics

METRICS_DIFF_JSON = "metrics-diff.json"
METRICS_DIFF_SUMMARY = "metrics-diff.md"
MetricsDiffStatus = Literal["passed", "failed", "skipped"]
MetricDirection = Literal["up", "down", "same"]
MetricClassification = Literal[
    "improved",
    "regressed",
    "changed",
    "unchanged",
    "added",
    "removed",
    "unknown",
]


@dataclass(frozen=True)
class MetricsDiffChange:
    """One metric difference row."""

    metric: str
    baseline_value: float | int | None
    candidate_value: float | int | None
    delta: float | int | None
    percent_delta: float | None
    direction: MetricDirection | None
    classification: MetricClassification
    notes: str = ""


@dataclass(frozen=True)
class MetricsDiffSummary:
    """Summary counts for metrics diff output."""

    compared_numeric_count: int = 0
    improved_count: int = 0
    regressed_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    added_count: int = 0
    removed_count: int = 0


@dataclass(frozen=True)
class MetricsDiffResult:
    """Structured metrics diff result."""

    status: MetricsDiffStatus
    baseline_source: str
    baseline_label: str | None
    baseline_run: str | None
    candidate_run: str | None
    baseline_metrics_source: str
    candidate_metrics_source: str
    baseline_metrics_valid: bool
    candidate_metrics_valid: bool
    summary: MetricsDiffSummary
    changes: list[MetricsDiffChange]
    errors: list[str]
    warnings: list[str]
    message: str
    baseline_run_dir: Path | None = None
    candidate_run_dir: Path | None = None
    json_path: Path | None = None
    summary_path: Path | None = None


@dataclass(frozen=True)
class MetricsSelection:
    """Selected metrics payload and its provenance."""

    run_dir: Path | None
    run_id: str | None
    metrics: dict[str, Any] | None
    source: str
    metrics_source: str
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def run_metrics_diff(
    project_root: Path,
    *,
    runs_dir: Path | None = None,
    baseline_run: str | Path | None = None,
    candidate_run: str | Path | None = None,
    baseline_label: str | None = None,
    strict: bool = False,
    include_unchanged: bool = False,
    top: int | None = None,
    json_output: Path | None = None,
    summary_output: Path | None = None,
) -> MetricsDiffResult:
    """Compare baseline and candidate metrics."""
    if top is not None and top < 1:
        raise ReportError("--top must be greater than 0.")
    root = project_root.resolve()
    candidate = select_candidate(root, runs_dir, candidate_run)
    if candidate.metrics is None:
        result = MetricsDiffResult(
            status="failed",
            baseline_source="none",
            baseline_label=baseline_label,
            baseline_run=None,
            candidate_run=candidate.run_id,
            baseline_metrics_source="none",
            candidate_metrics_source=candidate.metrics_source,
            baseline_metrics_valid=False,
            candidate_metrics_valid=False,
            summary=MetricsDiffSummary(),
            changes=[],
            errors=candidate.errors or ["No candidate run is available."],
            warnings=candidate.warnings,
            message="No candidate metrics are available.",
            candidate_run_dir=candidate.run_dir,
        )
        return write_metrics_diff_outputs(result, json_output, summary_output)

    baseline = select_baseline(root, runs_dir, candidate, baseline_run, baseline_label)
    if baseline.metrics is None:
        status: MetricsDiffStatus = "failed" if strict else "skipped"
        message = (
            baseline.errors[0]
            if baseline.errors
            else "No baseline metrics are available."
        )
        result = MetricsDiffResult(
            status=status,
            baseline_source=baseline.source,
            baseline_label=baseline_label,
            baseline_run=baseline.run_id,
            candidate_run=candidate.run_id,
            baseline_metrics_source=baseline.metrics_source,
            candidate_metrics_source=candidate.metrics_source,
            baseline_metrics_valid=False,
            candidate_metrics_valid=candidate.valid,
            summary=MetricsDiffSummary(),
            changes=[],
            errors=baseline.errors if strict else [],
            warnings=baseline.errors if not strict else baseline.warnings,
            message=message,
            baseline_run_dir=baseline.run_dir,
            candidate_run_dir=candidate.run_dir,
        )
        return write_metrics_diff_outputs(result, json_output, summary_output)

    result = evaluate_metrics_diff(
        baseline,
        candidate,
        baseline_label=baseline_label,
        include_unchanged=include_unchanged,
        top=top,
    )
    return write_metrics_diff_outputs(result, json_output, summary_output)


def select_candidate(
    project_root: Path,
    runs_dir: Path | None,
    candidate_run: str | Path | None,
) -> MetricsSelection:
    """Select candidate metrics."""
    if candidate_run is not None:
        return selection_from_run(
            resolve_run(project_root, Path(str(candidate_run))),
            source="explicit_run",
        )
    valid = find_valid_runs(project_root, runs_dir)
    if not valid.runs:
        return MetricsSelection(
            run_dir=None,
            run_id=None,
            metrics=None,
            source="none",
            metrics_source="none",
            valid=False,
            errors=["No valid candidate run exists."],
            warnings=valid.skipped_runs,
        )
    run_dir, _metrics = valid.runs[-1]
    return selection_from_run(run_dir, source="latest_run")


def select_baseline(
    project_root: Path,
    runs_dir: Path | None,
    candidate: MetricsSelection,
    baseline_run: str | Path | None,
    baseline_label: str | None,
) -> MetricsSelection:
    """Select baseline metrics."""
    if baseline_run is not None:
        return selection_from_run(
            resolve_run(project_root, Path(str(baseline_run))),
            source="explicit_run",
        )
    if baseline_label is not None:
        return selection_from_label(project_root, baseline_label)
    if candidate.run_dir is None:
        return MetricsSelection(
            run_dir=None,
            run_id=None,
            metrics=None,
            source="none",
            metrics_source="none",
            valid=False,
            errors=["No candidate run is available for previous-run selection."],
        )
    valid = find_valid_runs(project_root, runs_dir)
    previous = [
        run_dir
        for run_dir, _metrics in valid.runs
        if run_dir != candidate.run_dir and run_dir.name < candidate.run_dir.name
    ]
    if not previous:
        return MetricsSelection(
            run_dir=None,
            run_id=None,
            metrics=None,
            source="none",
            metrics_source="none",
            valid=False,
            errors=["No previous baseline run exists for metrics diff."],
            warnings=valid.skipped_runs,
        )
    return selection_from_run(previous[-1], source="previous_run")


def selection_from_label(project_root: Path, label: str) -> MetricsSelection:
    """Select metrics from a pinned baseline label."""
    pinned = show_pinned_baseline(project_root, label=label)
    if pinned.metadata is None:
        return MetricsSelection(
            run_dir=None,
            run_id=None,
            metrics=None,
            source="baseline_label",
            metrics_source="none",
            valid=False,
            errors=[pinned.message],
        )
    if pinned.live_metrics_available and pinned.run_dir is not None:
        return selection_from_run(
            pinned.run_dir,
            source="baseline_label",
            run_id=pinned.metadata.run_id,
        )
    if pinned.metadata.metrics_snapshot is not None:
        return selection_from_snapshot(pinned.metadata, pinned.run_dir)
    return MetricsSelection(
        run_dir=pinned.run_dir,
        run_id=pinned.metadata.run_id,
        metrics=None,
        source="baseline_label",
        metrics_source="none",
        valid=False,
        errors=[pinned.message],
    )


def selection_from_run(
    run_dir: Path,
    *,
    source: str,
    run_id: str | None = None,
) -> MetricsSelection:
    """Build a live metrics selection from a run directory."""
    try:
        metrics = load_metrics(run_dir)
    except json.JSONDecodeError as exc:
        return MetricsSelection(
            run_dir=run_dir,
            run_id=run_id or run_dir.name,
            metrics=None,
            source=source,
            metrics_source="none",
            valid=False,
            errors=[f"metrics.json in {run_dir} is not valid JSON: {exc}"],
        )
    validation = evaluate_metrics_run(run_dir)
    return MetricsSelection(
        run_dir=run_dir,
        run_id=run_id or run_dir.name,
        metrics=metrics,
        source=source,
        metrics_source="live",
        valid=validation.status != "failed",
        warnings=[
            check.message for check in validation.checks if check.status == "warning"
        ],
        errors=[
            check.message for check in validation.checks if check.status == "failed"
        ],
    )


def selection_from_snapshot(
    metadata: BaselineMetadata,
    run_dir: Path | None,
) -> MetricsSelection:
    """Build a baseline selection from a portable metrics snapshot."""
    snapshot = metadata.metrics_snapshot
    if snapshot is None:
        return MetricsSelection(
            run_dir=run_dir,
            run_id=metadata.run_id,
            metrics=None,
            source="baseline_label",
            metrics_source="none",
            valid=False,
            errors=["Pinned baseline has no portable metrics snapshot."],
        )
    metrics: dict[str, Any] = {
        "score": snapshot.score,
        "risk_level": snapshot.risk_level,
    }
    if snapshot.status is not None:
        metrics["overall_status"] = snapshot.status
    if snapshot.project is not None:
        metrics["project_name"] = snapshot.project
    if snapshot.created_at is not None:
        metrics["created_at"] = snapshot.created_at
    return MetricsSelection(
        run_dir=run_dir,
        run_id=metadata.run_id,
        metrics=metrics,
        source="baseline_label",
        metrics_source="snapshot",
        valid=True,
        warnings=(
            []
            if run_dir and run_dir.exists()
            else ["Using portable metrics snapshot."]
        ),
    )


def evaluate_metrics_diff(
    baseline: MetricsSelection,
    candidate: MetricsSelection,
    *,
    baseline_label: str | None,
    include_unchanged: bool,
    top: int | None,
) -> MetricsDiffResult:
    """Evaluate numeric metric changes between two selections."""
    base_metrics = baseline.metrics or {}
    candidate_metrics = candidate.metrics or {}
    base_flat = flatten_numeric_metrics(base_metrics)
    candidate_flat = flatten_numeric_metrics(candidate_metrics)
    all_metrics = sorted(set(base_flat) | set(candidate_flat))
    all_changes: list[MetricsDiffChange] = []
    compared_numeric_count = 0
    non_numeric_changed_count = count_non_numeric_changes(
        base_metrics,
        candidate_metrics,
    )
    warnings = [*baseline.warnings, *candidate.warnings]
    if non_numeric_changed_count:
        warnings.append(
            f"{non_numeric_changed_count} non-numeric metric value(s) changed "
            "and were not diffed."
        )

    for metric in all_metrics:
        in_base = metric in base_flat
        in_candidate = metric in candidate_flat
        if in_base and in_candidate:
            compared_numeric_count += 1
            change = metric_change(metric, base_flat[metric], candidate_flat[metric])
            if include_unchanged or change.classification != "unchanged":
                all_changes.append(change)
        elif in_candidate:
            all_changes.append(
                MetricsDiffChange(
                    metric=metric,
                    baseline_value=None,
                    candidate_value=candidate_flat[metric],
                    delta=None,
                    percent_delta=None,
                    direction=None,
                    classification="added",
                    notes="Numeric metric exists only in candidate.",
                )
            )
        else:
            all_changes.append(
                MetricsDiffChange(
                    metric=metric,
                    baseline_value=base_flat[metric],
                    candidate_value=None,
                    delta=None,
                    percent_delta=None,
                    direction=None,
                    classification="removed",
                    notes="Numeric metric exists only in baseline.",
                )
            )

    display_changes = limit_changes(all_changes, top)
    summary = MetricsDiffSummary(
        compared_numeric_count=compared_numeric_count,
        improved_count=count_class(all_changes, "improved"),
        regressed_count=count_class(all_changes, "regressed"),
        changed_count=sum(
            1
            for change in all_changes
            if change.classification in {"changed", "improved", "regressed"}
        ),
        unchanged_count=count_class(all_changes, "unchanged"),
        added_count=count_class(all_changes, "added"),
        removed_count=count_class(all_changes, "removed"),
    )
    status: MetricsDiffStatus = "failed" if summary.regressed_count else "passed"
    message = (
        "Metrics diff found semantic regressions."
        if status == "failed"
        else "Metrics diff completed."
    )
    return MetricsDiffResult(
        status=status,
        baseline_source=baseline.source,
        baseline_label=baseline_label,
        baseline_run=baseline.run_id,
        candidate_run=candidate.run_id,
        baseline_metrics_source=baseline.metrics_source,
        candidate_metrics_source=candidate.metrics_source,
        baseline_metrics_valid=baseline.valid,
        candidate_metrics_valid=candidate.valid,
        summary=summary,
        changes=display_changes,
        errors=[*baseline.errors, *candidate.errors],
        warnings=warnings,
        message=message,
        baseline_run_dir=baseline.run_dir,
        candidate_run_dir=candidate.run_dir,
    )


def flatten_numeric_metrics(metrics: dict[str, Any]) -> dict[str, float | int]:
    """Return deterministic numeric leaf metrics."""
    flattened: dict[str, float | int] = {}

    def visit(prefix: str, value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int | float):
            flattened[prefix] = value
            return
        if isinstance(value, str) and prefix == "risk_level":
            risk_value = risk_value_for_level(value)
            if risk_value is not None:
                flattened["risk"] = risk_value
            return
        if isinstance(value, dict):
            for key in sorted(value):
                child = f"{prefix}.{key}" if prefix else str(key)
                visit(child, value[key])

    visit("", metrics)
    return flattened


def flatten_leaf_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Flatten scalar JSON leaves for non-numeric change counting."""
    flattened: dict[str, Any] = {}

    def visit(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for key in sorted(value):
                child = f"{prefix}.{key}" if prefix else str(key)
                visit(child, value[key])
        elif isinstance(value, list):
            return
        else:
            flattened[prefix] = value

    visit("", metrics)
    return flattened


def count_non_numeric_changes(base: dict[str, Any], candidate: dict[str, Any]) -> int:
    """Count changed non-numeric leaf values."""
    base_flat = flatten_leaf_metrics(base)
    candidate_flat = flatten_leaf_metrics(candidate)
    numeric_paths = set(flatten_numeric_metrics(base)) | set(
        flatten_numeric_metrics(candidate)
    )
    count = 0
    for key in sorted(set(base_flat) | set(candidate_flat)):
        if key in numeric_paths or key == "risk_level":
            continue
        if base_flat.get(key) != candidate_flat.get(key):
            count += 1
    return count


def metric_change(
    metric: str,
    baseline_value: float | int,
    candidate_value: float | int,
) -> MetricsDiffChange:
    """Build one changed/same metric row."""
    delta = candidate_value - baseline_value
    direction: MetricDirection = "same"
    if delta > 0:
        direction = "up"
    elif delta < 0:
        direction = "down"
    percent_delta = None if baseline_value == 0 else (delta / baseline_value) * 100
    classification, notes = classify_metric(metric, direction)
    return MetricsDiffChange(
        metric=metric,
        baseline_value=baseline_value,
        candidate_value=candidate_value,
        delta=delta,
        percent_delta=percent_delta,
        direction=direction,
        classification=classification,
        notes=notes,
    )


def classify_metric(
    metric: str,
    direction: MetricDirection,
) -> tuple[MetricClassification, str]:
    """Classify a metric movement."""
    if direction == "same":
        return "unchanged", ""
    if metric == "score":
        return (
            "improved" if direction == "up" else "regressed",
            "Higher score is better.",
        )
    if metric in {"risk", "risk_value"}:
        return (
            "improved" if direction == "down" else "regressed",
            "Lower risk is better.",
        )
    return "changed", "No built-in good/bad semantics for this metric."


def limit_changes(
    changes: list[MetricsDiffChange],
    top: int | None,
) -> list[MetricsDiffChange]:
    """Limit changed metrics deterministically by largest absolute delta then name."""
    if top is None:
        return changes
    changed = [change for change in changes if change.classification != "unchanged"]
    ordered = sorted(
        changed,
        key=lambda change: (
            -abs(float(change.delta)) if change.delta is not None else 0,
            change.metric,
        ),
    )
    return ordered[:top]


def count_class(
    changes: list[MetricsDiffChange],
    classification: MetricClassification,
) -> int:
    """Count changes by classification."""
    return sum(1 for change in changes if change.classification == classification)


def write_metrics_diff_outputs(
    result: MetricsDiffResult,
    json_output: Path | None,
    summary_output: Path | None,
) -> MetricsDiffResult:
    """Write requested metrics-diff outputs."""
    json_path = None
    summary_path = None
    if json_output is not None:
        validate_output_path(json_output)
        json_output.write_text(metrics_diff_json(result) + "\n", encoding="utf-8")
        json_path = json_output.resolve()
    if summary_output is not None:
        validate_output_path(summary_output)
        summary_output.write_text(metrics_diff_markdown(result), encoding="utf-8")
        summary_path = summary_output.resolve()
    return MetricsDiffResult(
        status=result.status,
        baseline_source=result.baseline_source,
        baseline_label=result.baseline_label,
        baseline_run=result.baseline_run,
        candidate_run=result.candidate_run,
        baseline_metrics_source=result.baseline_metrics_source,
        candidate_metrics_source=result.candidate_metrics_source,
        baseline_metrics_valid=result.baseline_metrics_valid,
        candidate_metrics_valid=result.candidate_metrics_valid,
        summary=result.summary,
        changes=result.changes,
        errors=result.errors,
        warnings=result.warnings,
        message=result.message,
        baseline_run_dir=result.baseline_run_dir,
        candidate_run_dir=result.candidate_run_dir,
        json_path=json_path,
        summary_path=summary_path,
    )


def metrics_diff_payload(result: MetricsDiffResult) -> dict[str, object]:
    """Return deterministic JSON-compatible metrics-diff payload."""
    return {
        "status": result.status,
        "baseline_source": result.baseline_source,
        "baseline_label": result.baseline_label,
        "baseline_run": result.baseline_run,
        "candidate_run": result.candidate_run,
        "baseline_metrics_source": result.baseline_metrics_source,
        "candidate_metrics_source": result.candidate_metrics_source,
        "baseline_metrics_valid": result.baseline_metrics_valid,
        "candidate_metrics_valid": result.candidate_metrics_valid,
        "summary": {
            "compared_numeric_count": result.summary.compared_numeric_count,
            "improved_count": result.summary.improved_count,
            "regressed_count": result.summary.regressed_count,
            "changed_count": result.summary.changed_count,
            "unchanged_count": result.summary.unchanged_count,
            "added_count": result.summary.added_count,
            "removed_count": result.summary.removed_count,
        },
        "changes": [change_payload(change) for change in result.changes],
        "errors": result.errors,
        "warnings": result.warnings,
        "message": result.message,
    }


def change_payload(change: MetricsDiffChange) -> dict[str, object]:
    """Return JSON-safe change payload."""
    return {
        "metric": change.metric,
        "baseline_value": change.baseline_value,
        "candidate_value": change.candidate_value,
        "delta": change.delta,
        "percent_delta": change.percent_delta,
        "direction": change.direction,
        "classification": change.classification,
        "notes": change.notes,
    }


def metrics_diff_json(result: MetricsDiffResult) -> str:
    """Render metrics-diff JSON."""
    return json.dumps(metrics_diff_payload(result), indent=2, sort_keys=True)


def metrics_diff_markdown(result: MetricsDiffResult) -> str:
    """Render metrics-diff Markdown."""
    lines = [
        "# VibeBench Metrics Diff",
        "",
        f"- Status: `{result.status}`",
        f"- Baseline source: `{result.baseline_source}`",
        f"- Baseline label: `{result.baseline_label or 'none'}`",
        f"- Baseline run: `{result.baseline_run or 'none'}`",
        f"- Baseline metrics source: `{result.baseline_metrics_source}`",
        f"- Candidate run: `{result.candidate_run or 'none'}`",
        f"- Candidate metrics source: `{result.candidate_metrics_source}`",
        f"- Baseline metrics valid: `{str(result.baseline_metrics_valid).lower()}`",
        f"- Candidate metrics valid: `{str(result.candidate_metrics_valid).lower()}`",
        "",
        "## Summary",
        "",
        "| Count | Value |",
        "| --- | ---: |",
        f"| Compared numeric metrics | {result.summary.compared_numeric_count} |",
        f"| Improved | {result.summary.improved_count} |",
        f"| Regressed | {result.summary.regressed_count} |",
        f"| Changed | {result.summary.changed_count} |",
        f"| Unchanged | {result.summary.unchanged_count} |",
        f"| Added | {result.summary.added_count} |",
        f"| Removed | {result.summary.removed_count} |",
        "",
        "## Changed Numeric Metrics",
        "",
        "| Metric | Baseline | Candidate | Delta | Percent delta | "
        "Direction | Classification | Notes |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    changed = [
        change
        for change in result.changes
        if change.classification not in {"added", "removed"}
    ]
    if changed:
        for change in changed:
            lines.append(change_row(change))
    else:
        lines.append("| none |  |  |  |  |  |  |  |")
    lines.extend(["", "## Added Metrics", ""])
    added = [change for change in result.changes if change.classification == "added"]
    if added:
        for change in added:
            lines.append(
                f"- `{markdown_cell(change.metric)}` = "
                f"`{markdown_cell(change.candidate_value)}`"
            )
    else:
        lines.append("No added numeric metrics.")
    lines.extend(["", "## Removed Metrics", ""])
    removed = [
        change for change in result.changes if change.classification == "removed"
    ]
    if removed:
        for change in removed:
            lines.append(
                f"- `{markdown_cell(change.metric)}` was "
                f"`{markdown_cell(change.baseline_value)}`"
            )
    else:
        lines.append("No removed numeric metrics.")
    lines.extend(
        [
            "",
            "## Semantics",
            "",
            "- `score` treats higher values as better.",
            "- `risk` treats lower values as better.",
            "- Other numeric metrics are reported as changed/unchanged/"
            "added/removed unless VibeBench defines explicit semantics for them.",
            "",
        ]
    )
    if result.errors:
        lines.extend(["## Errors", ""])
        lines.extend(f"- {error}" for error in result.errors)
        lines.append("")
    if result.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in result.warnings)
        lines.append("")
    return "\n".join(lines)


def change_row(change: MetricsDiffChange) -> str:
    """Render one Markdown change row."""
    percent = "" if change.percent_delta is None else f"{change.percent_delta:.2f}%"
    return (
        "| "
        f"{markdown_cell(change.metric)} | "
        f"{markdown_cell(change.baseline_value)} | "
        f"{markdown_cell(change.candidate_value)} | "
        f"{markdown_cell(change.delta)} | "
        f"{markdown_cell(percent)} | "
        f"{markdown_cell(change.direction)} | "
        f"{markdown_cell(change.classification)} | "
        f"{markdown_cell(change.notes)} |"
    )


def markdown_cell(value: object) -> str:
    """Escape Markdown table cell content."""
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def validate_output_path(path: Path) -> None:
    """Validate an output file path."""
    if path.exists() and path.is_dir():
        raise ReportError(f"Output path is a directory: {path}")
    if not path.parent.exists():
        raise ReportError(f"Output parent directory does not exist: {path.parent}")
