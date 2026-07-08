"""Read-only preflight readiness summary for VibeBench adoption."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vibebench.config import ConfigError, default_config_model, load_effective_config
from vibebench.onboard import onboard_payload
from vibebench.paths import config_file
from vibebench.project_scan import run_project_scan
from vibebench.workflow_check import workflow_check_payload
from vibebench.workflow_template import (
    DEFAULT_WORKFLOW_INSTALL_COMMAND,
    WORKFLOW_PROFILES,
    WORKFLOW_RELATIVE_PATH,
    workflow_template_payload,
)

PREFLIGHT_JSON = "preflight.json"
PREFLIGHT_SUMMARY = "preflight.md"


def preflight_payload(
    project_root: Path,
    *,
    profile: str = "auto",
    strict: bool = False,
    enforce_policy: bool = False,
    required_ci_modes: list[str] | None = None,
) -> dict[str, Any]:
    """Return a deterministic read-only preflight payload."""
    root = project_root.resolve()
    if profile not in WORKFLOW_PROFILES:
        allowed = ", ".join(sorted(WORKFLOW_PROFILES))
        raise ConfigError(
            f"Unknown preflight profile '{profile}'. Choose one of: {allowed}."
        )

    scan = run_project_scan(root)
    onboard = onboard_payload(root)
    workflow_template = workflow_template_payload(
        root,
        root / WORKFLOW_RELATIVE_PATH,
        profile=profile,
        ci_mode="basic",
        install_command=DEFAULT_WORKFLOW_INSTALL_COMMAND,
        write=False,
        dry_run=False,
        force=False,
    )
    workflow_check = workflow_check_payload(
        root,
        strict=False,
        check_all=True,
        required_ci_modes=required_ci_modes,
    )
    discovered_paths = [
        str(path)
        for path in workflow_check.get("discovered_paths", [])
        if isinstance(path, str)
    ]
    workflow_count = len(discovered_paths)
    actionable_signal = has_actionable_signal(scan, workflow_count=workflow_count)
    config_required = actionable_signal
    workflow_check_strict = (
        workflow_check_payload(
            root,
            strict=True,
            check_all=True,
            required_ci_modes=required_ci_modes,
        )
        if strict and workflow_count
        else None
    )
    strict_failed = strict and preflight_strict_failed(
        scan,
        actionable_signal=actionable_signal,
        config_required=config_required,
        workflow_count=workflow_count,
        workflow_check_strict=workflow_check_strict,
    )
    status = preflight_status(
        scan,
        actionable_signal=actionable_signal,
        workflow_count=workflow_count,
        workflow_check=workflow_check,
    )
    command_sequence = suggested_commands(
        config_exists=bool(scan["config_present"]),
        workflow_count=workflow_count,
        profile=profile,
    )
    recommendations = preflight_recommendations(
        scan,
        actionable_signal=actionable_signal,
        workflow_count=workflow_count,
        workflow_check=workflow_check,
    )
    config_section = {
        "exists": bool(scan["config_present"]),
        "valid": bool(scan["config_valid"]),
        "path": str(scan["config_path"]),
        "message": str(scan["config_message"]),
    }
    project_scan_section = {
        "status": str(scan["status"]),
        "readiness": str(scan["status"]),
        "summary": {
            "finding_count": len(scan.get("findings", [])),
            "warning_count": count_findings(scan, severity="warning"),
            "error_count": count_findings(scan, severity="error"),
        },
    }
    onboard_section = {
        "status": str(onboard["status"]),
        "recommended_next_steps": list(onboard.get("suggested_commands", [])),
        "next_step": str(onboard.get("next_step") or ""),
    }
    workflow_template_section = {
        "preview_available": True,
        "status": str(workflow_template["status"]),
        "output_path": str(workflow_template["output_path"]),
        "intended_path": str(workflow_template["target_path"]),
        "ci_mode": str(workflow_template["ci_mode"]),
        "requested_profile": str(workflow_template["profile"]),
        "resolved_profile": str(workflow_template["resolved_profile"]),
    }
    workflow_check_section = {
        "discovered": discovered_paths,
        "status": str(workflow_check["status"]),
        "workflow_count": workflow_count,
        "usable_for_vibebench_ci": bool(workflow_check["usable_for_vibebench_ci"]),
        "summary": workflow_check["summary"],
    }
    if workflow_check.get("required_ci_modes"):
        workflow_check_section["detected_ci_modes"] = list(
            workflow_check.get("detected_ci_modes", [])
        )
        workflow_check_section["required_ci_modes"] = list(
            workflow_check.get("required_ci_modes", [])
        )
        workflow_check_section["missing_required_ci_modes"] = list(
            workflow_check.get("missing_required_ci_modes", [])
        )
    payload: dict[str, Any] = {
        "status": status,
        "strict": strict,
        "strict_failed": strict_failed,
        "project_root": str(root),
        "generated_at": generated_at(),
        "requested_profile": profile,
        "resolved_profile": str(workflow_template["resolved_profile"]),
        "detected_stacks": list(scan["detected_stacks"]),
        "detection_reasons": list(scan["detection_reasons"]),
        "config": config_section,
        "project_scan": project_scan_section,
        "onboard": onboard_section,
        "workflow_template": workflow_template_section,
        "workflow_check": workflow_check_section,
        "actionable_project_signal": actionable_signal,
        "recommendations": recommendations,
        "commands": command_sequence,
        "message": preflight_message(status),
    }
    if workflow_check_strict is not None:
        payload["workflow_check"]["strict_status"] = str(
            workflow_check_strict["status"]
        )
        payload["workflow_check"]["strict_summary"] = workflow_check_strict[
            "summary"
        ]
    if strict_failed:
        payload["strict_message"] = "Preflight is not ready for safe adoption."
    if enforce_policy:
        attach_preflight_policy(payload, root, enforced=True)
    return payload


def generated_at() -> str:
    """Return a stable UTC timestamp string for report generation."""
    return (
        datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def has_actionable_signal(scan: dict[str, Any], *, workflow_count: int) -> bool:
    """Return whether the project has enough local signals for guided adoption."""
    return bool(
        scan.get("config_present")
        or scan.get("detected_stacks")
        or workflow_count
        or scan.get("package_json_present")
        or scan.get("pyproject_present")
        or scan.get("requirements_present")
        or scan.get("setup_present")
        or scan.get("tests_dir_present")
    )


def preflight_status(
    scan: dict[str, Any],
    *,
    actionable_signal: bool,
    workflow_count: int,
    workflow_check: dict[str, Any],
) -> str:
    """Return a concise preflight readiness status."""
    if scan.get("status") == "blocked":
        return "blocked"
    if not actionable_signal:
        return "unknown"
    if not scan.get("config_present"):
        return "needs_init"
    if scan.get("status") == "needs_attention":
        return "needs_attention"
    if workflow_count and workflow_needs_attention(workflow_check):
        return "needs_attention"
    return "ready"


def workflow_needs_attention(workflow_check: dict[str, Any]) -> bool:
    """Return whether discovered workflows need follow-up review."""
    summary = workflow_check.get("summary")
    if not isinstance(summary, dict):
        return False
    return bool(summary.get("warning") or summary.get("failed"))


def preflight_strict_failed(
    scan: dict[str, Any],
    *,
    actionable_signal: bool,
    config_required: bool,
    workflow_count: int,
    workflow_check_strict: dict[str, Any] | None,
) -> bool:
    """Return whether strict preflight should fail."""
    if scan.get("status") == "blocked":
        return True
    if not actionable_signal:
        return True
    if config_required and not scan.get("config_present"):
        return True
    if workflow_count and workflow_check_strict is not None:
        return str(workflow_check_strict.get("status") or "") == "failed"
    return False


def preflight_recommendations(
    scan: dict[str, Any],
    *,
    actionable_signal: bool,
    workflow_count: int,
    workflow_check: dict[str, Any],
) -> list[str]:
    """Return concise next actions for a safe adoption path."""
    recommendations: list[str] = []
    if not actionable_signal:
        recommendations.append(
            "Add Python or Node project markers, or choose a profile "
            "before initialization."
        )
    if scan.get("config_present") and not scan.get("config_valid"):
        recommendations.append(
            "Fix .vibebench/config.yaml before running CI commands."
        )
    elif not scan.get("config_present") and actionable_signal:
        recommendations.append("Initialize VibeBench before enabling CI commands.")
    else:
        recommendations.append(
            "Validate the existing VibeBench config before CI adoption."
        )
    if workflow_count:
        if workflow_needs_attention(workflow_check):
            recommendations.append(
                "Review existing workflows with workflow-check before relying on them."
            )
        else:
            recommendations.append(
                "Keep the existing workflow review-only until CI output looks correct."
            )
    else:
        recommendations.append(
            "Preview or write a conservative workflow only after config looks correct."
        )
    recommendations.append("Run ci --dry-run before the first full ci execution.")
    return dedupe(recommendations)


def suggested_commands(
    *,
    config_exists: bool,
    workflow_count: int,
    profile: str,
) -> list[str]:
    """Return a safe command sequence for adoption."""
    commands: list[str] = []
    if not config_exists:
        commands.append(f"python3 -m vibebench init --profile {profile}")
    commands.append("python3 -m vibebench config --check")
    if workflow_count:
        commands.append("python3 -m vibebench workflow-check --strict")
    else:
        commands.append("python3 -m vibebench workflow-template --write")
    commands.extend(
        [
            "python3 -m vibebench ci --dry-run",
            "python3 -m vibebench ci",
        ]
    )
    return commands


def dedupe(items: list[str]) -> list[str]:
    """Return items in first-seen order without duplicates."""
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def count_findings(scan: dict[str, Any], *, severity: str) -> int:
    """Count scan findings by severity."""
    findings = scan.get("findings") or []
    return sum(
        1
        for finding in findings
        if isinstance(finding, dict) and finding.get("severity") == severity
    )


def preflight_message(status: str) -> str:
    """Return a short status message for human and JSON output."""
    if status == "blocked":
        return "Preflight found blocking readiness issues."
    if status == "unknown":
        return "Preflight found no actionable project signal yet."
    if status == "needs_init":
        return "Preflight found a detectable project, but no VibeBench config yet."
    if status == "needs_attention":
        return "Preflight found follow-up items before CI adoption."
    return "Preflight found a safe path to start VibeBench adoption."



def attach_preflight_policy(
    payload: dict[str, Any],
    project_root: Path,
    *,
    enforced: bool,
) -> None:
    """Attach preflight policy evaluation fields to an aggregate payload."""
    policy_source, effective_policy, config_exists = resolve_preflight_policy(
        project_root
    )
    policy_findings = evaluate_preflight_policy(
        payload,
        effective_policy,
        config_exists=config_exists,
    )
    payload["policy_enforced"] = enforced
    payload["policy_status"] = "failed" if policy_findings else "passed"
    payload["policy_source"] = policy_source
    payload["effective_policy"] = effective_policy
    payload["policy"] = effective_policy
    payload["policy_findings"] = policy_findings


def resolve_preflight_policy(project_root: Path) -> tuple[str, dict[str, Any], bool]:
    """Return the effective preflight policy, source, and config presence."""
    try:
        result = load_effective_config(config_file(project_root))
        policy = result.config.preflight.policy.model_dump()
        raw_source = result.sources.get("preflight", "built-in defaults")
        source = "config" if raw_source == "config file" else raw_source
        return source, policy, result.config_exists
    except ConfigError:
        return (
            "built-in defaults",
            default_config_model().preflight.policy.model_dump(),
            False,
        )


def evaluate_preflight_policy(
    payload: dict[str, Any],
    policy: dict[str, Any],
    *,
    config_exists: bool,
) -> list[dict[str, str]]:
    """Evaluate preflight policy against an existing aggregate payload."""
    findings: list[dict[str, str]] = []
    severity_findings = preflight_severity_findings(payload)

    if policy.get("require_config") and not config_exists:
        findings.append(
            preflight_policy_finding(
                "config_required",
                "error",
                "VibeBench config is required",
                "No usable .vibebench/config.yaml file exists for this project.",
                "Run python3 -m vibebench init --profile auto, then config --check.",
                "require_config",
            )
        )

    if policy.get("require_project_scan_ready") and not project_scan_ready(payload):
        status = nested_status(payload, "project_scan")
        findings.append(
            preflight_policy_finding(
                "project_scan_ready_required",
                "error",
                "Project-scan readiness is required",
                f"project_scan.readiness is {status!r}, not ready.",
                "Resolve project-scan findings or relax preflight.policy.",
                "require_project_scan_ready",
            )
        )

    if policy.get("require_onboard_ready") and not onboard_ready(payload):
        status = nested_status(payload, "onboard")
        findings.append(
            preflight_policy_finding(
                "onboard_ready_required",
                "error",
                "Onboard readiness is required",
                f"onboard.status is {status!r}, not ready.",
                "Resolve onboarding warnings or relax preflight.policy.",
                "require_onboard_ready",
            )
        )

    if policy.get("require_workflow_check_ready") and not workflow_check_ready(payload):
        workflow = payload.get("workflow_check") or {}
        status = (
            str(workflow.get("status") or "") if isinstance(workflow, dict) else ""
        )
        usable = (
            workflow.get("usable_for_vibebench_ci")
            if isinstance(workflow, dict)
            else False
        )
        findings.append(
            preflight_policy_finding(
                "workflow_check_ready_required",
                "error",
                "Workflow-check readiness is required",
                (
                    "workflow_check.usable_for_vibebench_ci is "
                    f"{str(bool(usable)).lower()} with status {status!r}."
                ),
                "Add or fix a VibeBench CI workflow, or relax preflight.policy.",
                "require_workflow_check_ready",
            )
        )

    if policy.get("require_workflow_template_ready") and not workflow_template_ready(
        payload
    ):
        status = nested_status(payload, "workflow_template")
        findings.append(
            preflight_policy_finding(
                "workflow_template_ready_required",
                "error",
                "Workflow-template readiness is required",
                f"workflow_template.status is {status!r}, not ready.",
                "Fix workflow-template preview inputs or relax preflight.policy.",
                "require_workflow_template_ready",
            )
        )

    if policy.get("fail_on_blockers"):
        for finding in severity_findings:
            if finding["level"] == "blocker":
                findings.append(severity_policy_finding(finding, "fail_on_blockers"))
    if policy.get("fail_on_errors"):
        for finding in severity_findings:
            if finding["level"] == "error":
                findings.append(severity_policy_finding(finding, "fail_on_errors"))
    if policy.get("fail_on_warnings"):
        for finding in severity_findings:
            if finding["level"] == "warning":
                findings.append(severity_policy_finding(finding, "fail_on_warnings"))
    return dedupe_policy_findings(findings)


def preflight_severity_findings(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Return blocker/error/warning findings from the aggregate payload."""
    findings: list[dict[str, str]] = []
    status = str(payload.get("status") or "")
    if status == "blocked":
        findings.append(
            {
                "id": "preflight_status_blocked",
                "level": "blocker",
                "title": "Preflight status is blocked",
                "message": str(payload.get("message") or "Preflight is blocked."),
            }
        )
    project_scan = payload.get("project_scan") or {}
    if isinstance(project_scan, dict):
        readiness = str(
            project_scan.get("readiness") or project_scan.get("status") or ""
        )
        if readiness == "blocked":
            findings.append(
                {
                    "id": "project_scan_blocked",
                    "level": "blocker",
                    "title": "Project-scan readiness is blocked",
                    "message": "project_scan.readiness is blocked.",
                }
            )
        summary = project_scan.get("summary") or {}
        if isinstance(summary, dict):
            if int(summary.get("error_count") or 0):
                findings.append(
                    {
                        "id": "project_scan_errors",
                        "level": "error",
                        "title": "Project-scan has error findings",
                        "message": (
                            "project_scan.summary.error_count="
                            f"{summary.get('error_count')}"
                        ),
                    }
                )
            if int(summary.get("warning_count") or 0):
                findings.append(
                    {
                        "id": "project_scan_warnings",
                        "level": "warning",
                        "title": "Project-scan has warning findings",
                        "message": (
                            "project_scan.summary.warning_count="
                            f"{summary.get('warning_count')}"
                        ),
                    }
                )
    workflow_check = payload.get("workflow_check") or {}
    if isinstance(workflow_check, dict):
        summary = workflow_check.get("summary") or {}
        if isinstance(summary, dict):
            if int(summary.get("failed") or 0):
                findings.append(
                    {
                        "id": "workflow_check_errors",
                        "level": "error",
                        "title": "Workflow-check has failed checks",
                        "message": (
                            "workflow_check.summary.failed="
                            f"{summary.get('failed')}"
                        ),
                    }
                )
            if int(summary.get("warning") or 0):
                findings.append(
                    {
                        "id": "workflow_check_warnings",
                        "level": "warning",
                        "title": "Workflow-check has warning checks",
                        "message": (
                            "workflow_check.summary.warning="
                            f"{summary.get('warning')}"
                        ),
                    }
                )
    return findings


