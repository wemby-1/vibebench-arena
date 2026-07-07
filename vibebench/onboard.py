"""Read-only onboarding plan for adopting VibeBench."""

import json
from pathlib import Path
from typing import Any

from vibebench.config import ConfigError
from vibebench.project_scan import run_project_scan

ONBOARD_JSON = "onboard.json"
ONBOARD_SUMMARY = "onboard.md"


def onboard_payload(project_root: Path, *, strict: bool = False) -> dict[str, Any]:
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
    return "\n".join(lines) + "\n"


def validate_output_path(path: Path, *, label: str) -> None:
    """Validate a requested onboard output path."""
    if path.exists() and path.is_dir():
        raise ConfigError(f"{label} path is a directory: {path}")
