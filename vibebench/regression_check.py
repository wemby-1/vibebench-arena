"""Local run quality regression gate for VibeBench."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vibebench.baseline import show_pinned_baseline
from vibebench.compare import (
    RISK_ORDER,
    find_valid_runs,
    load_run_snapshot,
    resolve_run,
)
from vibebench.report import ReportError

REGRESSION_CHECK_JSON = "regression-check.json"
REGRESSION_CHECK_SUMMARY = "regression-check.md"
RegressionStatus = Literal["passed", "failed", "skipped"]


@dataclass(frozen=True)
class RegressionThresholds:
    """Thresholds for local regression checks."""

    max_score_drop: float = 0.0
    max_risk_increase: float = 0.0
    require_baseline: bool = False


@dataclass(frozen=True)
class RegressionIssue:
    """One regression failure or warning."""

    code: str
    metric: str
    baseline_value: object | None
    candidate_value: object | None
    threshold: object | None
    message: str


@dataclass(frozen=True)
class RegressionCheckResult:
    """Structured result for a run quality regression check."""

    status: RegressionStatus
    baseline_run_dir: Path | None
    candidate_run_dir: Path | None
    baseline_run_id: str | None
    candidate_run_id: str | None
    thresholds: RegressionThresholds
    baseline_metrics: dict[str, object]
    candidate_metrics: dict[str, object]
    deltas: dict[str, object | None]
    failures: list[RegressionIssue]
    warnings: list[RegressionIssue]
    message: str
    baseline_source: str = "auto"
    baseline_label: str | None = None
    json_path: Path | None = None
    summary_path: Path | None = None


def run_regression_check(
    project_root: Path,
    *,
    runs_dir: Path | None = None,
    baseline_run: Path | None = None,
    candidate_run: Path | None = None,
    baseline_label: str | None = None,
    max_score_drop: float = 0.0,
    max_risk_increase: float = 0.0,
    require_baseline: bool = False,
    json_output: Path | None = None,
    summary_output: Path | None = None,
) -> RegressionCheckResult:
    """Compare a candidate run against a baseline run."""
    root = project_root.resolve()
    thresholds = RegressionThresholds(
        max_score_drop=max_score_drop,
        max_risk_increase=max_risk_increase,
        require_baseline=require_baseline,
    )
    if max_score_drop < 0:
        raise ReportError("--max-score-drop must be greater than or equal to 0.")
    if max_risk_increase < 0:
        raise ReportError("--max-risk-increase must be greater than or equal to 0.")

    candidate = select_candidate(root, runs_dir, candidate_run)
    if candidate is None:
        result = missing_baseline_result(
            thresholds,
            message="No candidate run is available; no baseline comparison was run.",
            failed=require_baseline,
        )
        return write_regression_outputs(result, json_output, summary_output)

    baseline_source = "auto"
    selected_baseline_label = None
    if baseline_run is not None:
        baseline = select_baseline(root, runs_dir, candidate, baseline_run)
        baseline_source = "explicit"
    elif baseline_label is not None:
        selected_baseline_label = baseline_label
        pinned = show_pinned_baseline(root, label=baseline_label)
        if pinned.metadata is None:
            result = missing_baseline_result(
                thresholds,
                message=pinned.message,
                failed=require_baseline,
                candidate_run=candidate,
                baseline_source="missing",
                baseline_label=baseline_label,
            )
            return write_regression_outputs(result, json_output, summary_output)
        if not pinned.is_valid or pinned.run_dir is None:
            raise ReportError(pinned.message)
        baseline = pinned.run_dir
        baseline_source = "pinned"
        selected_baseline_label = pinned.metadata.label
    else:
        baseline = select_baseline(root, runs_dir, candidate, baseline_run)

    if baseline is None:
        result = missing_baseline_result(
            thresholds,
            message="No previous baseline run exists for regression comparison.",
            failed=require_baseline,
            candidate_run=candidate,
            baseline_source="missing" if require_baseline else "auto",
            baseline_label=selected_baseline_label,
        )
        return write_regression_outputs(result, json_output, summary_output)

    result = evaluate_runs(
        baseline,
        candidate,
        thresholds,
        baseline_source=baseline_source,
        baseline_label=selected_baseline_label,
    )
    return write_regression_outputs(result, json_output, summary_output)


def select_candidate(
    project_root: Path,
    runs_dir: Path | None,
    candidate_run: Path | None,
) -> Path | None:
    """Select the candidate run directory."""
    if candidate_run is not None:
        return resolve_run(project_root, candidate_run)
    valid = find_valid_runs(project_root, runs_dir)
    if not valid.runs:
        return None
    return valid.runs[-1][0]


def select_baseline(
    project_root: Path,
    runs_dir: Path | None,
    candidate: Path,
    baseline_run: Path | None,
) -> Path | None:
    """Select the baseline run directory."""
    if baseline_run is not None:
        return resolve_run(project_root, baseline_run)
    valid = find_valid_runs(project_root, runs_dir)
    previous = [
        run_dir
        for run_dir, _metrics in valid.runs
        if run_dir != candidate and run_dir.name < candidate.name
    ]
    if previous:
        return previous[-1]
    return None


def missing_baseline_result(
    thresholds: RegressionThresholds,
    *,
    message: str,
    failed: bool,
    candidate_run: Path | None = None,
    baseline_source: str = "auto",
    baseline_label: str | None = None,
) -> RegressionCheckResult:
    """Return a skipped or failed no-baseline result."""
    status: RegressionStatus = "failed" if failed else "skipped"
    return RegressionCheckResult(
        status=status,
        baseline_run_dir=None,
        candidate_run_dir=candidate_run,
        baseline_run_id=None,
        candidate_run_id=candidate_run.name if candidate_run else None,
        thresholds=thresholds,
        baseline_metrics={},
        candidate_metrics=run_metrics(candidate_run) if candidate_run else {},
        deltas={"score_delta": None, "risk_delta": None},
        failures=[
            RegressionIssue(
                code="missing_baseline",
                metric="baseline",
                baseline_value=None,
                candidate_value=str(candidate_run) if candidate_run else None,
                threshold=None,
                message=message,
            )
        ]
        if failed
        else [],
        warnings=[],
        message=message,
        baseline_source=baseline_source,
        baseline_label=baseline_label,
    )


def evaluate_runs(
    baseline: Path,
    candidate: Path,
    thresholds: RegressionThresholds,
    *,
    baseline_source: str = "auto",
    baseline_label: str | None = None,
) -> RegressionCheckResult:
    """Evaluate candidate metrics against baseline metrics."""
    base = load_run_snapshot(baseline)
    head = load_run_snapshot(candidate)
    baseline_metrics = snapshot_metrics(base.score, base.risk_level)
    candidate_metrics = snapshot_metrics(head.score, head.risk_level)
    score_delta = head.score - base.score
    base_risk = risk_value(base.risk_level)
    head_risk = risk_value(head.risk_level)
    risk_delta = (
        None if base_risk is None or head_risk is None else head_risk - base_risk
    )
    warnings = metric_warnings(base.risk_level, head.risk_level)
    failures: list[RegressionIssue] = []

    if head.score < base.score - thresholds.max_score_drop:
        failures.append(
            RegressionIssue(
                code="score_regression",
                metric="score",
                baseline_value=base.score,
                candidate_value=head.score,
                threshold=thresholds.max_score_drop,
                message=(
                    "Candidate score dropped more than the allowed "
                    f"{thresholds.max_score_drop:g} points."
                ),
            )
        )
    if (
        base_risk is not None
        and head_risk is not None
        and head_risk > base_risk + thresholds.max_risk_increase
    ):
        failures.append(
            RegressionIssue(
                code="risk_regression",
                metric="risk",
                baseline_value=base.risk_level,
                candidate_value=head.risk_level,
                threshold=thresholds.max_risk_increase,
                message=(
                    "Candidate risk increased more than the allowed "
                    f"{thresholds.max_risk_increase:g} levels."
                ),
            )
        )

    status: RegressionStatus = "failed" if failures else "passed"
    message = (
        "Candidate run passed the local regression gate."
        if status == "passed"
        else "Candidate run failed the local regression gate."
    )
    return RegressionCheckResult(
        status=status,
        baseline_run_dir=base.run_dir,
        candidate_run_dir=head.run_dir,
        baseline_run_id=base.run_id,
        candidate_run_id=head.run_id,
        thresholds=thresholds,
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
        deltas={"score_delta": score_delta, "risk_delta": risk_delta},
        failures=failures,
        warnings=warnings,
        message=message,
        baseline_source=baseline_source,
        baseline_label=baseline_label,
    )


def snapshot_metrics(score: int, risk_level: str) -> dict[str, object]:
    """Return the metrics used by the regression gate."""
    return {
        "score": score,
        "risk_level": risk_level,
        "risk_value": risk_value(risk_level),
    }


def run_metrics(run_dir: Path | None) -> dict[str, object]:
    """Best-effort metrics for a selected run."""
    if run_dir is None:
        return {}
    try:
        snapshot = load_run_snapshot(run_dir)
    except ReportError:
        return {}
    return snapshot_metrics(snapshot.score, snapshot.risk_level)


def metric_warnings(base_risk: str, head_risk: str) -> list[RegressionIssue]:
    """Return warnings for metrics that cannot be compared."""
    warnings: list[RegressionIssue] = []
    if risk_value(base_risk) is None:
        warnings.append(
            RegressionIssue(
                code="unknown_baseline_risk",
                metric="risk",
                baseline_value=base_risk,
                candidate_value=head_risk,
                threshold=None,
                message="Baseline risk level is unknown and was not compared.",
            )
        )
    if risk_value(head_risk) is None:
        warnings.append(
            RegressionIssue(
                code="unknown_candidate_risk",
                metric="risk",
                baseline_value=base_risk,
                candidate_value=head_risk,
                threshold=None,
                message="Candidate risk level is unknown and was not compared.",
            )
        )
    return warnings


def risk_value(risk_level: str) -> int | None:
    """Return numeric risk level, or None for unknown values."""
    return RISK_ORDER.get(str(risk_level).lower())


def write_regression_outputs(
    result: RegressionCheckResult,
    json_output: Path | None,
    summary_output: Path | None,
) -> RegressionCheckResult:
    """Write requested regression-check artifacts."""
    json_path = None
    summary_path = None
    if json_output is not None:
        validate_output_path(json_output)
        json_output.write_text(regression_check_json(result) + "\n", encoding="utf-8")
        json_path = json_output.resolve()
    if summary_output is not None:
        validate_output_path(summary_output)
        summary_output.write_text(regression_check_markdown(result), encoding="utf-8")
        summary_path = summary_output.resolve()
    return RegressionCheckResult(
        status=result.status,
        baseline_run_dir=result.baseline_run_dir,
        candidate_run_dir=result.candidate_run_dir,
        baseline_run_id=result.baseline_run_id,
        candidate_run_id=result.candidate_run_id,
        thresholds=result.thresholds,
        baseline_metrics=result.baseline_metrics,
        candidate_metrics=result.candidate_metrics,
        deltas=result.deltas,
        failures=result.failures,
        warnings=result.warnings,
        message=result.message,
        baseline_source=result.baseline_source,
        baseline_label=result.baseline_label,
        json_path=json_path,
        summary_path=summary_path,
    )


def regression_check_payload(result: RegressionCheckResult) -> dict[str, object]:
    """Return deterministic JSON-compatible regression-check payload."""
    return {
        "status": result.status,
        "baseline_run_dir": (
            str(result.baseline_run_dir) if result.baseline_run_dir else None
        ),
        "candidate_run_dir": (
            str(result.candidate_run_dir) if result.candidate_run_dir else None
        ),
        "baseline_run_id": result.baseline_run_id,
        "candidate_run_id": result.candidate_run_id,
        "baseline_source": result.baseline_source,
        "baseline_label": result.baseline_label,
        "thresholds": {
            "max_score_drop": result.thresholds.max_score_drop,
            "max_risk_increase": result.thresholds.max_risk_increase,
            "require_baseline": result.thresholds.require_baseline,
        },
        "baseline_metrics": result.baseline_metrics,
        "candidate_metrics": result.candidate_metrics,
        "deltas": result.deltas,
        "failures": [issue_payload(issue) for issue in result.failures],
        "warnings": [issue_payload(issue) for issue in result.warnings],
        "message": result.message,
    }


def regression_check_json(result: RegressionCheckResult) -> str:
    """Render regression-check JSON."""
    return json.dumps(regression_check_payload(result), indent=2, sort_keys=True)


def issue_payload(issue: RegressionIssue) -> dict[str, object]:
    """Return JSON-safe issue payload."""
    return {
        "code": issue.code,
        "metric": issue.metric,
        "baseline_value": issue.baseline_value,
        "candidate_value": issue.candidate_value,
        "threshold": issue.threshold,
        "message": issue.message,
    }


def regression_check_markdown(result: RegressionCheckResult) -> str:
    """Render a human-readable Markdown regression-check report."""
    lines = [
        "# VibeBench Regression Check",
        "",
        f"- Status: `{result.status}`",
        f"- Baseline run: `{result.baseline_run_id or 'none'}`",
        f"- Baseline source: `{result.baseline_source}`",
        f"- Baseline label: `{result.baseline_label or 'none'}`",
        f"- Candidate run: `{result.candidate_run_id or 'none'}`",
        f"- Message: {result.message}",
        "",
        "## Thresholds",
        "",
        "| Threshold | Value |",
        "| --- | ---: |",
        f"| Max score drop | {result.thresholds.max_score_drop:g} |",
        f"| Max risk increase | {result.thresholds.max_risk_increase:g} |",
        f"| Require baseline | {str(result.thresholds.require_baseline).lower()} |",
        "",
        "## Metrics",
        "",
        "| Metric | Baseline | Candidate |",
        "| --- | --- | --- |",
        metric_row("score", result),
        metric_row("risk_level", result),
        "",
        "## Deltas",
        "",
        "| Metric | Delta |",
        "| --- | ---: |",
        f"| Score | {markdown_cell(result.deltas.get('score_delta'))} |",
        f"| Risk | {markdown_cell(result.deltas.get('risk_delta'))} |",
        "",
    ]
    lines.extend(issue_table("Failures", result.failures))
    lines.extend(issue_table("Warnings", result.warnings))
    lines.extend(
        [
            "## Scope",
            "",
            "- This is a local quality regression gate.",
            "- It is not a benchmark certification.",
            "- It depends on the metrics available in the run artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def metric_row(metric: str, result: RegressionCheckResult) -> str:
    """Render one metrics row."""
    baseline = result.baseline_metrics.get(metric)
    candidate = result.candidate_metrics.get(metric)
    return (
        "| "
        f"{markdown_cell(metric)} | "
        f"{markdown_cell(baseline)} | "
        f"{markdown_cell(candidate)} |"
    )


def issue_table(title: str, issues: list[RegressionIssue]) -> list[str]:
    """Render a Markdown issue table."""
    lines = [f"## {title}", ""]
    if not issues:
        lines.extend([f"No {title.lower()}.", ""])
        return lines
    lines.extend(
        [
            "| Code | Metric | Baseline | Candidate | Threshold | Message |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for issue in issues:
        lines.append(
            "| "
            f"{markdown_cell(issue.code)} | "
            f"{markdown_cell(issue.metric)} | "
            f"{markdown_cell(issue.baseline_value)} | "
            f"{markdown_cell(issue.candidate_value)} | "
            f"{markdown_cell(issue.threshold)} | "
            f"{markdown_cell(issue.message)} |"
        )
    lines.append("")
    return lines


def markdown_cell(value: object) -> str:
    """Escape Markdown table cell content."""
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def validate_output_path(path: Path) -> None:
    """Validate a file output path."""
    if path.exists() and path.is_dir():
        raise ReportError(f"Output path is a directory: {path}")
    if not path.parent.exists():
        raise ReportError(f"Output parent directory does not exist: {path.parent}")
