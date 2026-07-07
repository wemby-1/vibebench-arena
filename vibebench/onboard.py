"""Read-only onboarding plan for adopting VibeBench."""

import json
from pathlib import Path
from typing import Any

from vibebench.config import ConfigError, default_config_model, load_effective_config
from vibebench.paths import config_file
from vibebench.project_scan import run_project_scan

ONBOARD_JSON = "onboard.json"
ONBOARD_SUMMARY = "onboard.md"


def onboard_payload(
    project_root: Path,
    *,
    strict: bool = False,
    enforce_policy: bool = False,
) -> dict[str, Any]:
    """Return a deterministic read-only onboarding plan."""
    root = project_root.resolve()
    scan = run_project_scan(root)
    warnings = onboard_warnings(scan)
    strict_failed = strict and not onboarding_ready_for_ci(scan)
    status = "blocked" if strict_failed else "ready"
    if scan["status"] == "blocked":
        status = "blocked"
    elif not scan["config_present"]:
        status = "needs_init"
    elif scan["status"] == "needs_attention":
        status = "needs_attention"

    suggested_commands = onboard_suggested_commands(scan)
    payload: dict[str, Any] = {
        "status": status,
        "project_root": str(root),
        "config_exists": bool(scan["config_present"]),
        "detected_stacks": scan["detected_stacks"],
        "detection_reasons": scan["detection_reasons"],
        "recommended_profile": scan["recommended_profile"],
        "scan_status": scan["status"],
        "scan_readiness": scan["status"],
        "suggested_commands": suggested_commands,
        "warnings": warnings,
        "next_step": suggested_commands[0] if suggested_commands else "",
        "strict": strict,
        "strict_failed": strict_failed,
    }
    if strict_failed:
        payload["message"] = "Onboarding is not ready for immediate CI adoption."
    else:
        payload["message"] = "Onboarding plan generated without writing files."
    if enforce_policy:
        attach_onboard_policy(payload, root, enforced=True)
    return payload


def onboarding_ready_for_ci(scan: dict[str, Any]) -> bool:
    """Return whether the scanned project is immediately ready for CI adoption."""
    return bool(scan.get("config_present") and scan.get("config_valid")) and scan.get(
        "status"
    ) in {"ready", "needs_attention"}


def onboard_warnings(scan: dict[str, Any]) -> list[str]:
    """Return concise warnings derived from project-scan findings."""
    warnings: list[str] = []
    for finding in scan.get("findings", []):
        if not isinstance(finding, dict):
            continue
        if finding.get("severity") in {"warning", "error"}:
            warnings.append(str(finding.get("title") or finding.get("id")))
    if not scan.get("config_present"):
        warnings.append("No VibeBench config exists yet.")
    return warnings


def onboard_suggested_commands(scan: dict[str, Any]) -> list[str]:
    """Return deterministic onboarding commands for the current scan result."""
    commands: list[str] = []
    if not scan.get("config_present"):
        commands.append("python3 -m vibebench init --profile auto")
    commands.extend(
        [
            "python3 -m vibebench config --check",
            "python3 -m vibebench ci --dry-run",
            "python3 -m vibebench ci",
            "python3 -m vibebench ci --project-scan",
            "python3 -m vibebench ci --project-scan-policy",
            "python3 -m vibebench metrics-check",
            "python3 -m vibebench metrics-diff",
        ]
    )
    return commands


def attach_onboard_policy(
    payload: dict[str, Any],
    project_root: Path,
    *,
    enforced: bool,
) -> None:
    """Attach onboarding policy evaluation fields to a plan payload."""
    policy_source, effective_policy = resolve_onboard_policy(project_root)
    policy_findings = evaluate_onboard_policy(payload, effective_policy)
    payload["policy_source"] = policy_source
    payload["effective_policy"] = effective_policy
    payload["policy_status"] = "failed" if policy_findings else "passed"
    payload["policy_findings"] = policy_findings
    payload["policy_enforced"] = enforced


def resolve_onboard_policy(project_root: Path) -> tuple[str, dict[str, Any]]:
    """Return the effective onboarding policy and source."""
    try:
        result = load_effective_config(config_file(project_root))
        policy = result.config.onboard.policy.model_dump()
        raw_source = result.sources.get("onboard", "built-in defaults")
        source = "config" if raw_source == "config file" else raw_source
    except ConfigError:
        policy = default_config_model().onboard.policy.model_dump()
        source = "built-in defaults"
    return source, policy


