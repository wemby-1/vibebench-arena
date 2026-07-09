"""Read-only adoption workflow readiness report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vibebench.config import ConfigError, load_effective_config
from vibebench.doctor import run_doctor
from vibebench.paths import config_file
from vibebench.preflight import preflight_payload
from vibebench.release_check import run_release_check
from vibebench.workflow_check import normalize_required_ci_modes, workflow_check_payload

ADOPTION_READY_JSON = "adoption-ready.json"
ADOPTION_READY_SUMMARY = "adoption-ready.md"
DEFAULT_REQUIRED_MODE = "adoption-policy"


def adoption_ready_payload(
    project_root: Path,
    *,
    strict: bool = False,
    required_modes: list[str] | None = None,
) -> dict[str, Any]:
    """Return a deterministic read-only adoption readiness payload."""
    root = project_root.resolve()
    required_ci_modes = normalize_required_ci_modes(
        required_modes or [DEFAULT_REQUIRED_MODE],
        source="--require-mode",
    )
    workflow_check = workflow_check_payload(
        root,
        strict=False,
        check_all=True,
        required_ci_modes=required_ci_modes,
    )
    detected_ci_modes = [
        str(mode) for mode in workflow_check.get("detected_ci_modes") or []
    ]
    missing_required_ci_modes = [
        str(mode)
        for mode in workflow_check.get("missing_required_ci_modes") or []
    ]
    discovered_workflows = [
        str(path) for path in workflow_check.get("discovered_paths") or []
    ]

    checks = [
        config_present_check(root),
        config_valid_check(root),
        workflow_present_check(discovered_workflows),
        workflow_detected_ci_modes_check(detected_ci_modes),
        required_workflow_ci_modes_check(
            detected_ci_modes=detected_ci_modes,
            required_ci_modes=required_ci_modes,
            missing_required_ci_modes=missing_required_ci_modes,
        ),
        missing_workflow_ci_modes_check(missing_required_ci_modes),
        preflight_available_check(root, required_ci_modes=required_ci_modes),
        availability_check(
            "release_check_available",
            "Release-check availability",
            "release-check is available for follow-up readiness checks.",
            "Run python3 -m vibebench release-check before publishing.",
        ),
        availability_check(
            "doctor_strict_available",
            "Strict doctor availability",
            "doctor --strict is available for stricter local diagnostics.",
            "Run python3 -m vibebench doctor --strict before publishing.",
        ),
    ]
    if strict:
        replace_check(
            checks,
            release_check_available_check(
                root,
                required_ci_modes=required_ci_modes,
            ),
        )
        replace_check(
            checks,
            doctor_strict_available_check(
                root,
                required_ci_modes=required_ci_modes,
            ),
        )

    summary = summarize_checks(checks)
    status = "failed" if summary["failed"] else "passed"
    advice = dedupe(
        [
            str(check.get("advice"))
            for check in checks
            if check.get("status") == "failed" and check.get("advice")
        ]
    )
    return {
        "status": status,
        "strict": strict,
        "project_root": str(root),
        "required_mode": required_ci_modes[0] if len(required_ci_modes) == 1 else None,
        "detected_ci_modes": detected_ci_modes,
        "required_ci_modes": required_ci_modes,
        "missing_required_ci_modes": missing_required_ci_modes,
        "workflow_present": bool(discovered_workflows),
        "workflow_paths": discovered_workflows,
        "checks": checks,
        "summary": summary,
        "advice": advice,
        "read_only": True,
        "message": adoption_ready_message(status),
    }


def config_present_check(project_root: Path) -> dict[str, str]:
    """Return whether a VibeBench config file exists."""
    path = config_file(project_root)
    if path.is_file():
        return check(
            "config_present",
            "Config file present",
            "passed",
            f"Found VibeBench config at {path}.",
            "No action needed.",
        )
    return check(
        "config_present",
        "Config file present",
        "failed",
        "No .vibebench/config.yaml file was found.",
        "Run python3 -m vibebench init --profile auto before enabling adoption CI.",
    )


def config_valid_check(project_root: Path) -> dict[str, str]:
    """Return whether the VibeBench config can be loaded."""
    try:
        load_effective_config(config_file(project_root))
    except ConfigError as exc:
        return check(
            "config_valid",
            "Config file valid",
            "failed",
            f"VibeBench config could not be loaded: {exc}",
            "Run python3 -m vibebench config --check and fix the reported issue.",
        )
    return check(
        "config_valid",
        "Config file valid",
        "passed",
        "VibeBench config loaded successfully.",
        "No action needed.",
    )


def workflow_present_check(discovered_workflows: list[str]) -> dict[str, str]:
    """Return whether a likely workflow file was discovered."""
    if discovered_workflows:
        return check(
            "workflow_present",
            "Workflow present",
            "passed",
            f"Discovered {len(discovered_workflows)} likely workflow file(s).",
            "No action needed.",
        )
    return check(
        "workflow_present",
        "Workflow present",
        "failed",
        "No likely GitHub Actions workflow file was found.",
        (
            "Preview one with python3 -m vibebench workflow-template "
            "--ci-mode adoption-policy."
        ),
    )


def workflow_detected_ci_modes_check(detected_ci_modes: list[str]) -> dict[str, str]:
    """Return whether workflow-check detected any VibeBench CI mode."""
    if detected_ci_modes:
        return check(
            "workflow_detected_ci_modes",
            "Workflow detected CI modes",
            "passed",
            "Detected VibeBench CI mode(s): " + ", ".join(detected_ci_modes) + ".",
            "No action needed.",
        )
    return check(
        "workflow_detected_ci_modes",
        "Workflow detected CI modes",
        "failed",
        "No VibeBench CI modes were detected in discovered workflows.",
        (
            "Add a VibeBench CI invocation from workflow-template before "
            "relying on adoption CI."
        ),
    )


def required_workflow_ci_modes_check(
    *,
    detected_ci_modes: list[str],
    required_ci_modes: list[str],
    missing_required_ci_modes: list[str],
) -> dict[str, object]:
    """Return the required mode readiness check."""
    detected = ", ".join(detected_ci_modes) or "none"
    required = ", ".join(required_ci_modes) or "none"
    missing = ", ".join(missing_required_ci_modes) or "none"
    status = "passed" if not missing_required_ci_modes else "failed"
    advice = (
        "No action needed."
        if status == "passed"
        else "Update the workflow to run the missing VibeBench CI mode(s)."
    )
    payload = check(
        "required_workflow_ci_modes",
        "Required workflow CI modes",
        status,
        f"Detected: {detected}. Required: {required}. Missing: {missing}.",
        advice,
    )
    payload["detected_ci_modes"] = detected_ci_modes
    payload["required_ci_modes"] = required_ci_modes
    payload["missing_required_ci_modes"] = missing_required_ci_modes
    return payload


def missing_workflow_ci_modes_check(
    missing_required_ci_modes: list[str],
) -> dict[str, object]:
    """Return the missing mode readiness check."""
    if not missing_required_ci_modes:
        return check(
            "missing_workflow_ci_modes",
            "Missing workflow CI modes",
            "passed",
            "No required workflow CI modes are missing.",
            "No action needed.",
        )
    return check(
        "missing_workflow_ci_modes",
        "Missing workflow CI modes",
        "failed",
        "Missing required workflow CI mode(s): "
        + ", ".join(missing_required_ci_modes)
        + ".",
        "Regenerate or edit the workflow after reviewing workflow-template output.",
    )


def preflight_available_check(
    project_root: Path,
    *,
    required_ci_modes: list[str],
) -> dict[str, str]:
    """Return whether preflight can build its read-only payload."""
    try:
        preflight_payload(project_root, required_ci_modes=required_ci_modes)
    except ConfigError as exc:
        return check(
            "preflight_available",
            "Preflight availability",
            "failed",
            f"preflight could not build its readiness payload: {exc}",
            "Run python3 -m vibebench preflight --json for details.",
        )
    return check(
        "preflight_available",
        "Preflight availability",
        "passed",
        "preflight can build a read-only readiness payload.",
        "No action needed.",
    )


def release_check_available_check(
    project_root: Path,
    *,
    required_ci_modes: list[str],
) -> dict[str, str]:
    """Return strict release-check readiness."""
    try:
        result = run_release_check(
            project_root,
            required_workflow_ci_modes=required_ci_modes,
        )
    except (ConfigError, OSError) as exc:
        return check(
            "release_check_available",
            "Release-check availability",
            "failed",
            f"release-check could not run: {exc}",
            "Run python3 -m vibebench release-check for details.",
        )
    if result.ready:
        return check(
            "release_check_available",
            "Release-check availability",
            "passed",
            "release-check passed with the requested workflow mode requirement.",
            "No action needed.",
        )
    failed = [item for item in result.checks if item.status == "failed"]
    message = "; ".join(f"{item.name}: {item.message}" for item in failed)
    return check(
        "release_check_available",
        "Release-check availability",
        "failed",
        message or "release-check did not pass.",
        "Run python3 -m vibebench release-check and address failed checks.",
    )


def doctor_strict_available_check(
    project_root: Path,
    *,
    required_ci_modes: list[str],
) -> dict[str, str]:
    """Return strict doctor readiness."""
    try:
        result = run_doctor(
            project_root,
            strict=True,
            required_workflow_ci_modes=required_ci_modes,
        )
    except ConfigError as exc:
        return check(
            "doctor_strict_available",
            "Strict doctor availability",
            "failed",
            f"doctor --strict could not run: {exc}",
            "Run python3 -m vibebench doctor --strict for details.",
        )
    if result.overall_status == "passed":
        return check(
            "doctor_strict_available",
            "Strict doctor availability",
            "passed",
            "doctor --strict passed with the requested workflow mode requirement.",
            "No action needed.",
        )
    failed = [item for item in result.checks if item.status == "failed"]
    message = "; ".join(f"{item.category}: {item.message}" for item in failed)
    return check(
        "doctor_strict_available",
        "Strict doctor availability",
        "failed",
        message or "doctor --strict did not pass.",
        "Run python3 -m vibebench doctor --strict and address failed checks.",
    )


def availability_check(
    check_id: str,
    title: str,
    message: str,
    advice: str,
) -> dict[str, str]:
    """Return a default non-strict availability check."""
    return check(check_id, title, "passed", message, advice)


def check(
    check_id: str,
    title: str,
    status: str,
    message: str,
    advice: str,
) -> dict[str, str]:
    """Return one adoption readiness check."""
    return {
        "id": check_id,
        "title": title,
        "status": status,
        "message": message,
        "advice": advice,
    }


def replace_check(checks: list[dict[str, Any]], replacement: dict[str, Any]) -> None:
    """Replace a check in-place by id."""
    for index, existing in enumerate(checks):
        if existing.get("id") == replacement.get("id"):
            checks[index] = replacement
            return
    checks.append(replacement)


def summarize_checks(checks: list[dict[str, Any]]) -> dict[str, int]:
    """Return deterministic check counts."""
    failed = sum(1 for item in checks if item.get("status") == "failed")
    passed = sum(1 for item in checks if item.get("status") == "passed")
    return {
        "total": len(checks),
        "passed": passed,
        "failed": failed,
    }


def dedupe(items: list[str]) -> list[str]:
    """Return first-seen unique strings."""
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def adoption_ready_message(status: str) -> str:
    """Return a concise report message."""
    if status == "passed":
        return "Repository is ready for the requested VibeBench adoption workflow."
    return "Repository is not ready for the requested VibeBench adoption workflow."


def adoption_ready_json(payload: dict[str, Any]) -> str:
    """Return pure JSON for adoption-ready output."""
    return json.dumps(payload, indent=2, sort_keys=True)


def write_adoption_ready_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write adoption-ready JSON output."""
    validate_output_path(path, label="JSON output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(adoption_ready_json(payload) + "\n", encoding="utf-8")
    return path


def write_adoption_ready_summary(path: Path, payload: dict[str, Any]) -> Path:
    """Write adoption-ready Markdown output."""
    validate_output_path(path, label="Summary output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(adoption_ready_markdown(payload), encoding="utf-8")
    return path


def adoption_ready_markdown(payload: dict[str, Any]) -> str:
    """Render a compact adoption readiness Markdown report."""
    detected_modes = payload.get("detected_ci_modes") or []
    required_modes = payload.get("required_ci_modes") or []
    missing_modes = payload.get("missing_required_ci_modes") or []
    lines = [
        "# VibeBench Adoption Readiness",
        "",
        f"- Status: {payload['status']}",
        f"- Strict: {str(payload['strict']).lower()}",
        f"- Required mode: {payload.get('required_mode') or ', '.join(required_modes)}",
        "- Detected CI modes: " + (", ".join(detected_modes) or "none"),
        "- Missing required modes: " + (", ".join(missing_modes) or "none"),
        "",
        "## Checks",
        "",
        "| Check | Status | Message | Advice |",
        "| --- | --- | --- | --- |",
    ]
    for item in payload.get("checks", []):
        lines.append(
            "| {title} | {status} | {message} | {advice} |".format(
                title=markdown_cell(item["title"]),
                status=markdown_cell(item["status"]),
                message=markdown_cell(item["message"]),
                advice=markdown_cell(item["advice"]),
            )
        )
    lines.extend(["", "## Advice", ""])
    advice = payload.get("advice") or []
    if advice:
        for item in advice:
            lines.append(f"- {item}")
    else:
        lines.append("- No action needed.")
    return "\n".join(lines) + "\n"


def markdown_cell(value: object) -> str:
    """Escape Markdown table cell text."""
    return str(value).replace("|", "\\|").replace("\n", " ")


def validate_output_path(path: Path, *, label: str) -> None:
    """Validate a requested adoption-ready output path."""
    if path.exists() and path.is_dir():
        raise ConfigError(f"{label} path is a directory: {path}")
