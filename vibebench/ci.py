"""One-shot VibeBench CI pipeline orchestration."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vibebench.annotate import generate_annotations
from vibebench.badge import generate_ci_badges
from vibebench.bundle import create_bundle
from vibebench.config import ConfigError, load_config, load_effective_config
from vibebench.config_check import (
    CONFIG_CHECK_JSON,
    CONFIG_CHECK_SUMMARY,
    config_consistency_checks,
    write_config_check_json,
    write_config_check_summary,
)
from vibebench.explain import generate_explanation
from vibebench.export import export_json_for_ci
from vibebench.gate import run_gate
from vibebench.gh_summary import generate_github_summary
from vibebench.manifest import check_manifest, generate_manifest
from vibebench.paths import config_file
from vibebench.pr_comment import generate_pr_comment
from vibebench.report import ReportError, generate_report, load_metrics
from vibebench.runner import run_checks
from vibebench.status_block import generate_status_block
from vibebench.trend import analyze_trend, write_trend_json, write_trend_summary

StepStatus = Literal["passed", "failed", "skipped", "planned"]


@dataclass(frozen=True)
class CiStepResult:
    """Result for one CI pipeline step."""

    name: str
    status: StepStatus
    exit_code: int | None
    artifact_path: Path | None = None
    message: str = ""
    duration_seconds: float | None = 0.0


@dataclass(frozen=True)
class CiResult:
    """Complete VibeBench CI pipeline result."""

    run_dir: Path | None
    steps: list[CiStepResult]
    passed: bool
    dry_run: bool = False


def plan_ci_pipeline(
    *,
    skip_report: bool = False,
    skip_pr_comment: bool = False,
    skip_explain: bool = False,
    skip_bundle: bool = False,
    skip_export: bool = False,
    skip_badge: bool = False,
    skip_status_block: bool = False,
    skip_trend: bool = False,
    skip_config_check: bool = False,
    skip_manifest: bool = False,
    skip_annotate: bool = False,
    skip_gh_summary: bool = False,
) -> CiResult:
    """Return the CI pipeline plan without running commands or writing artifacts."""
    steps = [
        planned_step("check", "Would run configured checks"),
        planned_step("gate", "Would evaluate the quality gate"),
    ]
    for name, skipped, flag in ci_artifact_step_flags(
        skip_report=skip_report,
        skip_pr_comment=skip_pr_comment,
        skip_explain=skip_explain,
        skip_bundle=skip_bundle,
        skip_export=skip_export,
        skip_badge=skip_badge,
        skip_status_block=skip_status_block,
        skip_trend=skip_trend,
        skip_config_check=skip_config_check,
        skip_manifest=skip_manifest,
        skip_annotate=skip_annotate,
        skip_gh_summary=skip_gh_summary,
    ):
        if skipped:
            steps.append(skipped_plan_step(name, flag))
        else:
            steps.append(planned_step(name, f"Would run {name}"))
    return CiResult(run_dir=None, steps=steps, passed=True, dry_run=True)


def planned_step(name: str, message: str) -> CiStepResult:
    """Create a dry-run planned step."""
    return CiStepResult(
        name,
        "planned",
        None,
        artifact_path=None,
        message=message,
        duration_seconds=None,
    )


def skipped_plan_step(name: str, flag: str) -> CiStepResult:
    """Create a dry-run skipped step."""
    return CiStepResult(
        name,
        "skipped",
        None,
        artifact_path=None,
        message=f"Skipped by {flag}",
        duration_seconds=None,
    )


def ci_artifact_step_flags(
    *,
    skip_report: bool,
    skip_pr_comment: bool,
    skip_explain: bool,
    skip_bundle: bool,
    skip_export: bool,
    skip_badge: bool,
    skip_status_block: bool,
    skip_trend: bool,
    skip_config_check: bool,
    skip_manifest: bool,
    skip_annotate: bool,
    skip_gh_summary: bool,
) -> list[tuple[str, bool, str]]:
    """Return artifact step skip flags in canonical CI order."""
    return [
        ("config-check", skip_config_check, "--skip-config-check"),
        ("report", skip_report, "--skip-report"),
        ("pr-comment", skip_pr_comment, "--skip-pr-comment"),
        ("explain", skip_explain, "--skip-explain"),
        ("export", skip_export, "--skip-export"),
        ("badge", skip_badge, "--skip-badge"),
        ("status-block", skip_status_block, "--skip-status-block"),
        ("trend", skip_trend, "--skip-trend"),
        ("manifest", skip_manifest, "--skip-manifest"),
        ("manifest-check", skip_manifest, "--skip-manifest"),
        ("annotate", skip_annotate, "--skip-annotate"),
        ("bundle", skip_bundle, "--skip-bundle"),
        ("gh-summary", skip_gh_summary, "--skip-gh-summary"),
    ]


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
    skip_trend: bool = False,
    skip_config_check: bool = False,
    skip_manifest: bool = False,
    skip_annotate: bool = False,
    skip_gh_summary: bool = False,
    emit_annotations: bool = True,
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
            skip_trend=skip_trend,
            skip_config_check=skip_config_check,
            skip_manifest=skip_manifest,
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
        (
            "config-check",
            skip_config_check,
            lambda: generated_config_check_path(root, selected_run_dir),
        ),
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
            "trend",
            skip_trend,
            lambda: generated_trend_path(root, selected_run_dir),
        ),
        (
            "manifest",
            skip_manifest,
            lambda: generate_manifest(root, selected_run_dir).output_path,
        ),
        (
            "manifest-check",
            skip_manifest,
            lambda: check_manifest(root, selected_run_dir).manifest_path,
        ),
        (
            "annotate",
            skip_annotate,
            lambda: generated_annotations(
                root,
                selected_run_dir,
                emit=emit_annotations,
            ),
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
    skip_trend: bool,
    skip_config_check: bool,
    skip_manifest: bool,
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
        ("trend", skip_trend),
        ("config-check", skip_config_check),
        ("manifest", skip_manifest),
        ("manifest-check", skip_manifest),
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
    started = time.perf_counter()
    target = config_file(project_root)
    try:
        config = load_config(target)
        result = run_checks(config, project_root)
    except ConfigError as exc:
        return (
            CiStepResult(
                "check",
                "failed",
                1,
                message=str(exc),
                duration_seconds=elapsed_since(started),
            ),
            None,
        )
    except Exception as exc:
        return (
            CiStepResult(
                "check",
                "failed",
                1,
                message=str(exc),
                duration_seconds=elapsed_since(started),
            ),
            None,
        )

    status: StepStatus = "passed" if result.overall_status == "passed" else "failed"
    exit_code = 0 if status == "passed" else 1
    return (
        CiStepResult(
            "check",
            status,
            exit_code,
            artifact_path=result.metrics_path,
            message=f"status {result.overall_status}",
            duration_seconds=elapsed_since(started),
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
    started = time.perf_counter()
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
        return CiStepResult(
            "gate",
            "failed",
            1,
            message=str(exc),
            duration_seconds=elapsed_since(started),
        )

    status: StepStatus = "passed" if result.passed else "failed"
    return CiStepResult(
        "gate",
        status,
        0 if result.passed else 1,
        artifact_path=result.summary_path,
        message="passed" if result.passed else "; ".join(result.reasons),
        duration_seconds=elapsed_since(started),
    )


def run_artifact_step(name: str, callback: object) -> CiStepResult:
    """Run an artifact callback and capture errors."""
    started = time.perf_counter()
    try:
        artifact_path = callback()
    except Exception as exc:
        return CiStepResult(
            name,
            "failed",
            1,
            message=str(exc),
            duration_seconds=elapsed_since(started),
        )
    return CiStepResult(
        name,
        "passed",
        0,
        artifact_path=artifact_path,
        duration_seconds=elapsed_since(started),
    )


def elapsed_since(started: float) -> float:
    """Return elapsed monotonic time in seconds."""
    return time.perf_counter() - started


def ci_json_payload(result: CiResult) -> dict[str, object]:
    """Return a deterministic JSON-compatible CI result payload."""
    run_id = result.run_dir.name if result.run_dir is not None else None
    return {
        "status": (
            "planned"
            if result.dry_run
            else "passed"
            if result.passed
            else "failed"
        ),
        "dry_run": result.dry_run,
        "run_dir": str(result.run_dir) if result.run_dir is not None else None,
        "run_id": run_id,
        "steps": [
            {
                "name": step.name,
                "status": step.status,
                "exit_code": step.exit_code,
                "artifact": str(step.artifact_path) if step.artifact_path else None,
                "message": step.message,
                "duration_seconds": step.duration_seconds,
            }
            for step in result.steps
        ],
    }


def write_ci_json(result: CiResult, output_path: Path) -> Path:
    """Write CI JSON payload to a file."""
    if output_path.exists() and output_path.is_dir():
        raise ConfigError(f"CI JSON output path is a directory: {output_path}")
    if not output_path.parent.exists():
        raise ConfigError(f"CI JSON output parent does not exist: {output_path.parent}")
    output_path.write_text(
        json.dumps(ci_json_payload(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def generated_config_check_path(
    project_root: Path, run_dir: Path | None
) -> Path | None:
    """Generate config check artifacts and return the JSON path."""
    if run_dir is None:
        return None
    target = config_file(project_root)
    if not target.exists():
        raise ConfigError(
            f"No VibeBench config found at {target}.\n"
            'Run "vibebench init" to create one.'
        )
    result = load_effective_config(target)
    checks = config_consistency_checks(result, include_advice=True)
    json_path = run_dir / CONFIG_CHECK_JSON
    summary_path = run_dir / CONFIG_CHECK_SUMMARY
    write_config_check_json(result, checks, json_path, include_advice=True)
    write_config_check_summary(result, checks, summary_path, include_advice=True)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if payload["overall_status"] == "failed":
        raise ConfigError("Config consistency check failed.")
    return json_path


def generated_annotations(
    project_root: Path,
    run_dir: Path | None,
    *,
    emit: bool = True,
) -> None:
    """Generate annotations and print their output."""
    result = generate_annotations(project_root, run_dir)
    if emit and result.output:
        print(result.output)
    return None


def generated_explanation_path(project_root: Path, run_dir: Path | None) -> Path | None:
    """Generate explanation and return its path."""
    return generate_explanation(project_root, run_dir).output_path


def generated_trend_path(project_root: Path, run_dir: Path | None) -> Path | None:
    """Generate trend summary artifacts and return the Markdown path."""
    result = analyze_trend(project_root)
    markdown_output = run_dir / "trend.md" if run_dir is not None else None
    json_output = run_dir / "trend.json" if run_dir is not None else None
    markdown_path = write_trend_summary(result, markdown_output)
    write_trend_json(result, json_output)
    return markdown_path


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
