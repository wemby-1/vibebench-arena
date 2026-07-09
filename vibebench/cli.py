"""Command-line interface for VibeBench Arena."""

import json
import subprocess
import tomllib
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from vibebench import __version__
from vibebench.annotate import AnnotationResult, generate_annotations
from vibebench.artifacts import (
    ArtifactInventoryResult,
    ArtifactItem,
    collect_artifact_inventory,
    inventory_json,
)
from vibebench.badge import DEFAULT_BADGE_LABEL, BadgeResult, generate_badge
from vibebench.baseline import (
    BaselineStatus,
    BaselineVerificationResult,
    baseline_list_payload,
    baseline_status_payload,
    baseline_verification_json,
    baseline_verification_markdown,
    baseline_verification_payload,
    clear_pinned_baseline,
    export_pinned_baseline,
    import_pinned_baseline,
    list_pinned_baselines,
    set_baseline,
    set_pinned_baseline,
    show_baseline,
    show_pinned_baseline,
    verify_baseline_input,
    verify_pinned_baseline,
)
from vibebench.baseline_promotion import (
    BaselinePromotionResult,
    promote_baseline,
    promotion_json,
    promotion_markdown,
    promotion_payload,
)
from vibebench.bundle import BundleResult, create_bundle
from vibebench.ci import (
    CiRegressionGuardPolicy,
    CiResult,
    ci_json_payload,
    ci_regression_guard_policy,
    plan_ci_pipeline,
    run_ci_pipeline,
    write_ci_json,
    write_ci_plan_artifacts,
)
from vibebench.clean import CleanResult, clean_runs
from vibebench.compare import (
    CompareResult,
    compare_json_payload,
    compare_runs,
)
from vibebench.config import (
    ConfigError,
    EffectiveConfigResult,
    config_example_yaml,
    effective_config_payload,
    load_config,
    load_effective_config,
    resolve_init_config_profile,
)
from vibebench.config_check import (
    advice_for_config_error,
    config_check_payload,
    config_consistency_checks,
    write_config_check_json,
    write_config_check_summary,
)
from vibebench.demo import DemoError, copy_sample_pack, demo_payload
from vibebench.doctor import DoctorResult, doctor_json_payload, run_doctor
from vibebench.evidence_room import (
    EvidenceRoomError,
    evidence_room_json,
    evidence_room_payload,
    evidence_room_verification_json,
    verify_evidence_room,
    write_evidence_room,
    write_evidence_room_json,
    write_zip_only_evidence_room,
)
from vibebench.explain import ExplainResult, generate_explanation
from vibebench.export import ExportResult, export_run
from vibebench.gate import GateResult, run_gate
from vibebench.gh_summary import generate_github_summary
from vibebench.history import HistoryResult, HistoryRun, get_history
from vibebench.latest import (
    LatestRunResult,
    artifact_label,
    available_artifacts,
    get_latest_run,
    latest_json,
    latest_paths_json,
    select_artifact,
)
from vibebench.manifest import (
    ManifestCheckResult,
    ManifestResult,
    check_manifest,
    generate_manifest,
)
from vibebench.metrics_check import (
    MetricsCheckResult,
    metrics_check_json,
    run_metrics_check,
)
from vibebench.metrics_diff import (
    MetricsDiffResult,
    metrics_diff_json,
    run_metrics_diff,
)
from vibebench.onboard import (
    onboard_json,
    onboard_payload,
    write_onboard_json,
    write_onboard_summary,
)
from vibebench.package_check import (
    PackageReadinessResult,
    package_check_json_payload,
    run_package_check,
    write_package_check_json,
    write_package_check_summary,
)
from vibebench.paths import config_file
from vibebench.pr_comment import (
    DEFAULT_COMMENT_MARKER,
    DEFAULT_TOKEN_ENV,
    PrCommentPostResult,
    generate_pr_comment,
    post_pr_comment,
    pr_comment_post_json,
)
from vibebench.preflight import (
    preflight_json,
    preflight_payload,
    write_preflight_json,
    write_preflight_summary,
)
from vibebench.project_scan import (
    run_project_scan,
    write_project_scan_json,
    write_project_scan_summary,
)
from vibebench.proof import (
    ProofError,
    proof_json,
    proof_payload,
    verification_json,
    verify_proof_packet,
    write_proof_packet,
)
from vibebench.publish_check import (
    PublishReadinessResult,
    publish_check_json,
    run_publish_check,
    write_publish_check_json,
    write_publish_check_summary,
)
from vibebench.regression_check import (
    RegressionCheckResult,
    regression_check_json,
    run_regression_check,
)
from vibebench.release_audit import (
    ReleaseAuditResult,
    ReleaseAuditVerifyResult,
    create_release_audit,
    release_audit_json,
    release_audit_verify_json,
    verify_release_audit,
)
from vibebench.release_body import (
    ReleaseBodyResult,
    export_release_body,
    release_body_json,
)
from vibebench.release_check import (
    ReleaseReadinessResult,
    release_check_json,
    run_release_check,
    write_release_check_json,
    write_release_check_summary,
)
from vibebench.report import (
    ReportError,
    generate_report,
    load_metrics,
    recommendation_for,
)
from vibebench.run_index import (
    RunIndexResult,
    build_run_index,
    run_index_payload,
    write_run_index_json,
    write_run_index_summary,
)
from vibebench.runner import CheckRunResult, run_checks
from vibebench.share_check import (
    ShareCheckError,
    ShareCheckResult,
    run_share_check,
    share_check_json,
    write_share_check_json,
    write_share_check_markdown,
)
from vibebench.site_check import (
    run_site_check,
    site_check_json,
    write_site_check_json,
)
from vibebench.site_preview import (
    SitePreviewError,
    site_preview_json,
    site_preview_payload,
    site_preview_verification_json,
    verify_site_preview,
    write_site_preview,
    write_site_preview_json,
    write_zip_only_preview,
)
from vibebench.status_block import (
    DEFAULT_STATUS_TITLE,
    ReadmeStatusBlockResult,
    StatusBlockResult,
    generate_status_block,
    update_readme_status_block,
)
from vibebench.trend import (
    TrendResult,
    analyze_trend,
    trend_json,
    write_trend_json,
    write_trend_summary,
)
from vibebench.workflow_check import (
    normalize_required_ci_modes,
    workflow_check_json,
    workflow_check_payload,
    write_workflow_check_json,
    write_workflow_check_summary,
)
from vibebench.workflow_template import (
    DEFAULT_WORKFLOW_INSTALL_COMMAND,
    WORKFLOW_RELATIVE_PATH,
    workflow_template_error_payload,
    workflow_template_json,
    workflow_template_payload,
    write_workflow_template_json,
    write_workflow_template_summary,
)

app = typer.Typer(
    help="Codex-first quality gate for vibe coding projects.",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)

ProjectRootOption = Annotated[
    Path,
    typer.Option(
        "--project-root",
        "-C",
        help="Project directory where VibeBench should run.",
    ),
]


@app.command()
def version() -> None:
    """Show the installed VibeBench version."""
    console.print(f"VibeBench Arena {__version__}")


@app.command()
def init(
    project_root: ProjectRootOption = Path("."),
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            help="Starter config profile: generic, python, node, fullstack, or auto.",
        ),
    ] = "auto",
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite .vibebench/config.yaml when it already exists.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview init without writing files."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print init result as pure JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write init result JSON to PATH."),
    ] = None,
) -> None:
    """Create a safe starter .vibebench/config.yaml."""
    root = project_root.resolve()
    target = config_file(root)
    try:
        result = run_project_init(
            root,
            target,
            requested_profile=profile,
            force=force,
            dry_run=dry_run,
        )
        if json_output is not None:
            write_init_json_output(resolve_output_path(root, json_output), result)
    except ConfigError as exc:
        result = init_error_payload(root, target, profile, force, dry_run, str(exc))
        if json_output is not None:
            try:
                write_init_json_output(resolve_output_path(root, json_output), result)
            except ConfigError as output_exc:
                err_console.print(f"[red]{output_exc}[/]")
        if as_json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            err_console.print(f"[red]{exc}[/]")
            err_console.print("Use --force only when overwriting is intentional.")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        render_project_init_result(result)


def run_project_init(
    project_root: Path,
    config_path: Path,
    *,
    requested_profile: str,
    force: bool,
    dry_run: bool,
) -> dict[str, object]:
    """Plan or create a starter project config."""
    profile_result = resolve_init_config_profile(requested_profile, project_root)
    selected_profile = profile_result.selected_profile
    content = profile_result.config_yaml
    exists = config_path.exists()
    next_steps = init_next_steps(
        selected_profile=selected_profile,
        package_scripts=profile_result.package_scripts,
    )
    base_payload = {
        "dry_run": dry_run,
        "project_root": str(project_root),
        "config_path": str(config_path),
        "config_exists": exists,
        "selected_profile": selected_profile,
        "requested_profile": requested_profile,
        "detected_stacks": profile_result.detected_stacks,
        "detection_reasons": profile_result.detection_reasons,
        "created": False,
        "overwritten": False,
        "next_steps": next_steps,
    }
    if config_path.exists() and config_path.is_dir():
        raise ConfigError(f"Config path is a directory: {config_path}")
    if dry_run:
        blocked = exists and not force
        return {
            **base_payload,
            "status": "blocked" if blocked else "planned",
            "message": (
                "Config already exists; init would not overwrite without --force."
                if blocked
                else "Dry run only; no files were written."
            ),
        }
    if exists and not force:
        raise ConfigError(
            f"Config already exists at {config_path}. Init refused to overwrite it."
        )
    write_project_init_config(config_path, content)
    return {
        **base_payload,
        "status": "overwritten" if exists else "created",
        "config_exists": True,
        "created": not exists,
        "overwritten": exists,
        "message": "Config overwritten." if exists else "Config created.",
    }


