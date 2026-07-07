"""One-shot VibeBench CI pipeline orchestration."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from vibebench.annotate import generate_annotations
from vibebench.badge import generate_ci_badges
from vibebench.bundle import create_bundle
from vibebench.compare import compare_runs
from vibebench.config import ConfigError, load_config, load_effective_config
from vibebench.config_check import (
    CONFIG_CHECK_JSON,
    CONFIG_CHECK_SUMMARY,
    config_consistency_checks,
    write_config_check_json,
    write_config_check_summary,
)
from vibebench.evidence_room import write_evidence_room
from vibebench.explain import generate_explanation
from vibebench.export import export_json_for_ci
from vibebench.gate import run_gate
from vibebench.gh_summary import generate_github_summary
from vibebench.manifest import check_manifest, generate_manifest
from vibebench.metrics_check import (
    METRICS_CHECK_JSON,
    METRICS_CHECK_SUMMARY,
    run_metrics_check,
)
from vibebench.metrics_diff import (
    METRICS_DIFF_JSON,
    METRICS_DIFF_SUMMARY,
    run_metrics_diff,
)
from vibebench.onboard import (
    ONBOARD_JSON,
    ONBOARD_SUMMARY,
    onboard_payload,
    write_onboard_json,
    write_onboard_summary,
)
from vibebench.package_check import (
    PACKAGE_CHECK_JSON,
    PACKAGE_CHECK_SUMMARY,
    run_package_check,
    write_package_check_json,
    write_package_check_summary,
)
from vibebench.paths import config_dir, config_file
from vibebench.pr_comment import generate_pr_comment
from vibebench.project_scan import (
    PROJECT_SCAN_JSON,
    PROJECT_SCAN_SUMMARY,
    run_project_scan,
    write_project_scan_json,
    write_project_scan_summary,
)
from vibebench.regression_check import (
    REGRESSION_CHECK_JSON,
    REGRESSION_CHECK_SUMMARY,
    run_regression_check,
)
from vibebench.release_check import (
    RELEASE_CHECK_JSON,
    RELEASE_CHECK_SUMMARY,
    run_release_check,
    write_release_check_json,
    write_release_check_summary,
)
from vibebench.report import ReportError, generate_report, load_metrics
from vibebench.run_index import (
    build_run_index,
    write_run_index_json,
    write_run_index_summary,
)
from vibebench.runner import run_checks
from vibebench.status_block import generate_status_block
from vibebench.trend import analyze_trend, write_trend_json, write_trend_summary
from vibebench.workflow_template import (
    DEFAULT_WORKFLOW_INSTALL_COMMAND,
    WORKFLOW_TEMPLATE_JSON,
    WORKFLOW_TEMPLATE_SUMMARY,
    WORKFLOW_TEMPLATE_YAML,
    workflow_template_payload,
    write_workflow_template_json,
    write_workflow_template_summary,
)

StepStatus = Literal["passed", "failed", "skipped", "planned"]
RegressionGuardSource = Literal["cli", "config", "default"]
CI_PLAN_JSON = "ci-plan.json"
CI_PLAN_MARKDOWN = "ci-plan.md"


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
class CiRegressionGuardPolicy:
    """Effective CI compare regression guard policy."""

    enabled: bool = False
    source: RegressionGuardSource = "default"
    message: str = "Disabled by default."


@dataclass(frozen=True)
class CiResult:
    """Complete VibeBench CI pipeline result."""

    run_dir: Path | None
    steps: list[CiStepResult]
    passed: bool
    dry_run: bool = False
    regression_guard: CiRegressionGuardPolicy = CiRegressionGuardPolicy()


@dataclass(frozen=True)
class CiPlanArtifacts:
    """Artifacts written for a CI dry-run plan."""

    output_dir: Path | None
    json_path: Path | None
    markdown_path: Path | None


def ci_regression_guard_policy(
    *,
    enabled: bool = False,
    source: RegressionGuardSource | None = None,
    message: str | None = None,
) -> CiRegressionGuardPolicy:
    """Return the effective CI regression guard policy."""
    selected_source: RegressionGuardSource = source or ("cli" if enabled else "default")
    if message is None:
        if enabled and selected_source == "cli":
            message = "Enabled by --fail-on-regression."
        elif enabled and selected_source == "config":
            message = "Enabled by compare.fail_on_regression."
        elif selected_source == "cli":
            message = "Disabled by --no-fail-on-regression."
        elif selected_source == "config":
            message = "Disabled by compare.fail_on_regression."
        else:
            message = "Disabled by default."
    return CiRegressionGuardPolicy(
        enabled=enabled,
        source=selected_source,
        message=message,
    )


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
    skip_run_index: bool = False,
    skip_compare: bool = False,
    skip_config_check: bool = False,
    skip_manifest: bool = False,
    skip_annotate: bool = False,
    skip_gh_summary: bool = False,
    skip_release_check: bool = False,
    skip_package_check: bool = False,
    skip_evidence_room: bool = False,
    onboard: bool = False,
    skip_onboard: bool = False,
    onboard_policy: bool = False,
    project_scan: bool = False,
    skip_project_scan: bool = False,
    project_scan_policy: bool = False,
    metrics_check: bool = False,
    skip_metrics_check: bool = False,
    metrics_diff: bool = False,
    skip_metrics_diff: bool = False,
    metrics_diff_policy: bool = False,
    skip_metrics_diff_policy: bool = False,
    workflow_template: bool = False,
    skip_workflow_template: bool = False,
    workflow_template_profile: str = "auto",
    workflow_template_ci_mode: str = "adoption",
    workflow_template_install_command: str = DEFAULT_WORKFLOW_INSTALL_COMMAND,
    regression_check: bool = False,
    require_regression_baseline: bool = False,
    baseline_label: str | None = None,
    regression_policy_source: str = "default",
    max_score_drop: float = 0.0,
    max_risk_increase: float = 0.0,
    fail_on_missing_metrics: bool = True,
    fail_on_regression: bool = False,
    regression_guard_source: RegressionGuardSource | None = None,
    regression_guard_message: str | None = None,
) -> CiResult:
    """Return the CI pipeline plan without running commands or writing artifacts."""
    regression_guard = ci_regression_guard_policy(
        enabled=fail_on_regression,
        source=regression_guard_source,
        message=regression_guard_message,
    )
    if skip_compare and regression_guard.enabled:
        regression_guard = ci_regression_guard_policy(
            enabled=False,
            source="cli",
            message="Disabled because --skip-compare skips compare.",
        )
    steps = [
        planned_step("check", "Would run configured checks"),
        planned_step("gate", "Would evaluate the quality gate"),
    ]
    validate_project_scan_flags(
        project_scan=project_scan,
        skip_project_scan=skip_project_scan,
        project_scan_policy=project_scan_policy,
    )
    validate_metrics_artifact_flags(
        metrics_check=metrics_check,
        skip_metrics_check=skip_metrics_check,
        metrics_diff=metrics_diff,
        skip_metrics_diff=skip_metrics_diff,
        metrics_diff_policy=metrics_diff_policy,
        skip_metrics_diff_policy=skip_metrics_diff_policy,
    )
    metrics_diff_enabled = metrics_diff or metrics_diff_policy
    if metrics_check:
        steps.append(
            planned_step("metrics-check", "Would validate metrics.json contract")
        )
    elif skip_metrics_check:
        steps.append(skipped_plan_step("metrics-check", "--skip-metrics-check"))
    if metrics_diff_enabled:
        message = "Would compare metrics against baseline"
        if metrics_diff_policy:
            message += " with policy enforcement"
        steps.append(planned_step("metrics-diff", message))
    elif skip_metrics_diff:
        steps.append(skipped_plan_step("metrics-diff", "--skip-metrics-diff"))
    if skip_onboard:
        steps.append(skipped_plan_step("onboard", "--skip-onboard"))
    elif onboard_policy:
        steps.append(
            planned_step(
                "onboard",
                "Would write onboarding plan artifacts with policy enforcement",
            )
        )
    elif onboard:
        steps.append(planned_step("onboard", "Would write onboarding plan artifacts"))
    if project_scan_policy:
        steps.append(
            planned_step(
                "project-scan",
                "Would run project-scan report with policy enforcement",
            )
        )
    elif project_scan:
        steps.append(planned_step("project-scan", "Would run project-scan report"))
    elif skip_project_scan:
        steps.append(skipped_plan_step("project-scan", "--skip-project-scan"))
    if workflow_template and not skip_workflow_template:
        steps.append(
            planned_step(
                "workflow-template",
                "Would write workflow-template artifacts",
                artifact=Path(WORKFLOW_TEMPLATE_JSON),
            )
        )
    elif skip_workflow_template:
        steps.append(
            skipped_plan_step(
                "workflow-template",
                "--skip-workflow-template",
                artifact=Path(WORKFLOW_TEMPLATE_JSON),
            )
        )
    for name, skipped, flag in ci_artifact_step_flags(
        skip_report=skip_report,
        skip_pr_comment=skip_pr_comment,
        skip_explain=skip_explain,
        skip_bundle=skip_bundle,
        skip_export=skip_export,
        skip_badge=skip_badge,
        skip_status_block=skip_status_block,
        skip_trend=skip_trend,
        skip_run_index=skip_run_index,
        skip_compare=skip_compare,
        skip_config_check=skip_config_check,
        skip_manifest=skip_manifest,
        skip_annotate=skip_annotate,
        skip_gh_summary=skip_gh_summary,
        skip_release_check=skip_release_check,
        skip_package_check=skip_package_check,
        skip_evidence_room=skip_evidence_room,
    ):
        if skipped:
            if name == "evidence-room":
                steps.append(
                    skipped_plan_step(
                        name,
                        flag,
                        artifact=Path("evidence-room"),
                    )
                )
            else:
                steps.append(skipped_plan_step(name, flag))
        elif name == "compare" and regression_guard.enabled:
            steps.append(planned_step(name, "Would run compare with regression guard"))
        elif name == "evidence-room":
            steps.append(
                planned_step(
                    name,
                    "Would generate evidence room artifact",
                    artifact=Path("evidence-room"),
                )
            )
        else:
            steps.append(planned_step(name, f"Would run {name}"))
        if name == "compare" and regression_check:
            steps.append(
                planned_step(
                    "regression-check",
                    regression_check_plan_message(
                        require_regression_baseline,
                        baseline_label=baseline_label,
                        policy_source=regression_policy_source,
                        max_score_drop=max_score_drop,
                        max_risk_increase=max_risk_increase,
                        fail_on_missing_metrics=fail_on_missing_metrics,
                    ),
                )
            )
    return CiResult(
        run_dir=None,
        steps=steps,
        passed=True,
        dry_run=True,
        regression_guard=regression_guard,
    )


def planned_step(
    name: str,
    message: str,
    *,
    artifact: Path | None = None,
) -> CiStepResult:
    """Create a dry-run planned step."""
    return CiStepResult(
        name,
        "planned",
        None,
        artifact_path=artifact,
        message=message,
        duration_seconds=None,
    )


def skipped_plan_step(
    name: str,
    flag: str,
    *,
    artifact: Path | None = None,
) -> CiStepResult:
    """Create a dry-run skipped step."""
    return CiStepResult(
        name,
        "skipped",
        None,
        artifact_path=artifact,
        message=f"Skipped by {flag}",
        duration_seconds=None,
    )


def regression_check_plan_message(
    require_baseline: bool,
    *,
    baseline_label: str | None = None,
    policy_source: str = "default",
    max_score_drop: float = 0.0,
    max_risk_increase: float = 0.0,
    fail_on_missing_metrics: bool = True,
) -> str:
    """Return dry-run message for the optional regression-check step."""
    label_text = (
        f" using pinned baseline label {baseline_label!r}" if baseline_label else ""
    )
    threshold_text = (
        f" (policy={policy_source}, max_score_drop={max_score_drop:g}, "
        f"max_risk_increase={max_risk_increase:g}, "
        f"fail_on_missing_metrics={str(fail_on_missing_metrics).lower()})"
    )
    if require_baseline:
        return (
            f"Would run regression-check{label_text} and require a baseline"
            + threshold_text
        )
    return (
        f"Would run regression-check{label_text}; missing baseline would be skipped"
        + threshold_text
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
    skip_run_index: bool,
    skip_compare: bool,
    skip_config_check: bool,
    skip_manifest: bool,
    skip_annotate: bool,
    skip_gh_summary: bool,
    skip_release_check: bool,
    skip_package_check: bool,
    skip_evidence_room: bool,
) -> list[tuple[str, bool, str]]:
    """Return artifact step skip flags in canonical CI order."""
    return [
        ("config-check", skip_config_check, "--skip-config-check"),
        ("package-check", skip_package_check, "--skip-package-check"),
        ("report", skip_report, "--skip-report"),
        ("pr-comment", skip_pr_comment, "--skip-pr-comment"),
        ("explain", skip_explain, "--skip-explain"),
        ("export", skip_export, "--skip-export"),
        ("badge", skip_badge, "--skip-badge"),
        ("status-block", skip_status_block, "--skip-status-block"),
        ("trend", skip_trend, "--skip-trend"),
        ("run-index", skip_run_index, "--skip-run-index"),
        ("compare", skip_compare, "--skip-compare"),
        ("evidence-room", skip_evidence_room, "--skip-evidence-room"),
        ("manifest", skip_manifest, "--skip-manifest"),
        ("manifest-check", skip_manifest, "--skip-manifest"),
        ("release-check", skip_release_check, "--skip-release-check"),
        ("annotate", skip_annotate, "--skip-annotate"),
        ("bundle", skip_bundle, "--skip-bundle"),
        ("gh-summary", skip_gh_summary, "--skip-gh-summary"),
    ]


def write_ci_plan_artifacts(
    project_root: Path,
    result: CiResult,
    *,
    output_dir: Path | None = None,
    json_output: Path | None = None,
    summary_output: Path | None = None,
    create_default_dir: bool = False,
) -> CiPlanArtifacts:
    """Write dry-run plan artifacts and return their paths."""
    if not result.dry_run:
        raise ConfigError("CI plan artifacts can only be written for --dry-run/--plan.")
    no_outputs_requested = (
        not create_default_dir
        and output_dir is None
        and json_output is None
        and summary_output is None
    )
    if no_outputs_requested:
        return CiPlanArtifacts(output_dir=None, json_path=None, markdown_path=None)

    root = project_root.resolve()
    selected_output_dir = output_dir.resolve() if output_dir is not None else None
    if selected_output_dir is None and create_default_dir:
        selected_output_dir = create_plan_dir(root)
    if selected_output_dir is not None:
        validate_plan_output_dir(selected_output_dir)
        selected_output_dir.mkdir(parents=True, exist_ok=True)
        write_plan_metrics(selected_output_dir)

    json_path = resolve_plan_output_path(
        selected_output_dir,
        json_output,
        CI_PLAN_JSON,
    )
    markdown_path = resolve_plan_output_path(
        selected_output_dir,
        summary_output,
        CI_PLAN_MARKDOWN,
    )

    if json_path is not None:
        validate_file_output_path(json_path)
        json_path.write_text(
            json.dumps(ci_json_payload(result), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if markdown_path is not None:
        validate_file_output_path(markdown_path)
        markdown_path.write_text(render_ci_plan_markdown(result), encoding="utf-8")
    return CiPlanArtifacts(
        output_dir=selected_output_dir,
        json_path=json_path,
        markdown_path=markdown_path,
    )


def create_plan_dir(project_root: Path) -> Path:
    """Create a timestamped run-like directory for CI plan artifacts."""
    timestamp = datetime.now(UTC).astimezone().strftime("%Y%m%d_%H%M%S_plan")
    base_dir = config_dir(project_root) / "runs" / timestamp
    output_dir = base_dir
    suffix = 1
    while output_dir.exists():
        output_dir = Path(f"{base_dir}_{suffix}")
        suffix += 1
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def validate_plan_output_dir(output_dir: Path) -> None:
    """Validate a requested plan output directory."""
    if output_dir.exists() and not output_dir.is_dir():
        raise ConfigError(f"CI plan output path is not a directory: {output_dir}")
    if not output_dir.exists() and not output_dir.parent.exists():
        raise ConfigError(f"CI plan output parent does not exist: {output_dir.parent}")


def resolve_plan_output_path(
    output_dir: Path | None,
    explicit_output: Path | None,
    default_name: str,
) -> Path | None:
    """Resolve a plan artifact output path."""
    if explicit_output is not None:
        return explicit_output.resolve()
    if output_dir is None:
        return None
    return output_dir / default_name


def validate_file_output_path(output_path: Path) -> None:
    """Validate a requested artifact file path."""
    if output_path.exists() and output_path.is_dir():
        raise ConfigError(f"CI plan output path is a directory: {output_path}")
    if not output_path.parent.exists():
        raise ConfigError(f"CI plan output parent does not exist: {output_path.parent}")


def write_plan_metrics(output_dir: Path) -> None:
    """Write minimal metrics so plan artifacts can use run artifact tooling."""
    now = datetime.now(UTC).isoformat()
    payload = {
        "schema_version": "1.0",
        "project_name": "vibebench-ci-plan",
        "created_at": now,
        "overall_status": "planned",
        "score": 0,
        "risk_level": "low",
        "command_results": [],
        "diff_analysis": {
            "git_available": False,
            "changed_files": [],
            "deleted_files": [],
            "added_files": [],
            "modified_files": [],
            "renamed_files": [],
            "test_files_changed": [],
            "tests_deleted": [],
            "forbidden_paths_touched": [],
            "secret_like_files_touched": [],
            "lockfiles_changed": [],
            "total_added_lines": 0,
            "total_deleted_lines": 0,
            "total_patch_lines": 0,
            "changed_file_count": 0,
            "warnings": ["CI dry-run plan artifact; checks were not executed."],
            "file_changes": [],
        },
        "risk_findings": [],
        "summary": {
            "total_commands": 0,
            "passed_commands": 0,
            "failed_commands": 0,
            "total_findings": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "warning_findings": 0,
            "info_findings": 0,
        },
    }
    output_dir.joinpath("metrics.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def render_ci_plan_markdown(result: CiResult) -> str:
    """Render a human-readable Markdown CI plan."""
    generated_at = datetime.now(UTC).isoformat()
    lines = [
        "# VibeBench CI Plan",
        "",
        "- Status: planned",
        "- dry_run: true",
        f"- Generated: {generated_at}",
        "",
        "| Step | Status | Exit code | Artifact | Message |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in result.steps:
        lines.append(
            "| "
            f"{markdown_cell(step.name)} | "
            f"{markdown_cell(step.status)} | "
            f"{markdown_cell(step.exit_code)} | "
            f"{markdown_cell(step.artifact_path)} | "
            f"{markdown_cell(step.message)} |"
        )
    lines.append("")
    return "\n".join(lines)


def markdown_cell(value: object) -> str:
    """Escape a Markdown table cell."""
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


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
    skip_run_index: bool = False,
    skip_compare: bool = False,
    skip_config_check: bool = False,
    skip_manifest: bool = False,
    skip_annotate: bool = False,
    skip_gh_summary: bool = False,
    skip_release_check: bool = False,
    skip_package_check: bool = False,
    skip_evidence_room: bool = False,
    onboard: bool = False,
    skip_onboard: bool = False,
    onboard_policy: bool = False,
    project_scan: bool = False,
    skip_project_scan: bool = False,
    project_scan_policy: bool = False,
    metrics_check: bool = False,
    skip_metrics_check: bool = False,
    metrics_diff: bool = False,
    skip_metrics_diff: bool = False,
    metrics_diff_policy: bool = False,
    skip_metrics_diff_policy: bool = False,
    workflow_template: bool = False,
    skip_workflow_template: bool = False,
    workflow_template_profile: str = "auto",
    workflow_template_ci_mode: str = "adoption",
    workflow_template_install_command: str = DEFAULT_WORKFLOW_INSTALL_COMMAND,
    regression_check: bool = False,
    require_regression_baseline: bool = False,
    baseline_label: str | None = None,
    regression_policy_source: str = "default",
    max_score_drop: float = 0.0,
    max_risk_increase: float = 0.0,
    fail_on_missing_metrics: bool = True,
    emit_annotations: bool = True,
    bundle_include_report_assets: bool = False,
    bundle_strict: bool = False,
    min_score: int | None = None,
    max_risk: str | None = None,
    allow_findings: int | None = None,
    require_status_passed: bool | None = None,
    fail_on_regression: bool = False,
    regression_guard_source: RegressionGuardSource | None = None,
    regression_guard_message: str | None = None,
) -> CiResult:
    """Run the complete local CI pipeline."""
    regression_guard = ci_regression_guard_policy(
        enabled=fail_on_regression,
        source=regression_guard_source,
        message=regression_guard_message,
    )
    if skip_compare and regression_guard.enabled:
        regression_guard = ci_regression_guard_policy(
            enabled=False,
            source="cli",
            message="Disabled because --skip-compare skips compare.",
        )
    validate_project_scan_flags(
        project_scan=project_scan,
        skip_project_scan=skip_project_scan,
        project_scan_policy=project_scan_policy,
    )
    validate_metrics_artifact_flags(
        metrics_check=metrics_check,
        skip_metrics_check=skip_metrics_check,
        metrics_diff=metrics_diff,
        skip_metrics_diff=skip_metrics_diff,
        metrics_diff_policy=metrics_diff_policy,
        skip_metrics_diff_policy=skip_metrics_diff_policy,
    )
    metrics_diff_enabled = metrics_diff or metrics_diff_policy
    onboard_enabled = onboard or onboard_policy
    project_scan_enabled = project_scan or project_scan_policy
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
            skip_run_index=skip_run_index,
            skip_compare=skip_compare,
            skip_config_check=skip_config_check,
            skip_manifest=skip_manifest,
            skip_annotate=skip_annotate,
            skip_gh_summary=skip_gh_summary,
            skip_release_check=skip_release_check,
            skip_package_check=skip_package_check,
            skip_evidence_room=skip_evidence_room,
            onboard=onboard_enabled,
            skip_onboard=skip_onboard,
            project_scan=project_scan_enabled,
            skip_project_scan=skip_project_scan,
            metrics_check=metrics_check,
            skip_metrics_check=skip_metrics_check,
            metrics_diff=metrics_diff_enabled,
            skip_metrics_diff=skip_metrics_diff,
            workflow_template=workflow_template,
            skip_workflow_template=skip_workflow_template,
            regression_check=regression_check,
        )
        return CiResult(
            run_dir=None,
            steps=steps,
            passed=False,
            regression_guard=regression_guard,
        )

    gate_step = run_gate_step(
        root,
        selected_run_dir,
        min_score=min_score,
        max_risk=max_risk,
        allow_findings=allow_findings,
        require_status_passed=require_status_passed,
    )
    steps.append(gate_step)
    if metrics_check:
        steps.append(run_metrics_check_artifact_step(root, selected_run_dir))
    elif skip_metrics_check:
        steps.append(
            CiStepResult("metrics-check", "skipped", 0, message="skipped by flag")
        )
    if metrics_diff_enabled:
        steps.append(
            run_metrics_diff_artifact_step(
                root,
                selected_run_dir,
                enforce_policy=metrics_diff_policy,
            )
        )
    elif skip_metrics_diff:
        steps.append(
            CiStepResult("metrics-diff", "skipped", 0, message="skipped by flag")
        )
    if skip_onboard:
        steps.append(CiStepResult("onboard", "skipped", 0, message="skipped by flag"))
    elif onboard_enabled:
        steps.append(
            run_onboard_artifact_step(
                root,
                selected_run_dir,
                enforce_policy=onboard_policy,
            )
        )
    if project_scan_enabled:
        steps.append(
            run_project_scan_artifact_step(
                root,
                selected_run_dir,
                enforce_policy=project_scan_policy,
            )
        )
    elif skip_project_scan:
        steps.append(
            CiStepResult("project-scan", "skipped", 0, message="skipped by flag")
        )
    if workflow_template and not skip_workflow_template:
        steps.append(
            run_workflow_template_artifact_step(
                root,
                selected_run_dir,
                profile=workflow_template_profile,
                ci_mode=workflow_template_ci_mode,
                install_command=workflow_template_install_command,
            )
        )
    elif skip_workflow_template:
        steps.append(
            CiStepResult(
                "workflow-template", "skipped", 0, message="skipped by flag"
            )
        )

    artifact_steps: list[tuple[str, bool, object]] = [
        (
            "config-check",
            skip_config_check,
            lambda: generated_config_check_path(root, selected_run_dir),
        ),
        (
            "package-check",
            skip_package_check,
            lambda: generated_package_check_path(root, selected_run_dir),
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
            "run-index",
            skip_run_index,
            lambda: generated_run_index_path(root, selected_run_dir),
        ),
        (
            "compare",
            skip_compare,
            lambda: generated_compare_path(root, selected_run_dir),
        ),
        (
            "evidence-room",
            skip_evidence_room,
            lambda: generated_evidence_room_path(root, selected_run_dir),
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
            "release-check",
            skip_release_check,
            lambda: generated_release_check_path(root, selected_run_dir),
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
            if name == "compare" and regression_check:
                steps.append(
                    run_regression_check_artifact_step(
                        root,
                        selected_run_dir,
                        require_baseline=require_regression_baseline,
                        baseline_label=baseline_label,
                        policy_source=regression_policy_source,
                        max_score_drop=max_score_drop,
                        max_risk_increase=max_risk_increase,
                        fail_on_missing_metrics=fail_on_missing_metrics,
                    )
                )
            continue
        if name == "compare":
            steps.append(
                run_compare_artifact_step(
                    root,
                    selected_run_dir,
                    fail_on_regression=regression_guard.enabled,
                )
            )
            if regression_check:
                steps.append(
                    run_regression_check_artifact_step(
                        root,
                        selected_run_dir,
                        require_baseline=require_regression_baseline,
                        baseline_label=baseline_label,
                        policy_source=regression_policy_source,
                        max_score_drop=max_score_drop,
                        max_risk_increase=max_risk_increase,
                        fail_on_missing_metrics=fail_on_missing_metrics,
                    )
                )
            continue
        steps.append(run_artifact_step(name, callback))

    if not skip_manifest:
        refresh_manifest_after_ci(root, selected_run_dir)

    passed = all(step.exit_code == 0 for step in steps if step.status != "skipped")
    return CiResult(
        run_dir=selected_run_dir,
        steps=steps,
        passed=passed,
        regression_guard=regression_guard,
    )


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
    skip_run_index: bool,
    skip_compare: bool,
    skip_config_check: bool,
    skip_manifest: bool,
    skip_annotate: bool,
    skip_gh_summary: bool,
    skip_release_check: bool,
    skip_package_check: bool,
    skip_evidence_room: bool,
    onboard: bool = False,
    skip_onboard: bool = False,
    onboard_policy: bool = False,
    project_scan: bool = False,
    skip_project_scan: bool = False,
    metrics_check: bool = False,
    skip_metrics_check: bool = False,
    metrics_diff: bool = False,
    skip_metrics_diff: bool = False,
    workflow_template: bool = False,
    skip_workflow_template: bool = False,
    regression_check: bool = False,
) -> None:
    """Append artifact steps when no run directory exists."""
    if metrics_check:
        steps.append(
            CiStepResult(
                "metrics-check",
                "failed",
                1,
                message="no run directory available",
            )
        )
    elif skip_metrics_check:
        steps.append(
            CiStepResult("metrics-check", "skipped", 0, message="skipped by flag")
        )
    if metrics_diff:
        steps.append(
            CiStepResult(
                "metrics-diff",
                "failed",
                1,
                message="no run directory available",
            )
        )
    elif skip_metrics_diff:
        steps.append(
            CiStepResult("metrics-diff", "skipped", 0, message="skipped by flag")
        )
    if skip_onboard:
        steps.append(CiStepResult("onboard", "skipped", 0, message="skipped by flag"))
    elif onboard:
        steps.append(
            CiStepResult(
                "onboard",
                "failed",
                1,
                message="no run directory available",
            )
        )
    if project_scan:
        steps.append(
            CiStepResult(
                "project-scan",
                "failed",
                1,
                message="no run directory available",
            )
        )
    elif skip_project_scan:
        steps.append(
            CiStepResult("project-scan", "skipped", 0, message="skipped by flag")
        )
    if workflow_template and not skip_workflow_template:
        steps.append(
            CiStepResult(
                "workflow-template",
                "failed",
                1,
                message="no run directory available",
            )
        )
    elif skip_workflow_template:
        steps.append(
            CiStepResult(
                "workflow-template", "skipped", 0, message="skipped by flag"
            )
        )

    flags = [
        ("report", skip_report),
        ("pr-comment", skip_pr_comment),
        ("explain", skip_explain),
        ("export", skip_export),
        ("badge", skip_badge),
        ("status-block", skip_status_block),
        ("trend", skip_trend),
        ("run-index", skip_run_index),
        ("compare", skip_compare),
        ("evidence-room", skip_evidence_room),
        ("config-check", skip_config_check),
        ("package-check", skip_package_check),
        ("manifest", skip_manifest),
        ("manifest-check", skip_manifest),
        ("release-check", skip_release_check),
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
        if name == "compare" and regression_check:
            steps.append(
                CiStepResult(
                    "regression-check",
                    "failed",
                    1,
                    message="no run directory available",
                )
            )


def refresh_manifest_after_ci(project_root: Path, run_dir: Path) -> None:
    """Refresh manifest after late artifact steps."""
    generate_manifest(project_root, run_dir)


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


def validate_project_scan_flags(
    *,
    project_scan: bool,
    skip_project_scan: bool,
    project_scan_policy: bool = False,
) -> None:
    """Validate optional project-scan artifact flags."""
    if project_scan and skip_project_scan:
        raise ConfigError("--project-scan and --skip-project-scan cannot be combined.")
    if project_scan_policy and skip_project_scan:
        raise ConfigError(
            "--project-scan-policy cannot be combined with --skip-project-scan."
        )


def validate_metrics_artifact_flags(
    *,
    metrics_check: bool,
    skip_metrics_check: bool,
    metrics_diff: bool,
    skip_metrics_diff: bool,
    metrics_diff_policy: bool = False,
    skip_metrics_diff_policy: bool = False,
) -> None:
    """Validate optional metrics artifact flags."""
    if metrics_check and skip_metrics_check:
        raise ConfigError(
            "--metrics-check and --skip-metrics-check cannot be combined."
        )
    if metrics_diff and skip_metrics_diff:
        raise ConfigError(
            "--metrics-diff and --skip-metrics-diff cannot be combined."
        )
    if metrics_diff_policy and skip_metrics_diff_policy:
        raise ConfigError(
            "--metrics-diff-policy and --skip-metrics-diff-policy cannot be combined."
        )
    if metrics_diff_policy and skip_metrics_diff:
        raise ConfigError(
            "--metrics-diff-policy cannot be combined with --skip-metrics-diff."
        )


def run_workflow_template_artifact_step(
    project_root: Path,
    run_dir: Path,
    *,
    profile: str = "auto",
    ci_mode: str = "adoption",
    install_command: str = DEFAULT_WORKFLOW_INSTALL_COMMAND,
) -> CiStepResult:
    """Generate workflow-template artifacts and return CI step status."""
    started = time.perf_counter()
    try:
        yaml_path = run_dir / WORKFLOW_TEMPLATE_YAML
        payload = workflow_template_payload(
            project_root,
            yaml_path,
            profile=profile,
            ci_mode=ci_mode,
            install_command=install_command,
            write=False,
            dry_run=False,
            force=False,
        )
        json_path = run_dir / WORKFLOW_TEMPLATE_JSON
        summary_path = run_dir / WORKFLOW_TEMPLATE_SUMMARY
        write_workflow_template_json(json_path, payload)
        write_workflow_template_summary(summary_path, payload)
        yaml_path.write_text(str(payload["workflow_yaml"]), encoding="utf-8")
    except Exception as exc:
        return CiStepResult(
            "workflow-template",
            "failed",
            1,
            message=str(exc),
            duration_seconds=elapsed_since(started),
        )
    return CiStepResult(
        "workflow-template",
        "passed",
        0,
        artifact_path=json_path,
        message=f"profile {payload['resolved_profile']}; ci-mode {payload['ci_mode']}",
        duration_seconds=elapsed_since(started),
    )


def run_onboard_artifact_step(
    project_root: Path,
    run_dir: Path,
    *,
    enforce_policy: bool = False,
) -> CiStepResult:
    """Generate onboard artifacts and return CI step status."""
    started = time.perf_counter()
    try:
        payload = onboard_payload(project_root, enforce_policy=enforce_policy)
        json_path = run_dir / ONBOARD_JSON
        summary_path = run_dir / ONBOARD_SUMMARY
        write_onboard_json(json_path, payload)
        write_onboard_summary(summary_path, payload)
    except Exception as exc:
        return CiStepResult(
            "onboard",
            "failed",
            1,
            message=str(exc),
            duration_seconds=elapsed_since(started),
        )
    policy_failed = (
        payload.get("policy_enforced") and payload.get("policy_status") == "failed"
    )
    message = f"plan {payload['status']}"
    if payload.get("policy_status") is not None:
        message = f"policy {payload['policy_status']}"
    return CiStepResult(
        "onboard",
        "failed" if policy_failed else "passed",
        1 if policy_failed else 0,
        artifact_path=json_path,
        message=message,
        duration_seconds=elapsed_since(started),
    )


def run_project_scan_artifact_step(
    project_root: Path,
    run_dir: Path,
    *,
    enforce_policy: bool = False,
) -> CiStepResult:
    """Generate project-scan artifacts and return CI step status."""
    started = time.perf_counter()
    try:
        payload = run_project_scan(
            project_root, strict=False, enforce_policy=enforce_policy
        )
        json_path = run_dir / PROJECT_SCAN_JSON
        summary_path = run_dir / PROJECT_SCAN_SUMMARY
        write_project_scan_json(json_path, payload)
        write_project_scan_summary(summary_path, payload)
    except Exception as exc:
        return CiStepResult(
            "project-scan",
            "failed",
            1,
            message=str(exc),
            duration_seconds=elapsed_since(started),
        )
    policy_failed = enforce_policy and payload.get("policy_status") == "failed"
    message = f"readiness {payload['status']}"
    if enforce_policy:
        message += f"; policy {payload['policy_status']}"
    return CiStepResult(
        "project-scan",
        "failed" if policy_failed else "passed",
        1 if policy_failed else 0,
        artifact_path=json_path,
        message=message,
        duration_seconds=elapsed_since(started),
    )


def run_metrics_check_artifact_step(project_root: Path, run_dir: Path) -> CiStepResult:
    """Generate metrics-check artifacts and return CI step status."""
    started = time.perf_counter()
    try:
        result = run_metrics_check(
            project_root,
            run_dir=run_dir,
            json_output=run_dir / METRICS_CHECK_JSON,
            summary_output=run_dir / METRICS_CHECK_SUMMARY,
        )
    except Exception as exc:
        return CiStepResult(
            "metrics-check",
            "failed",
            1,
            message=str(exc),
            duration_seconds=elapsed_since(started),
        )

    if result.status == "failed":
        return CiStepResult(
            "metrics-check",
            "failed",
            1,
            artifact_path=result.json_path,
            message="metrics contract failed",
            duration_seconds=elapsed_since(started),
        )
    message = "metrics contract passed"
    if result.status == "warning":
        message = "metrics contract passed with warnings"
    return CiStepResult(
        "metrics-check",
        "passed",
        0,
        artifact_path=result.json_path,
        message=message,
        duration_seconds=elapsed_since(started),
    )



def run_metrics_diff_artifact_step(
    project_root: Path,
    run_dir: Path,
    *,
    enforce_policy: bool = False,
) -> CiStepResult:
    """Generate metrics-diff artifacts and return CI step status."""
    started = time.perf_counter()
    try:
        result = run_metrics_diff(
            project_root,
            candidate_run=run_dir,
            enforce_policy=enforce_policy,
            json_output=run_dir / METRICS_DIFF_JSON,
            summary_output=run_dir / METRICS_DIFF_SUMMARY,
        )
    except Exception as exc:
        return CiStepResult(
            "metrics-diff",
            "failed",
            1,
            message=str(exc),
            duration_seconds=elapsed_since(started),
        )

    if result.status == "skipped":
        return CiStepResult(
            "metrics-diff",
            "skipped",
            0,
            artifact_path=result.json_path,
            message=result.message,
            duration_seconds=elapsed_since(started),
        )
    if result.status == "failed":
        return CiStepResult(
            "metrics-diff",
            "failed",
            1,
            artifact_path=result.json_path,
            message=result.message,
            duration_seconds=elapsed_since(started),
        )
    return CiStepResult(
        "metrics-diff",
        "passed",
        0,
        artifact_path=result.json_path,
        message=result.message,
        duration_seconds=elapsed_since(started),
    )


def run_compare_artifact_step(
    project_root: Path,
    run_dir: Path | None,
    *,
    fail_on_regression: bool,
) -> CiStepResult:
    """Generate compare artifacts and optionally fail on a regressed verdict."""
    started = time.perf_counter()
    try:
        result = compare_runs(
            project_root,
            head_run=run_dir,
            fail_on_regression=fail_on_regression,
        )
    except Exception as exc:
        return CiStepResult(
            "compare",
            "failed",
            1,
            message=str(exc),
            duration_seconds=elapsed_since(started),
        )

    if result.regression_guard.status == "failed":
        return CiStepResult(
            "compare",
            "failed",
            1,
            artifact_path=result.json_path,
            message=result.regression_guard.message,
            duration_seconds=elapsed_since(started),
        )

    message = result.regression_guard.message if result.regression_guard.enabled else ""
    return CiStepResult(
        "compare",
        "passed",
        0,
        artifact_path=result.json_path,
        message=message,
        duration_seconds=elapsed_since(started),
    )


def run_regression_check_artifact_step(
    project_root: Path,
    run_dir: Path,
    *,
    require_baseline: bool,
    baseline_label: str | None = None,
    policy_source: str = "default",
    max_score_drop: float = 0.0,
    max_risk_increase: float = 0.0,
    fail_on_missing_metrics: bool = True,
) -> CiStepResult:
    """Generate regression-check artifacts and return CI step status."""
    started = time.perf_counter()
    try:
        result = run_regression_check(
            project_root,
            candidate_run=run_dir,
            require_baseline=require_baseline,
            baseline_label=baseline_label,
            max_score_drop=max_score_drop,
            max_risk_increase=max_risk_increase,
            fail_on_missing_metrics=fail_on_missing_metrics,
            policy_source=policy_source,
            json_output=run_dir / REGRESSION_CHECK_JSON,
            summary_output=run_dir / REGRESSION_CHECK_SUMMARY,
        )
    except Exception as exc:
        return CiStepResult(
            "regression-check",
            "failed",
            1,
            message=str(exc),
            duration_seconds=elapsed_since(started),
        )

    if result.status == "skipped":
        return CiStepResult(
            "regression-check",
            "skipped",
            0,
            artifact_path=result.json_path,
            message=result.message,
            duration_seconds=elapsed_since(started),
        )
    if result.status == "failed":
        return CiStepResult(
            "regression-check",
            "failed",
            1,
            artifact_path=result.json_path,
            message=result.message,
            duration_seconds=elapsed_since(started),
        )
    return CiStepResult(
        "regression-check",
        "passed",
        0,
        artifact_path=result.json_path,
        message=result.message,
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
        "regression_guard": {
            "enabled": result.regression_guard.enabled,
            "source": result.regression_guard.source,
            "message": result.regression_guard.message,
        },
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


def generated_package_check_path(
    project_root: Path,
    run_dir: Path | None,
) -> Path | None:
    """Generate package check artifacts and return the JSON path."""
    if run_dir is None:
        return None
    result = run_package_check(project_root, advice=True)
    json_path = run_dir / PACKAGE_CHECK_JSON
    summary_path = run_dir / PACKAGE_CHECK_SUMMARY
    write_package_check_json(result, json_path)
    write_package_check_summary(result, summary_path)
    if not result.ready:
        failed = [check for check in result.checks if check.status == "failed"]
        message = "; ".join(f"{check.name}: {check.message}" for check in failed)
        raise ConfigError(message or "Package readiness check failed.")
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


def generated_run_index_path(project_root: Path, run_dir: Path | None) -> Path | None:
    """Generate run index artifacts and return the JSON path."""
    result = build_run_index(project_root)
    if run_dir is None:
        return None
    json_path = run_dir / "run-index.json"
    summary_path = run_dir / "run-index.md"
    write_run_index_json(result, json_path)
    write_run_index_summary(result, summary_path)
    return json_path


def generated_compare_path(project_root: Path, run_dir: Path | None) -> Path | None:
    """Generate compare artifacts and return the JSON path."""
    if run_dir is None:
        return None
    result = compare_runs(project_root, head_run=run_dir)
    return result.json_path


def generated_evidence_room_path(
    project_root: Path,
    run_dir: Path | None,
) -> Path | None:
    """Generate the evidence room artifact and return its directory."""
    if run_dir is None:
        return None
    output_dir = run_dir / "evidence-room"
    write_evidence_room(
        project_root=project_root,
        site_root=project_root / "docs",
        root_label="docs",
        output_dir=output_dir,
        create_zip=True,
    )
    return output_dir


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


def generated_release_check_path(project_root: Path, run_dir: Path) -> Path:
    """Write release-check artifacts for a CI run and return the JSON path."""
    result = run_release_check(project_root)
    json_path = run_dir / RELEASE_CHECK_JSON
    summary_path = run_dir / RELEASE_CHECK_SUMMARY
    write_release_check_json(result, json_path)
    write_release_check_summary(result, summary_path)
    return json_path
