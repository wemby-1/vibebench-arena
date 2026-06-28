"""Evaluate VibeBench runs against an explicit quality gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from vibebench.baseline import show_baseline
from vibebench.compare import find_comparable_runs, resolve_run
from vibebench.report import ReportError

RiskLevel = Literal["low", "medium", "high", "critical"]

RISK_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


class GateSnapshot(BaseModel):
    """Comparable gate data loaded from metrics.json."""

    model_config = ConfigDict(extra="forbid")

    run_dir: Path
    overall_status: str
    score: int
    risk_level: str
    risk_findings_count: int


class GateThresholds(BaseModel):
    """Quality gate thresholds."""

    model_config = ConfigDict(extra="forbid")

    min_score: int = 80
    max_risk: RiskLevel = "medium"
    allow_findings: int = 0
    require_status_passed: bool = True


class GateResult(BaseModel):
    """Quality gate evaluation result."""

    model_config = ConfigDict(extra="forbid")

    run_dir: Path
    passed: bool
    thresholds: GateThresholds
    snapshot: GateSnapshot
    reasons: list[str]
    baseline_used: bool = False
    baseline_snapshot: GateSnapshot | None = None
    summary_path: Path | None = None


def run_gate(
    project_root: Path,
    run_dir: Path | None = None,
    min_score: int = 80,
    max_risk: RiskLevel = "medium",
    allow_findings: int = 0,
    require_status_passed: bool = True,
    use_baseline: bool = False,
    write_gate_summary: bool = False,
) -> GateResult:
    """Evaluate a VibeBench run against threshold and baseline rules."""
    root = project_root.resolve()
    if max_risk not in RISK_ORDER:
        raise ReportError(
            "--max-risk must be one of: low, medium, high, critical."
        )
    if allow_findings < 0:
        raise ReportError("--allow-findings must be 0 or greater.")
    thresholds = GateThresholds(
        min_score=min_score,
        max_risk=max_risk,
        allow_findings=allow_findings,
        require_status_passed=require_status_passed,
    )
    selected_run_dir = select_gate_run(root, run_dir)
    snapshot = load_gate_snapshot(selected_run_dir)
    reasons = threshold_reasons(snapshot, thresholds)
    baseline_snapshot = None

    if use_baseline:
        baseline_status = show_baseline(root)
        if baseline_status.metadata is None:
            raise ReportError(
                "No baseline found. Run 'python -m vibebench baseline --set latest' "
                "first."
            )
        if not baseline_status.is_valid or baseline_status.run_dir is None:
            raise ReportError(baseline_status.message)
        baseline_snapshot = load_gate_snapshot(baseline_status.run_dir)
        reasons.extend(baseline_reasons(snapshot, baseline_snapshot))

    result = GateResult(
        run_dir=selected_run_dir,
        passed=not reasons,
        thresholds=thresholds,
        snapshot=snapshot,
        reasons=reasons,
        baseline_used=use_baseline,
        baseline_snapshot=baseline_snapshot,
    )

    if write_gate_summary:
        summary_path = selected_run_dir / "gate-summary.md"
        summary_path.write_text(render_gate_summary(result), encoding="utf-8")
        result = result.model_copy(update={"summary_path": summary_path})

    return result


def select_gate_run(project_root: Path, run_dir: Path | None) -> Path:
    """Select the explicit or latest valid run directory."""
    if run_dir is not None:
        selected = resolve_run(project_root, run_dir)
        if not selected.exists() or not selected.is_dir():
            raise ReportError(f"Run directory does not exist: {selected}")
        if not (selected / "metrics.json").exists():
            raise ReportError(f"No metrics.json found in {selected}.")
        return selected

    runs = find_comparable_runs(project_root)
    if not runs:
        raise ReportError("No VibeBench runs found. Run 'vibebench check' first.")
    return runs[-1]


def load_gate_snapshot(run_dir: Path) -> GateSnapshot:
    """Load gate fields from a run's metrics.json."""
    metrics_path = run_dir / "metrics.json"
    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReportError(f"No metrics.json found in {run_dir}.") from exc
    except json.JSONDecodeError as exc:
        raise ReportError(f"Could not parse metrics.json in {run_dir}: {exc}") from exc
    if not isinstance(metrics, dict):
        raise ReportError(f"metrics.json in {run_dir} is not an object.")

    summary = as_dict(metrics.get("summary"))
    findings = as_list(metrics.get("risk_findings"))
    actionable_findings = [
        finding
        for finding in findings
        if as_dict(finding).get("severity") != "info"
    ]
    finding_count = (
        len(actionable_findings)
        if findings
        else as_int(summary.get("total_findings"))
    )
    return GateSnapshot(
        run_dir=run_dir,
        overall_status=text(metrics.get("overall_status", "unknown")),
        score=as_int(metrics.get("score")),
        risk_level=text(metrics.get("risk_level", "unknown")),
        risk_findings_count=finding_count,
    )