def write_project_init_config(config_path: Path, content: str) -> None:
    """Atomically write and validate an init config."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config_path.with_name(config_path.name + ".tmp")
    try:
        temp_path.write_text(content, encoding="utf-8")
        loaded = load_config(temp_path)
        checks = config_consistency_checks(
            EffectiveConfigResult(
                config=loaded,
                sources={
                    "project": "generated",
                    "checks": "generated",
                    "gate": "generated",
                    "risk": "generated",
                    "compare": "generated",
                    "regression": "generated",
                    "metrics_diff": "generated",
                    "project_scan": "generated",
                },
                config_path=temp_path,
                config_exists=True,
            )
        )
        failed = [check for check in checks if check["status"] == "failed"]
        if failed:
            messages = "; ".join(check["message"] for check in failed)
            raise ConfigError(f"Generated config failed validation: {messages}")
        temp_path.replace(config_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def init_error_payload(
    project_root: Path,
    config_path: Path,
    requested_profile: str,
    force: bool,
    dry_run: bool,
    message: str,
) -> dict[str, object]:
    """Return JSON-safe init error details."""
    return {
        "status": "failed",
        "dry_run": dry_run,
        "project_root": str(project_root),
        "config_path": str(config_path),
        "config_exists": config_path.exists(),
        "selected_profile": None,
        "requested_profile": requested_profile,
        "detected_stacks": [],
        "detection_reasons": [],
        "created": False,
        "overwritten": False,
        "force": force,
        "message": message,
        "next_steps": init_next_steps(),
    }


def init_next_steps(
    *,
    selected_profile: str | None = None,
    package_scripts: list[str] | None = None,
) -> list[str]:
    """Return standard onboarding next-step commands."""
    steps = [
        "python3 -m vibebench config --check",
        "python3 -m vibebench ci --dry-run",
        "python3 -m vibebench ci",
    ]
    scripts = set(package_scripts or [])
    if selected_profile in {"node", "fullstack"}:
        if "lint" not in scripts and "test" not in scripts:
            steps.append(
                "Add package.json lint/test scripts, then rerun "
                "python3 -m vibebench init --profile node --force"
            )
        elif "build" in scripts:
            steps.append(
                "Build script detected; add npm run build to your workflow if needed."
            )
    return steps


def write_init_json_output(path: Path, payload: dict[str, object]) -> Path:
    """Write init JSON output."""
    if path.exists() and path.is_dir():
        raise ConfigError(f"JSON output path is a directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def render_project_init_result(payload: dict[str, object]) -> None:
    """Render concise project init output."""
    status = str(payload["status"])
    console.print("VibeBench init")
    console.print(f"Status: {status}")
    console.print(f"Config path: {payload['config_path']}")
    console.print(f"Selected profile: {payload['selected_profile']}")
    stacks = payload.get("detected_stacks") or []
    reasons = payload.get("detection_reasons") or []
    console.print("Detected stacks: " + (", ".join(stacks) if stacks else "none"))
    if reasons:
        reason_text = ", ".join(str(reason) for reason in reasons)
        console.print("Detection reasons: " + reason_text)
    console.print(str(payload["message"]))
    if status == "blocked":
        console.print("Use --force only when overwriting is intentional.")
    console.print("Next steps:")
    for step in payload["next_steps"]:
        console.print(f"  {step}")


def config_status_text(config: dict[str, object]) -> str:
    """Return a concise config status label for human output."""
    if config.get("valid"):
        return "valid"
    if config.get("exists"):
        return "invalid"
    return "missing"


@app.command("preflight")
def preflight_command(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print preflight result as pure JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write preflight JSON to PATH."),
    ] = None,
    summary_output: Annotated[
        Path | None,
        typer.Option("--summary-output", help="Write preflight Markdown to PATH."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Exit non-zero when preflight is not ready for safe adoption.",
        ),
    ] = False,
    enforce_policy: Annotated[
        bool,
        typer.Option(
            "--enforce-policy",
            help="Evaluate preflight policy and fail on policy violations.",
        ),
    ] = False,
    require_ci_mode: Annotated[
        list[str] | None,
        typer.Option(
            "--require-ci-mode",
            help=(
                "Require detected VibeBench CI mode(s): default, adoption, or "
                "adoption-policy. Repeat the option to require multiple modes."
            ),
        ),
    ] = None,
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            help="Init/workflow profile: generic, python, node, fullstack, or auto.",
        ),
    ] = "auto",
) -> None:
    """Summarize safe read-only adoption readiness before enabling VibeBench."""
    root = project_root.resolve()
    try:
        normalized_required_ci_modes = normalize_required_ci_modes(
            require_ci_mode or [],
            source="--require-ci-mode",
        )
        payload = preflight_payload(
            root,
            profile=profile,
            strict=strict,
            enforce_policy=enforce_policy,
            required_ci_modes=normalized_required_ci_modes,
        )
        if json_output is not None:
            write_preflight_json(resolve_output_path(root, json_output), payload)
        if summary_output is not None:
            write_preflight_summary(resolve_output_path(root, summary_output), payload)
    except ConfigError as exc:
        if as_json:
            print(
                json.dumps(
                    {
                        "status": "failed",
                        "strict": strict,
                        "policy_enforced": enforce_policy,
                        "project_root": str(root),
                        "message": str(exc),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            err_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(preflight_json(payload))
    else:
        render_preflight_result(payload)
    if payload.get("strict_failed") or (
        enforce_policy and payload.get("policy_status") == "failed"
    ):
        raise typer.Exit(code=1)


def render_preflight_result(payload: dict[str, object]) -> None:
    """Render concise preflight output."""
    stacks = payload.get("detected_stacks") or []
    stack_text = ", ".join(str(stack) for stack in stacks) if stacks else "none"
    config = payload["config"]
    workflow_check = payload["workflow_check"]
    workflow_template = payload["workflow_template"]
    assert isinstance(config, dict)
    assert isinstance(workflow_check, dict)
    assert isinstance(workflow_template, dict)
    console.print("VibeBench preflight")
    console.print(f"Project root: {payload['project_root']}")
    console.print(f"Status: {payload['status']}")
    console.print(f"Strict: {format_bool(payload['strict'])}")
    if "policy_status" in payload:
        console.print(
            f"Policy: {payload['policy_status']} ({payload['policy_source']})"
        )
    console.print(f"Detected stacks: {stack_text}")
    console.print(
        f"Profile: {payload['requested_profile']} -> {payload['resolved_profile']}"
    )
    console.print(f"Config status: {config_status_text(config)}")
    console.print(f"Config message: {config['message']}")
    console.print(
        "Workflow status: "
        f"{workflow_check['status']} ({workflow_check['workflow_count']} discovered)"
    )
    required_modes = workflow_check.get("required_ci_modes") or []
    missing_required_modes = workflow_check.get("missing_required_ci_modes") or []
    if required_modes:
        console.print(
            "Required CI modes: "
            + ", ".join(str(mode) for mode in required_modes)
        )
        console.print(
            "Missing required CI modes: "
            + (
                ", ".join(str(mode) for mode in missing_required_modes)
                or "none"
            )
        )
    console.print(
        "Workflow template preview: "
        f"{workflow_template['output_path']} ({workflow_template['ci_mode']})"
    )
    console.print(str(payload["message"]))
    console.print("Recommendations:")
    for recommendation in payload.get("recommendations", []):
        console.print(f"  {recommendation}")
    console.print("Suggested commands:")
    for command in payload.get("commands", []):
        console.print(f"  {command}")
    if payload.get("strict_failed"):
        console.print("Strict mode: preflight is not ready for safe adoption.")


@app.command("onboard")
def onboard_command(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print onboarding plan as pure JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write onboarding plan JSON to PATH."),
    ] = None,
    summary_output: Annotated[
        Path | None,
        typer.Option("--summary-output", help="Write onboarding plan Markdown."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Exit non-zero when onboarding is not ready for immediate CI.",
        ),
    ] = False,
    enforce_policy: Annotated[
        bool,
        typer.Option(
            "--enforce-policy",
            help="Evaluate onboard policy and fail when it is violated.",
        ),
    ] = False,
) -> None:
    """Plan read-only VibeBench adoption steps for this project."""
    root = project_root.resolve()
    try:
        payload = onboard_payload(root, strict=strict, enforce_policy=enforce_policy)
        if json_output is not None:
            write_onboard_json(resolve_output_path(root, json_output), payload)
        if summary_output is not None:
            write_onboard_summary(resolve_output_path(root, summary_output), payload)
    except ConfigError as exc:
        if as_json:
            print(
                json.dumps(
                    {
                        "status": "failed",
                        "project_root": str(root),
                        "message": str(exc),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            err_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(onboard_json(payload))
    else:
        render_onboard_result(payload)
    if payload.get("strict_failed") or (
        payload.get("policy_enforced") and payload.get("policy_status") == "failed"
    ):
        raise typer.Exit(code=1)


def render_onboard_result(payload: dict[str, object]) -> None:
    """Render concise onboarding plan output."""
    stacks = payload.get("detected_stacks") or []
    reasons = payload.get("detection_reasons") or []
    stack_text = ", ".join(str(stack) for stack in stacks) if stacks else "none"
    console.print("VibeBench onboarding plan")
    console.print(f"Project root: {payload['project_root']}")
    console.print(f"Status: {payload['status']}")
    console.print(f"Detected stacks: {stack_text}")
    if reasons:
        console.print(
            "Detection reasons: " + ", ".join(str(reason) for reason in reasons)
        )
    console.print(f"Recommended init profile: {payload['recommended_profile']}")
    console.print(f"Project-scan readiness: {payload['scan_readiness']}")
    console.print(f"Config exists: {str(payload['config_exists']).lower()}")
    warnings = payload.get("warnings") or []
    if warnings:
        table = Table(title="Warnings")
        table.add_column("Warning")
        for warning in warnings:
            table.add_row(str(warning))
        console.print(table)
    policy_findings = payload.get("policy_findings") or []
    if "policy_status" in payload:
        console.print(f"Policy status: {payload['policy_status']}")
        console.print(f"Policy source: {payload['policy_source']}")
        console.print(f"Policy enforced: {str(payload['policy_enforced']).lower()}")
        if policy_findings:
            policy_table = Table(title="Policy Findings")
            policy_table.add_column("Severity")
            policy_table.add_column("Finding")
            policy_table.add_column("Rule")
            policy_table.add_column("Recommendation")
            for finding in policy_findings:
                policy_table.add_row(
                    str(finding["severity"]),
                    str(finding["title"]),
                    str(finding["rule"]),
                    str(finding["recommendation"]),
                )
            console.print(policy_table)
    console.print("Suggested commands:")
    for command in payload.get("suggested_commands", []):
        console.print(f"  {command}")
    if payload.get("strict_failed"):
        console.print("Strict mode: onboarding is not ready for immediate CI.")


@app.command("project-scan")
def project_scan_command(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print project scan result as pure JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write project scan JSON to PATH."),
    ] = None,
    summary_output: Annotated[
        Path | None,
        typer.Option("--summary-output", help="Write project scan Markdown to PATH."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Exit non-zero for invalid config or malformed package.json.",
        ),
    ] = False,
    enforce_policy: Annotated[
        bool,
        typer.Option(
            "--enforce-policy",
            help="Evaluate project-scan policy and fail when it is violated.",
        ),
    ] = False,
) -> None:
    """Inspect onboarding readiness without writing project artifacts."""
    root = project_root.resolve()
    try:
        payload = run_project_scan(root, strict=strict, enforce_policy=enforce_policy)
        if json_output is not None:
            write_project_scan_json(resolve_output_path(root, json_output), payload)
        if summary_output is not None:
            write_project_scan_summary(
                resolve_output_path(root, summary_output), payload
            )
    except ConfigError as exc:
        if as_json:
            print(
                json.dumps(
                    {
                        "status": "failed",
                        "project_root": str(root),
                        "message": str(exc),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            err_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        render_project_scan_result(payload)
    if payload.get("strict_failed") or (
        payload.get("policy_enforced") and payload.get("policy_status") == "failed"
    ):
        raise typer.Exit(code=1)


def render_project_scan_result(payload: dict[str, object]) -> None:
    """Render concise project scan output."""
    stacks = payload.get("detected_stacks") or []
    stack_text = ", ".join(str(stack) for stack in stacks) if stacks else "none"
    console.print("VibeBench project scan")
    console.print(f"Project root: {payload['project_root']}")
    console.print(f"Status: {payload['status']}")
    console.print(f"Recommended profile: {payload['recommended_profile']}")
    console.print(f"Detected stacks: {stack_text}")
    console.print(f"Config status: {payload['config_status']}")
    findings = payload.get("findings") or []
    if findings:
        table = Table(title="Findings")
        table.add_column("Severity")
        table.add_column("Finding")
        table.add_column("Recommendation")
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            table.add_row(
                str(finding.get("severity", "")),
                str(finding.get("title", "")),
                str(finding.get("recommendation", "")),
            )
        console.print(table)
    policy_findings = payload.get("policy_findings") or []
    if "policy_status" in payload:
        console.print(f"Policy status: {payload['policy_status']}")
        console.print(f"Policy source: {payload['policy_source']}")
        console.print(f"Policy enforced: {str(payload['policy_enforced']).lower()}")
        if policy_findings:
            policy_table = Table(title="Policy Findings")
            policy_table.add_column("Severity")
            policy_table.add_column("Finding")
            policy_table.add_column("Rule")
            policy_table.add_column("Recommendation")
            for finding in policy_findings:
                if not isinstance(finding, dict):
                    continue
                policy_table.add_row(
                    str(finding.get("severity", "")),
                    str(finding.get("title", "")),
                    str(finding.get("rule", "")),
                    str(finding.get("recommendation", "")),
                )
            console.print(policy_table)
    console.print("Next steps:")
    for step in payload.get("next_steps", []):
        console.print(f"  {step}")


@app.command("workflow-template")
def workflow_template_command(
    project_root: ProjectRootOption = Path("."),
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            help="Workflow profile: generic, python, node, fullstack, or auto.",
        ),
    ] = "auto",
    ci_mode: Annotated[
        str,
        typer.Option(
            "--ci-mode",
            help=(
                "CI command set: basic, default, adoption, adoption-policy, "
                "or strict."
            ),
        ),
    ] = "basic",
    install_command: Annotated[
        str,
        typer.Option(
            "--install-command",
            help="Install command to place in the generated workflow.",
        ),
    ] = DEFAULT_WORKFLOW_INSTALL_COMMAND,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview without writing the workflow file."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print workflow template result as pure JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write workflow template JSON to PATH."),
    ] = None,
    summary_output: Annotated[
        Path | None,
        typer.Option("--summary-output", help="Write workflow template Markdown."),
    ] = None,
    write: Annotated[
        bool,
        typer.Option("--write", help="Write the workflow file."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Workflow file path to preview or write."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Overwrite an existing workflow when using --write."
        ),
    ] = False,
) -> None:
    """Generate a safe GitHub Actions workflow template."""
    root = project_root.resolve()
    target = (
        resolve_output_path(root, output)
        if output is not None
        else root / WORKFLOW_RELATIVE_PATH
    )
    try:
        payload = workflow_template_payload(
            root,
            target,
            profile=profile,
            ci_mode=ci_mode,
            install_command=install_command,
            write=write,
            dry_run=dry_run,
            force=force,
        )
        if json_output is not None:
            write_workflow_template_json(
                resolve_output_path(root, json_output), payload
            )
        if summary_output is not None:
            write_workflow_template_summary(
                resolve_output_path(root, summary_output), payload
            )
    except ConfigError as exc:
        payload = workflow_template_error_payload(
            root,
            target,
            profile=profile,
            ci_mode=ci_mode,
            install_command=install_command,
            write=write,
            dry_run=dry_run,
            force=force,
            message=str(exc),
        )
        if json_output is not None:
            try:
                write_workflow_template_json(
                    resolve_output_path(root, json_output), payload
                )
            except ConfigError as output_exc:
                err_console.print(f"[red]{output_exc}[/]")
        if summary_output is not None:
            try:
                write_workflow_template_summary(
                    resolve_output_path(root, summary_output), payload
                )
            except ConfigError as output_exc:
                err_console.print(f"[red]{output_exc}[/]")
        if as_json:
            print(workflow_template_json(payload))
        else:
            err_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(workflow_template_json(payload))
    else:
        render_workflow_template_result(payload)


def render_workflow_template_result(payload: dict[str, object]) -> None:
    """Render concise workflow-template output."""
    console.print("VibeBench workflow template")
    console.print(f"Status: {payload['status']}")
    console.print(f"Target path: {payload['output_path']}")
    console.print(f"Profile: {payload['profile']} -> {payload['resolved_profile']}")
    console.print(f"CI mode: {payload['ci_mode']}")
    console.print(f"Would write: {format_bool(payload['would_write'])}")
    console.print(f"Workflow written: {format_bool(payload['workflow_written'])}")
    console.print(str(payload["message"]))
    warnings = payload.get("warnings") or []
    if warnings:
        table = Table(title="Warnings")
        table.add_column("Warning")
        for warning in warnings:
            table.add_row(str(warning))
        console.print(table)
    console.print("Commands included:")
    for command in payload.get("commands", []):
        console.print(f"  {command}")
    console.print("Workflow YAML preview:")
    console.print(str(payload["workflow_yaml"]))


@app.command("workflow-check")
def workflow_check_command(
    project_root: ProjectRootOption = Path("."),
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Workflow file to check."),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print workflow check as pure JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write workflow check JSON to PATH."),
    ] = None,
    summary_output: Annotated[
        Path | None,
        typer.Option("--summary-output", help="Write workflow check Markdown."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Fail on missing or risky workflow signals."),
    ] = False,
    check_all: Annotated[
        bool,
        typer.Option("--all", help="Check all likely workflow candidates."),
    ] = False,
    enforce_policy: Annotated[
        bool,
        typer.Option(
            "--enforce-policy",
            help="Evaluate workflow_check.policy and fail when it does not pass.",
        ),
    ] = False,
    require_ci_mode: Annotated[
        list[str] | None,
        typer.Option(
            "--require-ci-mode",
            help=(
                "Require detected VibeBench CI mode(s): default, adoption, or "
                "adoption-policy. Repeat the option to require multiple modes."
            ),
        ),
    ] = None,
) -> None:
    """Check existing GitHub Actions workflows for VibeBench readiness."""
    root = project_root.resolve()
    try:
        normalized_required_ci_modes = normalize_required_ci_modes(
            require_ci_mode or [],
            source="--require-ci-mode",
        )
        payload = workflow_check_payload(
            root,
            path=path,
            strict=strict,
            check_all=check_all,
            enforce_policy=enforce_policy,
            required_ci_modes=normalized_required_ci_modes,
        )
        if json_output is not None:
            write_workflow_check_json(resolve_output_path(root, json_output), payload)
        if summary_output is not None:
            write_workflow_check_summary(
                resolve_output_path(root, summary_output), payload
            )
    except ConfigError as exc:
        if as_json:
            print(
                workflow_check_json(
                    {
                        "status": "failed",
                        "strict": strict,
                        "workflow_path": None,
                        "discovered_paths": [],
                        "checks": [],
                        "findings": [],
                        "summary": {
                            "total": 0,
                            "passed": 0,
                            "warning": 0,
                            "failed": 1,
                        },
                        "detected_ci_modes": [],
                        "usable_for_vibebench_ci": False,
                        "safe_preview_only": True,
                        "message": str(exc),
                    }
                )
            )
        else:
            err_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(workflow_check_json(payload))
    else:
        render_workflow_check_result(payload)
    if payload["status"] == "failed":
        raise typer.Exit(code=1)


def render_workflow_check_result(payload: dict[str, object]) -> None:
    """Render concise workflow-check output."""
    console.print("VibeBench workflow check")
    console.print(f"Status: {payload['status']}")
    console.print(f"Workflow path: {payload['workflow_path']}")
    console.print(f"Strict: {format_bool(payload['strict'])}")
    detected_modes = payload.get("detected_ci_modes") or []
    console.print(
        "Detected CI modes: "
        + (", ".join(str(mode) for mode in detected_modes) or "none")
    )
    required_modes = payload.get("required_ci_modes") or []
    missing_required_modes = payload.get("missing_required_ci_modes") or []
    if required_modes:
        console.print(
            "Required CI modes: "
            + ", ".join(str(mode) for mode in required_modes)
            + " (missing: "
            + (", ".join(str(mode) for mode in missing_required_modes) or "none")
            + ")"
        )
    if payload.get("policy_evaluated"):
        console.print(
            f"Policy: {payload['policy_status']} ({payload['policy_source']})"
        )
        effective_policy = payload.get("effective_policy") or {}
        if effective_policy.get("required_ci_modes"):
            console.print(
                "Policy required CI modes: "
                + ", ".join(
                    str(mode) for mode in effective_policy["required_ci_modes"]
                )
            )
    summary = payload["summary"]
    if isinstance(summary, dict):
        console.print(
            "Summary: "
            f"{summary['passed']} passed, "
            f"{summary['warning']} warnings, "
            f"{summary['failed']} failed"
        )
    findings = payload.get("findings") or []
    if findings:
        table = Table(title="Findings")
        table.add_column("Severity")
        table.add_column("Finding")
        table.add_column("Advice")
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            table.add_row(
                str(finding.get("severity", "")),
                str(finding.get("title", "")),
                str(finding.get("advice", "")),
            )
        console.print(table)
    console.print(str(payload["message"]))


@app.command("config")
def config_command(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print effective configuration as JSON."),
    ] = False,
    validate_only: Annotated[
        bool,
        typer.Option("--validate", help="Only validate config and print a result."),
    ] = False,
    show: Annotated[
        bool,
        typer.Option("--show", help="Show the active config file summary."),
    ] = False,
    check_config: Annotated[
        bool,
        typer.Option("--check", help="Run config consistency checks."),
    ] = False,
    advice: Annotated[
        bool,
        typer.Option("--advice", help="Show actionable config check advice."),
    ] = False,
    write_json: Annotated[
        Path | None,
        typer.Option("--write-json", help="Write config check JSON to PATH."),
    ] = None,
    write_summary: Annotated[
        Path | None,
        typer.Option("--write-summary", help="Write config check Markdown to PATH."),
    ] = None,
    show_source: Annotated[
        bool,
        typer.Option("--show-source", help="Show config file/default sources."),
    ] = False,
    show_path: Annotated[
        bool,
        typer.Option("--path", help="Print the expected config file path."),
    ] = False,
    example: Annotated[
        bool,
        typer.Option("--example", help="Print a starter config example."),
    ] = False,
    write_example: Annotated[
        Path | None,
        typer.Option("--write-example", help="Write a starter config example to PATH."),
    ] = None,
    init_config: Annotated[
        bool,
        typer.Option(
            "--init",
            help="Create .vibebench/config.yaml from the starter example.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite .vibebench/config.yaml when using --init.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview --init without writing files."),
    ] = False,
) -> None:
    """Inspect and validate the effective VibeBench configuration."""
    root = project_root.resolve()
    target = config_file(root)
    if show_path:
        payload = config_path_payload(root, target)
        if as_json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(payload["config_path"])
        return

    if init_config:
        if dry_run:
            payload = config_init_plan_payload(root, target, force=force)
            if as_json:
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                render_config_init_plan(payload)
            return

        example_yaml = config_example_yaml()
        try:
            written_path, overwritten = write_config_init(
                target,
                example_yaml,
                force=force,
            )
        except ConfigError as exc:
            target_console = err_console if as_json else console
            target_console.print(str(exc))
            raise typer.Exit(code=1) from exc
        action = "overwritten" if overwritten else "written"
        print(f"Config {action}: {written_path}")
        return

    if example or write_example is not None:
        example_yaml = config_example_yaml()
        if write_example is not None:
            try:
                written_path = write_config_example(
                    resolve_output_path(root, write_example),
                    example_yaml,
                )
            except ConfigError as exc:
                target_console = err_console if as_json else console
                target_console.print(str(exc))
                raise typer.Exit(code=1) from exc
            if not example:
                print(f"Config example written: {written_path}")
                return
        print(example_yaml, end="")
        return

    try:
        if (show or check_config) and not target.exists():
            raise ConfigError(
                f"No VibeBench config found at {target}.\n"
                'Run "vibebench init" to create one.'
            )
        result = load_effective_config(target)
    except ConfigError as exc:
        output_console = err_console if (show or check_config) and as_json else console
        output_console.print(f"[red]{exc}[/]")
        if check_config and advice and not as_json:
            render_config_error_advice(exc)
        raise typer.Exit(code=1) from exc

    if check_config:
        checks = config_consistency_checks(result, include_advice=advice)
        payload = config_check_payload(result, checks, include_advice=advice)
        try:
            written_json = (
                write_config_check_json(
                    result,
                    checks,
                    resolve_output_path(root, write_json),
                    include_advice=advice,
                )
                if write_json is not None
                else None
            )
            written_summary = (
                write_config_check_summary(
                    result,
                    checks,
                    resolve_output_path(root, write_summary),
                    include_advice=advice,
                )
                if write_summary is not None
                else None
            )
        except ConfigError as exc:
            output_console = err_console if as_json else console
            output_console.print(f"[red]{exc}[/]")
            raise typer.Exit(code=1) from exc

        if as_json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            render_config_check_summary(
                result,
                checks,
                include_advice=advice,
                written_json=written_json,
                written_summary=written_summary,
            )
        if payload["overall_status"] == "failed":
            raise typer.Exit(code=1)
        return

    if validate_only:
        source = result.config_path if result.config_exists else "built-in defaults"
        console.print(f"[green]VibeBench config is valid.[/] Source: {source}")
        return

    if show:
        payload = config_show_payload(result)
    else:
        payload = effective_config_payload(result)
    if show_source:
        payload["sources"] = result.sources

    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    render_config_summary(result, show_source=show_source)


def config_path_payload(project_root: Path, path: Path) -> dict[str, object]:
    """Return JSON-safe config path inspection output."""
    return {
        "project_root": str(project_root),
        "config_path": str(path),
        "exists": path.exists(),
    }


def config_init_plan_payload(
    project_root: Path,
    path: Path,
    *,
    force: bool,
) -> dict[str, object]:
    """Return JSON-safe config init dry-run output."""
    exists = path.exists()
    would_write = (not exists or force) and not path.is_dir()
    return {
        "status": "planned" if would_write else "blocked",
        "project_root": str(project_root),
        "config_path": str(path),
        "exists": exists,
        "would_write": would_write,
        "force": force,
        "dry_run": True,
    }


def render_config_init_plan(payload: dict[str, object]) -> None:
    """Render a concise config init dry-run plan."""
    print("Config init dry run")
    print("Project root: " + str(payload["project_root"]))
    print("Config path: " + str(payload["config_path"]))
    print("Config exists: " + format_bool(payload["exists"]))
    print("Would write: " + format_bool(payload["would_write"]))
    print("Force: " + format_bool(payload["force"]))
    if payload["would_write"]:
        print("Dry run only: no files or directories were written.")
    else:
        print("Normal init would not overwrite without --force.")


def write_config_init(
    output_path: Path,
    content: str,
    *,
    force: bool,
) -> tuple[Path, bool]:
    """Initialize .vibebench/config.yaml from the starter example."""
    if output_path.exists() and output_path.is_dir():
        raise ConfigError(f"Config path is a directory: {output_path}")
    if output_path.exists() and not force:
        raise ConfigError(
            f"Config already exists at {output_path}. "
            "Use --force to overwrite it intentionally."
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    overwritten = output_path.exists()
    output_path.write_text(content, encoding="utf-8")
    return output_path, overwritten


def write_config_example(output_path: Path, content: str) -> Path:
    """Write a starter config example to a requested path."""
    if output_path.exists() and output_path.is_dir():
        raise ConfigError(f"Config example output path is a directory: {output_path}")
    if not output_path.parent.exists():
        raise ConfigError(
            f"Config example output parent does not exist: {output_path.parent}"
        )
    output_path.write_text(content, encoding="utf-8")
    return output_path


def config_show_payload(result: EffectiveConfigResult) -> dict[str, object]:
    """Return JSON-safe active config inspection output."""
    payload = effective_config_payload(result)
    return {
        "config_path": str(result.config_path),
        "project": payload["project"],
        "commands": payload["checks"],
        "gate": payload["gate"],
        "risk": payload["risk"],
        "regression": payload["regression"],
        "metrics_diff": payload["metrics_diff"],
        "project_scan": payload["project_scan"],
        "onboard": payload["onboard"],
        "workflow_check": payload["workflow_check"],
        "preflight": payload["preflight"],
    }


def render_config_summary(
    result: EffectiveConfigResult,
    *,
    show_source: bool,
) -> None:
    """Render the effective VibeBench config as Rich tables."""
    source = str(result.config_path) if result.config_exists else "built-in defaults"
    console.print(f"[bold]VibeBench config[/] ({source})")

    payload = effective_config_payload(result)
    for section_name in [
        "project",
        "checks",
        "gate",
        "risk",
        "regression",
        "metrics_diff",
        "project_scan",
        "onboard",
        "workflow_check",
        "preflight",
    ]:
        table = Table(title=section_name)
        table.add_column("Key")
        table.add_column("Value")
        if show_source:
            table.add_column("Source")
        section = payload[section_name]
        for key, value in section.items():
            row = [key, format_config_value(value)]
            if show_source:
                row.append(result.sources[section_name])
            table.add_row(*row)
        console.print(table)


def format_config_value(value: object) -> str:
    """Format config values for terminal display."""
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


def format_bool(value: object) -> str:
    """Format booleans for concise human output."""
    return "yes" if value else "no"


def render_config_check_summary(
    result: EffectiveConfigResult,
    checks: list[dict[str, str]],
    *,
    include_advice: bool = False,
    written_json: Path | None = None,
    written_summary: Path | None = None,
) -> None:
    """Render config consistency checks as a Rich table."""
    payload = config_check_payload(result, checks, include_advice=include_advice)
    console.print(f"[bold]VibeBench config check[/] ({result.config_path})")
    console.print(f"Overall status: {payload['overall_status']}")
    table = Table(title="Config consistency")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")
    for check in checks:
        style = "green" if check["status"] == "passed" else "red"
        table.add_row(check["name"], f"[{style}]{check['status']}[/]", check["message"])
    console.print(table)
    if include_advice:
        advice_rows = [check for check in checks if "advice" in check]
        if advice_rows:
            advice_table = Table(title="Advice")
            advice_table.add_column("Check")
            advice_table.add_column("Advice")
            for check in advice_rows:
                advice_table.add_row(check["name"], check["advice"])
            console.print(advice_table)
    if written_json is not None:
        console.print(f"Config check JSON: {written_json}")
    if written_summary is not None:
        console.print(f"Config check summary: {written_summary}")


def render_config_error_advice(exc: ConfigError) -> None:
    """Render advice for config errors that happen before consistency checks run."""
    console.print(f"Advice: {advice_for_config_error(exc)}")


def resolve_output_path(project_root: Path, output_path: Path) -> Path:
    """Resolve a CLI output path relative to the project root."""
    if output_path.is_absolute():
        return output_path.resolve()
    return (project_root / output_path).resolve()


@app.command()
def check(project_root: ProjectRootOption = Path(".")) -> None:
    """Run configured checks and write VibeBench metrics."""
    root = project_root.resolve()
    target = config_file(root)

    try:
        config = load_config(target)
    except ConfigError as exc:
        if not target.exists():
            console.print(
                "[red]No .vibebench/config.yaml found. Run 'vibebench init' first.[/]"
            )
        else:
            console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    result = run_checks(config, root)
    render_check_summary(result)

    if result.overall_status == "failed":
        raise typer.Exit(code=1)


@app.command()
def report(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to render.",
        ),
    ] = None,
) -> None:
    """Generate a static HTML report for a VibeBench run."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()

    try:
        report_path = generate_report(root, selected_run_dir)
        metrics = load_metrics(report_path.parent.parent)
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    recommendation = recommendation_for(metrics)
    console.print("[green]Report generated.[/]")
    console.print(f"Run directory: {report_path.parent.parent}")
    console.print(f"Report path: {report_path}")
    console.print(f"Recommendation: {recommendation}")


@app.command("pr-comment")
def pr_comment(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to summarize.",
        ),
    ] = None,
    post: Annotated[
        bool,
        typer.Option("--post", help="Post or update the comment on a GitHub PR."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview posting without network calls."),
    ] = False,
    body_file: Annotated[
        Path | None,
        typer.Option("--body-file", help="Markdown file to post as the PR comment."),
    ] = None,
    repo: Annotated[
        str | None,
        typer.Option("--repo", help="GitHub repository as OWNER/REPO."),
    ] = None,
    pr_number: Annotated[
        int | None,
        typer.Option("--pr-number", help="GitHub pull request number."),
    ] = None,
    comment_marker: Annotated[
        str,
        typer.Option("--comment-marker", help="Hidden marker for comment updates."),
    ] = DEFAULT_COMMENT_MARKER,
    token_env: Annotated[
        str,
        typer.Option("--token-env", help="Environment variable containing token."),
    ] = DEFAULT_TOKEN_ENV,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print posting result as JSON."),
    ] = False,
    fail_on_error: Annotated[
        bool,
        typer.Option(
            "--fail-on-error/--no-fail-on-error",
            help="Exit nonzero when posting fails.",
        ),
    ] = True,
) -> None:
    """Generate or post a PR-ready Markdown summary for a VibeBench run."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()
    selected_body_file = None
    if body_file:
        selected_body_file = (
            body_file if body_file.is_absolute() else root / body_file
        ).resolve()

    if post:
        try:
            result = post_pr_comment(
                root,
                run_dir=selected_run_dir,
                body_file=selected_body_file,
                repo=repo,
                pr_number=pr_number,
                marker=comment_marker,
                token_env=token_env,
                dry_run=dry_run,
                fail_on_error=fail_on_error,
            )
        except ReportError as exc:
            if as_json:
                err_console.print(str(exc))
            else:
                console.print(f"[red]{exc}[/]")
            raise typer.Exit(code=1) from exc

        if as_json:
            print(json.dumps(pr_comment_post_json(result), indent=2))
        else:
            render_pr_comment_post_result(result)
        if result.status == "failed" and fail_on_error:
            raise typer.Exit(code=1)
        return

    try:
        comment_path = generate_pr_comment(root, selected_run_dir)
        metrics = load_metrics(comment_path.parent)
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    recommendation = recommendation_for(metrics)
    console.print("[green]PR comment generated.[/]")
    console.print(f"Run directory: {comment_path.parent}")
    console.print(f"Output path: {comment_path}")
    console.print(f"Recommendation: {recommendation}")


def render_pr_comment_post_result(result: PrCommentPostResult) -> None:
    """Render the GitHub PR comment posting result."""
    color = {
        "created": "green",
        "updated": "green",
        "would-post": "yellow",
        "skipped": "yellow",
        "failed": "red",
    }.get(result.status, "white")
    console.print(f"[{color}]PR comment posting: {result.status}[/]")
    console.print(f"Action: {result.action}")
    if result.repo:
        console.print(f"Repository: {result.repo}")
    if result.pr_number is not None:
        console.print(f"PR number: {result.pr_number}")
    if result.body_file:
        console.print(f"Body file: {result.body_file}")
    if result.comment_url:
        console.print(f"Comment URL: {result.comment_url}")
    console.print(f"Message: {result.message}")


@app.command("gh-summary")
def gh_summary(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to summarize.",
        ),
    ] = None,
) -> None:
    """Write a GitHub Actions step summary for a VibeBench run."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()

    try:
        summary_path = generate_github_summary(root, selected_run_dir)
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    console.print("[green]GitHub step summary written.[/]")
    console.print(f"Output path: {summary_path}")


