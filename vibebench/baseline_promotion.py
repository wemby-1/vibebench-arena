"""Guarded promotion of pinned regression baselines."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from vibebench.baseline import (
    baseline_status_payload,
    load_metrics,
    metadata_from_run,
    normalize_label,
    pinned_baseline_file,
    select_run,
    set_pinned_baseline,
    show_pinned_baseline,
)
from vibebench.history import resolve_runs_dir
from vibebench.manifest import check_manifest
from vibebench.regression_check import (
    RegressionCheckResult,
    regression_check_payload,
    run_regression_check,
)
from vibebench.report import ReportError

PromotionStatus = Literal["promoted", "failed", "planned"]
CheckStatus = Literal["passed", "failed", "skipped", "warning"]


@dataclass(frozen=True)
class PromotionCheck:
    """One baseline promotion validation check."""

    name: str
    status: CheckStatus
    message: str
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class BaselinePromotionPolicy:
    """Effective policy used while validating promotion."""

    baseline_label: str | None = None
    require_baseline: bool = False
    max_score_drop: float = 0.0
    max_risk_increase: float = 0.0
    fail_on_missing_metrics: bool = True
    require_existing_baseline: bool = False
    require_manifest: bool = False
    require_regression_pass: bool = True
    allow_regression_failure: bool = False


@dataclass(frozen=True)
class BaselinePromotionResult:
    """Structured result for a guarded baseline promotion."""

    status: PromotionStatus
    dry_run: bool
    label: str
    candidate_run_id: str | None
    baseline_before: dict[str, object] | None
    baseline_after: dict[str, object] | None
    promotion_forced: bool
    checks: list[PromotionCheck]
    message: str
    policy_source: str
    effective_policy: BaselinePromotionPolicy
    baseline_path: Path
    candidate_run_dir: Path | None = None
    regression_check: RegressionCheckResult | None = None
    baseline_written: bool = False


def promote_baseline(
    project_root: Path,
    run_id: str,
    *,
    label: str,
    runs_dir: Path | None = None,
    source: str = "promote-run",
    dry_run: bool = False,
    require_existing_baseline: bool = False,
    require_manifest: bool = False,
    require_regression_pass: bool = True,
    allow_regression_failure: bool = False,
    max_score_drop: float = 0.0,
    max_risk_increase: float = 0.0,
    fail_on_missing_metrics: bool = True,
    policy_source: str = "default",
) -> BaselinePromotionResult:
    """Validate and optionally promote a run to a pinned baseline label."""
    if allow_regression_failure:
        require_regression_pass = False
    root = project_root.resolve()
    selected_label = normalize_label(label)
    selected_runs_dir = resolve_runs_dir(root, runs_dir)
    checks: list[PromotionCheck] = []
    baseline_path = pinned_baseline_file(root, selected_label)
    policy = BaselinePromotionPolicy(
        baseline_label=selected_label,
        require_baseline=require_existing_baseline,
        max_score_drop=max_score_drop,
        max_risk_increase=max_risk_increase,
        fail_on_missing_metrics=fail_on_missing_metrics,
        require_existing_baseline=require_existing_baseline,
        require_manifest=require_manifest,
        require_regression_pass=require_regression_pass,
        allow_regression_failure=allow_regression_failure,
    )

    run_dir: Path | None = None
    metrics: dict[str, Any] | None = None
    try:
        run_dir = select_run(selected_runs_dir, run_id)
        checks.append(
            PromotionCheck(
                "run_exists",
                "passed",
                f"Candidate run found: {run_dir.name}",
                {"run_dir": str(run_dir)},
            )
        )
    except ReportError as exc:
        checks.append(PromotionCheck("run_exists", "failed", str(exc)))

    if run_dir is not None:
        try:
            metrics = load_metrics(run_dir)
            missing = [name for name in ["score", "risk_level"] if name not in metrics]
            if missing:
                checks.append(
                    PromotionCheck(
                        "metrics_available",
                        "failed",
                        "metrics.json is missing required regression metric(s): "
                        + ", ".join(missing),
                        {"missing": missing},
                    )
                )
            else:
                checks.append(
                    PromotionCheck(
                        "metrics_available",
                        "passed",
                        "metrics.json is parseable and includes score/risk fields.",
                    )
                )
        except ReportError as exc:
            checks.append(PromotionCheck("metrics_available", "failed", str(exc)))

        manifest_path = run_dir / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = check_manifest(root, run_dir)
                if manifest.passed:
                    checks.append(
                        PromotionCheck(
                            "manifest_consistent",
                            "passed",
                            "manifest.json is consistent.",
                            {"manifest_path": str(manifest.manifest_path)},
                        )
                    )
                else:
                    checks.append(
                        PromotionCheck(
                            "manifest_consistent",
                            "failed",
                            "manifest.json differs from current run artifacts.",
                            {"differences": manifest.differences},
                        )
                    )
            except ReportError as exc:
                checks.append(
                    PromotionCheck("manifest_consistent", "failed", str(exc))
                )
        elif require_manifest:
            checks.append(
                PromotionCheck(
                    "manifest_consistent",
                    "failed",
                    f"manifest.json is required but missing at {manifest_path}.",
                )
            )
        else:
            checks.append(
                PromotionCheck(
                    "manifest_consistent",
                    "skipped",
                    "manifest.json is not present; promotion does not require it.",
                )
            )

    previous = show_pinned_baseline(root, label=selected_label)
    baseline_before = (
        baseline_status_payload(previous) if previous.metadata is not None else None
    )
    regression_result = None
    promotion_forced = False
    if previous.metadata is None:
        status: CheckStatus = "failed" if require_existing_baseline else "passed"
        checks.append(
            PromotionCheck(
                "regression_policy",
                status,
                "No previous pinned baseline exists for this label."
                if require_existing_baseline
                else "First promotion for this label; regression comparison skipped.",
                {
                    "baseline_source": "none"
                    if require_existing_baseline
                    else "first_promotion"
                },
            )
        )
    elif not previous.is_valid or previous.run_dir is None:
        checks.append(
            PromotionCheck(
                "regression_policy",
                "failed",
                previous.message,
                {"baseline_source": "stale"},
            )
        )
    elif run_dir is not None:
        try:
            regression_result = run_regression_check(
                root,
                baseline_run=previous.run_dir,
                candidate_run=run_dir,
                max_score_drop=max_score_drop,
                max_risk_increase=max_risk_increase,
                require_baseline=True,
                fail_on_missing_metrics=fail_on_missing_metrics,
                policy_source=policy_source,
            )
        except ReportError as exc:
            checks.append(PromotionCheck("regression_policy", "failed", str(exc)))
        else:
            if regression_result.status == "passed":
                checks.append(
                    PromotionCheck(
                        "regression_policy",
                        "passed",
                        (
                            "Candidate passed regression-check against the "
                            "current baseline."
                        ),
                        {"baseline_source": "pinned"},
                    )
                )
            elif allow_regression_failure:
                promotion_forced = True
                checks.append(
                    PromotionCheck(
                        "regression_policy",
                        "warning",
                        "Candidate failed regression-check, but promotion was allowed.",
                        {"baseline_source": "pinned"},
                    )
                )
            else:
                checks.append(
                    PromotionCheck(
                        "regression_policy",
                        "failed",
                        (
                            "Candidate failed regression-check against the "
                            "current baseline."
                        ),
                        {"baseline_source": "pinned"},
                    )
                )

    blockers = [check for check in checks if check.status == "failed"]
    candidate_id = run_dir.name if run_dir is not None else None
    baseline_after = None
    baseline_written = False
    if blockers:
        status = "failed"
        message = "Baseline promotion failed validation."
    elif dry_run:
        status = "planned"
        message = "Baseline promotion passed validation; dry run did not write state."
        if run_dir is not None and metrics is not None:
            baseline_after = metadata_from_run(
                root,
                run_dir,
                metrics,
                label=selected_label,
                source=source,
                runs_dir=selected_runs_dir,
            ).model_dump(mode="json")
    else:
        if run_dir is None:
            status = "failed"
            message = "Baseline promotion failed validation."
        else:
            saved = set_pinned_baseline(
                root,
                run_dir.name,
                label=selected_label,
                runs_dir=selected_runs_dir,
                source=source,
            )
            baseline_after = (
                saved.metadata.model_dump(mode="json") if saved.metadata else None
            )
            baseline_written = True
            status = "promoted"
            message = "Pinned baseline promoted."

    return BaselinePromotionResult(
        status=status,
        dry_run=dry_run,
        label=selected_label,
        candidate_run_id=candidate_id,
        baseline_before=baseline_before,
        baseline_after=baseline_after,
        promotion_forced=promotion_forced,
        checks=checks,
        message=message,
        policy_source=policy_source,
        effective_policy=policy,
        baseline_path=baseline_path,
        candidate_run_dir=run_dir,
        regression_check=regression_result,
        baseline_written=baseline_written,
    )


def promotion_payload(result: BaselinePromotionResult) -> dict[str, object]:
    """Return deterministic JSON-compatible promotion output."""
    return {
        "status": result.status,
        "dry_run": result.dry_run,
        "label": result.label,
        "candidate_run_id": result.candidate_run_id,
        "candidate_run_dir": str(result.candidate_run_dir)
        if result.candidate_run_dir
        else None,
        "baseline_path": str(result.baseline_path),
        "baseline_before": result.baseline_before,
        "baseline_after": result.baseline_after,
        "baseline_written": result.baseline_written,
        "promotion_forced": result.promotion_forced,
        "checks": [check_payload(check) for check in result.checks],
        "regression_check": regression_check_summary(result.regression_check),
        "policy_source": result.policy_source,
        "effective_policy": {
            "baseline_label": result.effective_policy.baseline_label,
            "require_baseline": result.effective_policy.require_baseline,
            "max_score_drop": result.effective_policy.max_score_drop,
            "max_risk_increase": result.effective_policy.max_risk_increase,
            "fail_on_missing_metrics": result.effective_policy.fail_on_missing_metrics,
            "require_existing_baseline": (
                result.effective_policy.require_existing_baseline
            ),
            "require_manifest": result.effective_policy.require_manifest,
            "require_regression_pass": result.effective_policy.require_regression_pass,
            "allow_regression_failure": (
                result.effective_policy.allow_regression_failure
            ),
        },
        "message": result.message,
    }


def check_payload(check: PromotionCheck) -> dict[str, object]:
    """Return JSON-compatible check output."""
    payload: dict[str, object] = {
        "name": check.name,
        "status": check.status,
        "message": check.message,
    }
    if check.details:
        payload["details"] = check.details
    return payload


def regression_check_summary(
    result: RegressionCheckResult | None,
) -> dict[str, object] | None:
    """Return compact regression-check details for promotion output."""
    if result is None:
        return None
    payload = regression_check_payload(result)
    return {
        "status": payload["status"],
        "baseline_run_id": payload["baseline_run_id"],
        "candidate_run_id": payload["candidate_run_id"],
        "baseline_source": payload["baseline_source"],
        "baseline_label": payload["baseline_label"],
        "policy_source": payload["policy_source"],
        "effective_policy": payload["effective_policy"],
        "failures": payload["failures"],
        "warnings": payload["warnings"],
        "message": payload["message"],
    }


def promotion_json(result: BaselinePromotionResult) -> str:
    """Render promotion JSON."""
    return json.dumps(promotion_payload(result), indent=2, sort_keys=True)


def promotion_markdown(result: BaselinePromotionResult) -> str:
    """Render a compact Markdown baseline promotion report."""
    previous = "none"
    if result.baseline_before:
        baseline = result.baseline_before.get("baseline")
        if isinstance(baseline, dict):
            previous = str(baseline.get("run_id") or "none")
    lines = [
        "# VibeBench Baseline Promotion",
        "",
        f"- Status: `{result.status}`",
        f"- Label: `{result.label}`",
        f"- Candidate run: `{result.candidate_run_id or 'none'}`",
        f"- Previous baseline: `{previous}`",
        f"- Baseline file written: `{str(result.baseline_written).lower()}`",
        f"- Promotion forced: `{str(result.promotion_forced).lower()}`",
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
    if result.regression_check is not None:
        lines.extend(
            [
                "",
                "## Regression Check",
                "",
                f"- Status: `{result.regression_check.status}`",
                f"- Message: {result.regression_check.message}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def markdown_cell(value: object) -> str:
    """Escape Markdown table cell content."""
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")