def evaluate_onboard_policy(
    payload: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, str]]:
    """Evaluate onboarding policy against an existing onboard payload."""
    findings: list[dict[str, str]] = []
    status = str(payload.get("status") or "")
    scan_status = str(payload.get("scan_status") or "")
    warnings = [str(warning) for warning in payload.get("warnings", [])]

    if policy.get("require_config") and not payload.get("config_exists"):
        findings.append(
            onboard_policy_finding(
                "config_required",
                "error",
                "VibeBench config is required",
                "No .vibebench/config.yaml file exists for this project.",
                "Run python3 -m vibebench init --profile auto, then config --check.",
                "require_config",
            )
        )

    if policy.get("require_ci_ready") and status != "ready":
        findings.append(
            onboard_policy_finding(
                "ci_ready_required",
                "error",
                "Onboarding plan must be CI-ready",
                f"Onboarding status is {status!r}, not ready.",
                "Resolve onboarding warnings or relax onboard.policy.require_ci_ready.",
                "require_ci_ready",
            )
        )

    if policy.get("fail_on_blockers") and (
        status == "blocked" or scan_status == "blocked"
    ):
        findings.append(
            onboard_policy_finding(
                "onboarding_blocked",
                "error",
                "Onboarding blockers are not allowed",
                "The onboarding plan or project scan is blocked.",
                (
                    "Fix blocking project-scan findings before enforcing "
                    "onboarding policy."
                ),
                "fail_on_blockers",
            )
        )

    if policy.get("fail_on_errors") and (
        status == "blocked" or scan_status == "blocked"
    ):
        findings.append(
            onboard_policy_finding(
                "onboarding_errors",
                "error",
                "Onboarding errors are not allowed",
                "The onboarding plan includes error-level readiness signals.",
                "Fix onboarding errors or relax onboard.policy.fail_on_errors.",
                "fail_on_errors",
            )
        )

    if policy.get("fail_on_warnings") and warnings:
        for index, warning in enumerate(warnings):
            findings.append(
                onboard_policy_finding(
                    f"onboarding_warning:{index}",
                    "warning",
                    "Onboarding warning is not allowed",
                    warning,
                    "Resolve the warning or relax onboard.policy.fail_on_warnings.",
                    "fail_on_warnings",
                )
            )
    return findings


def onboard_policy_finding(
    finding_id: str,
    severity: str,
    title: str,
    message: str,
    recommendation: str,
    rule: str,
) -> dict[str, str]:
    """Return a deterministic onboarding policy finding."""
    return {
        "id": finding_id,
        "severity": severity,
        "title": title,
        "message": message,
        "recommendation": recommendation,
        "rule": rule,
    }


def onboard_json(payload: dict[str, Any]) -> str:
    """Return pure JSON for an onboarding plan."""
    return json.dumps(payload, indent=2, sort_keys=True)


def write_onboard_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write onboarding plan JSON."""
    validate_output_path(path, label="JSON output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(onboard_json(payload) + "\n", encoding="utf-8")
    return path


def write_onboard_summary(path: Path, payload: dict[str, Any]) -> Path:
    """Write onboarding plan Markdown."""
    validate_output_path(path, label="Summary output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(onboard_markdown(payload), encoding="utf-8")
    return path


def onboard_markdown(payload: dict[str, Any]) -> str:
    """Render an onboarding plan as compact Markdown."""
    stacks = payload.get("detected_stacks") or []
    stack_text = ", ".join(str(stack) for stack in stacks) if stacks else "none"
    lines = [
        "# VibeBench Onboarding Plan",
        "",
        f"- Status: {payload['status']}",
        f"- Project root: `{payload['project_root']}`",
        f"- Detected stacks: {stack_text}",
        f"- Recommended profile: {payload['recommended_profile']}",
        f"- Project-scan readiness: {payload['scan_readiness']}",
        f"- Config exists: {str(payload['config_exists']).lower()}",
        "",
        "## Suggested Commands",
        "",
    ]
    for command in payload["suggested_commands"]:
        lines.append(f"- `{command}`")
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
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
                    "- Default onboard remains report-only unless "
                    "enforcement is requested."
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
                        severity=finding["severity"],
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
    """Validate a requested onboard output path."""
    if path.exists() and path.is_dir():
        raise ConfigError(f"{label} path is a directory: {path}")