@app.command()
def explain(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to explain.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Custom Markdown output path."),
    ] = None,
    no_write: Annotated[
        bool,
        typer.Option(
            "--no-write",
            help="Print explanation without writing explain.md.",
        ),
    ] = False,
) -> None:
    """Explain a VibeBench run in human-readable Markdown."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()

    try:
        result = generate_explanation(
            root,
            selected_run_dir,
            selected_output,
            write=not no_write,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_explain_summary(result, write=not no_write)


@app.command()
def bundle(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to bundle.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Custom zip output path."),
    ] = None,
    include_report_assets: Annotated[
        bool,
        typer.Option(
            "--include-report-assets",
            help="Include the whole report directory recursively.",
        ),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Fail if any standard artifact is missing."),
    ] = False,
) -> None:
    """Package a VibeBench run's artifacts into a zip file."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()

    try:
        result = create_bundle(
            root,
            selected_run_dir,
            selected_output,
            include_report_assets=include_report_assets,
            strict=strict,
        )
        if (
            selected_output is None
            and result.output_path == result.run_dir / "vibebench-bundle.zip"
            and result.run_dir.joinpath("manifest.json").exists()
        ):
            generate_manifest(root, result.run_dir)
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_bundle_summary(result)


@app.command()
def badge(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to badge.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write badge output to this file."),
    ] = None,
    badge_format: Annotated[
        str,
        typer.Option("--format", help="Badge format: json, markdown, or url."),
    ] = "json",
    label: Annotated[
        str,
        typer.Option("--label", help="Badge label text."),
    ] = DEFAULT_BADGE_LABEL,
) -> None:
    """Generate a Shields.io-compatible badge artifact."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()

    try:
        result = generate_badge(
            root,
            selected_run_dir,
            selected_output,
            label=label,
            badge_format=badge_format,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_badge_summary(result)


@app.command("status-block")
def status_block(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to summarize.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write status block to this file."),
    ] = None,
    readme: Annotated[
        list[Path] | None,
        typer.Option(
            "--readme",
            help="README file containing VibeBench status markers.",
        ),
    ] = None,
    write_readme: Annotated[
        bool,
        typer.Option("--write-readme", help="Update README content between markers."),
    ] = False,
    check_readme: Annotated[
        bool,
        typer.Option("--check-readme", help="Check README marker content is current."),
    ] = False,
    title: Annotated[
        str,
        typer.Option("--title", help="Markdown heading text."),
    ] = DEFAULT_STATUS_TITLE,
    include_badge: Annotated[
        bool,
        typer.Option("--include-badge/--no-include-badge"),
    ] = True,
    include_artifacts: Annotated[
        bool,
        typer.Option("--include-artifacts/--no-include-artifacts"),
    ] = True,
) -> None:
    """Generate or update a README status block."""
    if write_readme and check_readme:
        console.print(
            "[red]--write-readme and --check-readme cannot be used together.[/]"
        )
        raise typer.Exit(code=1)
    readme_paths = readme or []
    if (write_readme or check_readme) and not readme_paths:
        console.print(
            "[red]--readme is required with --write-readme or --check-readme.[/]"
        )
        raise typer.Exit(code=1)

    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = run_dir if run_dir.is_absolute() else root / run_dir
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()

    try:
        result = generate_status_block(
            root,
            selected_run_dir,
            selected_output,
            title=title,
            include_badge=include_badge,
            include_artifacts=include_artifacts,
        )
        readme_results = update_status_block_readmes(
            root,
            readme_paths,
            result.content,
            write=write_readme,
            check=check_readme,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_status_block_summary(result)
    if readme_results:
        render_status_block_readme_summary(readme_results, check=check_readme)
        if check_readme and not all(item.current for item in readme_results):
            raise typer.Exit(code=1)


@app.command("trend")
def trend_command(
    project_root: ProjectRootOption = Path("."),
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum number of recent valid runs to show."),
    ] = 10,
    runs_dir: Annotated[
        Path | None,
        typer.Option("--runs-dir", help="Directory containing VibeBench run dirs."),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print trend summary as JSON."),
    ] = False,
    write_summary: Annotated[
        bool,
        typer.Option("--write-summary", help="Write trend.md Markdown summary."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write trend summary Markdown to this path."),
    ] = None,
    write_json: Annotated[
        bool,
        typer.Option("--write-json", help="Write trend.json machine-readable data."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write trend JSON to this path."),
    ] = None,
) -> None:
    """Show quality trend across recent VibeBench runs."""
    root = project_root.resolve()
    selected_runs_dir = None
    if runs_dir:
        selected_runs_dir = (
            runs_dir if runs_dir.is_absolute() else root / runs_dir
        ).resolve()
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()
    selected_json_output = None
    if json_output:
        selected_json_output = (
            json_output if json_output.is_absolute() else root / json_output
        ).resolve()

    try:
        result = analyze_trend(root, selected_runs_dir, limit=limit)
        summary_path = (
            write_trend_summary(result, selected_output) if write_summary else None
        )
        json_path = (
            write_trend_json(result, selected_json_output) if write_json else None
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(json.dumps(trend_json(result), indent=2))
        return

    render_trend_summary(result)
    if summary_path is not None:
        console.print(f"Trend summary: {summary_path}")
    if json_path is not None:
        console.print(f"Trend JSON: {json_path}")


@app.command("latest")
def latest_command(
    project_root: ProjectRootOption = Path("."),
    runs_dir: Annotated[
        Path | None,
        typer.Option("--runs-dir", help="Directory containing VibeBench run dirs."),
    ] = None,
    artifact: Annotated[
        str | None,
        typer.Option("--artifact", help="Show one known artifact by alias."),
    ] = None,
    path_only: Annotated[
        bool,
        typer.Option("--path-only", help="Print only the selected artifact path."),
    ] = False,
    all_paths: Annotated[
        bool,
        typer.Option("--all-paths", help="Print all available artifact paths."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print latest run details as JSON."),
    ] = False,
) -> None:
    """Locate the latest valid VibeBench run and artifacts."""
    root = project_root.resolve()
    selected_runs_dir = None
    if runs_dir:
        selected_runs_dir = (
            runs_dir if runs_dir.is_absolute() else root / runs_dir
        ).resolve()

    if all_paths and artifact is not None:
        console.print("[red]--all-paths cannot be combined with --artifact.[/]")
        raise typer.Exit(code=1)
    if all_paths and path_only:
        console.print("[red]--all-paths cannot be combined with --path-only.[/]")
        raise typer.Exit(code=1)
    if path_only and artifact is None:
        console.print("[red]--path-only requires --artifact NAME.[/]")
        raise typer.Exit(code=1)

    try:
        result = get_latest_run(root, selected_runs_dir)
        selected_artifact = select_artifact(result, artifact) if artifact else None
        if path_only:
            if selected_artifact is None:
                raise ReportError("--path-only requires --artifact NAME.")
            if not selected_artifact.available:
                raise ReportError(
                    f"Artifact '{artifact}' is unavailable for run {result.run_id}."
                )
            print(selected_artifact.display_path.as_posix())
            return
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if all_paths:
        if as_json:
            print(json.dumps(latest_paths_json(result), indent=2))
            return
        render_latest_paths(result)
        return

    if as_json:
        print(json.dumps(latest_json(result, selected_artifact), indent=2))
        return

    render_latest_summary(result, selected_artifact)


@app.command("demo")
def demo_command(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print local showcase demo details as JSON."),
    ] = False,
    copy_to: Annotated[
        Path | None,
        typer.Option("--copy-to", help="Copy the sample artifact pack to PATH."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Replace conflicting files under --copy-to."),
    ] = False,
) -> None:
    """Show or copy the checked-in local showcase artifact pack."""
    root = project_root.resolve()
    copy_result = None
    try:
        if copy_to is not None:
            copy_result = copy_sample_pack(root, copy_to, force=force)
    except DemoError as exc:
        if as_json:
            payload = demo_payload(root, conflicts=[str(exc)])
            payload["status"] = "error"
            print(json.dumps(payload, indent=2))
            raise typer.Exit(code=1) from exc
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    payload = demo_payload(root, copy_result=copy_result)
    if as_json:
        print(json.dumps(payload, indent=2))
        if copy_result is not None and copy_result.conflicts:
            raise typer.Exit(code=1)
        return

    render_demo_summary(payload)
    if copy_result is not None and copy_result.conflicts:
        raise typer.Exit(code=1)


@app.command("proof")
def proof_command(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print local proof packet details as JSON."),
    ] = False,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Write proof packet files under PATH."),
    ] = None,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write proof JSON to PATH."),
    ] = None,
    summary_output: Annotated[
        Path | None,
        typer.Option("--summary-output", help="Write proof Markdown to PATH."),
    ] = None,
    html_output: Annotated[
        Path | None,
        typer.Option("--html-output", help="Write self-contained proof HTML to PATH."),
    ] = None,
    create_zip: Annotated[
        bool,
        typer.Option("--zip", help="Write proof.zip with relative packet files."),
    ] = False,
    zip_output: Annotated[
        Path | None,
        typer.Option(
            "--zip-output",
            help="Write proof archive to PATH; implies --zip when --output-dir is set.",
        ),
    ] = None,
    verify: Annotated[
        Path | None,
        typer.Option("--verify", help="Verify a proof packet directory or proof.zip."),
    ] = None,
) -> None:
    """Generate or verify a local proof packet for VibeBench Arena."""
    root = project_root.resolve()

    if verify is not None:
        result = verify_proof_packet(verify)
        if as_json:
            print(verification_json(result))
        else:
            render_proof_verification(result)
        if not result["verified"]:
            raise typer.Exit(code=1)
        return

    payload = proof_payload(root)
    try:
        written = write_proof_packet(
            payload,
            project_root=root,
            output_dir=output_dir,
            json_output=json_output,
            summary_output=summary_output,
            html_output=html_output,
            create_zip=create_zip,
            zip_output=zip_output,
        )
    except ProofError as exc:
        if as_json:
            error_payload = dict(payload)
            error_payload["status"] = "error"
            error_payload["message"] = str(exc)
            print(proof_json(error_payload))
        else:
            console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(proof_json(payload))
        return

    render_proof_summary(payload)
    if "summary" in written:
        console.print(f"Proof Markdown: {written['summary']}")
    if "json" in written:
        console.print(f"Proof JSON: {written['json']}")
    if "html" in written:
        console.print(f"Proof HTML: {written['html']}")
    if "manifest" in written:
        console.print(f"Proof manifest: {written['manifest']}")
    if "zip" in written:
        console.print(f"Proof archive: {written['zip']}")


@app.command("site-check")
def site_check_command(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print static site readiness as JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write static site readiness JSON to PATH."),
    ] = None,
    root: Annotated[
        Path,
        typer.Option("--root", help="Static site root to check."),
    ] = Path("docs"),
) -> None:
    """Check the GitHub Pages-ready static docs site."""
    project = project_root.resolve()
    selected_root = root if root.is_absolute() else project / root
    root_label = root.as_posix()
    payload = run_site_check(selected_root, root_label=root_label)

    selected_json_output = None
    if json_output is not None:
        selected_json_output = (
            json_output if json_output.is_absolute() else project / json_output
        )
        write_site_check_json(payload, selected_json_output)

    if as_json:
        print(site_check_json(payload))
    else:
        render_site_check_summary(payload)
        if selected_json_output is not None:
            console.print(f"Site check JSON: {selected_json_output}")

    if payload["status"] != "passed":
        raise typer.Exit(code=1)


@app.command("site-preview")
def site_preview_command(
    project_root: ProjectRootOption = Path("."),
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Write static site preview files to PATH."),
    ] = None,
    create_zip: Annotated[
        bool,
        typer.Option("--zip", help="Write site-preview.zip with relative files."),
    ] = False,
    zip_output: Annotated[
        Path | None,
        typer.Option("--zip-output", help="Write site preview archive to PATH."),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print static site preview details as JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write static site preview JSON to PATH."),
    ] = None,
    verify: Annotated[
        Path | None,
        typer.Option("--verify", help="Verify a site preview directory or zip."),
    ] = None,
    root: Annotated[
        Path,
        typer.Option("--root", help="Static site root to preview."),
    ] = Path("docs"),
) -> None:
    """Plan, write, zip, or verify a static site preview packet."""
    project = project_root.resolve()
    selected_root = root if root.is_absolute() else project / root
    root_label = root.as_posix()

    if verify is not None:
        result = verify_site_preview(verify)
        selected_json_output = None
        if json_output is not None:
            selected_json_output = (
                json_output if json_output.is_absolute() else project / json_output
            )
            write_site_preview_json(result, selected_json_output)
        if as_json:
            print(site_preview_verification_json(result))
        else:
            render_site_preview_verification(result)
            if selected_json_output is not None:
                console.print(f"Site preview JSON: {selected_json_output}")
        if not result["verified"]:
            raise typer.Exit(code=1)
        return

    selected_output_dir = None
    if output_dir is not None:
        selected_output_dir = (
            output_dir if output_dir.is_absolute() else project / output_dir
        )
    selected_zip_output = None
    if zip_output is not None:
        selected_zip_output = (
            zip_output if zip_output.is_absolute() else project / zip_output
        )

    try:
        if selected_output_dir is not None:
            payload = write_site_preview(
                project_root=project,
                site_root=selected_root,
                root_label=root_label,
                output_dir=selected_output_dir,
                create_zip=create_zip,
                zip_output=selected_zip_output,
            )
        elif selected_zip_output is not None:
            payload = write_zip_only_preview(
                project_root=project,
                site_root=selected_root,
                root_label=root_label,
                zip_output=selected_zip_output,
            )
        else:
            payload = site_preview_payload(
                project,
                site_root=selected_root,
                root_label=root_label,
            )
            if create_zip:
                raise SitePreviewError("--zip requires --output-dir or --zip-output.")
            if payload["status"] != "ready":
                raise SitePreviewError("Static site readiness check failed.")
    except SitePreviewError as exc:
        payload = site_preview_payload(
            project,
            site_root=selected_root,
            root_label=root_label,
            output_dir=selected_output_dir,
            zip_output=selected_zip_output,
        )
        payload["status"] = "failed"
        payload["message"] = str(exc)
        if as_json:
            print(site_preview_json(payload))
        else:
            console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if json_output is not None:
        selected_json_output = (
            json_output if json_output.is_absolute() else project / json_output
        )
        write_site_preview_json(payload, selected_json_output)
    else:
        selected_json_output = None

    if as_json:
        print(site_preview_json(payload))
    else:
        render_site_preview_summary(payload)
        if selected_json_output is not None:
            console.print(f"Site preview JSON: {selected_json_output}")

    if payload["status"] == "failed":
        raise typer.Exit(code=1)


@app.command("evidence-room")
def evidence_room_command(
    project_root: ProjectRootOption = Path("."),
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Write evidence room files to PATH."),
    ] = None,
    create_zip: Annotated[
        bool,
        typer.Option("--zip", help="Write evidence-room.zip with relative files."),
    ] = False,
    zip_output: Annotated[
        Path | None,
        typer.Option("--zip-output", help="Write evidence room archive to PATH."),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print evidence room details as JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write evidence room JSON to PATH."),
    ] = None,
    verify: Annotated[
        Path | None,
        typer.Option("--verify", help="Verify an evidence room directory or zip."),
    ] = None,
    root: Annotated[
        Path,
        typer.Option("--root", help="Static site root to include."),
    ] = Path("docs"),
) -> None:
    """Plan, write, zip, or verify a combined evidence room package."""
    project = project_root.resolve()
    selected_root = root if root.is_absolute() else project / root
    root_label = root.as_posix()

    if verify is not None:
        result = verify_evidence_room(verify)
        selected_json_output = None
        if json_output is not None:
            selected_json_output = (
                json_output if json_output.is_absolute() else project / json_output
            )
            write_evidence_room_json(result, selected_json_output)
        if as_json:
            print(evidence_room_verification_json(result))
        else:
            render_evidence_room_verification(result)
            if selected_json_output is not None:
                console.print(f"Evidence room JSON: {selected_json_output}")
        if not result["verified"]:
            raise typer.Exit(code=1)
        return

    selected_output_dir = None
    if output_dir is not None:
        selected_output_dir = (
            output_dir if output_dir.is_absolute() else project / output_dir
        )
    selected_zip_output = None
    if zip_output is not None:
        selected_zip_output = (
            zip_output if zip_output.is_absolute() else project / zip_output
        )

    try:
        if selected_output_dir is not None:
            payload = write_evidence_room(
                project_root=project,
                site_root=selected_root,
                root_label=root_label,
                output_dir=selected_output_dir,
                create_zip=create_zip,
                zip_output=selected_zip_output,
            )
        elif selected_zip_output is not None:
            payload = write_zip_only_evidence_room(
                project_root=project,
                site_root=selected_root,
                root_label=root_label,
                zip_output=selected_zip_output,
            )
        else:
            payload = evidence_room_payload(root_label=root_label)
            if create_zip:
                raise EvidenceRoomError("--zip requires --output-dir or --zip-output.")
    except EvidenceRoomError as exc:
        payload = evidence_room_payload(
            root_label=root_label,
            output_dir=selected_output_dir,
            zip_output=selected_zip_output,
            status="failed",
            warnings=[str(exc)],
        )
        if as_json:
            print(evidence_room_json(payload))
        else:
            console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if json_output is not None:
        selected_json_output = (
            json_output if json_output.is_absolute() else project / json_output
        )
        write_evidence_room_json(payload, selected_json_output)
    else:
        selected_json_output = None

    if as_json:
        print(evidence_room_json(payload))
    else:
        render_evidence_room_summary(payload)
        if selected_json_output is not None:
            console.print(f"Evidence room JSON: {selected_json_output}")


@app.command("metrics-check")
def metrics_check_command(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option("--run-dir", help="Specific VibeBench run directory to check."),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print metrics-check result as pure JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write metrics-check JSON to PATH."),
    ] = None,
    summary_output: Annotated[
        Path | None,
        typer.Option("--summary-output", help="Write metrics-check Markdown."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Fail when metrics-check warnings exist."),
    ] = False,
) -> None:
    """Check that a run metrics.json satisfies regression/baseline contracts."""
    root = project_root.resolve()
    selected_run_dir = resolve_optional_output_path(root, run_dir)
    selected_json_output = resolve_optional_output_path(root, json_output)
    selected_summary_output = resolve_optional_output_path(root, summary_output)
    try:
        result = run_metrics_check(
            root,
            run_dir=selected_run_dir,
            strict=strict,
            json_output=selected_json_output,
            summary_output=selected_summary_output,
        )
    except ReportError as exc:
        target_console = err_console if as_json else console
        target_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(metrics_check_json(result))
    else:
        render_metrics_check_summary(result)
        if result.json_path is not None:
            console.print(f"Metrics-check JSON: {result.json_path}")
        if result.summary_path is not None:
            console.print(f"Metrics-check Markdown: {result.summary_path}")

    if result.status == "failed":
        raise typer.Exit(code=1)


@app.command("metrics-diff")
def metrics_diff_command(
    project_root: ProjectRootOption = Path("."),
    runs_dir: Annotated[
        Path | None,
        typer.Option("--runs-dir", help="Custom runs directory to compare."),
    ] = None,
    baseline_run: Annotated[
        str | None,
        typer.Option("--baseline-run", help="Baseline run id or path."),
    ] = None,
    candidate_run: Annotated[
        str | None,
        typer.Option("--candidate-run", help="Candidate run id or path."),
    ] = None,
    baseline_label: Annotated[
        str | None,
        typer.Option("--baseline-label", help="Pinned baseline label to use."),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print metrics-diff result as pure JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write metrics-diff JSON to PATH."),
    ] = None,
    summary_output: Annotated[
        Path | None,
        typer.Option("--summary-output", help="Write metrics-diff Markdown."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Fail when no baseline metrics are available."),
    ] = False,
    include_unchanged: Annotated[
        bool,
        typer.Option("--include-unchanged", help="Include unchanged numeric metrics."),
    ] = False,
    top: Annotated[
        int | None,
        typer.Option("--top", help="Limit displayed changed metrics."),
    ] = None,
    enforce_policy: Annotated[
        bool,
        typer.Option(
            "--enforce-policy",
            help="Evaluate metrics-diff policy and fail on policy errors.",
        ),
    ] = False,
    allow_policy_failure: Annotated[
        bool,
        typer.Option(
            "--allow-policy-failure",
            help="Evaluate metrics-diff policy but keep it report-only.",
        ),
    ] = False,
) -> None:
    """Compare numeric metrics between baseline and candidate runs."""
    root = project_root.resolve()
    selected_runs_dir = resolve_optional_output_path(root, runs_dir)
    selected_json_output = resolve_optional_output_path(root, json_output)
    selected_summary_output = resolve_optional_output_path(root, summary_output)
    try:
        result = run_metrics_diff(
            root,
            runs_dir=selected_runs_dir,
            baseline_run=baseline_run,
            candidate_run=candidate_run,
            baseline_label=baseline_label,
            strict=strict,
            include_unchanged=include_unchanged,
            top=top,
            enforce_policy=enforce_policy,
            allow_policy_failure=allow_policy_failure,
            json_output=selected_json_output,
            summary_output=selected_summary_output,
        )
    except ReportError as exc:
        target_console = err_console if as_json else console
        target_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(metrics_diff_json(result))
    else:
        render_metrics_diff_summary(result)
        if result.json_path is not None:
            console.print(f"Metrics-diff JSON: {result.json_path}")
        if result.summary_path is not None:
            console.print(f"Metrics-diff Markdown: {result.summary_path}")

    if result.status == "failed":
        raise typer.Exit(code=1)


@app.command("regression-check")
def regression_check_command(
    project_root: ProjectRootOption = Path("."),
    runs_dir: Annotated[
        Path | None,
        typer.Option("--runs-dir", help="Custom runs directory to compare."),
    ] = None,
    baseline_run: Annotated[
        Path | None,
        typer.Option("--baseline-run", help="Explicit baseline run directory."),
    ] = None,
    candidate_run: Annotated[
        Path | None,
        typer.Option("--candidate-run", help="Explicit candidate run directory."),
    ] = None,
    baseline_label: Annotated[
        str | None,
        typer.Option("--baseline-label", help="Pinned baseline label to use."),
    ] = None,
    max_score_drop: Annotated[
        float | None,
        typer.Option("--max-score-drop", help="Allowed score drop."),
    ] = None,
    max_risk_increase: Annotated[
        float | None,
        typer.Option("--max-risk-increase", help="Allowed risk-level increase."),
    ] = None,
    require_baseline: Annotated[
        bool | None,
        typer.Option(
            "--require-baseline/--no-require-baseline",
            help="Fail if no baseline is available.",
        ),
    ] = None,
    fail_on_missing_metrics: Annotated[
        bool | None,
        typer.Option(
            "--fail-on-missing-metrics/--allow-missing-metrics",
            help="Fail when score or risk metrics are missing.",
        ),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print regression-check result as pure JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write regression-check JSON to PATH."),
    ] = None,
    summary_output: Annotated[
        Path | None,
        typer.Option("--summary-output", help="Write regression-check Markdown."),
    ] = None,
) -> None:
    """Compare candidate run quality against a baseline run."""
    root = project_root.resolve()
    selected_runs_dir = resolve_optional_output_path(root, runs_dir)
    selected_baseline_run = resolve_optional_output_path(root, baseline_run)
    selected_candidate_run = resolve_optional_output_path(root, candidate_run)
    selected_json_output = resolve_optional_output_path(root, json_output)
    selected_summary_output = resolve_optional_output_path(root, summary_output)
    try:
        policy = resolve_regression_check_policy(
            root,
            baseline_run=selected_baseline_run,
            baseline_label=baseline_label,
            max_score_drop=max_score_drop,
            max_risk_increase=max_risk_increase,
            require_baseline=require_baseline,
            fail_on_missing_metrics=fail_on_missing_metrics,
        )
        result = run_regression_check(
            root,
            runs_dir=selected_runs_dir,
            baseline_run=selected_baseline_run,
            candidate_run=selected_candidate_run,
            baseline_label=policy["baseline_label"],
            max_score_drop=policy["max_score_drop"],
            max_risk_increase=policy["max_risk_increase"],
            require_baseline=policy["require_baseline"],
            fail_on_missing_metrics=policy["fail_on_missing_metrics"],
            policy_source=policy["policy_source"],
            json_output=selected_json_output,
            summary_output=selected_summary_output,
        )
    except ReportError as exc:
        target_console = err_console if as_json else console
        target_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(regression_check_json(result))
    else:
        render_regression_check_summary(result)
        if result.json_path is not None:
            console.print(f"Regression-check JSON: {result.json_path}")
        if result.summary_path is not None:
            console.print(f"Regression-check Markdown: {result.summary_path}")

    if result.status == "failed":
        raise typer.Exit(code=1)


@app.command("share-check")
def share_check_command(
    target: Annotated[
        Path,
        typer.Argument(help="Evidence room, proof packet, site preview, or zip path."),
    ],
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print share-check result as pure JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write share-check JSON to PATH."),
    ] = None,
    markdown_output: Annotated[
        Path | None,
        typer.Option("--markdown-output", help="Write share-check Markdown to PATH."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Fail when warnings are present."),
    ] = False,
    allow_remote_urls: Annotated[
        bool,
        typer.Option(
            "--allow-remote-urls",
            help="Downgrade remote URL findings from errors to warnings.",
        ),
    ] = False,
    allow_example_temp_paths: Annotated[
        bool,
        typer.Option(
            "--allow-example-temp-paths",
            help="Allow documented /tmp/vibebench-* example paths.",
        ),
    ] = False,
) -> None:
    """Scan a local review package before sharing it externally."""
    project = project_root.resolve()
    selected_target = target if target.is_absolute() else project / target
    try:
        result = run_share_check(
            selected_target,
            strict=strict,
            allow_remote_urls=allow_remote_urls,
            allow_example_temp_paths=allow_example_temp_paths,
        )
    except ShareCheckError as exc:
        if as_json:
            payload = {
                "status": "failed",
                "target": str(selected_target),
                "target_type": "missing",
                "strict": strict,
                "checked_files": [],
                "summary": {
                    "checked_file_count": 0,
                    "finding_count": 1,
                    "error_count": 1,
                    "warning_count": 0,
                    "info_count": 0,
                },
                "findings": [
                    {
                        "severity": "error",
                        "code": "target_error",
                        "file": str(selected_target),
                        "line": None,
                        "message": str(exc),
                        "snippet": None,
                    }
                ],
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    selected_json_output = None
    if json_output is not None:
        selected_json_output = (
            json_output if json_output.is_absolute() else project / json_output
        )
        write_share_check_json(result, selected_json_output)
    selected_markdown_output = None
    if markdown_output is not None:
        selected_markdown_output = (
            markdown_output
            if markdown_output.is_absolute()
            else project / markdown_output
        )
        write_share_check_markdown(result, selected_markdown_output)

    if as_json:
        print(share_check_json(result))
    else:
        render_share_check_summary(result)
        if selected_json_output is not None:
            console.print(f"Share-check JSON: {selected_json_output}")
        if selected_markdown_output is not None:
            console.print(f"Share-check Markdown: {selected_markdown_output}")

    if result.status == "failed":
        raise typer.Exit(code=1)


@app.command("manifest")
def manifest_command(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to manifest.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write manifest output to this file."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Validate the manifest can be read."),
    ] = False,
    check: Annotated[
        bool,
        typer.Option("--check", help="Check existing manifest consistency."),
    ] = False,
) -> None:
    """Write or check a machine-readable manifest for a VibeBench run."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()

    try:
        if check:
            check_result = check_manifest(
                root,
                selected_run_dir,
                selected_output,
                strict=strict,
            )
            render_manifest_check_summary(check_result)
            if not check_result.passed:
                raise typer.Exit(code=1)
            return

        result = generate_manifest(
            root,
            selected_run_dir,
            selected_output,
            strict=strict,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_manifest_summary(result)


@app.command("artifacts")
def artifacts_command(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to inspect.",
        ),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print artifact inventory as JSON."),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Fail if any known artifact is missing."),
    ] = False,
    only_available: Annotated[
        bool,
        typer.Option("--only-available", help="Show only available artifacts."),
    ] = False,
) -> None:
    """List known artifacts for a VibeBench run."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()

    try:
        result = collect_artifact_inventory(
            root,
            selected_run_dir,
            only_available=only_available,
            strict=strict,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(json.dumps(inventory_json(result), indent=2))
        return

    render_artifacts_summary(result)


@app.command("export")
def export_command(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to export.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write export output to this file."),
    ] = None,
    export_format: Annotated[
        str,
        typer.Option("--format", help="Export format: json or markdown."),
    ] = "json",
    pretty: Annotated[
        bool,
        typer.Option("--pretty", help="Pretty-print JSON output."),
    ] = False,
) -> None:
    """Export a machine-readable VibeBench run summary."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()

    try:
        result = export_run(
            root,
            selected_run_dir,
            selected_output,
            export_format=export_format,
            pretty=pretty,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_export_summary(result)


@app.command()
def annotate(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to annotate.",
        ),
    ] = None,
    min_severity: Annotated[
        str,
        typer.Option("--min-severity", help="Minimum finding severity to emit."),
    ] = "warning",
    github_actions: Annotated[
        bool,
        typer.Option(
            "--github-actions/--no-github-actions",
            help="Emit GitHub workflow commands or plain text.",
        ),
    ] = True,
) -> None:
    """Emit GitHub Actions annotations for a VibeBench run."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()

    try:
        result = generate_annotations(
            root,
            selected_run_dir,
            min_severity=min_severity,
            github_actions=github_actions,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_annotation_summary(result)


def resolve_regression_check_policy(
    root: Path,
    *,
    baseline_run: Path | None = None,
    baseline_label: str | None = None,
    max_score_drop: float | None = None,
    max_risk_increase: float | None = None,
    require_baseline: bool | None = None,
    fail_on_missing_metrics: bool | None = None,
) -> dict[str, object]:
    """Resolve regression-check policy from CLI flags, config, and defaults."""
    effective_config = load_effective_config(config_file(root))
    regression = effective_config.config.regression
    cli_override = any(
        value is not None
        for value in [
            baseline_run,
            baseline_label,
            max_score_drop,
            max_risk_increase,
            require_baseline,
            fail_on_missing_metrics,
        ]
    )
    policy_source = (
        "cli"
        if cli_override
        else (
            "config"
            if effective_config.sources.get("regression") == "config file"
            else "default"
        )
    )
    selected_label = baseline_label
    if selected_label is None and baseline_run is None:
        selected_label = regression.baseline_label
    return {
        "policy_source": policy_source,
        "baseline_label": selected_label,
        "require_baseline": (
            require_baseline
            if require_baseline is not None
            else regression.require_baseline
        ),
        "max_score_drop": (
            max_score_drop if max_score_drop is not None else regression.max_score_drop
        ),
        "max_risk_increase": (
            max_risk_increase
            if max_risk_increase is not None
            else regression.max_risk_increase
        ),
        "fail_on_missing_metrics": (
            fail_on_missing_metrics
            if fail_on_missing_metrics is not None
            else regression.fail_on_missing_metrics
        ),
    }


def resolve_ci_regression_check_policy(
    root: Path,
    *,
    regression_check: bool,
    skip_regression_check: bool,
    require_regression_baseline: bool | None,
    baseline_label: str | None,
) -> dict[str, object]:
    """Resolve whether CI should run regression-check and with what policy."""
    effective_config = load_effective_config(config_file(root))
    regression = effective_config.config.regression
    if skip_regression_check:
        enabled = False
        policy_source = "cli"
    elif regression_check:
        enabled = True
        policy_source = "cli"
    elif regression.enabled:
        enabled = True
        policy_source = (
            "config"
            if effective_config.sources.get("regression") == "config file"
            else "default"
        )
    else:
        enabled = False
        policy_source = (
            "config"
            if effective_config.sources.get("regression") == "config file"
            else "default"
        )
    selected_label = (
        baseline_label if baseline_label is not None else regression.baseline_label
    )
    require_baseline = (
        require_regression_baseline
        if require_regression_baseline is not None
        else regression.require_baseline
    )
    return {
        "enabled": enabled,
        "policy_source": policy_source,
        "baseline_label": selected_label,
        "require_baseline": require_baseline,
        "max_score_drop": regression.max_score_drop,
        "max_risk_increase": regression.max_risk_increase,
        "fail_on_missing_metrics": regression.fail_on_missing_metrics,
    }


def resolve_ci_regression_guard(
    root: Path,
    fail_on_regression: bool | None,
    skip_compare: bool,
) -> CiRegressionGuardPolicy:
    """Resolve CI compare regression guard from CLI flags and config."""
    if skip_compare:
        return ci_regression_guard_policy(
            enabled=False,
            source="cli",
            message="Disabled because --skip-compare skips compare.",
        )
    if fail_on_regression is not None:
        return ci_regression_guard_policy(
            enabled=fail_on_regression,
            source="cli",
        )

    effective_config = load_effective_config(config_file(root))
    source = (
        "config"
        if effective_config.sources.get("compare") == "config file"
        else "default"
    )
    return ci_regression_guard_policy(
        enabled=effective_config.config.compare.fail_on_regression,
        source=source,
    )


def resolve_adoption_workflow_required_ci_modes(
    explicit_modes: list[str],
    *,
    require_adoption_workflow: bool,
    source: str,
) -> list[str]:
    """Apply the adoption workflow convenience flag to required CI modes."""
    if not require_adoption_workflow:
        return explicit_modes
    conflicting = [mode for mode in explicit_modes if mode != "adoption-policy"]
    if conflicting:
        raise ConfigError(
            "--require-adoption-workflow requires "
            f"{source} adoption-policy mode. Remove conflicting mode(s): "
            + ", ".join(conflicting)
            + "."
        )
    return normalize_required_ci_modes(
        [*explicit_modes, "adoption-policy"],
        source=source,
    )


@app.command("ci")
def ci_command(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Existing .vibebench/runs/<timestamp> directory to process.",
        ),
    ] = None,
    skip_report: Annotated[
        bool,
        typer.Option("--skip-report", help="Skip HTML report generation."),
    ] = False,
    skip_pr_comment: Annotated[
        bool,
        typer.Option("--skip-pr-comment", help="Skip PR comment generation."),
    ] = False,
    skip_explain: Annotated[
        bool,
        typer.Option("--skip-explain", help="Skip run explanation generation."),
    ] = False,
    skip_bundle: Annotated[
        bool,
        typer.Option("--skip-bundle", help="Skip artifact bundle generation."),
    ] = False,
    skip_export: Annotated[
        bool,
        typer.Option("--skip-export", help="Skip machine-readable export generation."),
    ] = False,
    skip_badge: Annotated[
        bool,
        typer.Option("--skip-badge", help="Skip badge artifact generation."),
    ] = False,
    skip_status_block: Annotated[
        bool,
        typer.Option(
            "--skip-status-block",
            help="Skip README status block generation.",
        ),
    ] = False,
    skip_trend: Annotated[
        bool,
        typer.Option("--skip-trend", help="Skip trend summary generation."),
    ] = False,
    skip_run_index: Annotated[
        bool,
        typer.Option("--skip-run-index", help="Skip run-index artifact generation."),
    ] = False,
    skip_compare: Annotated[
        bool,
        typer.Option("--skip-compare", help="Skip run comparison artifacts."),
    ] = False,
    skip_config_check: Annotated[
        bool,
        typer.Option("--skip-config-check", help="Skip config check artifacts."),
    ] = False,
    skip_manifest: Annotated[
        bool,
        typer.Option("--skip-manifest", help="Skip run manifest generation."),
    ] = False,
    skip_package_check: Annotated[
        bool,
        typer.Option("--skip-package-check", help="Skip package-check artifacts."),
    ] = False,
    skip_annotate: Annotated[
        bool,
        typer.Option("--skip-annotate", help="Skip GitHub annotation output."),
    ] = False,
    skip_gh_summary: Annotated[
        bool,
        typer.Option("--skip-gh-summary", help="Skip GitHub summary generation."),
    ] = False,
    skip_release_check: Annotated[
        bool,
        typer.Option(
            "--skip-release-check",
            help="Skip release-check artifact generation.",
        ),
    ] = False,
    skip_evidence_room: Annotated[
        bool,
        typer.Option(
            "--skip-evidence-room",
            help="Skip evidence-room artifact generation.",
        ),
    ] = False,
    adoption: Annotated[
        bool,
        typer.Option(
            "--adoption",
            help="Write the full report-only adoption evidence suite.",
        ),
    ] = False,
    adoption_policy: Annotated[
        bool,
        typer.Option(
            "--adoption-policy",
            help="Write adoption artifacts and enforce policy-capable checks.",
        ),
    ] = False,
    require_adoption_workflow: Annotated[
        bool,
        typer.Option(
            "--require-adoption-workflow",
            help=(
                "Require adoption-policy CI mode through workflow-check and "
                "preflight."
            ),
        ),
    ] = False,
    onboard: Annotated[
        bool,
        typer.Option(
            "--onboard",
            help="Write read-only onboarding plan artifacts.",
        ),
    ] = False,
    skip_onboard: Annotated[
        bool,
        typer.Option(
            "--skip-onboard",
            help="Skip optional onboarding plan artifact generation.",
        ),
    ] = False,
    onboard_policy: Annotated[
        bool,
        typer.Option(
            "--onboard-policy",
            help="Write onboard artifacts with policy enforcement.",
        ),
    ] = False,
    project_scan: Annotated[
        bool,
        typer.Option(
            "--project-scan",
            help="Run project-scan and write onboarding readiness artifacts.",
        ),
    ] = False,
    skip_project_scan: Annotated[
        bool,
        typer.Option(
            "--skip-project-scan",
            help="Skip optional project-scan artifact generation.",
        ),
    ] = False,
    project_scan_policy: Annotated[
        bool,
        typer.Option(
            "--project-scan-policy",
            help="Run project-scan artifacts with policy enforcement.",
        ),
    ] = False,
    preflight: Annotated[
        bool,
        typer.Option(
            "--preflight",
            help="Write report-only preflight artifacts.",
        ),
    ] = False,
    preflight_policy: Annotated[
        bool,
        typer.Option(
            "--preflight-policy",
            help="Write preflight artifacts with policy enforcement.",
        ),
    ] = False,
    skip_preflight: Annotated[
        bool,
        typer.Option(
            "--skip-preflight",
            help="Skip optional preflight artifact generation.",
        ),
    ] = False,
    preflight_require_ci_mode: Annotated[
        list[str] | None,
        typer.Option(
            "--preflight-require-ci-mode",
            help=(
                "Require detected preflight workflow CI mode(s): default, adoption, "
                "or adoption-policy. Repeat the option to require multiple modes."
            ),
        ),
    ] = None,
    metrics_check: Annotated[
        bool,
        typer.Option(
            "--metrics-check",
            help="Run metrics-check and write metrics-check artifacts.",
        ),
    ] = False,
    skip_metrics_check: Annotated[
        bool,
        typer.Option(
            "--skip-metrics-check",
            help="Skip optional metrics-check artifact generation.",
        ),
    ] = False,
    metrics_diff: Annotated[
        bool,
        typer.Option(
            "--metrics-diff",
            help="Run metrics-diff and write metrics-diff artifacts.",
        ),
    ] = False,
    skip_metrics_diff: Annotated[
        bool,
        typer.Option(
            "--skip-metrics-diff",
            help="Skip optional metrics-diff artifact generation.",
        ),
    ] = False,
    metrics_diff_policy: Annotated[
        bool,
        typer.Option(
            "--metrics-diff-policy",
            help="Run metrics-diff artifacts with policy enforcement.",
        ),
    ] = False,
    skip_metrics_diff_policy: Annotated[
        bool,
        typer.Option(
            "--skip-metrics-diff-policy",
            help="Disable metrics-diff policy enforcement for this CI run.",
        ),
    ] = False,
    workflow_check: Annotated[
        bool,
        typer.Option(
            "--workflow-check",
            help="Run workflow-check and write report-only artifacts.",
        ),
    ] = False,
    workflow_check_policy: Annotated[
        bool,
        typer.Option(
            "--workflow-check-policy",
            help="Run workflow-check artifacts with policy enforcement.",
        ),
    ] = False,
    skip_workflow_check: Annotated[
        bool,
        typer.Option(
            "--skip-workflow-check",
            help="Skip optional workflow-check artifact generation.",
        ),
    ] = False,
    workflow_check_require_ci_mode: Annotated[
        list[str] | None,
        typer.Option(
            "--workflow-check-require-ci-mode",
            help=(
                "Require detected workflow-check CI mode(s): default, adoption, or "
                "adoption-policy. Repeat the option to require multiple modes."
            ),
        ),
    ] = None,
    workflow_template: Annotated[
        bool,
        typer.Option(
            "--workflow-template",
            help="Write report-only workflow-template artifacts.",
        ),
    ] = False,
    skip_workflow_template: Annotated[
        bool,
        typer.Option(
            "--skip-workflow-template",
            help="Skip optional workflow-template artifact generation.",
        ),
    ] = False,
    workflow_template_profile: Annotated[
        str,
        typer.Option(
            "--workflow-template-profile",
            help=(
                "Workflow-template profile: generic, python, node, fullstack, or auto."
            ),
        ),
    ] = "auto",
    workflow_template_ci_mode: Annotated[
        str,
        typer.Option(
            "--workflow-template-ci-mode",
            help="Workflow-template CI mode: basic, adoption, or strict.",
        ),
    ] = "adoption",
    workflow_template_install_command: Annotated[
        str,
        typer.Option(
            "--workflow-template-install-command",
            help="Install command to place in workflow-template artifacts.",
        ),
    ] = DEFAULT_WORKFLOW_INSTALL_COMMAND,
    regression_check: Annotated[
        bool,
        typer.Option(
            "--regression-check",
            help="Run the optional candidate-vs-baseline regression gate.",
        ),
    ] = False,
    skip_regression_check: Annotated[
        bool,
        typer.Option(
            "--skip-regression-check",
            help="Disable config-enabled regression-check for this CI run.",
        ),
    ] = False,
    require_regression_baseline: Annotated[
        bool | None,
        typer.Option(
            "--require-regression-baseline/--no-require-regression-baseline",
            help="Fail regression-check when no baseline run exists.",
        ),
    ] = None,
    baseline_label: Annotated[
        str | None,
        typer.Option("--baseline-label", help="Pinned regression baseline label."),
    ] = None,
    fail_on_regression: Annotated[
        bool | None,
        typer.Option(
            "--fail-on-regression/--no-fail-on-regression",
            help=(
                "Override whether CI fails when the compare step verdict is regressed."
            ),
        ),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print CI result as JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write CI result JSON to this file."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show the CI pipeline plan without running it."),
    ] = False,
    plan: Annotated[
        bool,
        typer.Option("--plan", help="Alias for --dry-run."),
    ] = False,
    write_plan: Annotated[
        bool,
        typer.Option("--write-plan", help="Write ci-plan.json and ci-plan.md."),
    ] = False,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Directory for CI plan artifacts."),
    ] = None,
    plan_json_output: Annotated[
        Path | None,
        typer.Option("--plan-json-output", help="Write CI plan JSON to this file."),
    ] = None,
    plan_summary_output: Annotated[
        Path | None,
        typer.Option(
            "--plan-summary-output",
            help="Write CI plan Markdown to this file.",
        ),
    ] = None,
    bundle_include_report_assets: Annotated[
        bool,
        typer.Option(
            "--bundle-include-report-assets",
            help="Include report assets recursively in the bundle.",
        ),
    ] = False,
    bundle_strict: Annotated[
        bool,
        typer.Option("--bundle-strict", help="Fail bundle on missing artifacts."),
    ] = False,
    min_score: Annotated[
        int | None,
        typer.Option("--min-score", help="Override minimum acceptable VibeScore."),
    ] = None,
    max_risk: Annotated[
        str | None,
        typer.Option("--max-risk", help="Override maximum acceptable risk level."),
    ] = None,
    allow_findings: Annotated[
        int | None,
        typer.Option("--allow-findings", help="Override allowed finding count."),
    ] = None,
    require_status_passed: Annotated[
        bool | None,
        typer.Option("--require-status-passed/--no-require-status-passed"),
    ] = None,
) -> None:
    """Run the full VibeBench CI pipeline."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()
    selected_json_output = None
    if json_output:
        selected_json_output = (
            json_output if json_output.is_absolute() else root / json_output
        ).resolve()
    selected_output_dir = None
    if output_dir:
        selected_output_dir = (
            output_dir if output_dir.is_absolute() else root / output_dir
        ).resolve()
    selected_plan_json_output = None
    if plan_json_output:
        selected_plan_json_output = (
            plan_json_output
            if plan_json_output.is_absolute()
            else root / plan_json_output
        ).resolve()
    selected_plan_summary_output = None
    if plan_summary_output:
        selected_plan_summary_output = (
            plan_summary_output
            if plan_summary_output.is_absolute()
            else root / plan_summary_output
        ).resolve()
    plan_mode = dry_run or plan
    plan_outputs_requested = any(
        [
            write_plan,
            selected_output_dir,
            selected_plan_json_output,
            selected_plan_summary_output,
        ]
    )
    if plan_outputs_requested and not plan_mode:
        console.print("[red]CI plan output options require --dry-run or --plan.[/]")
        raise typer.Exit(code=1)

    explicit_workflow_check_required_ci_modes = normalize_required_ci_modes(
        workflow_check_require_ci_mode or [],
        source="--workflow-check-require-ci-mode",
    )
    explicit_preflight_required_ci_modes = normalize_required_ci_modes(
        preflight_require_ci_mode or [],
        source="--preflight-require-ci-mode",
    )
    if explicit_workflow_check_required_ci_modes and skip_workflow_check:
        raise ConfigError(
            "--workflow-check-require-ci-mode cannot be combined with "
            "--skip-workflow-check."
        )
    normalized_workflow_check_required_ci_modes = (
        resolve_adoption_workflow_required_ci_modes(
            explicit_workflow_check_required_ci_modes,
            require_adoption_workflow=require_adoption_workflow,
            source="--workflow-check-require-ci-mode",
        )
    )
    normalized_preflight_required_ci_modes = (
        resolve_adoption_workflow_required_ci_modes(
            explicit_preflight_required_ci_modes,
            require_adoption_workflow=require_adoption_workflow,
            source="--preflight-require-ci-mode",
        )
    )

    adoption_enabled = adoption or adoption_policy
    effective_onboard_policy = (onboard_policy or adoption_policy) and not skip_onboard
    effective_project_scan_policy = project_scan_policy or (
        adoption_policy and not skip_project_scan
    )
    effective_workflow_check_policy = (
        workflow_check_policy or adoption_policy
    ) and not skip_workflow_check
    effective_preflight_policy = (
        preflight_policy or adoption_policy
    ) and not skip_preflight
    effective_onboard = (
        onboard or (adoption_enabled and not adoption_policy)
    ) and not skip_onboard
    effective_project_scan = project_scan or (
        adoption_enabled and not adoption_policy and not skip_project_scan
    )
    effective_workflow_check = (
        workflow_check
        or bool(normalized_workflow_check_required_ci_modes)
        or (adoption_enabled and not adoption_policy)
    ) and not skip_workflow_check
    effective_preflight = (
        preflight
        or bool(normalized_preflight_required_ci_modes)
        or (adoption_enabled and not adoption_policy)
    ) and not skip_preflight
    effective_workflow_template = (
        workflow_template or adoption_enabled
    ) and not skip_workflow_template

    try:
        plan_artifacts = None
        regression_guard = resolve_ci_regression_guard(
            root,
            fail_on_regression,
            skip_compare,
        )
        regression_policy = resolve_ci_regression_check_policy(
            root,
            regression_check=regression_check,
            skip_regression_check=skip_regression_check,
            require_regression_baseline=require_regression_baseline,
            baseline_label=baseline_label,
        )
        if plan_mode:
            result = plan_ci_pipeline(
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
                onboard=effective_onboard,
                skip_onboard=skip_onboard,
                onboard_policy=effective_onboard_policy,
                project_scan=effective_project_scan,
                skip_project_scan=skip_project_scan,
                project_scan_policy=effective_project_scan_policy,
                preflight=effective_preflight,
                preflight_policy=effective_preflight_policy,
                skip_preflight=skip_preflight,
                preflight_required_ci_modes=normalized_preflight_required_ci_modes,
                metrics_check=metrics_check,
                skip_metrics_check=skip_metrics_check,
                metrics_diff=metrics_diff,
                skip_metrics_diff=skip_metrics_diff,
                metrics_diff_policy=metrics_diff_policy,
                skip_metrics_diff_policy=skip_metrics_diff_policy,
                workflow_check=effective_workflow_check,
                workflow_check_policy=effective_workflow_check_policy,
                skip_workflow_check=skip_workflow_check,
                workflow_check_required_ci_modes=(
                    normalized_workflow_check_required_ci_modes
                ),
                workflow_template=effective_workflow_template,
                skip_workflow_template=skip_workflow_template,
                workflow_template_profile=workflow_template_profile,
                workflow_template_ci_mode=workflow_template_ci_mode,
                workflow_template_install_command=workflow_template_install_command,
                regression_check=bool(regression_policy["enabled"]),
                require_regression_baseline=bool(regression_policy["require_baseline"]),
                baseline_label=regression_policy["baseline_label"],
                regression_policy_source=str(regression_policy["policy_source"]),
                max_score_drop=float(regression_policy["max_score_drop"]),
                max_risk_increase=float(regression_policy["max_risk_increase"]),
                fail_on_missing_metrics=bool(
                    regression_policy["fail_on_missing_metrics"]
                ),
                fail_on_regression=regression_guard.enabled,
                regression_guard_source=regression_guard.source,
                regression_guard_message=regression_guard.message,
            )
            plan_artifacts = write_ci_plan_artifacts(
                root,
                result,
                output_dir=selected_output_dir,
                json_output=selected_plan_json_output,
                summary_output=selected_plan_summary_output,
                create_default_dir=write_plan,
            )
        else:
            result = run_ci_pipeline(
                root,
                run_dir=selected_run_dir,
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
                onboard=effective_onboard,
                skip_onboard=skip_onboard,
                onboard_policy=effective_onboard_policy,
                project_scan=effective_project_scan,
                skip_project_scan=skip_project_scan,
                project_scan_policy=effective_project_scan_policy,
                preflight=effective_preflight,
                preflight_policy=effective_preflight_policy,
                skip_preflight=skip_preflight,
                preflight_required_ci_modes=normalized_preflight_required_ci_modes,
                metrics_check=metrics_check,
                skip_metrics_check=skip_metrics_check,
                metrics_diff=metrics_diff,
                skip_metrics_diff=skip_metrics_diff,
                metrics_diff_policy=metrics_diff_policy,
                skip_metrics_diff_policy=skip_metrics_diff_policy,
                workflow_check=effective_workflow_check,
                workflow_check_policy=effective_workflow_check_policy,
                skip_workflow_check=skip_workflow_check,
                workflow_check_required_ci_modes=(
                    normalized_workflow_check_required_ci_modes
                ),
                workflow_template=effective_workflow_template,
                skip_workflow_template=skip_workflow_template,
                workflow_template_profile=workflow_template_profile,
                workflow_template_ci_mode=workflow_template_ci_mode,
                workflow_template_install_command=workflow_template_install_command,
                regression_check=bool(regression_policy["enabled"]),
                require_regression_baseline=bool(regression_policy["require_baseline"]),
                baseline_label=regression_policy["baseline_label"],
                regression_policy_source=str(regression_policy["policy_source"]),
                max_score_drop=float(regression_policy["max_score_drop"]),
                max_risk_increase=float(regression_policy["max_risk_increase"]),
                fail_on_missing_metrics=bool(
                    regression_policy["fail_on_missing_metrics"]
                ),
                emit_annotations=not as_json,
                bundle_include_report_assets=bundle_include_report_assets,
                bundle_strict=bundle_strict,
                min_score=min_score,
                max_risk=max_risk,
                allow_findings=allow_findings,
                require_status_passed=require_status_passed,
                fail_on_regression=regression_guard.enabled,
                regression_guard_source=regression_guard.source,
                regression_guard_message=regression_guard.message,
            )
        if selected_json_output is not None:
            write_ci_json(result, selected_json_output)
    except (ReportError, ConfigError) as exc:
        target_console = err_console if as_json else console
        target_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(json.dumps(ci_json_payload(result), indent=2, sort_keys=True))
    else:
        render_ci_summary(result)
        if selected_json_output is not None:
            console.print(f"CI JSON: {selected_json_output}")
        if plan_artifacts is not None:
            render_ci_plan_artifact_summary(plan_artifacts)

    if not result.passed:
        raise typer.Exit(code=1)


