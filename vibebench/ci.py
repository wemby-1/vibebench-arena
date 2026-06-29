"""One-shot VibeBench CI pipeline orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vibebench.annotate import generate_annotations
from vibebench.badge import generate_ci_badges
from vibebench.bundle import create_bundle
from vibebench.config import ConfigError, load_config
from vibebench.explain import generate_explanation
from vibebench.export import export_json_for_ci
from vibebench.gate import run_gate
from vibebench.gh_summary import generate_github_summary
from vibebench.paths import config_file
from vibebench.pr_comment import generate_pr_comment
from vibebench.report import ReportError, generate_report, load_metrics
from vibebench.runner import run_checks
from vibebench.status_block import generate_status_block

StepStatus = Literal["passed", "failed", "skipped"]


@dataclass(frozen=True)
class CiStepResult:
    """Result for one CI pipeline step."""

    name: str
    status: StepStatus
    exit_code: int
    artifact_path: Path | None = None
    message: str = ""


@dataclass(frozen=True)
class CiResult:
    """Complete VibeBench CI pipeline result."""

    run_dir: Path | None
    steps: list[CiStepResult]
    passed: bool


def run_ci_pipeline(
    project_root: Path,
    *,
    run_dir: Path | None = None,
    skip_report: bool = False,
    skip_pr_comment: bool = False,
    skip_explain: bool = False,
    skip_bundle: bool = False,
    skip_export: bool = False,
    skip_badge: bool = False,
    skip_status_block: bool = False,
    skip_annotate: bool = False,
    skip_gh_summary: bool = False,
    bundle_include_report_assets: bool = False,
    bundle_strict: bool = False,
    min_score: int | None = None,
    max_risk: str | None = None,
    allow_findings: int | None = None,
    require_status_passed: bool | None = None,
) -> CiResult:
    """Run the complete local CI pipeline."""
    root = project_root.resolve()
    selected_run_dir = run_dir.resolve() if run_dir is not None else None
    steps: list[CiStepResult] = []

    if selected_run_dir is None:
        check_step, selected_run_dir = run_check_step(root)
        steps.append(check_step)
    else:
        validate_explicit_run(selected_run_dir)
        steps.append(CiStepResult("check", "skipped", 0, message="using --run-dir"))

    if selected_run_dir is None:
        steps.append(
            CiStepResult(
                "gate",
                "failed",
                1,
                message="no run directory available",
            )
        )
        append_unavailable_artifact_steps(
            steps,
            skip_report=skip_report,
            skip_pr_comment=skip_pr_comment,
            skip_explain=skip_explain,
            skip_bundle=skip_bundle,
            skip_export=skip_export,
            skip_badge=skip_badge,
            skip_status_block=skip_status_block,
            skip_annotate=skip_annotate,
            skip_gh_summary=skip_gh_summary,
        )
        return CiResult(run_dir=None, steps=steps, passed=False)

    gate_step = run_gate_step(
        root,
        selected_run_dir,
        min_score=min_score,
        max_risk=max_risk,
        allow_findings=allow_findings,
        require_status_passed=require_status_passed,
    )
    steps.append(gate_step)

    artifact_steps: list[tuple[str, bool, object]] = [
        ("report", skip_report, lambda: generate_report(root, selected_run_dir)),
        (
            "pr-comment",
            skip_pr_comment,
            lambda: generate_pr_comment(root, selected_run_dir),
        ),
        (
            "explain",
            skip_explain,
            lambda: generated_explanation_path(root, selected_run_dir),
        ),
        (
            "export",
            skip_export,
            lambda: export_json_for_ci(root, selected_run_dir),
        ),
        (
            "badge",
            skip_badge,
            lambda: generate_ci_badges(root, selected_run_dir),
        ),
        (
            "status-block",
            skip_status_block,
            lambda: generate_status_block(root, selected_run_dir).output_path,
        ),
        (
            "bundle",
            skip_bundle,
            lambda: create_bundle(
                root,
                selected_run_dir,
                include_report_assets=bundle_include_report_assets,
                strict=bundle_strict,
            ).output_path,
        ),
        (
            "annotate",
            skip_annotate,
            lambda: generated_annotations(root, selected_run_dir),
        ),
        (
            "gh-summary",
            skip_gh_summary,
            lambda: generate_github_summary(root, selected_run_dir),
        ),
    ]
    for name, skipped, callback in artifact_steps:
        if skipped:
            steps.append(CiStepResult(name, "skipped", 0, message="skipped by flag"))
            continue
        steps.append(run_artifact_step(name, callback))

    passed = all(step.exit_code == 0 for step in steps if step.status != "skipped")
    return CiResult(run_dir=selected_run_dir, steps=steps, passed=passed)


def append_unavailable_artifact_steps(
    steps: list[CiStepResult],
    *,
    skip_report: bool,
    skip_pr_comment: bool,
    skip_explain: bool,
    skip_bundle: bool,
    skip_export: bool,
    skip_badge: bool,
    skip_status_block: bool,
    skip_annotate: bool,
    skip_gh_summary: bool,
) -> None:
    """Append artifact steps when no run directory exists."""
    flags = [
        ("report", skip_report),
        ("pr-comment", skip_pr_comment),
        ("explain", skip_explain),
        ("export", skip_export),
        ("badge", skip_badge),
        ("status-block", skip_status_block),
        ("bundle", skip_bundle),
        ("annotate", skip_annotate),
        ("gh-summary", skip_gh_summary),
    ]
    for name, skipped in flags:
        if skipped:
            steps.append(CiStepResult(name, "skipped", 0, message="skipped by flag"))
        else:
            steps.append(
                CiStepResult(
                    name,
                    "failed",
                    1,
                    message="no run directory available",
                )
            )


def run_check_step(project_root: Path) -> tuple[CiStepResult, Path | None]:
    """Run the check step and return its selected run directory."""
    target = config_file(project_root)
    try:
        config = load_config(target)
        result = run_checks(config, project_root)
    except ConfigError as exc:
        return CiStepResult("check", "failed", 1, message=str(exc)), None
    except Exception as exc:
        return CiStepResult("check", "failed", 1, message=str(exc)), None

    status: StepStatus = "passed" if result.overall_status == "passed" else "failed"
    exit_code = 0 if status == "passed" else 1
    return (
        CiStepResult(
            "check",
            status,
            exit_code,
            artifact_path=result.metrics_path,
            message=f"status {result.overall_status}",
        ),
        result.run_dir,
    )


def run_gate_step(
    project_root: Path,
    run_dir: Path | None,
    *,
    min_score: int | None,
    max_risk: str | None,
    allow_findings: int | None,
    require_status_passed: bool | None,
) -> CiStepResult:
    """Run the gate step."""
    try:
        result = run_gate(
            project_root,
            run_dir=run_dir,
            min_score=min_score,
            max_risk=max_risk,
            allow_findings=allow_findings,
            require_status_passed=require_status_passed,
            write_gate_summary=True,
        )
    except Exception as exc:
        return CiStepResult("gate", "failed", 1, message=str(exc))

    status: StepStatus = "passed" if result.passed else "failed"
    return CiStepResult(
        "gate",
        status,
        0 if result.passed else 1,
        artifact_path=result.summary_path,
        message="passed" if result.passed else "; ".join(result.reasons),
    )


def run_artifact_step(name: str, callback: object) -> CiStepResult:
    """Run an artifact callback and capture errors."""
    try:
        artifact_path = callback()
    except Exception as exc:
        return CiStepResult(name, "failed", 1, message=str(exc))
    return CiStepResult(name, "passed", 0, artifact_path=artifact_path)


def generated_annotations(project_root: Path, run_dir: Path | None) -> None:
    """Generate annotations and print their output."""
    result = generate_annotations(project_root, run_dir)
    if result.output:
        print(result.output)
    return None


def generated_explanation_path(project_root: Path, run_dir: Path | None) -> Path | None:
    """Generate explanation and return its path."""
    return generate_explanation(project_root, run_dir).output_path


def validate_explicit_run(run_dir: Path) -> None:
    """Validate an explicit run directory before CI artifact orchestration."""
    if not run_dir.exists():
        raise ReportError(f"Run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise ReportError(f"Run path is not a directory: {run_dir}")
    try:
        load_metrics(run_dir)
    except json.JSONDecodeError as exc:
        raise ReportError(f"metrics.json in {run_dir} is not valid JSON.") from exc