def project_scan_ready(payload: dict[str, Any]) -> bool:
    """Return whether project-scan readiness is acceptable for policy."""
    status = nested_status(payload, "project_scan", fallback_key="readiness")
    return status in {"ready", "needs_attention"}


def onboard_ready(payload: dict[str, Any]) -> bool:
    """Return whether onboard readiness is acceptable for policy."""
    return nested_status(payload, "onboard") == "ready"


def workflow_check_ready(payload: dict[str, Any]) -> bool:
    """Return whether workflow-check readiness is acceptable for policy."""
    section = payload.get("workflow_check") or {}
    if not isinstance(section, dict):
        return False
    if int(section.get("workflow_count") or 0) == 0:
        return True
    return bool(section.get("usable_for_vibebench_ci"))


def workflow_template_ready(payload: dict[str, Any]) -> bool:
    """Return whether workflow-template preview readiness is acceptable."""
    section = payload.get("workflow_template") or {}
    return isinstance(section, dict) and bool(section.get("preview_available"))


def nested_status(
    payload: dict[str, Any],
    key: str,
    *,
    fallback_key: str = "status",
) -> str:
    """Return a nested status/readiness field from a preflight section."""
    section = payload.get(key) or {}
    if not isinstance(section, dict):
        return ""
    return str(section.get(fallback_key) or section.get("status") or "")