@app.command("run-index")
def run_index_command(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print run index as JSON."),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum number of recent runs to index."),
    ] = 10,
    runs_dir: Annotated[
        Path | None,
        typer.Option("--runs-dir", help="Custom runs directory to index."),
    ] = None,
    write_json: Annotated[
        Path | None,
        typer.Option("--write-json", help="Write run index JSON to this path."),
    ] = None,
    write_summary: Annotated[
        Path | None,
        typer.Option("--write-summary", help="Write run index Markdown to this path."),
    ] = None,
) -> None:
    """Index recent VibeBench run directories and artifacts."""
    root = project_root.resolve()
    selected_runs_dir = resolve_optional_output_path(root, runs_dir)
    selected_json_path = resolve_optional_output_path(root, write_json)
    selected_summary_path = resolve_optional_output_path(root, write_summary)
    try:
        result = build_run_index(root, runs_dir=selected_runs_dir, limit=limit)
        if selected_json_path is not None:
            write_run_index_json(result, selected_json_path)
        if selected_summary_path is not None:
            write_run_index_summary(result, selected_summary_path)
    except ReportError as exc:
        target_console = err_console if as_json else console
        target_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(json.dumps(run_index_payload(result), indent=2, sort_keys=True))
    else:
        render_run_index_summary(result)
        if selected_json_path is not None:
            console.print(f"Run index JSON: {selected_json_path}")
        if selected_summary_path is not None:
            console.print(f"Run index summary: {selected_summary_path}")