def threshold_reasons(
    snapshot: GateSnapshot,
    thresholds: GateThresholds,
) -> list[str]:
    """Return threshold failure reasons."""
    reasons: list[str] = []
    if thresholds.require_status_passed and snapshot.overall_status != "passed":
        reasons.append(f"overall status is {snapshot.overall_status}, expected passed")
    if snapshot.score < thresholds.min_score:
        reasons.append(
            f"score {snapshot.score} is below minimum {thresholds.min_score}"
        )
    if risk_rank(snapshot.risk_level) > risk_rank(thresholds.max_risk):
        reasons.append(
            f"risk {snapshot.risk_level} is above maximum {thresholds.max_risk}"
        )
    if snapshot.risk_findings_count > thresholds.allow_findings:
        reasons.append(
            f"risk findings {snapshot.risk_findings_count} exceed allowed "
            f"{thresholds.allow_findings}"
        )
    return reasons


def baseline_reasons(
    current: GateSnapshot,
    baseline: GateSnapshot,
) -> list[str]:
    """Return baseline regression failure reasons."""
    reasons: list[str] = []
    if current.score < baseline.score:
        reasons.append(
            f"score regressed from baseline {baseline.score} to {current.score}"
        )
    if risk_rank(current.risk_level) > risk_rank(baseline.risk_level):
        reasons.append(
            f"risk worsened from baseline {baseline.risk_level} to "
            f"{current.risk_level}"
        )
    if current.risk_findings_count > baseline.risk_findings_count:
        reasons.append(
            "risk findings increased from baseline "
            f"{baseline.risk_findings_count} to {current.risk_findings_count}"
        )
    return reasons


def render_gate_summary(result: GateResult) -> str:
    """Render gate-summary.md."""
    lines = [
        "# VibeBench Gate Summary",
        "",
        f"- Result: **{'passed' if result.passed else 'failed'}**",
        f"- Run: `{result.run_dir}`",
        "",
        "## Thresholds",
        "",
        f"- Minimum score: `{result.thresholds.min_score}`",
        f"- Maximum risk: `{result.thresholds.max_risk}`",
        f"- Allowed findings: `{result.thresholds.allow_findings}`",
        f"- Require status passed: `{result.thresholds.require_status_passed}`",
        "",
        "## Actual",
        "",
        f"- Overall status: `{result.snapshot.overall_status}`",
        f"- Score: `{result.snapshot.score}`",
        f"- Risk level: `{result.snapshot.risk_level}`",
        f"- Risk findings: `{result.snapshot.risk_findings_count}`",
        "",
        "## Failed Reasons",
        "",
    ]
    if result.reasons:
        lines.extend(f"- {reason}" for reason in result.reasons)
    else:
        lines.append("- None")

    if result.baseline_used and result.baseline_snapshot is not None:
        baseline = result.baseline_snapshot
        lines.extend(
            [
                "",
                "## Baseline Comparison",
                "",
                f"- Baseline run: `{baseline.run_dir}`",
                f"- Baseline score: `{baseline.score}`",
                f"- Baseline risk: `{baseline.risk_level}`",
                f"- Baseline findings: `{baseline.risk_findings_count}`",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def risk_rank(value: str) -> int:
    """Return a comparable risk rank; unknown values are treated as worst."""
    return RISK_ORDER.get(value.lower(), len(RISK_ORDER))


def as_dict(value: object) -> dict[str, Any]:
    """Return value as a dict if possible."""
    return value if isinstance(value, dict) else {}


def as_list(value: object) -> list[Any]:
    """Return value as a list if possible."""
    return value if isinstance(value, list) else []


def as_int(value: object, default: int = 0) -> int:
    """Coerce a dynamic value to int safely."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def text(value: object) -> str:
    """Convert a dynamic value to text."""
    if value is None:
        return ""
    return str(value)