def severity_policy_finding(
    finding: dict[str, str],
    rule: str,
) -> dict[str, str]:
    """Convert an aggregate severity signal into a policy finding."""
    level = finding["level"]
    severity = "warning" if level == "warning" else "error"
    return preflight_policy_finding(
        finding["id"],
        severity,
        finding["title"],
        finding["message"],
        f"Resolve the {level} signal or relax preflight.policy.{rule}.",
        rule,
    )


def preflight_policy_finding(
    finding_id: str,
    severity: str,
    title: str,
    message: str,
    recommendation: str,
    rule: str,
) -> dict[str, str]:
    """Return a deterministic preflight policy finding."""
    return {
        "id": finding_id,
        "severity": severity,
        "title": title,
        "message": message,
        "recommendation": recommendation,
        "rule": rule,
    }


def dedupe_policy_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return policy findings without duplicate id/rule pairs."""
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for finding in findings:
        key = (finding["id"], finding["rule"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def preflight_json(payload: dict[str, Any]) -> str:
    """Return pure JSON for preflight output."""
    return json.dumps(payload, indent=2, sort_keys=True)


def write_preflight_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write preflight JSON output."""
    validate_output_path(path, label="JSON output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(preflight_json(payload) + "\n", encoding="utf-8")
    return path


def write_preflight_summary(path: Path, payload: dict[str, Any]) -> Path:
    """Write preflight Markdown output."""
    validate_output_path(path, label="Summary output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(preflight_markdown(payload), encoding="utf-8")
    return path


def preflight_markdown(payload: dict[str, Any]) -> str:
    """Render a compact preflight Markdown report."""
    stacks = payload.get("detected_stacks") or []
    stack_text = ", ".join(str(stack) for stack in stacks) if stacks else "none"
    config = payload["config"]
    workflow_check = payload["workflow_check"]
    workflow_template = payload["workflow_template"]
    required_modes = workflow_check.get("required_ci_modes") or []
    missing_required_modes = workflow_check.get("missing_required_ci_modes") or []
    lines = [
        "# VibeBench Preflight",
        "",
        f"- Status: {payload['status']}",
        f"- Strict: {str(payload['strict']).lower()}",
        f"- Detected stack: {stack_text}",
        f"- Requested profile: {payload['requested_profile']}",
        f"- Resolved profile: {payload['resolved_profile']}",
        (
            "- Config status: valid"
            if config["valid"]
            else "- Config status: invalid"
            if config["exists"]
            else "- Config status: missing"
        ),
        (
            f"- Workflow status: {workflow_check['status']} "
            f"({workflow_check['workflow_count']} discovered)"
        ),
        f"- Workflow template preview: `{workflow_template['output_path']}`",
        "",
        "## Recommendations",
        "",
    ]
    if required_modes:
        lines.extend(
            [
                "- Required CI modes: "
                + ", ".join(str(mode) for mode in required_modes),
                "- Missing required CI modes: "
                + (
                    ", ".join(str(mode) for mode in missing_required_modes)
                    or "none"
                ),
            ]
        )
        lines.append("")
    for recommendation in payload.get("recommendations", []):
        lines.append(f"- {recommendation}")
    lines.extend(["", "## Suggested Command Sequence", ""])
    for command in payload.get("commands", []):
        lines.append(f"- `{command}`")
    if "policy_status" in payload:
        lines.extend(
            [
                "",
                "## Policy",
                "",
                f"- Status: {payload['policy_status']}",
                f"- Source: {payload['policy_source']}",
                f"- Enforced: {str(payload['policy_enforced']).lower()}",
                (
                    "- Default preflight remains report-only unless enforcement "
                    "is requested."
                ),
                "",
                "| Severity | Finding | Rule | Recommendation |",
                "| --- | --- | --- | --- |",
            ]
        )
        policy_findings = payload.get("policy_findings") or []
        if policy_findings:
            for finding in policy_findings:
                lines.append(
                    "| {severity} | {title} | {rule} | {recommendation} |".format(
                        severity=markdown_cell(finding["severity"]),
                        title=markdown_cell(finding["title"]),
                        rule=markdown_cell(finding["rule"]),
                        recommendation=markdown_cell(finding["recommendation"]),
                    )
                )
        else:
            lines.append("| info | Policy passed | none | No action needed. |")
    return "\n".join(lines) + "\n"


def markdown_cell(value: object) -> str:
    """Escape Markdown table cell text."""
    return str(value).replace("|", "\\|").replace("\n", " ")


def validate_output_path(path: Path, *, label: str) -> None:
    """Validate a requested preflight output path."""
    if path.exists() and path.is_dir():
        raise ConfigError(f"{label} path is a directory: {path}")