@app.command()
def doctor(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print doctor diagnostics as JSON."),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Run stricter release/CI preflight checks."),
    ] = False,
    advice: Annotated[
        bool,
        typer.Option("--advice", help="Show advice for failed or warning checks."),
    ] = False,
) -> None:
    """Diagnose whether this project is ready to run VibeBench."""
    result = run_doctor(project_root, strict=strict, advice=advice)
    if as_json:
        print(json.dumps(doctor_json_payload(result), indent=2, sort_keys=True))
    else:
        render_doctor_summary(result)
    if result.overall_status == "failed":
        raise typer.Exit(code=1)


@app.command("package-check")
def package_check_command(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print package readiness as JSON."),
    ] = False,
    advice: Annotated[
        bool,
        typer.Option("--advice", help="Show advice for failed package checks."),
    ] = False,
    build: Annotated[
        bool,
        typer.Option(
            "--build",
            help="Run an opt-in local-only package build readiness check.",
        ),
    ] = False,
    write_json: Annotated[
        Path | None,
        typer.Option("--write-json", help="Write package readiness JSON."),
    ] = None,
    write_summary: Annotated[
        Path | None,
        typer.Option("--write-summary", help="Write package readiness Markdown."),
    ] = None,
) -> None:
    """Check local package and install readiness without network access."""
    root = project_root.resolve()
    result = run_package_check(root, advice=advice, build=build)
    selected_json_path = resolve_optional_output_path(root, write_json)
    selected_summary_path = resolve_optional_output_path(root, write_summary)
    try:
        if selected_json_path is not None:
            write_package_check_json(result, selected_json_path)
        if selected_summary_path is not None:
            write_package_check_summary(result, selected_summary_path)
    except ReportError as exc:
        target_console = err_console if as_json else console
        target_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(
            json.dumps(
                package_check_json_payload(result),
                indent=2,
                sort_keys=True,
            )
        )
    else:
        render_package_check_summary(result)
        if selected_json_path is not None:
            console.print(f"Package-check JSON: {selected_json_path}")
        if selected_summary_path is not None:
            console.print(f"Package-check summary: {selected_summary_path}")
    if not result.ready:
        raise typer.Exit(code=1)


@app.command("publish-check")
def publish_check_command(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print publish readiness as JSON."),
    ] = False,
    advice: Annotated[
        bool,
        typer.Option("--advice", help="Show advice for publish readiness checks."),
    ] = False,
    write_json: Annotated[
        Path | None,
        typer.Option("--write-json", help="Write publish readiness JSON."),
    ] = None,
    write_summary: Annotated[
        Path | None,
        typer.Option("--write-summary", help="Write publish readiness Markdown."),
    ] = None,
) -> None:
    """Run a local-only package publishing readiness dry-run."""
    root = project_root.resolve()
    result = run_publish_check(root, advice=advice)
    selected_json_path = resolve_optional_output_path(root, write_json)
    selected_summary_path = resolve_optional_output_path(root, write_summary)
    try:
        if selected_json_path is not None:
            write_publish_check_json(result, selected_json_path)
        if selected_summary_path is not None:
            write_publish_check_summary(result, selected_summary_path)
    except ReportError as exc:
        target_console = err_console if as_json else console
        target_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(publish_check_json(result))
    else:
        render_publish_check_summary(result)
        if selected_json_path is not None:
            console.print(f"Publish-check JSON: {selected_json_path}")
        if selected_summary_path is not None:
            console.print(f"Publish-check summary: {selected_summary_path}")
    if result.overall_status == "failed":
        raise typer.Exit(code=1)


@app.command("release-body")
def release_body_command(
    project_root: ProjectRootOption = Path("."),
    version: Annotated[
        str,
        typer.Option("--version", help="Release version, for example v0.3.0."),
    ] = "",
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write the release body Markdown to this path."),
    ] = None,
    check_only: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Validate the release body without writing files.",
        ),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print release body result as JSON."),
    ] = False,
) -> None:
    """Export a local GitHub Release body from release notes."""
    root = project_root.resolve()
    selected_output_path = resolve_optional_output_path(root, output)
    try:
        result = export_release_body(
            root,
            version=version,
            output_path=None if check_only else selected_output_path,
        )
    except ReportError as exc:
        target_console = err_console if as_json else console
        target_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(release_body_json(result))
    elif check_only:
        render_release_body_check_summary(result)
    elif selected_output_path is not None:
        console.print(f"Release body written: {selected_output_path}")
    else:
        print(result.body or "", end="")
    if result.status == "failed":
        raise typer.Exit(code=1)


@app.command("release-audit")
def release_audit_command(
    project_root: ProjectRootOption = Path("."),
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Write audit artifacts to this directory."),
    ] = None,
    version: Annotated[
        str | None,
        typer.Option("--version", help="Target release version, for example v0.3.0."),
    ] = None,
    zip_archive: Annotated[
        bool,
        typer.Option(
            "--zip",
            help="Write release-audit.zip inside the audit output directory.",
        ),
    ] = False,
    zip_output: Annotated[
        Path | None,
        typer.Option("--zip-output", help="Write the release audit zip to this path."),
    ] = None,
    verify: Annotated[
        Path | None,
        typer.Option(
            "--verify",
            help="Verify an existing release audit directory or zip archive.",
        ),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print release audit result as JSON."),
    ] = False,
) -> None:
    """Create or verify a local release audit without release side effects."""
    root = project_root.resolve()
    selected_verify_path = resolve_optional_output_path(root, verify)
    if selected_verify_path is not None:
        verify_result = verify_release_audit(selected_verify_path)
        if as_json:
            print(release_audit_verify_json(verify_result))
        else:
            render_release_audit_verify_summary(verify_result)
        if verify_result.status == "failed":
            raise typer.Exit(code=1)
        return

    selected_output_dir = resolve_optional_output_path(root, output_dir)
    selected_zip_output = resolve_optional_output_path(root, zip_output)
    checklist_payload = release_checklist_payload(root, requested_version=version)
    try:
        result = create_release_audit(
            root,
            output_dir=selected_output_dir,
            version=version,
            create_zip=zip_archive,
            zip_output_path=selected_zip_output,
            release_checklist_payload=checklist_payload,
        )
    except ReportError as exc:
        target_console = err_console if as_json else console
        target_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(release_audit_json(result))
    else:
        render_release_audit_summary(result)
    if result.status == "failed":
        raise typer.Exit(code=1)


@app.command("release-check")
def release_check_command(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print release readiness as JSON."),
    ] = False,
    write_json: Annotated[
        Path | None,
        typer.Option(
            "--write-json",
            help="Write release readiness JSON to this path.",
        ),
    ] = None,
    write_summary: Annotated[
        Path | None,
        typer.Option(
            "--write-summary",
            help="Write release readiness Markdown to this path.",
        ),
    ] = None,
) -> None:
    """Run pre-release readiness checks."""
    result = run_release_check(project_root)
    try:
        if write_json is not None:
            write_release_check_json(result, write_json)
        if write_summary is not None:
            write_release_check_summary(result, write_summary)
    except ReportError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc

    if as_json:
        print(release_check_json(result))
    else:
        render_release_check_summary(result)
    if not result.ready:
        raise typer.Exit(code=1)


@app.command("release-checklist")
def release_checklist_command(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print release checklist as JSON."),
    ] = False,
    version: Annotated[
        str | None,
        typer.Option("--version", help="Target release version, for example v0.3.0."),
    ] = None,
    write_json: Annotated[
        Path | None,
        typer.Option("--write-json", help="Write release checklist JSON."),
    ] = None,
    write_summary: Annotated[
        Path | None,
        typer.Option("--write-summary", help="Write release checklist Markdown."),
    ] = None,
) -> None:
    """Inspect local release readiness without creating tags or releases."""
    root = project_root.resolve()
    payload = release_checklist_payload(root, requested_version=version)
    selected_json_path = resolve_optional_output_path(root, write_json)
    selected_summary_path = resolve_optional_output_path(root, write_summary)
    try:
        if selected_json_path is not None:
            write_release_checklist_json(payload, selected_json_path)
        if selected_summary_path is not None:
            write_release_checklist_summary(payload, selected_summary_path)
    except ReportError as exc:
        target_console = err_console if as_json else console
        target_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(release_checklist_json(payload))
    else:
        render_release_checklist(payload)
        if selected_json_path is not None:
            console.print(f"Release-checklist JSON: {selected_json_path}")
        if selected_summary_path is not None:
            console.print(f"Release-checklist summary: {selected_summary_path}")
    if payload["overall_status"] == "failed":
        raise typer.Exit(code=1)


def release_checklist_json(payload: dict[str, object]) -> str:
    """Return deterministic JSON for a release checklist payload."""
    return json.dumps(payload, indent=2, sort_keys=True)


def write_release_checklist_json(
    payload: dict[str, object],
    output_path: Path,
) -> Path:
    """Write release checklist JSON to a selected path."""
    validate_release_checklist_output_path(output_path)
    output_path.write_text(release_checklist_json(payload) + "\n", encoding="utf-8")
    return output_path


def write_release_checklist_summary(
    payload: dict[str, object],
    output_path: Path,
) -> Path:
    """Write release checklist Markdown to a selected path."""
    validate_release_checklist_output_path(output_path)
    output_path.write_text(render_release_checklist_markdown(payload), encoding="utf-8")
    return output_path


