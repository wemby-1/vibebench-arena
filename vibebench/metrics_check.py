"""Validate VibeBench metrics.json contracts for regression workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from vibebench.history import resolve_runs_dir
from vibebench.report import ReportError

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

MetricsCheckStatus = Literal["passed", "warning", "failed"]
CheckStatus = Literal["passed", "warning", "failed"]


@dataclass(frozen=True)
class MetricsContractCheck:
    """One metrics contract check."""

    name: str
    status: CheckStatus
    message: str


@dataclass(frozen=True)
class MetricValueResult:
    """Validated score/risk values used by regression and baselines."""

    score_value: float | int | None
    risk_level: str | None
    risk_value: int | None
    checks: list[MetricsContractCheck]

    @property
    def usable(self) -> bool:
        """Return whether score/risk can be used by regression comparisons."""
        return not any(check.status == "failed" for check in self.checks)


@dataclass(frozen=True)
class MetricsCheckResult:
    """Structured metrics contract check result."""

    status: MetricsCheckStatus
    run_dir: Path | None
    metrics_path: Path | None
    usable_for_regression: bool
    usable_as_baseline: bool
    score_value: float | int | None
    risk_value: int | None
    checks: list[MetricsContractCheck]
    advice: list[str]
    strict: bool = False
    json_path: Path | None = None
    summary_path: Path | None = None


def run_metrics_check(
    project_root: Path,
    *,
    run_dir: Path | None = None,
    strict: bool = False,
    json_output: Path | None = None,
    summary_output: Path | None = None,
) -> MetricsCheckResult:
    """Check a run metrics.json contract."""
    root = project_root.resolve()
    selected_run = resolve_metrics_run(root, run_dir)
    result = evaluate_metrics_run(selected_run, strict=strict)
    return write_metrics_check_outputs(result, json_output, summary_output)


def resolve_metrics_run(project_root: Path, run_dir: Path | None) -> Path | None:
    """Resolve explicit or latest run directory for metrics checking."""
    if run_dir is not None:
        selected = run_dir if run_dir.is_absolute() else project_root / run_dir
        return selected.resolve()
    runs_dir = resolve_runs_dir(project_root, None)
    valid_runs = [
        path.resolve()
        for path in sorted(runs_dir.iterdir())
        if path.is_dir() and path.joinpath("metrics.json").is_file()
    ] if runs_dir.exists() and runs_dir.is_dir() else []
    if valid_runs:
        return valid_runs[-1]
    if not runs_dir.exists():
        return None
    candidates = sorted(path for path in runs_dir.iterdir() if path.is_dir())
    return candidates[-1].resolve() if candidates else None


def evaluate_metrics_run(
    run_dir: Path | None,
    *,
    strict: bool = False,
) -> MetricsCheckResult:
    """Evaluate one run directory's metrics contract."""
    checks: list[MetricsContractCheck] = []
    metrics_path = run_dir / "metrics.json" if run_dir is not None else None
    metrics: dict[str, Any] | None = None
    if run_dir is None:
        checks.append(
            MetricsContractCheck(
                "run_dir_exists",
                "failed",
                "No VibeBench run directory is available.",
            )
        )
    elif not run_dir.exists() or not run_dir.is_dir():
        checks.append(
            MetricsContractCheck(
                "run_dir_exists",
                "failed",
                f"Run directory does not exist: {run_dir}",
            )
        )
    else:
        checks.append(
            MetricsContractCheck(
                "run_dir_exists",
                "passed",
                "Run directory exists.",
            )
        )
        if metrics_path is None or not metrics_path.exists():
            checks.append(
                MetricsContractCheck(
                    "metrics_json_exists",
                    "failed",
                    f"metrics.json is missing in {run_dir}.",
                )
            )
        else:
            checks.append(
                MetricsContractCheck(
                    "metrics_json_exists",
                    "passed",
                    "metrics.json exists.",
                )
            )
            try:
                raw = json.loads(metrics_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                checks.append(
                    MetricsContractCheck(
                        "metrics_json_valid",
                        "failed",
                        f"metrics.json is not valid JSON: {exc}",
                    )
                )
            else:
                checks.append(
                    MetricsContractCheck(
                        "metrics_json_valid",
                        "passed",
                        "metrics.json is valid JSON.",
                    )
                )
                if not isinstance(raw, dict):
                    checks.append(
                        MetricsContractCheck(
                            "metrics_payload_object",
                            "failed",
                            "metrics.json must contain a JSON object.",
                        )
                    )
                else:
                    metrics = raw
                    checks.append(
                        MetricsContractCheck(
                            "metrics_payload_object",
                            "passed",
                            "metrics payload is a JSON object.",
                        )
                    )
                    checks.extend(validate_metrics_payload(metrics).checks)
                    checks.extend(summary_structure_checks(metrics))

    return build_metrics_result(
        run_dir=run_dir,
        metrics_path=metrics_path,
        metrics=metrics,
        checks=checks,
        strict=strict,
    )


def validate_metrics_payload(metrics: dict[str, Any]) -> MetricValueResult:
    """Validate score and risk metrics used by regression/baseline workflows."""
    checks: list[MetricsContractCheck] = []
    score_value = numeric_metric(metrics.get("score")) if "score" in metrics else None
    if "score" not in metrics:
        checks.append(
            MetricsContractCheck(
                "score_numeric",
                "failed",
                "Regression-critical metric 'score' is missing.",
            )
        )
    elif score_value is None:
        checks.append(
            MetricsContractCheck(
                "score_numeric",
                "failed",
                "Regression-critical metric 'score' must be numeric.",
            )
        )
    else:
        checks.append(
            MetricsContractCheck(
                "score_numeric",
                "passed",
                "Regression-critical metric 'score' is numeric.",
            )
        )

    risk_level = None
    risk_value = None
    if "risk_level" not in metrics:
        checks.append(
            MetricsContractCheck(
                "risk_numeric",
                "failed",
                "Regression-critical metric 'risk_level' is missing.",
            )
        )
    else:
        risk_level = str(metrics.get("risk_level", ""))
        risk_value = risk_value_for_level(risk_level)
        if risk_value is None:
            checks.append(
                MetricsContractCheck(
                    "risk_numeric",
                    "failed",
                    "Regression-critical metric 'risk_level' must be comparable.",
                )
            )
        else:
            checks.append(
                MetricsContractCheck(
                    "risk_numeric",
                    "passed",
                    "Regression-critical metric 'risk_level' maps to a numeric risk.",
                )
            )
    return MetricValueResult(score_value, risk_level, risk_value, checks)


def validate_score_risk_values(
    score: object,
    risk_level: object,
) -> MetricValueResult:
    """Validate score/risk values from non-run sources such as snapshots."""
    metrics: dict[str, Any] = {}
    if score is not None:
        metrics["score"] = score
    if risk_level is not None:
        metrics["risk_level"] = risk_level
    return validate_metrics_payload(metrics)


def numeric_metric(value: object) -> float | int | None:
    """Return a numeric metric value, excluding booleans."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return value
    return None


def risk_value_for_level(risk_level: object) -> int | None:
    """Return numeric risk value for known risk levels."""
    return RISK_ORDER.get(str(risk_level).lower())


def summary_structure_checks(metrics: dict[str, Any]) -> list[MetricsContractCheck]:
    """Return structural checks for summary fields used by reports/artifacts."""
    checks: list[MetricsContractCheck] = []
    optional_shapes = {
        "summary": dict,
        "diff_analysis": dict,
        "command_results": list,
        "risk_findings": list,
    }
    for field_name, expected_type in optional_shapes.items():
        if field_name not in metrics:
            checks.append(
                MetricsContractCheck(
                    f"{field_name}_structure",
                    "warning",
                    f"Optional field '{field_name}' is missing.",
                )
            )
            continue
        if not isinstance(metrics[field_name], expected_type):
            checks.append(
                MetricsContractCheck(
                    f"{field_name}_structure",
                    "failed",
                    f"Field '{field_name}' has the wrong structure.",
                )
            )
        else:
            checks.append(
                MetricsContractCheck(
                    f"{field_name}_structure",
                    "passed",
                    f"Field '{field_name}' has the expected structure.",
                )
            )
    return checks


def build_metrics_result(
    *,
    run_dir: Path | None,
    metrics_path: Path | None,
    metrics: dict[str, Any] | None,
    checks: list[MetricsContractCheck],
    strict: bool,
) -> MetricsCheckResult:
    """Build final metrics-check result."""
    value_result = (
        validate_metrics_payload(metrics or {}) if metrics is not None else None
    )
    usable = value_result.usable if value_result is not None else False
    score_value = value_result.score_value if value_result is not None else None
    risk_value = value_result.risk_value if value_result is not None else None
    has_failed = any(check.status == "failed" for check in checks)
    has_warning = any(check.status == "warning" for check in checks)
    if strict and has_warning:
        checks = [
            *checks,
            MetricsContractCheck(
                "strict",
                "failed",
                "--strict treats metrics-check warnings as failures.",
            ),
        ]
        has_failed = True
    status: MetricsCheckStatus = "passed"
    if has_failed:
        status = "failed"
    elif has_warning:
        status = "warning"
    advice: list[str] = []
    if has_failed:
        advice.append(
            "Fix failed metrics checks before promotion or regression comparison."
        )
    elif has_warning:
        advice.append("Review warnings; use --strict to fail on warnings.")
    return MetricsCheckResult(
        status=status,
        run_dir=run_dir,
        metrics_path=metrics_path,
        usable_for_regression=usable and not has_failed,
        usable_as_baseline=usable and not has_failed,
        score_value=score_value,
        risk_value=risk_value,
        checks=checks,
        advice=advice,
        strict=strict,
    )


def write_metrics_check_outputs(
    result: MetricsCheckResult,
    json_output: Path | None,
    summary_output: Path | None,
) -> MetricsCheckResult:
    """Write requested metrics-check outputs."""
    json_path = None
    summary_path = None
    if json_output is not None:
        validate_output_path(json_output)
        json_output.write_text(metrics_check_json(result) + "\n", encoding="utf-8")
        json_path = json_output.resolve()
    if summary_output is not None:
        validate_output_path(summary_output)
        summary_output.write_text(metrics_check_markdown(result), encoding="utf-8")
        summary_path = summary_output.resolve()
    return MetricsCheckResult(
        status=result.status,
        run_dir=result.run_dir,
        metrics_path=result.metrics_path,
        usable_for_regression=result.usable_for_regression,
        usable_as_baseline=result.usable_as_baseline,
        score_value=result.score_value,
        risk_value=result.risk_value,
        checks=result.checks,
        advice=result.advice,
        strict=result.strict,
        json_path=json_path,
        summary_path=summary_path,
    )


def metrics_check_payload(result: MetricsCheckResult) -> dict[str, object]:
    """Return deterministic JSON-compatible metrics-check payload."""
    return {
        "status": result.status,
        "run_dir": str(result.run_dir) if result.run_dir else None,
        "metrics_path": str(result.metrics_path) if result.metrics_path else None,
        "usable_for_regression": result.usable_for_regression,
        "usable_as_baseline": result.usable_as_baseline,
        "score_value": result.score_value,
        "risk_value": result.risk_value,
        "strict": result.strict,
        "checks": [
            {"name": check.name, "status": check.status, "message": check.message}
            for check in result.checks
        ],
        "advice": result.advice,
    }


def metrics_check_json(result: MetricsCheckResult) -> str:
    """Render metrics-check JSON."""
    return json.dumps(metrics_check_payload(result), indent=2, sort_keys=True)


def metrics_check_markdown(result: MetricsCheckResult) -> str:
    """Render metrics-check Markdown."""
    lines = [
        "# VibeBench Metrics Check",
        "",
        f"- Status: `{result.status}`",
        f"- Run dir: `{result.run_dir or 'none'}`",
        f"- Metrics path: `{result.metrics_path or 'none'}`",
        f"- Usable for regression: `{str(result.usable_for_regression).lower()}`",
        f"- Usable as baseline: `{str(result.usable_as_baseline).lower()}`",
        f"- Strict: `{str(result.strict).lower()}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Message |",
        "| --- | --- | --- |",
    ]
    for check in result.checks:
        lines.append(
            "| "
            f"{markdown_cell(check.name)} | "
            f"{markdown_cell(check.status)} | "
            f"{markdown_cell(check.message)} |"
        )
    lines.extend(["", "## Advice", ""])
    if result.advice:
        for item in result.advice:
            lines.append(f"- {item}")
    else:
        lines.append("No advice.")
    lines.append("")
    return "\n".join(lines)


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