def validate_release_checklist_output_path(output_path: Path) -> None:
    """Validate a release-checklist output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(
            f"Release-checklist output path is a directory: {output_path}"
        )
    if not output_path.parent.exists():
        raise ReportError(
            f"Release-checklist output parent does not exist: {output_path.parent}"
        )


def render_release_checklist_markdown(payload: dict[str, object]) -> str:
    """Render a concise Markdown release checklist summary."""
    lines = [
        "# VibeBench Release Checklist",
        "",
        f"- Version: `{markdown_cell(payload.get('target_version', 'unknown'))}`",
        (
            "- Overall status: "
            f"`{markdown_cell(payload.get('overall_status', 'unknown'))}`"
        ),
        "",
        "| Item | Status | Message |",
        "| --- | --- | --- |",
    ]
    checks = payload.get("checks", [])
    if isinstance(checks, list):
        for check in checks:
            if not isinstance(check, dict):
                continue
            lines.append(
                "| "
                f"{markdown_cell(check.get('name', ''))} | "
                f"{markdown_cell(check.get('status', ''))} | "
                f"{markdown_cell(check.get('message', ''))} |"
            )
    lines.extend(
        [
            "",
            "## Safety Note",
            "",
            "- No tag is created.",
            "- No GitHub Release is created.",
            "- No package publish or upload is performed.",
            "- No version bump is performed.",
            "",
        ]
    )
    return "\n".join(lines)


def markdown_cell(value: object) -> str:
    """Escape Markdown table-sensitive content."""
    return str(value).replace("|", "\\|").replace("\n", " ")


def release_checklist_payload(
    project_root: Path,
    *,
    requested_version: str | None,
) -> dict[str, object]:
    """Return JSON-safe release checklist output."""
    package_version = read_project_version(project_root)
    target_version = normalize_release_version(requested_version or package_version)
    checks: list[dict[str, str]] = []

    checks.append(working_tree_clean_check(project_root))
    checks.append(package_version_check(package_version, target_version))
    checks.append(release_notes_check(project_root, target_version))
    checks.append(local_tag_check(project_root, target_version))
    checks.append(remote_tag_check(project_root, target_version))
    checks.append(package_check_can_run(project_root))
    checks.append(release_check_can_run(project_root))
    checks.append(strict_doctor_can_run(project_root))
    checks.append(
        checklist_check(
            "github_release_page",
            "warning",
            "GitHub Release page is manual unless explicitly automated.",
            "Create or update the GitHub Release page manually after verification.",
        )
    )

    return {
        "overall_status": release_checklist_status(checks),
        "target_version": target_version,
        "package_version": package_version,
        "checks": checks,
    }


def normalize_release_version(version: str | None) -> str:
    """Normalize release versions to a leading-v tag."""
    if not version:
        return "unknown"
    normalized = version.strip()
    if not normalized:
        return "unknown"
    return normalized if normalized.startswith("v") else f"v{normalized}"


def release_version_number(target_version: str) -> str:
    """Return the bare semantic version for a normalized release target."""
    return target_version[1:] if target_version.startswith("v") else target_version


def read_project_version(project_root: Path) -> str | None:
    """Read project.version from pyproject.toml if available."""
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    version = payload.get("project", {}).get("version")
    return version if isinstance(version, str) and version else None


def checklist_check(
    name: str,
    status: str,
    message: str,
    advice: str,
) -> dict[str, str]:
    """Return one release checklist check."""
    return {
        "name": name,
        "status": status,
        "message": message,
        "advice": advice,
    }


def release_checklist_status(checks: list[dict[str, str]]) -> str:
    """Summarize checklist status."""
    statuses = {check["status"] for check in checks}
    if "failed" in statuses:
        return "failed"
    if "warning" in statuses or "skipped" in statuses:
        return "warning"
    return "ready"


def release_checklist_git(
    project_root: Path,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    """Run a local git command for release checklist inspection."""
    return subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )


def working_tree_clean_check(project_root: Path) -> dict[str, str]:
    """Check whether git status reports a clean working tree."""
    result = release_checklist_git(project_root, ["status", "--porcelain"])
    if result.returncode != 0:
        return checklist_check(
            "working_tree_clean",
            "failed",
            "Could not inspect working tree status.",
            "Run git status and resolve repository errors before release.",
        )
    if result.stdout.strip():
        return checklist_check(
            "working_tree_clean",
            "warning",
            "Working tree has uncommitted changes.",
            "Commit or discard local changes before creating a release tag.",
        )
    return checklist_check(
        "working_tree_clean",
        "passed",
        "Working tree is clean.",
        "No action needed.",
    )


def package_version_check(
    package_version: str | None,
    target_version: str,
) -> dict[str, str]:
    """Check package metadata version availability and target alignment."""
    if package_version is None:
        return checklist_check(
            "package_metadata_version",
            "failed",
            "Package metadata version was not found.",
            "Set project.version in pyproject.toml.",
        )
    expected = release_version_number(target_version)
    if expected != "unknown" and package_version != expected:
        return checklist_check(
            "package_metadata_version",
            "warning",
            (
                f"Package metadata version is {package_version}; "
                f"target is {target_version}."
            ),
            "Update package metadata or choose the matching --version target.",
        )
    return checklist_check(
        "package_metadata_version",
        "passed",
        f"Package metadata version is {package_version}.",
        "No action needed.",
    )


def release_notes_check(project_root: Path, target_version: str) -> dict[str, str]:
    """Check whether release notes exist for the target version."""
    notes_path = project_root / f"RELEASE_NOTES_{target_version}.md"
    if notes_path.exists():
        return checklist_check(
            "release_notes_file",
            "passed",
            f"Release notes found: {notes_path.name}.",
            "No action needed.",
        )
    return checklist_check(
        "release_notes_file",
        "failed",
        f"Release notes missing: {notes_path.name}.",
        "Create release notes before tagging.",
    )


def local_tag_check(project_root: Path, target_version: str) -> dict[str, str]:
    """Check whether the target tag exists locally."""
    result = release_checklist_git(project_root, ["tag", "--list", target_version])
    if result.returncode != 0:
        return checklist_check(
            "local_tag_exists",
            "warning",
            "Could not inspect local tags.",
            "Run git tag --list locally before release.",
        )
    if result.stdout.strip() == target_version:
        return checklist_check(
            "local_tag_exists",
            "passed",
            f"Local tag exists: {target_version}.",
            "No action needed.",
        )
    return checklist_check(
        "local_tag_exists",
        "warning",
        f"Local tag does not exist yet: {target_version}.",
        "Create the annotated tag only after final verification passes.",
    )


def remote_tag_check(project_root: Path, target_version: str) -> dict[str, str]:
    """Check whether the target tag exists on origin."""
    result = release_checklist_git(
        project_root,
        ["ls-remote", "origin", f"refs/tags/{target_version}"],
    )
    if result.returncode != 0:
        return checklist_check(
            "remote_tag_exists",
            "warning",
            "Could not inspect remote tag through git.",
            "Check network access and run git ls-remote origin manually.",
        )
    if result.stdout.strip():
        return checklist_check(
            "remote_tag_exists",
            "passed",
            f"Remote tag exists: {target_version}.",
            "No action needed.",
        )
    return checklist_check(
        "remote_tag_exists",
        "warning",
        f"Remote tag does not exist yet: {target_version}.",
        "Push the tag only after final verification passes.",
    )


def package_check_can_run(project_root: Path) -> dict[str, str]:
    """Check whether package-check passes."""
    result = run_package_check(project_root)
    if result.ready:
        return checklist_check(
            "package_check",
            "passed",
            "package-check passed.",
            "No action needed.",
        )
    return checklist_check(
        "package_check",
        "failed",
        "package-check did not pass.",
        "Run python -m vibebench package-check and address reported issues.",
    )


def release_check_can_run(project_root: Path) -> dict[str, str]:
    """Check whether release-check passes."""
    result = run_release_check(project_root)
    if result.ready:
        return checklist_check(
            "release_check",
            "passed",
            "release-check passed.",
            "No action needed.",
        )
    return checklist_check(
        "release_check",
        "failed",
        "release-check did not pass.",
        "Run python -m vibebench release-check and address reported issues.",
    )


def strict_doctor_can_run(project_root: Path) -> dict[str, str]:
    """Check whether doctor --strict passes."""
    result = run_doctor(project_root, strict=True, advice=False)
    if result.overall_status != "failed":
        return checklist_check(
            "doctor_strict",
            "passed",
            "doctor --strict passed.",
            "No action needed.",
        )
    return checklist_check(
        "doctor_strict",
        "failed",
        "doctor --strict did not pass.",
        "Run python -m vibebench doctor --strict and address reported issues.",
    )


def render_release_checklist(payload: dict[str, object]) -> None:
    """Render release checklist as a concise table."""
    console.print(f"[bold]VibeBench release checklist[/] ({payload['target_version']})")
    console.print(f"Overall status: {payload['overall_status']}")
    console.print(f"Package version: {payload['package_version'] or 'unknown'}")
    table = Table(title="Release checklist")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")
    table.add_column("Advice")
    for check in payload["checks"]:
        status = check["status"]
        style = "green" if status == "passed" else "yellow"
        if status == "failed":
            style = "red"
        table.add_row(
            check["name"],
            f"[{style}]{status}[/]",
            check["message"],
            check["advice"],
        )
    console.print(table)


@app.command()
def gate(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option("--run-dir", help="Specific run directory to evaluate."),
    ] = None,
    min_score: Annotated[
        int | None,
        typer.Option("--min-score", help="Override minimum acceptable VibeScore."),
    ] = None,
    max_risk: Annotated[
        str | None,
        typer.Option("--max-risk", help="Override maximum acceptable risk level."),
    ] = None,
    allow_findings: Annotated[
        int | None,
        typer.Option("--allow-findings", help="Override allowed risk finding count."),
    ] = None,
    require_status_passed: Annotated[
        bool | None,
        typer.Option("--require-status-passed/--no-require-status-passed"),
    ] = None,
    baseline: Annotated[
        bool,
        typer.Option("--baseline", help="Fail on regression against saved baseline."),
    ] = False,
    write_gate_summary: Annotated[
        bool,
        typer.Option("--write-gate-summary", help="Write gate-summary.md."),
    ] = False,
) -> None:
    """Evaluate a run against an explicit quality gate."""
    root = project_root.resolve()
    try:
        result = run_gate(
            root,
            run_dir=run_dir,
            min_score=min_score,
            max_risk=max_risk,
            allow_findings=allow_findings,
            require_status_passed=require_status_passed,
            use_baseline=baseline,
            write_gate_summary=write_gate_summary,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_gate_summary(result)
    if not result.passed:
        raise typer.Exit(code=1)


@app.command()
def baseline(
    project_root: ProjectRootOption = Path("."),
    legacy_set_run: Annotated[
        str | None,
        typer.Option(
            "--set",
            help="Save legacy baseline to 'latest' or a specific run id.",
        ),
    ] = None,
    set_latest: Annotated[
        bool,
        typer.Option("--set-latest", help="Pin the latest run as a labeled baseline."),
    ] = False,
    set_run: Annotated[
        str | None,
        typer.Option("--set-run", help="Pin a specific run id or path."),
    ] = None,
    promote_latest: Annotated[
        bool,
        typer.Option(
            "--promote-latest",
            help="Validate and promote the latest run as a labeled baseline.",
        ),
    ] = False,
    promote_run: Annotated[
        str | None,
        typer.Option("--promote-run", help="Validate and promote a run id or path."),
    ] = None,
    show: Annotated[
        bool,
        typer.Option("--show", help="Show a labeled pinned baseline."),
    ] = False,
    clear: Annotated[
        bool,
        typer.Option("--clear", help="Clear a labeled pinned baseline."),
    ] = False,
    list_baselines: Annotated[
        bool,
        typer.Option("--list", help="List labeled pinned baselines."),
    ] = False,
    verify_baseline: Annotated[
        bool,
        typer.Option("--verify", help="Verify a pinned or exported baseline."),
    ] = False,
    input_path: Annotated[
        Path | None,
        typer.Option("--input", help="Exported baseline JSON file to verify."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Fail baseline verification on warnings."),
    ] = False,
    require_portable: Annotated[
        bool,
        typer.Option(
            "--require-portable",
            help="Require a valid portable metrics snapshot.",
        ),
    ] = False,
    require_live_metrics: Annotated[
        bool,
        typer.Option(
            "--require-live-metrics",
            help="Require the original live metrics.json to be available.",
        ),
    ] = False,
    export_baseline: Annotated[
        bool,
        typer.Option("--export", help="Export a portable pinned baseline."),
    ] = False,
    import_baseline: Annotated[
        Path | None,
        typer.Option("--import", help="Import a portable pinned baseline JSON file."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write exported baseline JSON to PATH."),
    ] = None,
    include_local_paths: Annotated[
        bool,
        typer.Option(
            "--include-local-paths",
            help="Include local path metadata in exported baseline JSON.",
        ),
    ] = False,
    label: Annotated[
        str | None,
        typer.Option("--label", help="Pinned baseline label."),
    ] = None,
    runs_dir: Annotated[
        Path | None,
        typer.Option("--runs-dir", help="Directory containing VibeBench runs."),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print baseline status as pure JSON."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write baseline JSON to PATH."),
    ] = None,
    summary_output: Annotated[
        Path | None,
        typer.Option("--summary-output", help="Write baseline promotion Markdown."),
    ] = None,
    dry_run: Annotated[
        bool,
        (
            typer.Option(
                "--dry-run",
                help="Validate promotion without writing baseline state.",
            )
        ),
    ] = False,
    require_existing_baseline: Annotated[
        bool,
        typer.Option(
            "--require-existing-baseline",
            help="Fail promotion if the target label has no baseline yet.",
        ),
    ] = False,
    require_manifest: Annotated[
        bool,
        typer.Option("--require-manifest", help="Require manifest.json to exist."),
    ] = False,
    require_regression_pass: Annotated[
        bool,
        typer.Option(
            "--require-regression-pass/--no-require-regression-pass",
            help="Require regression-check to pass when a baseline exists.",
        ),
    ] = True,
    allow_regression_failure: Annotated[
        bool,
        typer.Option(
            "--allow-regression-failure",
            help="Allow promotion even when regression-check fails.",
        ),
    ] = False,
) -> None:
    """Show, set, list, or clear baseline run metadata."""
    root = project_root.resolve()
    selected_json_output = resolve_optional_output_path(root, json_output)
    selected_summary_output = resolve_optional_output_path(root, summary_output)
    selected_output = resolve_optional_output_path(root, output)
    selected_import = resolve_optional_output_path(root, import_baseline)
    selected_input = resolve_optional_output_path(root, input_path)
    promotion_requested = promote_latest or promote_run is not None
    selected_label = resolve_baseline_label(root, label, use_config=promotion_requested)
    pinned_action_requested = (
        any(
            [
                set_latest,
                set_run is not None,
                promotion_requested,
                show,
                clear,
                list_baselines,
                verify_baseline,
                input_path is not None,
                export_baseline,
                import_baseline is not None,
                as_json,
                json_output,
                summary_output,
            ]
        )
        or selected_label != "default"
    )
    action_count = sum(
        [
            bool(legacy_set_run is not None),
            set_latest,
            bool(set_run is not None),
            promote_latest,
            bool(promote_run is not None),
            verify_baseline,
            export_baseline,
            bool(import_baseline is not None),
            clear,
            list_baselines,
        ]
    )
    if input_path is not None and not verify_baseline:
        console.print("[red]--input can only be used with --verify.[/]")
        raise typer.Exit(code=1)
    if action_count > 1:
        console.print("[red]Choose only one baseline action.[/]")
        raise typer.Exit(code=1)

    try:
        list_result = None
        promotion_result = None
        verification_result = None
        operation_payload = None
        if legacy_set_run is not None and not pinned_action_requested:
            result = set_baseline(root, legacy_set_run, runs_dir=runs_dir)
            payload = baseline_status_payload(result)
        elif list_baselines:
            list_result = list_pinned_baselines(root)
            payload = baseline_list_payload(list_result)
            result = None
        elif selected_summary_output is not None and not (
            promotion_requested or verify_baseline
        ):
            raise ReportError(
                "--summary-output is only supported for promotion or verification."
            )
        elif verify_baseline:
            if selected_input is not None:
                verification_result = verify_baseline_input(
                    root,
                    selected_input,
                    expected_label=label,
                    strict=strict,
                    require_portable=require_portable,
                    require_live_metrics=require_live_metrics,
                )
            else:
                verification_result = verify_pinned_baseline(
                    root,
                    label=selected_label,
                    strict=strict,
                    require_portable=require_portable,
                    require_live_metrics=require_live_metrics,
                )
            payload = baseline_verification_payload(verification_result)
            result = None
        elif export_baseline:
            if selected_output is None:
                raise ReportError("--export requires --output PATH.")
            operation_payload = export_pinned_baseline(
                root,
                label=selected_label,
                output=selected_output,
                include_local_paths=include_local_paths,
            )
            payload = operation_payload
            result = None
        elif import_baseline is not None:
            if selected_import is None:
                raise ReportError("--import requires a PATH.")
            operation_payload = import_pinned_baseline(
                root,
                label=selected_label,
                input_path=selected_import,
            )
            payload = operation_payload
            result = None
        elif set_latest:
            result = set_pinned_baseline(
                root,
                "latest",
                label=selected_label,
                runs_dir=runs_dir,
                source="set-latest",
            )
            payload = baseline_status_payload(result)
        elif set_run is not None:
            result = set_pinned_baseline(
                root,
                set_run,
                label=selected_label,
                runs_dir=runs_dir,
                source="set-run",
            )
            payload = baseline_status_payload(result)
        elif promotion_requested:
            policy = resolve_regression_check_policy(
                root,
                baseline_label=selected_label,
            )
            promotion_result = promote_baseline(
                root,
                "latest" if promote_latest else str(promote_run),
                label=selected_label,
                runs_dir=runs_dir,
                source="promote-latest" if promote_latest else "promote-run",
                dry_run=dry_run,
                require_existing_baseline=require_existing_baseline,
                require_manifest=require_manifest,
                require_regression_pass=require_regression_pass,
                allow_regression_failure=allow_regression_failure,
                max_score_drop=float(policy["max_score_drop"]),
                max_risk_increase=float(policy["max_risk_increase"]),
                fail_on_missing_metrics=bool(policy["fail_on_missing_metrics"]),
                policy_source=str(policy["policy_source"]),
            )
            payload = promotion_payload(promotion_result)
            result = None
        elif clear:
            result = clear_pinned_baseline(root, label=selected_label)
            payload = baseline_status_payload(result)
        elif pinned_action_requested:
            result = show_pinned_baseline(root, label=selected_label)
            payload = baseline_status_payload(result)
        else:
            result = show_baseline(root)
            payload = baseline_status_payload(result)
    except ReportError as exc:
        target_console = err_console if as_json else console
        target_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if selected_json_output is not None:
        selected_json_output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if selected_summary_output is not None:
        selected_summary_output.write_text(
            baseline_verification_markdown(verification_result)
            if verification_result is not None
            else promotion_markdown(promotion_result),
            encoding="utf-8",
        )

    if as_json:
        if promotion_result is not None:
            print(promotion_json(promotion_result))
        elif verification_result is not None:
            print(baseline_verification_json(verification_result))
        else:
            print(json.dumps(payload, indent=2, sort_keys=True))
    elif verification_result is not None:
        render_baseline_verification_summary(verification_result)
        if selected_json_output is not None:
            console.print(f"Baseline JSON: {selected_json_output}")
        if selected_summary_output is not None:
            console.print(f"Baseline verification Markdown: {selected_summary_output}")
    elif operation_payload is not None:
        console.print(operation_payload["message"])
        if "output" in operation_payload:
            console.print(f"Baseline export: {operation_payload['output']}")
        if "baseline_path" in operation_payload:
            console.print(f"Baseline file: {operation_payload['baseline_path']}")
        if selected_json_output is not None:
            console.print(f"Baseline JSON: {selected_json_output}")
    elif promotion_result is not None:
        render_baseline_promotion_summary(promotion_result)
        if selected_json_output is not None:
            console.print(f"Baseline JSON: {selected_json_output}")
        if selected_summary_output is not None:
            console.print(f"Baseline promotion Markdown: {selected_summary_output}")
    elif list_result is not None:
        render_baseline_list_summary(list_result)
        if selected_json_output is not None:
            console.print(f"Baseline JSON: {selected_json_output}")
    else:
        render_baseline_summary(result)
        if selected_json_output is not None:
            console.print(f"Baseline JSON: {selected_json_output}")

    if promotion_result is not None and promotion_result.status == "failed":
        raise typer.Exit(code=1)
    if verification_result is not None and verification_result.status == "failed":
        raise typer.Exit(code=1)
    if result is not None and result.metadata is not None and not result.is_valid:
        raise typer.Exit(code=1)


@app.command()
def clean(
    project_root: ProjectRootOption = Path("."),
    keep: Annotated[
        int,
        typer.Option("--keep", help="Number of newest valid runs to preserve."),
    ] = 20,
    runs_dir: Annotated[
        Path | None,
        typer.Option("--runs-dir", help="Directory containing VibeBench runs."),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Actually delete cleanup candidates."),
    ] = False,
) -> None:
    """Safely clean old VibeBench run directories."""
    root = project_root.resolve()
    try:
        result = clean_runs(root, runs_dir=runs_dir, keep=keep, yes=yes)
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_clean_summary(result)


@app.command()
def history(
    project_root: ProjectRootOption = Path("."),
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            help="Maximum number of recent runs to show.",
        ),
    ] = 10,
    runs_dir: Annotated[
        Path | None,
        typer.Option(
            "--runs-dir",
            help="Specific directory containing VibeBench run directories.",
        ),
    ] = None,
) -> None:
    """Show recent VibeBench run history."""
    root = project_root.resolve()
    try:
        result = get_history(root, runs_dir=runs_dir, limit=limit)
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_history_summary(result)


@app.command()
def compare(
    project_root: ProjectRootOption = Path("."),
    runs_dir: Annotated[
        Path | None,
        typer.Option("--runs-dir", help="Directory containing VibeBench run dirs."),
    ] = None,
    base_run_dir: Annotated[
        Path | None,
        typer.Option(
            "--base-run-dir",
            "--base-run",
            help="Base .vibebench/runs/<timestamp> directory.",
        ),
    ] = None,
    head_run_dir: Annotated[
        Path | None,
        typer.Option(
            "--head-run-dir",
            "--head-run",
            "--current-run",
            help="Head .vibebench/runs/<timestamp> directory.",
        ),
    ] = None,
    base: Annotated[
        str | None,
        typer.Option("--base", help="Base run id under --runs-dir."),
    ] = None,
    head: Annotated[
        str | None,
        typer.Option("--head", help="Head run id under --runs-dir."),
    ] = None,
    baseline: Annotated[
        bool,
        typer.Option(
            "--baseline",
            help="Compare the saved baseline against the latest or head run.",
        ),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print comparison as pure JSON."),
    ] = False,
    write_json: Annotated[
        Path | None,
        typer.Option("--write-json", help="Write compare JSON to this path."),
    ] = None,
    write_summary: Annotated[
        Path | None,
        typer.Option("--write-summary", help="Write compare Markdown to this path."),
    ] = None,
    fail_on_regression: Annotated[
        bool,
        typer.Option(
            "--fail-on-regression",
            help="Exit non-zero when the comparison verdict is regressed.",
        ),
    ] = False,
) -> None:
    """Compare VibeBench runs."""
    root = project_root.resolve()
    selected_runs_dir = resolve_optional_output_path(root, runs_dir)
    selected_json_path = resolve_optional_output_path(root, write_json)
    selected_summary_path = resolve_optional_output_path(root, write_summary)
    selected_base_run = resolve_optional_output_path(root, base_run_dir)
    selected_head_run = resolve_optional_output_path(root, head_run_dir)
    try:
        result = compare_runs(
            root,
            head_run=selected_head_run,
            base_run=selected_base_run,
            use_baseline=baseline,
            runs_dir=selected_runs_dir,
            base_run_id=base,
            head_run_id=head,
            write_json_path=selected_json_path,
            write_summary_path=selected_summary_path,
            write_default_artifacts=True,
            fail_on_regression=fail_on_regression,
        )
    except ReportError as exc:
        target_console = err_console if as_json else console
        target_console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(json.dumps(compare_json_payload(result), indent=2, sort_keys=True))
        if result.regression_guard.status == "failed":
            raise typer.Exit(code=1)
        return

    render_compare_summary(result)
    if selected_json_path is not None:
        console.print(f"Compare JSON: {selected_json_path}")
    if selected_summary_path is not None:
        console.print(f"Compare summary: {selected_summary_path}")
    if result.regression_guard.status == "failed":
        raise typer.Exit(code=1)


def render_check_summary(result: CheckRunResult) -> None:
    """Render a concise Rich summary for a check run."""
    status_style = "green" if result.overall_status == "passed" else "red"
    risk_style = {
        "low": "green",
        "medium": "yellow",
        "high": "magenta",
        "critical": "red",
    }[result.risk_level]

    console.print()
    console.print(f"[bold]VibeBench check:[/] {result.project_name}")
    console.print(f"Status: [{status_style}]{result.overall_status}[/]")
    console.print(f"Score: [bold]{result.score}[/]")
    console.print(f"Risk: [{risk_style}]{result.risk_level}[/]")
    console.print(
        "Diff: "
        f"{result.diff_analysis.changed_file_count} files, "
        f"{result.diff_analysis.total_patch_lines} patch lines"
    )
    console.print(
        "Findings: "
        f"{result.summary.critical_findings} critical, "
        f"{result.summary.high_findings} high, "
        f"{result.summary.warning_findings} warning, "
        f"{result.summary.info_findings} info"
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("Group")
    table.add_column("Command")
    table.add_column("Status")
    table.add_column("Exit")
    table.add_column("Duration")

    for command in result.command_results:
        command_style = "green" if command.status == "passed" else "red"
        table.add_row(
            command.group,
            command.command,
            f"[{command_style}]{command.status}[/]",
            str(command.exit_code),
            f"{command.duration_seconds:.3f}s",
        )

    console.print(table)
    render_findings(result)
    console.print(f"Metrics: {result.metrics_path}")


def render_status_block_summary(result: StatusBlockResult) -> None:
    """Render a concise status block command summary."""
    console.print("Status block generated.")
    console.print(f"Run directory: {result.run_dir}")
    console.print(f"Output path: {result.output_path}")
    console.print(f"Title: {result.title}")


def update_status_block_readmes(
    project_root: Path,
    readme_paths: list[Path],
    status_content: str,
    *,
    write: bool,
    check: bool,
) -> list[ReadmeStatusBlockResult]:
    """Update or check requested README status blocks."""
    if not write and not check:
        return []

    results = []
    for readme_path in readme_paths:
        selected_path = (
            readme_path if readme_path.is_absolute() else project_root / readme_path
        ).resolve()
        results.append(
            update_readme_status_block(
                selected_path,
                status_content,
                write=write,
            )
        )
    return results


def render_status_block_readme_summary(
    results: list[ReadmeStatusBlockResult],
    *,
    check: bool,
) -> None:
    """Render README update/check results."""
    table = Table(title="README status block")
    table.add_column("README")
    table.add_column("Status")
    for result in results:
        if check:
            status = "current" if result.current else "stale"
        else:
            status = "updated" if result.changed else "already current"
        table.add_row(str(result.readme_path), status)
    console.print(table)


def render_trend_summary(result: TrendResult) -> None:
    """Render trend runs and aggregate summary."""
    console.print(f"Runs directory: {result.runs_dir}")
    if result.skipped_runs:
        for warning in result.skipped_runs:
            console.print(f"[yellow]{warning}[/]")
    if not result.runs:
        console.print("No valid VibeBench runs found.")
        return

    table = Table(title="VibeBench trend")
    table.add_column("Run")
    table.add_column("Status")
    table.add_column("Score", justify="right")
    table.add_column("Risk")
    table.add_column("Findings", justify="right")
    table.add_column("Files", justify="right")
    table.add_column("Patch", justify="right")
    for run in result.runs:
        table.add_row(
            run.run_id,
            run.overall_status,
            str(run.score),
            run.risk_level,
            str(run.risk_findings_count),
            str(run.changed_files),
            str(run.patch_lines),
        )
    console.print(table)

    summary = result.summary
    summary_table = Table(title="Trend summary")
    summary_table.add_column("Field")
    summary_table.add_column("Value")
    summary_table.add_row("Valid runs", str(summary.valid_run_count))
    summary_table.add_row("Pass rate", f"{summary.pass_rate * 100:.1f}%")
    summary_table.add_row("Latest score", optional_text(summary.latest_score))
    summary_table.add_row("Oldest score", optional_text(summary.oldest_score))
    summary_table.add_row("Score delta", optional_delta(summary.score_delta))
    summary_table.add_row("Best score", optional_text(summary.best_score))
    summary_table.add_row("Worst score", optional_text(summary.worst_score))
    summary_table.add_row("Highest risk", optional_text(summary.highest_risk_level))
    summary_table.add_row(
        "Latest findings", optional_text(summary.latest_finding_count)
    )
    summary_table.add_row(
        "Oldest findings", optional_text(summary.oldest_finding_count)
    )
    summary_table.add_row("Finding delta", optional_delta(summary.finding_count_delta))
    summary_table.add_row("Verdict", summary.verdict)
    console.print(summary_table)
    console.print(summary.message)


def optional_text(value: object) -> str:
    """Render an optional summary value."""
    return "n/a" if value is None else str(value)


def optional_delta(value: int | None) -> str:
    """Render an optional signed delta."""
    if value is None:
        return "n/a"
    if value > 0:
        return f"+{value}"
    return str(value)


def render_latest_paths(result: LatestRunResult) -> None:
    """Render available artifact paths for copy/paste use."""
    for item in available_artifacts(result):
        console.print(f"{artifact_label(item)}: {item.display_path.as_posix()}")


def render_latest_summary(
    result: LatestRunResult,
    selected_artifact: ArtifactItem | None,
) -> None:
    """Render latest run details."""
    console.print("\n[bold]VibeBench latest[/]")
    console.print(f"Run id: {result.run_id}")
    console.print(f"Run directory: {result.run_dir}")
    console.print(f"Status: {result.status}")
    console.print(f"VibeScore: {result.score}")
    console.print(f"Risk: {result.risk}")
    if result.created_at:
        console.print(f"Created at: {result.created_at}")
    if result.skipped_runs:
        console.print(f"Skipped corrupt runs: {len(result.skipped_runs)}")

    table = Table(title="Artifacts")
    table.add_column("Artifact")
    table.add_column("Path")
    table.add_column("Availability")
    table.add_column("Size")
    artifacts = (
        [selected_artifact]
        if selected_artifact is not None
        else result.inventory.artifacts
    )
    for item in artifacts:
        availability = "available" if item.available else "missing"
        size = (
            artifact_size_text(item.size_bytes) if item.size_bytes is not None else ""
        )
        table.add_row(item.name, item.display_path.as_posix(), availability, size)
    console.print(table)


def render_site_check_summary(payload: dict[str, object]) -> None:
    """Render a concise static site readiness summary."""
    status = str(payload["status"])
    status_style = "green" if status == "passed" else "red"
    checked_files = ", ".join(str(item) for item in payload["checked_files"])

    console.print()
    console.print("[bold]VibeBench site check[/]")
    console.print(f"Status: [{status_style}]{status}[/]")
    console.print(f"Root: {payload['root']}")
    console.print(f"Checked files: {checked_files}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Status", no_wrap=True)
    table.add_column("Message")
    for check in payload["checks"]:
        if not isinstance(check, dict):
            continue
        check_status = str(check["status"])
        check_style = "green" if check_status == "passed" else "red"
        table.add_row(
            str(check["name"]),
            f"[{check_style}]{check_status}[/]",
            str(check["message"]),
        )
    console.print(table)


def render_site_preview_summary(payload: dict[str, object]) -> None:
    """Render a concise static site preview summary."""
    status = str(payload["status"])
    status_style = "green" if status in {"ready", "passed"} else "red"
    console.print()
    console.print("[bold]VibeBench site preview[/]")
    console.print(f"Status: [{status_style}]{status}[/]")
    console.print(f"Root: {payload['root']}")
    if payload.get("output_dir"):
        console.print(f"Output directory: {payload['output_dir']}")
    if payload.get("zip_output"):
        console.print(f"Zip archive: {payload['zip_output']}")

    files = payload.get("included_files")
    if isinstance(files, list):
        table = Table(show_header=True, header_style="bold")
        table.add_column("Included file")
        for item in files:
            table.add_row(str(item))
        console.print(table)

    commands = payload.get("commands")
    if isinstance(commands, dict):
        console.print("Local preview: " + str(commands.get("local_preview", "")))
        console.print("Docs preview: " + str(commands.get("docs_preview", "")))
        console.print("Readiness: " + str(commands.get("readiness", "")))


def render_site_preview_verification(result: dict[str, object]) -> None:
    """Render static site preview verification output."""
    if result["verified"]:
        console.print("[green]Site preview verification passed.[/]")
    else:
        console.print("[red]Site preview verification failed.[/]")
    console.print(f"Target: {result['target']} ({result['target_type']})")
    for check in result["checks"]:
        item = check if isinstance(check, dict) else {}
        status = str(item.get("status", "unknown"))
        name = str(item.get("name", "check"))
        message = str(item.get("message", ""))
        style = "green" if status == "passed" else "red"
        console.print(f"- [{style}]{status}[/]: {name} - {message}")


def render_evidence_room_summary(payload: dict[str, object]) -> None:
    """Render a concise evidence room summary."""
    status = str(payload["status"])
    status_style = "green" if status in {"ready", "passed"} else "red"
    console.print()
    console.print("[bold]VibeBench evidence room[/]")
    console.print(f"Status: [{status_style}]{status}[/]")
    console.print(f"Root: {payload['root']}")
    if payload.get("output_dir"):
        console.print(f"Output directory: {payload['output_dir']}")
    if payload.get("zip_output"):
        console.print(f"Zip archive: {payload['zip_output']}")

    files = payload.get("files")
    if isinstance(files, list):
        table = Table(show_header=True, header_style="bold")
        table.add_column("Included file")
        for item in files:
            table.add_row(str(item))
        console.print(table)

    commands = payload.get("commands")
    if isinstance(commands, list):
        console.print("Local commands:")
        for command in commands:
            console.print(f"- {command}")


def render_evidence_room_verification(result: dict[str, object]) -> None:
    """Render evidence room verification output."""
    if result["verified"]:
        console.print("[green]Evidence room verification passed.[/]")
    else:
        console.print("[red]Evidence room verification failed.[/]")
    console.print(f"Target: {result['target']} ({result['target_type']})")
    for check in result["checks"]:
        item = check if isinstance(check, dict) else {}
        status = str(item.get("status", "unknown"))
        name = str(item.get("name", "check"))
        message = str(item.get("message", ""))
        style = "green" if status == "passed" else "red"
        console.print(f"- [{style}]{status}[/]: {name} - {message}")


def render_regression_check_summary(result: RegressionCheckResult) -> None:
    """Render a compact regression-check summary."""
    status_style = {
        "passed": "green",
        "failed": "red",
        "skipped": "yellow",
    }.get(result.status, "white")
    console.print()
    console.print("[bold]VibeBench Regression Check[/]")
    console.print(f"Status: [{status_style}]{result.status}[/]")
    console.print(f"Baseline run: {result.baseline_run_id or 'none'}")
    console.print(f"Baseline source: {result.baseline_source}")
    console.print(f"Baseline label: {result.baseline_label or 'none'}")
    console.print(f"Candidate run: {result.candidate_run_id or 'none'}")
    console.print(f"Message: {result.message}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Baseline")
    table.add_column("Candidate")
    table.add_column("Delta")
    table.add_row(
        "score",
        str(result.baseline_metrics.get("score", "")),
        str(result.candidate_metrics.get("score", "")),
        str(result.deltas.get("score_delta", "")),
    )
    table.add_row(
        "risk",
        str(result.baseline_metrics.get("risk_level", "")),
        str(result.candidate_metrics.get("risk_level", "")),
        str(result.deltas.get("risk_delta", "")),
    )
    console.print(table)

    for item in result.failures:
        console.print(f"[red]{item.code}[/]: {item.message}")
    for item in result.warnings:
        console.print(f"[yellow]{item.code}[/]: {item.message}")
    console.print(
        "Regression-check is a local quality gate, not a benchmark certification."
    )


def render_share_check_summary(result: ShareCheckResult) -> None:
    """Render a compact share-check summary."""
    payload = json.loads(share_check_json(result))
    summary = payload["summary"]
    status_style = "green" if result.status == "passed" else "red"
    console.print()
    console.print("[bold]VibeBench share-check[/]")
    console.print(f"Target: {result.target}")
    console.print(f"Target type: {result.target_type}")
    console.print(f"Checked files: {summary['checked_file_count']}")
    console.print(
        "Findings: "
        f"{summary['finding_count']} "
        f"(errors {summary['error_count']}, "
        f"warnings {summary['warning_count']}, "
        f"info {summary['info_count']})"
    )
    console.print(f"Status: [{status_style}]{result.status}[/]")

    if result.findings:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Severity")
        table.add_column("Code")
        table.add_column("File")
        table.add_column("Line")
        table.add_column("Message", overflow="fold")
        for item in result.findings:
            style = {
                "error": "red",
                "warning": "yellow",
                "info": "cyan",
            }.get(item.severity, "white")
            table.add_row(
                f"[{style}]{item.severity}[/]",
                item.code,
                item.file,
                str(item.line) if item.line is not None else "",
                item.message,
            )
        console.print(table)
        render_share_check_hints(sorted({item.code for item in result.findings}))
    else:
        console.print("No high-confidence sharing issues found.")

    console.print(
        "Reminder: share-check is a local pre-sharing aid, not a security "
        "certification, third-party audit, or guarantee."
    )


def render_share_check_hints(codes: list[str]) -> None:
    """Render remediation hints for finding codes."""
    hints = {
        "remote_url": "Use local relative assets or rerun with --allow-remote-urls.",
        "html_script_tag": "Remove scripts from static review HTML.",
        "html_remote_script": "Bundle scripts locally or remove them.",
        "html_remote_stylesheet": "Use inline CSS or local relative styles.",
        "html_remote_image": "Remove remote images or use local relative assets.",
        "html_iframe": "Remove iframe embeds from shareable review packages.",
        "absolute_home_path": "Replace machine-local paths with placeholders.",
        "absolute_users_path": "Replace machine-local paths with placeholders.",
        "absolute_data_code_path": "Replace project-local paths with placeholders.",
        "absolute_windows_user_path": "Replace machine-local paths with placeholders.",
        "absolute_windows_drive_path": "Replace drive paths with placeholders.",
        "absolute_tmp_path": "Use placeholders for temp paths unless clearly examples.",
        "github_token": "Revoke the token and remove it from artifacts.",
        "openai_api_key": "Revoke the key and remove it from artifacts.",
        "aws_access_key": "Rotate the key and remove it from artifacts.",
        "secret_assignment": "Remove secret assignments before sharing.",
        "password_assignment": "Remove password assignments before sharing.",
        "private_key_block": "Remove private key material before sharing.",
        "fake_trust_claim": "Replace unsupported claims with conservative non-claims.",
        "unsafe_zip_path": "Rebuild the zip with safe relative entry names.",
    }
    console.print("Remediation hints:")
    for code in codes:
        console.print(f"- {code}: {hints.get(code, 'Review this finding.')}")


def render_proof_summary(payload: dict[str, object]) -> None:
    """Render the visitor-facing local proof packet summary."""
    console.print("\n[bold]VibeBench Proof Packet[/]")
    console.print(str(payload["summary"]))
    console.print(
        "Codex-first / vibe-coding quality console; local-first and evidence-first."
    )
    console.print("\nRecommended next commands:")
    for command in payload["recommended_commands"]:
        console.print(f"- {command}")
    console.print("\nDocs and artifacts to inspect:")
    for doc in payload["recommended_docs"]:
        console.print(f"- {doc}")
    for artifact in payload["recommended_artifacts"][:3]:
        console.print(f"- {artifact}")
    console.print("\nHonest limitations:")
    for limit in payload["honest_limits"]:
        console.print(f"- {limit}")


def render_proof_verification(result: dict[str, object]) -> None:
    """Render proof packet verification output."""
    if result["verified"]:
        console.print("[green]Proof packet verification passed.[/]")
    else:
        console.print("[red]Proof packet verification failed.[/]")
    console.print(f"Target: {result['target']} ({result['target_type']})")
    for check in result["checks"]:
        item = check if isinstance(check, dict) else {}
        status = str(item.get("status", "unknown"))
        name = str(item.get("name", "check"))
        message = str(item.get("message", ""))
        console.print(f"- {status}: {name} - {message}")
    errors = result.get("errors") or []
    if errors:
        console.print("Errors:")
        for error in errors:
            console.print(f"- {error}")


def render_demo_summary(payload: dict[str, object]) -> None:
    """Render the local showcase demo summary."""
    console.print("\n[bold]VibeBench local showcase demo[/]")
    console.print(str(payload["description"]))
    console.print(f"Available: {payload['available']}")
    console.print(f"Sample artifact directory: {payload['sample_dir']}")
    if not payload["available"]:
        console.print("[yellow]Source-tree sample artifact pack is missing.[/]")

    table = Table(title="Included demo artifact pack")
    table.add_column("Artifact")
    table.add_column("Kind")
    table.add_column("Exists")
    for item in payload["artifacts"]:
        artifact = item if isinstance(item, dict) else {}
        table.add_row(
            str(artifact.get("path", "")),
            str(artifact.get("kind", "")),
            "yes" if artifact.get("exists") else "no",
        )
    console.print(table)

    if payload.get("output_dir"):
        console.print(f"Copied to: {payload['output_dir']}")
        copied_files = payload.get("copied_files") or []
        skipped_files = payload.get("skipped_files") or []
        conflicts = payload.get("conflicts") or []
        console.print(f"Copied files: {len(copied_files)}")
        console.print(f"Skipped files: {len(skipped_files)}")
        if conflicts:
            conflict_text = ", ".join(str(item) for item in conflicts)
            console.print(f"[red]Conflicting files: {conflict_text}[/]")
            console.print("Use --force to replace conflicting files under --copy-to.")

    console.print("\nUseful next commands:")
    for command in payload["commands"]:
        console.print(f"- {command}")


def render_manifest_summary(result: ManifestResult) -> None:
    """Render a concise manifest command summary."""
    console.print("Manifest written.")
    console.print(f"Run id: {result.run_id}")
    console.print(f"Run directory: {result.run_dir}")
    console.print(f"Output path: {result.output_path}")
    console.print(f"Status: {result.payload.get('status', 'unknown')}")
    console.print(f"Score: {result.payload.get('score', 0)}")
    console.print(f"Available artifacts: {result.available_artifact_count}")


def render_manifest_check_summary(result: ManifestCheckResult) -> None:
    """Render a concise manifest consistency check summary."""
    if result.passed:
        console.print(f"Manifest is consistent: {result.manifest_path}")
        return

    console.print("[red]Manifest drift detected:[/]")
    for difference in result.differences:
        console.print(f"- {difference}")


def render_artifacts_summary(result: ArtifactInventoryResult) -> None:
    """Render an artifact inventory table."""
    table = Table(title="VibeBench artifacts")
    table.add_column("Artifact")
    table.add_column("Path")
    table.add_column("Availability")
    table.add_column("Size")
    for item in result.artifacts:
        availability = "available" if item.available else "missing"
        size = (
            artifact_size_text(item.size_bytes) if item.size_bytes is not None else ""
        )
        table.add_row(
            item.name,
            item.display_path.as_posix(),
            availability,
            size,
        )
    console.print(f"Run directory: {result.run_dir}")
    console.print(table)


def artifact_size_text(size_bytes: int) -> str:
    """Format an artifact byte count for terminal output."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    size_kib = size_bytes / 1024
    if size_kib < 1024:
        return f"{size_kib:.1f} KiB"
    return f"{size_kib / 1024:.1f} MiB"


def render_badge_summary(result: BadgeResult) -> None:
    """Render a concise badge command summary."""
    console.print("Badge generated.")
    console.print(f"Run directory: {result.run_dir}")
    console.print(f"Output path: {result.output_path}")
    console.print(
        f"Badge: {result.label} | {result.message} | {result.color} | {result.format}"
    )


def render_export_summary(result: ExportResult) -> None:
    """Render export output or a concise write summary."""
    if result.output_path is None:
        print(result.content, end="")
        return
    console.print("Export written.")
    console.print(f"Run directory: {result.run_dir}")
    console.print(f"Output path: {result.output_path}")


def render_annotation_summary(result: AnnotationResult) -> None:
    """Render annotation output."""
    console.print(result.output, markup=False)


def render_ci_plan_artifact_summary(artifacts: object) -> None:
    """Render paths written for CI plan artifacts."""
    output_dir = getattr(artifacts, "output_dir", None)
    json_path = getattr(artifacts, "json_path", None)
    markdown_path = getattr(artifacts, "markdown_path", None)
    if output_dir is not None:
        console.print(f"CI plan directory: {output_dir}")
    if json_path is not None:
        console.print(f"CI plan JSON: {json_path}")
    if markdown_path is not None:
        console.print(f"CI plan Markdown: {markdown_path}")


def render_ci_summary(result: CiResult) -> None:
    """Render a concise CI pipeline summary."""
    console.print()
    title = "VibeBench CI plan" if result.dry_run else "VibeBench CI"
    console.print(f"[bold]{title}[/]")
    if result.dry_run:
        console.print("Dry run: no checks or artifacts will be executed.")
    if result.run_dir is not None:
        console.print(f"Run directory: {result.run_dir}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Step")
    table.add_column("Status")
    table.add_column("Exit")
    table.add_column("Artifact")
    table.add_column("Message", overflow="fold")
    status_style = {
        "passed": "green",
        "failed": "red",
        "skipped": "yellow",
        "planned": "cyan",
    }
    for step in result.steps:
        table.add_row(
            step.name,
            f"[{status_style[step.status]}]{step.status}[/]",
            str(step.exit_code) if step.exit_code is not None else "",
            str(step.artifact_path) if step.artifact_path else "",
            step.message,
        )
    console.print(table)

    if result.dry_run:
        console.print("Final CI verdict: [cyan]planned[/]")
        return
    verdict = "passed" if result.passed else "failed"
    style = "green" if result.passed else "red"
    console.print(f"Final CI verdict: [{style}]{verdict}[/]")


def render_doctor_summary(result: DoctorResult) -> None:
    """Render a concise Rich summary for doctor diagnostics."""
    console.print()
    title = "VibeBench Doctor (strict)" if result.strict else "VibeBench Doctor"
    console.print(f"[bold]{title}[/]")
    console.print(f"Project root: {result.project_root}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")
    if result.advice:
        table.add_column("Advice")
    status_style = {"passed": "green", "warning": "yellow", "failed": "red"}
    for check in result.checks:
        row = [
            check.category,
            f"[{status_style[check.status]}]{check.status}[/]",
            check.message,
        ]
        if result.advice:
            row.append(check.advice or "")
        table.add_row(*row)
    console.print(table)
    if result.advice:
        advice_items = [check for check in result.checks if check.advice]
        if advice_items:
            console.print("[bold]Advice[/]")
            for check in advice_items:
                console.print(f"- {check.category}: {check.advice}")


def resolve_optional_output_path(root: Path, output_path: Path | None) -> Path | None:
    """Resolve an optional CLI output path relative to project root."""
    if output_path is None:
        return None
    if output_path.is_absolute():
        return output_path.resolve()
    return (root / output_path).resolve()


def render_run_index_summary(result: RunIndexResult) -> None:
    """Render run index summary."""
    console.print()
    console.print("[bold]VibeBench Run Index[/]")
    console.print(f"Runs directory: {result.runs_dir}")
    console.print(f"Total run directories seen: {result.total_runs_seen}")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Run")
    table.add_column("Status")
    table.add_column("Score", justify="right")
    table.add_column("Risk")
    table.add_column("Artifacts", justify="right")
    table.add_column("Path")
    table.add_column("Message")
    for index, item in enumerate(result.runs):
        run_id = f"{item.run_id} (latest)" if index == 0 else item.run_id
        score = "" if item.score is None else str(item.score)
        artifacts = f"{item.available_artifacts}/{item.total_artifacts}"
        table.add_row(
            run_id,
            item.status,
            score,
            item.risk_level,
            artifacts,
            item.path.as_posix(),
            item.message,
        )
    if result.runs:
        console.print(table)
    else:
        console.print("No VibeBench run directories found.")


def render_package_check_summary(result: PackageReadinessResult) -> None:
    """Render package readiness summary."""
    console.print()
    console.print("[bold]VibeBench Package Check[/]")
    console.print(f"Project root: {result.project_root}")
    if result.package_name:
        console.print(f"Package: {result.package_name}")
    if result.version:
        console.print(f"Version: {result.version}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")
    if result.advice:
        table.add_column("Advice")
    status_style = {"passed": "green", "failed": "red"}
    for check in result.checks:
        row = [
            check.name,
            f"[{status_style[check.status]}]{check.status}[/]",
            check.message,
        ]
        if result.advice:
            row.append(check.advice or "")
        table.add_row(*row)
    console.print(table)
    if result.build is not None:
        tool = result.build.tool or "unavailable"
        console.print(f"Build readiness: {result.build.status} ({tool})")
        if result.build.advice and result.build.status == "failed":
            console.print(f"Build advice: {result.build.advice}")
    status_style_name = "green" if result.ready else "red"
    console.print(f"Package readiness: [{status_style_name}]{result.status}[/]")


def render_publish_check_summary(result: PublishReadinessResult) -> None:
    """Render publish readiness summary."""
    console.print()
    console.print("[bold]VibeBench Publish Check[/]")
    console.print(f"Project root: {result.project_root}")
    console.print(f"Package version: {result.package_version or 'unknown'}")

    show_advice = result.advice or result.overall_status != "ready"
    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")
    if show_advice:
        table.add_column("Advice")
    status_style = {"passed": "green", "warning": "yellow", "failed": "red"}
    for check in result.checks:
        row = [
            check.name,
            f"[{status_style[check.status]}]{check.status}[/]",
            check.message,
        ]
        if show_advice:
            row.append(check.advice or "")
        table.add_row(*row)
    console.print(table)

    final_style = {
        "ready": "green",
        "warning": "yellow",
        "failed": "red",
    }[result.overall_status]
    console.print(f"Publish readiness: [{final_style}]{result.overall_status}[/]")


def render_release_audit_verify_summary(result: ReleaseAuditVerifyResult) -> None:
    """Render a concise release audit verification summary."""
    console.print()
    console.print("[bold]VibeBench Release Audit Verification[/]")
    console.print(f"Target: {result.target}")
    console.print(f"Target type: {result.target_type}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")
    for check in result.checks:
        table.add_row(check.name, check.status, check.message)
    console.print(table)

    failed_checks = [check for check in result.checks if check.status == "failed"]
    if failed_checks:
        console.print("Failures:")
        for check in failed_checks:
            console.print(f"- {check.message}")

    style = "green" if result.status == "passed" else "red"
    console.print(f"Release audit verification: [{style}]{result.status}[/]")


def render_release_body_check_summary(result: ReleaseBodyResult) -> None:
    """Render a concise release body validation summary."""
    style = "green" if result.status == "passed" else "red"
    console.print(f"Release body check: [{style}]{result.status}[/]")
    for check in result.checks:
        if check.status == "failed":
            console.print(f"- {check.message}")


def render_release_audit_summary(result: ReleaseAuditResult) -> None:
    """Render a concise release audit summary."""
    console.print()
    console.print("[bold]VibeBench Release Audit[/]")
    console.print(f"Output directory: {result.output_dir}")
    console.print(f"Version: {result.version}")
    console.print(f"Generated at: {result.generated_at}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("File")
    table.add_column("Kind")
    table.add_column("Path")
    for item in result.files:
        table.add_row(item.name, item.kind, str(item.path))
    console.print(table)

    summary = Table(title="Status summary")
    summary.add_column("Check")
    summary.add_column("Status")
    summary.add_row("package-check", result.package_status)
    summary.add_row("publish-check", result.publish_status)
    summary.add_row("release-checklist", result.release_checklist_status)
    console.print(summary)

    console.print(
        "Local-only safety: no tag, GitHub Release, package upload, or version bump."
    )
    if result.archive.requested and result.archive.path is not None:
        console.print(f"Archive: {result.archive.path}")

    style = "red" if result.status == "failed" else "yellow"
    if result.status == "ready":
        style = "green"
    console.print(f"Release audit: [{style}]{result.status}[/]")


def render_release_check_summary(result: ReleaseReadinessResult) -> None:
    """Render release readiness summary."""
    console.print()
    console.print("[bold]VibeBench Release Check[/]")
    console.print(f"Project root: {result.project_root}")
    if result.latest_run_dir is not None:
        console.print(f"Latest run: {result.latest_run_dir}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")
    status_style = {"passed": "green", "failed": "red"}
    for check in result.checks:
        table.add_row(
            check.name,
            f"[{status_style[check.status]}]{check.status}[/]",
            check.message,
        )
    console.print(table)

    style = "green" if result.ready else "red"
    console.print(f"Release readiness: [{style}]{result.status}[/]")


def render_gate_summary(result: GateResult) -> None:
    """Render a concise quality gate summary."""
    status_style = "green" if result.passed else "red"
    console.print()
    console.print("[bold]VibeBench gate[/]")
    console.print(f"Run directory: {result.run_dir}")
    gate_status = "passed" if result.passed else "failed"
    console.print(f"Result: [{status_style}]{gate_status}[/]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Actual")
    table.add_column("Gate")
    table.add_row("Status", result.snapshot.overall_status, "passed")
    table.add_row(
        "Score",
        str(result.snapshot.score),
        f">= {result.thresholds.min_score}",
    )
    table.add_row(
        "Risk",
        result.snapshot.risk_level,
        f"<= {result.thresholds.max_risk}",
    )
    table.add_row(
        "Findings",
        str(result.snapshot.risk_findings_count),
        f"<= {result.thresholds.allow_findings}",
    )
    console.print(table)

    if result.baseline_used and result.baseline_snapshot is not None:
        baseline = result.baseline_snapshot
        console.print(
            "Baseline: "
            f"score {baseline.score}, risk {baseline.risk_level}, "
            f"findings {baseline.risk_findings_count}"
        )

    if result.reasons:
        reason_table = Table(
            show_header=True,
            header_style="bold",
            title="Gate Failures",
        )
        reason_table.add_column("Reason")
        for reason in result.reasons:
            reason_table.add_row(reason)
        console.print(reason_table)

    if result.summary_path is not None:
        console.print(f"Gate summary: {result.summary_path}")


def render_explain_summary(result: ExplainResult, *, write: bool) -> None:
    """Render a concise explanation command summary."""
    console.print()
    console.print("[bold]VibeBench explain[/]")
    console.print(f"Run directory: {result.run_dir}")
    if write and result.output_path is not None:
        console.print(f"Explanation: {result.output_path}")
    else:
        console.print("[yellow]Explanation was not written (--no-write).[/]")
        console.print()
        console.print(result.markdown)
    console.print(f"Recommendation: {result.recommendation}")


def render_bundle_summary(result: BundleResult) -> None:
    """Render a concise bundle command summary."""
    console.print()
    console.print("[bold]VibeBench bundle[/]")
    console.print(f"Run: {result.run_id}")
    console.print(f"Output: {result.output_path}")
    console.print(f"Size: {format_bytes(result.size_bytes)}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Included files")
    if result.included_files:
        for relative_path in result.included_files:
            table.add_row(str(relative_path))
    else:
        table.add_row("none")
    console.print(table)

    skipped_table = Table(show_header=True, header_style="bold")
    skipped_table.add_column("Skipped missing optional files")
    if result.skipped_files:
        for relative_path in result.skipped_files:
            skipped_table.add_row(str(relative_path))
    else:
        skipped_table.add_row("none")
    console.print(skipped_table)


def resolve_baseline_label(root: Path, label: str | None, *, use_config: bool) -> str:
    """Resolve baseline label, optionally using regression config."""
    if label is not None:
        return label
    if use_config:
        effective_config = load_effective_config(config_file(root))
        if effective_config.config.regression.baseline_label:
            return effective_config.config.regression.baseline_label
    return "default"


def render_metrics_check_summary(result: MetricsCheckResult) -> None:
    """Render metrics-check output."""
    style = "green" if result.status == "passed" else "yellow"
    if result.status == "failed":
        style = "red"
    console.print()
    console.print("[bold]VibeBench metrics check[/]")
    console.print(f"Status: [{style}]{result.status}[/]")
    console.print(f"Run dir: {result.run_dir or 'none'}")
    console.print(f"Metrics path: {result.metrics_path or 'none'}")
    console.print(f"Usable for regression: {str(result.usable_for_regression).lower()}")
    console.print(f"Usable as baseline: {str(result.usable_as_baseline).lower()}")
    table = Table(title="Metrics checks")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")
    for check in result.checks:
        check_style = "green" if check.status == "passed" else "yellow"
        if check.status == "failed":
            check_style = "red"
        table.add_row(check.name, f"[{check_style}]{check.status}[/]", check.message)
    console.print(table)
    if result.advice:
        advice_table = Table(title="Advice")
        advice_table.add_column("Item")
        for item in result.advice:
            advice_table.add_row(item)
        console.print(advice_table)


def render_metrics_diff_summary(result: MetricsDiffResult) -> None:
    """Render metrics-diff output."""
    style = "green" if result.status == "passed" else "yellow"
    if result.status == "failed":
        style = "red"
    console.print()
    console.print("[bold]VibeBench metrics diff[/]")
    console.print(f"Status: [{style}]{result.status}[/]")
    console.print(f"Baseline source: {result.baseline_source}")
    console.print(f"Baseline run: {result.baseline_run or 'none'}")
    console.print(f"Candidate run: {result.candidate_run or 'none'}")
    console.print(f"Message: {result.message}")

    counts = Table(title="Metrics diff summary")
    counts.add_column("Count")
    counts.add_column("Value", justify="right")
    counts.add_row("Compared numeric", str(result.summary.compared_numeric_count))
    counts.add_row("Improved", str(result.summary.improved_count))
    counts.add_row("Regressed", str(result.summary.regressed_count))
    counts.add_row("Changed", str(result.summary.changed_count))
    counts.add_row("Unchanged", str(result.summary.unchanged_count))
    counts.add_row("Added", str(result.summary.added_count))
    counts.add_row("Removed", str(result.summary.removed_count))
    console.print(counts)

    table = Table(title="Metric changes")
    table.add_column("Metric")
    table.add_column("Baseline")
    table.add_column("Candidate")
    table.add_column("Delta")
    table.add_column("Class")
    for change in result.changes[:20]:
        table.add_row(
            change.metric,
            str(change.baseline_value),
            str(change.candidate_value),
            str(change.delta),
            change.classification,
        )
    if not result.changes:
        table.add_row("none", "", "", "", "")
    console.print(table)
    if result.policy_status is not None:
        policy_table = Table(title="Metrics diff policy")
        policy_table.add_column("Metric")
        policy_table.add_column("Severity")
        policy_table.add_column("Rule")
        policy_table.add_column("Delta")
        policy_table.add_column("Threshold")
        policy_table.add_column("Message")
        if result.policy_findings:
            for finding in result.policy_findings:
                policy_table.add_row(
                    finding.metric,
                    finding.severity,
                    finding.rule,
                    str(finding.delta),
                    str(finding.threshold),
                    finding.message,
                )
        else:
            policy_table.add_row("none", "", "", "", "", "")
        console.print(
            f"Policy status: {result.policy_status}; "
            f"enforced={str(result.policy_enforced).lower()}"
        )
        console.print(policy_table)
    if result.warnings:
        warning_table = Table(title="Warnings")
        warning_table.add_column("Message")
        for warning in result.warnings:
            warning_table.add_row(warning)
        console.print(warning_table)
    if result.errors:
        error_table = Table(title="Errors")
        error_table.add_column("Message")
        for error in result.errors:
            error_table.add_row(error)
        console.print(error_table)


def render_baseline_verification_summary(result: BaselineVerificationResult) -> None:
    """Render baseline verification output."""
    style = "green" if result.status == "passed" else "yellow"
    if result.status == "failed":
        style = "red"
    console.print()
    console.print("[bold]VibeBench baseline verification[/]")
    console.print(f"Status: [{style}]{result.status}[/]")
    console.print(f"Label: {result.label or 'none'}")
    console.print(f"Run id: {result.run_id or 'none'}")
    console.print(f"Baseline path: {result.baseline_path}")
    console.print(f"Live metrics: {str(result.live_metrics_available).lower()}")
    console.print(f"Portable: {str(result.portable).lower()}")
    console.print(f"Usable for regression: {str(result.usable_for_regression).lower()}")
    table = Table(title="Verification checks")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")
    for check in result.checks:
        check_style = "green" if check.status == "passed" else "yellow"
        if check.status == "failed":
            check_style = "red"
        table.add_row(check.name, f"[{check_style}]{check.status}[/]", check.message)
    console.print(table)
    if result.advice:
        advice_table = Table(title="Advice")
        advice_table.add_column("Item")
        for item in result.advice:
            advice_table.add_row(item)
        console.print(advice_table)


def render_baseline_promotion_summary(result: BaselinePromotionResult) -> None:
    """Render baseline promotion output."""
    style = "green" if result.status in {"promoted", "planned"} else "red"
    console.print()
    console.print("[bold]VibeBench baseline promotion[/]")
    console.print(f"Status: [{style}]{result.status}[/]")
    console.print(f"Label: {result.label}")
    console.print(f"Candidate run: {result.candidate_run_id or 'none'}")
    console.print(f"Promotion happened: {str(result.baseline_written).lower()}")
    console.print(f"Promotion forced: {str(result.promotion_forced).lower()}")
    table = Table(title="Promotion checks")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")
    for check in result.checks:
        check_style = "green" if check.status == "passed" else "yellow"
        if check.status == "failed":
            check_style = "red"
        table.add_row(check.name, f"[{check_style}]{check.status}[/]", check.message)
    console.print(table)
    console.print(
        "Verify with: "
        f"python3 -m vibebench baseline --show --label {result.label} --json"
    )


def render_baseline_summary(result: BaselineStatus) -> None:
    """Render saved baseline metadata."""
    console.print()
    console.print("[bold]VibeBench baseline[/]")
    console.print(f"Baseline file: {result.baseline_path}")

    if result.metadata is None:
        console.print(f"[yellow]{result.message}[/]")
        return

    status_style = "green" if result.is_valid else "red"
    console.print(f"Status: [{status_style}]{result.message}[/]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    metadata = result.metadata
    table.add_row("Label", metadata.label)
    table.add_row("Source", metadata.source)
    table.add_row("Run", metadata.run_id)
    table.add_row("Run path", metadata.run_path)
    table.add_row("Metrics", metadata.metrics_path)
    table.add_row("Portable", str(result.snapshot_available).lower())
    table.add_row("Live metrics available", str(result.live_metrics_available).lower())
    table.add_row("Project", metadata.project or "")
    table.add_row("Created at", metadata.created_at or "")
    table.add_row("Overall status", metadata.status)
    table.add_row("Score", str(metadata.score))
    table.add_row("Risk", metadata.risk_level)
    table.add_row("Pinned at", metadata.pinned_at or "")
    table.add_row("Saved at", metadata.saved_at)
    console.print(table)


def render_baseline_list_summary(results: list[BaselineStatus]) -> None:
    """Render labeled pinned baselines."""
    console.print()
    console.print("[bold]VibeBench pinned baselines[/]")
    if not results:
        console.print("No pinned baselines saved.")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Label")
    table.add_column("Run")
    table.add_column("Status")
    table.add_column("Score")
    table.add_column("Risk")
    table.add_column("Portable")
    table.add_column("Message")
    for result in results:
        metadata = result.metadata
        table.add_row(
            metadata.label if metadata else result.baseline_path.stem,
            metadata.run_id if metadata else "",
            "valid" if result.is_valid else "stale" if metadata else "missing",
            str(metadata.score) if metadata else "",
            metadata.risk_level if metadata else "",
            str(result.snapshot_available).lower() if metadata else "",
            result.message,
        )
    console.print(table)


def render_clean_summary(result: CleanResult) -> None:
    """Render a safe cleanup summary."""
    console.print()
    console.print("[bold]VibeBench clean[/]")
    console.print(f"Runs directory: {result.runs_dir}")
    console.print(f"Mode: {'dry-run' if result.dry_run else 'delete'}")
    console.print(f"Keep count: {result.keep}")
    console.print(f"Total valid runs: {result.total_valid_runs}")
    console.print(f"Preserved count: {result.preserved_count}")
    console.print(f"Cleanup candidates: {len(result.candidates)}")
    console.print(
        f"Approximate candidate size: {format_bytes(result.total_candidate_size_bytes)}"
    )

    if not result.candidates:
        console.print("[green]Nothing to clean.[/]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Run", no_wrap=True)
    table.add_column("Size")
    table.add_column("Path")
    for candidate in result.candidates:
        table.add_row(
            candidate.run_id,
            format_bytes(candidate.size_bytes),
            str(candidate.path),
        )
    console.print(table)

    if result.dry_run:
        console.print(
            "[yellow]Dry run only. Re-run with --yes to delete these runs.[/]"
        )
    else:
        console.print(f"[green]Deleted {result.deleted_count} run(s).[/]")


def format_bytes(value: int) -> str:
    """Format a byte count for terminal output."""
    units = ["B", "KiB", "MiB", "GiB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"


def render_history_summary(result: HistoryResult) -> None:
    """Render a concise Rich table for recent run history."""
    console.print()
    console.print("[bold]VibeBench history[/]")
    console.print(f"Runs directory: {result.runs_dir}")

    if not result.runs:
        console.print(
            "[yellow]No VibeBench runs found. Run 'vibebench check' first.[/]"
        )
        return

    for warning in result.warnings:
        console.print(f"[yellow]Warning:[/] {warning}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Run", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Score")
    table.add_column("Risk", no_wrap=True)
    table.add_column("Files")
    table.add_column("Patch")
    table.add_column("Find")
    table.add_column("Artifacts")

    status_style = {"passed": "green", "failed": "red"}
    risk_style = {
        "low": "green",
        "medium": "yellow",
        "high": "magenta",
        "critical": "red",
    }
    for run in result.runs:
        table.add_row(
            run.run_id,
            f"[{status_style.get(run.overall_status, 'white')}]{run.overall_status}[/]",
            str(run.score),
            f"[{risk_style.get(run.risk_level, 'white')}]{run.risk_level}[/]",
            str(run.changed_files),
            str(run.patch_lines),
            str(run.risk_findings_count),
            artifact_flags(run),
        )
    console.print(table)


def artifact_flags(run: HistoryRun) -> str:
    """Format generated artifact markers."""
    return " ".join(
        [
            f"report:{plain_yes_no(run.has_report)}",
            f"pr:{plain_yes_no(run.has_pr_comment)}",
            f"gh:{plain_yes_no(run.has_github_summary)}",
            f"cmp:{plain_yes_no(run.has_compare)}",
        ]
    )


def plain_yes_no(value: bool) -> str:
    """Format a boolean artifact marker."""
    return "yes" if value else "no"


def render_compare_summary(result: CompareResult) -> None:
    """Render a concise Rich summary for a run comparison."""
    verdict_style = {
        "improved": "green",
        "stable": "blue",
        "regressed": "red",
        "mixed": "yellow",
        "insufficient-data": "yellow",
    }[result.verdict]

    console.print()
    console.print("[bold]VibeBench compare[/]")
    console.print(f"Base run: {result.base_run_id or 'n/a'}")
    console.print(f"Head run: {result.head_run_id or 'n/a'}")
    console.print(f"Verdict: [{verdict_style}]{result.verdict}[/]")
    if result.regression_guard.enabled:
        guard_style = "red" if result.regression_guard.status == "failed" else "green"
        console.print(
            "Regression guard: "
            f"[{guard_style}]{result.regression_guard.status}[/] - "
            f"{result.regression_guard.message}"
        )
    if result.status == "insufficient-data":
        for warning in result.skipped_runs:
            console.print(f"[yellow]{warning}[/]")
        console.print(f"Recommendation: {result.recommendation}")
        return

    console.print(f"Score delta: {format_optional_signed(result.score_delta)}")
    console.print(f"Risk level change: {result.risk_level_change}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Base")
    table.add_column("Head")
    table.add_column("Delta")
    for metric in result.metrics:
        table.add_row(metric.name, metric.base, metric.head, metric.delta)
    console.print(table)

    if result.command_status_changes:
        console.print(f"Command status changes: {len(result.command_status_changes)}")
    if result.artifact_availability_changes:
        console.print(
            "Artifact availability changes: "
            f"{len(result.artifact_availability_changes)}"
        )
    console.print(f"Recommendation: {result.recommendation}")
    if result.summary_path is not None:
        console.print(f"Comparison summary: {result.summary_path}")
    if result.json_path is not None:
        console.print(f"Comparison JSON: {result.json_path}")


def format_signed(value: int) -> str:
    """Format a signed integer for terminal output."""
    if value > 0:
        return f"+{value}"
    return str(value)


def format_optional_signed(value: int | None) -> str:
    """Format an optional signed integer for terminal output."""
    if value is None:
        return "n/a"
    return format_signed(value)


def render_findings(result: CheckRunResult) -> None:
    """Render concise risk findings."""
    visible_findings = [
        finding
        for finding in result.risk_findings
        if finding.severity in {"critical", "high", "warning"}
    ]
    if not visible_findings:
        return

    table = Table(show_header=True, header_style="bold", title="Risk Findings")
    table.add_column("Severity")
    table.add_column("Code")
    table.add_column("Message")
    table.add_column("Paths")

    severity_style = {"critical": "red", "high": "magenta", "warning": "yellow"}
    for finding in visible_findings:
        paths = ", ".join(finding.paths[:3]) if finding.paths else ""
        if len(finding.paths) > 3:
            paths = f"{paths}, +{len(finding.paths) - 3} more"
        table.add_row(
            f"[{severity_style[finding.severity]}]{finding.severity}[/]",
            finding.code,
            finding.message,
            paths,
        )

    console.print(table)


def main() -> None:
    """CLI entry point."""
    app()
