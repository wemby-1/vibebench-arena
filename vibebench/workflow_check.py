"""Read-only GitHub Actions workflow validation for VibeBench adoption."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from vibebench.config import ConfigError, load_effective_config
from vibebench.paths import config_file

WORKFLOW_CHECK_JSON = "workflow-check.json"
WORKFLOW_CHECK_SUMMARY = "workflow-check.md"

DEFAULT_WORKFLOW_CANDIDATES = [
    Path(".github") / "workflows" / "vibebench.yml",
    Path(".github") / "workflows" / "vibebench.yaml",
    Path(".github") / "workflows" / "ci.yml",
    Path(".github") / "workflows" / "ci.yaml",
]

VIBEBENCH_CI_PATTERNS = [
    "python -m vibebench ci",
    "python3 -m vibebench ci",
    "uv run python -m vibebench ci",
    "uv run python3 -m vibebench ci",
]
CI_MODE_ORDER = ["default", "adoption", "adoption-policy"]
CI_MODE_SET = set(CI_MODE_ORDER)
VIBEBENCH_CI_COMMAND_RE = re.compile(
    r"(?:uv\s+run\s+)?python3?\s+-m\s+vibebench\s+ci\b[^\n;&|]*",
    re.IGNORECASE,
)
VIBEBENCH_ACTION_USES_RE = re.compile(
    r"^\s*uses:\s*(?:wemby-1/vibebench-arena@[A-Za-z0-9._/-]+|\./)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
VIBEBENCH_ACTION_PRESET_RE = re.compile(
    r"^\s*preset:\s*(minimal|strict|proof)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
VIBEBENCH_ACTION_REQUIRED_MODE_RE = re.compile(
    r"^\s*required-mode:\s*([A-Za-z0-9_, -]+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
OPTIONAL_VIBEBENCH_PATTERNS = {
    "vibebench_ci_json": "vibebench ci --json",
    "workflow_template_ci": "vibebench ci --workflow-template",
    "artifacts": "vibebench artifacts",
    "bundle": "vibebench bundle",
    "manifest_check": "vibebench manifest --check",
    "doctor_strict": "vibebench doctor --strict",
}
RISK_PATTERNS = {
    "gh_release": ["gh release"],
    "gh_api": ["gh api"],
    "create_release": ["create-release", "create release"],
    "pages_deploy": ["pages deploy", "deploy-pages", "github-pages deploy"],
    "npm_publish": ["npm publish"],
    "twine_upload": ["twine upload"],
    "pypi_publish": ["pypi publish"],
    "docker_push": ["docker push"],
    "force_push": ["force push", "git push --force", "git push -f"],
}
REPOSITORY_WRITE_HINTS = [
    "git commit",
    "git push",
    "git add .",
    "git add -a",
    "git checkout -b",
]
SAFE_WRITE_HINTS = [
    "vibebench workflow-template --write",
    "workflow-template --write",
]


def workflow_check_payload(
    project_root: Path,
    *,
    path: Path | None = None,
    strict: bool = False,
    check_all: bool = False,
    enforce_policy: bool = False,
    required_ci_modes: list[str] | None = None,
) -> dict[str, Any]:
    """Return a deterministic read-only workflow check payload."""
    root = project_root.resolve()
    normalized_required_ci_modes = normalize_required_ci_modes(
        required_ci_modes or [],
        source="--require-ci-mode",
    )
    selected_paths = resolve_workflow_paths(root, path=path, check_all=check_all)
    discovered_paths = [str(item) for item in discover_workflows(root)]
    if path is not None and not discovered_paths:
        discovered_paths = [str(resolve_workflow_path(root, path))]

    checks: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    detected_ci_modes: list[str] = []
    selected_workflow_path = selected_paths[0] if selected_paths else None

    if not selected_paths:
        target = root / DEFAULT_WORKFLOW_CANDIDATES[0]
        add_check(
            checks,
            findings,
            check_id="workflow_exists",
            title="Workflow file exists",
            passed=False,
            strict=strict,
            message="No likely GitHub Actions workflow file was found.",
            path=target,
            advice="Run python3 -m vibebench workflow-template to preview one.",
        )
    for workflow_path in selected_paths:
        detected_ci_modes.extend(
            analyze_workflow_path(
                workflow_path, strict=strict, checks=checks, findings=findings
            )
        )

    detected_ci_modes = unique_ci_modes(detected_ci_modes)
    missing_required_ci_modes = missing_required_ci_modes_for(
        normalized_required_ci_modes,
        detected_ci_modes,
    )
    if normalized_required_ci_modes:
        add_required_ci_modes_check(
            checks,
            findings,
            required_ci_modes=normalized_required_ci_modes,
            missing_required_ci_modes=missing_required_ci_modes,
            path=selected_workflow_path or (root / DEFAULT_WORKFLOW_CANDIDATES[0]),
        )
    summary = summarize_checks(checks)
    status = "failed" if summary["failed"] else "passed"
    usable = bool(
        selected_paths
        and any(
            check["id"] == "vibebench_ci_invocation" and check["status"] == "passed"
            for check in checks
        )
        and not any(check["severity"] == "error" for check in checks)
    )
    payload: dict[str, Any] = {
        "status": status,
        "strict": strict,
        "workflow_path": str(selected_workflow_path)
        if selected_workflow_path
        else None,
        "discovered_paths": discovered_paths,
        "checks": checks,
        "findings": findings,
        "summary": summary,
        "detected_ci_modes": detected_ci_modes,
        "usable_for_vibebench_ci": usable,
        "safe_preview_only": True,
        "message": workflow_check_message(status, selected_workflow_path),
    }
    if normalized_required_ci_modes:
        payload["required_ci_modes"] = normalized_required_ci_modes
        payload["missing_required_ci_modes"] = missing_required_ci_modes
    if enforce_policy:
        attach_workflow_check_policy(payload, root)
    return payload


def resolve_workflow_paths(
    project_root: Path,
    *,
    path: Path | None,
    check_all: bool,
) -> list[Path]:
    """Resolve workflow paths without creating files or directories."""
    if path is not None:
        return [resolve_workflow_path(project_root, path)]
    discovered = discover_workflows(project_root)
    return discovered if check_all else discovered[:1]


def resolve_workflow_path(project_root: Path, path: Path) -> Path:
    """Resolve a user-provided workflow path relative to project root."""
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def discover_workflows(project_root: Path) -> list[Path]:
    """Return likely workflow files in deterministic preference order."""
    return [
        (project_root / candidate).resolve()
        for candidate in DEFAULT_WORKFLOW_CANDIDATES
        if (project_root / candidate).is_file()
    ]


def analyze_workflow_path(
    workflow_path: Path,
    *,
    strict: bool,
    checks: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> list[str]:
    """Analyze one workflow file with conservative text checks."""
    if not workflow_path.exists():
        add_check(
            checks,
            findings,
            check_id="workflow_exists",
            title="Workflow file exists",
            passed=False,
            strict=strict,
            message="Workflow file does not exist.",
            path=workflow_path,
            advice="Run python3 -m vibebench workflow-template to preview one.",
        )
        return []
    if not workflow_path.is_file():
        add_check(
            checks,
            findings,
            check_id="workflow_is_file",
            title="Workflow path is a file",
            passed=False,
            strict=strict,
            message="Workflow path is not a regular file.",
            path=workflow_path,
            advice="Pass --path to a workflow YAML file.",
        )
        return []
    try:
        content = workflow_path.read_text(encoding="utf-8")
    except OSError as exc:
        add_check(
            checks,
            findings,
            check_id="workflow_readable",
            title="Workflow file is readable",
            passed=False,
            strict=strict,
            message=f"Workflow file could not be read: {exc}",
            path=workflow_path,
            advice="Check file permissions and rerun workflow-check.",
        )
        return []

    add_check(
        checks,
        findings,
        check_id="workflow_exists",
        title="Workflow file exists",
        passed=True,
        strict=strict,
        message="Workflow file was found.",
        path=workflow_path,
        advice="No action needed.",
    )
    add_check(
        checks,
        findings,
        check_id="workflow_readable",
        title="Workflow file is readable",
        passed=True,
        strict=strict,
        message="Workflow file was read successfully.",
        path=workflow_path,
        advice="No action needed.",
    )
    non_empty = bool(content.strip())
    add_check(
        checks,
        findings,
        check_id="workflow_not_empty",
        title="Workflow file is not empty",
        passed=non_empty,
        strict=strict,
        message="Workflow file has content."
        if non_empty
        else "Workflow file is empty.",
        path=workflow_path,
        advice="Add a GitHub Actions workflow YAML body.",
    )
    if not non_empty:
        return []

    lower = content.lower()
    detected_ci_modes = detect_vibebench_ci_modes(content)
    basic_requirements = [
        ("workflow_has_name", "Workflow has a name", "name:"),
        ("workflow_has_on", "Workflow has triggers", "on:"),
        ("workflow_has_jobs", "Workflow has jobs", "jobs:"),
        ("workflow_has_runs_on", "Workflow has a runner", "runs-on:"),
        ("workflow_has_steps", "Workflow has steps", "steps:"),
    ]
    for check_id, title, token in basic_requirements:
        add_check(
            checks,
            findings,
            check_id=check_id,
            title=title,
            passed=token in lower,
            strict=strict,
            message=(
                f"Workflow contains {token}."
                if token in lower
                else f"Workflow is missing {token}."
            ),
            path=workflow_path,
            advice="Use python3 -m vibebench workflow-template for a known-good shape.",
            line=find_line(content, token),
        )

    has_vibebench_ci = any(
        pattern in lower for pattern in VIBEBENCH_CI_PATTERNS
    ) or bool(VIBEBENCH_ACTION_USES_RE.search(content))
    add_check(
        checks,
        findings,
        check_id="vibebench_ci_invocation",
        title="Workflow runs VibeBench CI",
        passed=has_vibebench_ci,
        strict=strict,
        message=(
            "Workflow includes a VibeBench CI invocation."
            if has_vibebench_ci
            else (
                "Workflow does not run python3 -m vibebench ci or the "
                "VibeBench action."
            )
        ),
        path=workflow_path,
        advice="Add python3 -m vibebench ci or the reusable VibeBench action.",
        line=first_matching_line(content, VIBEBENCH_CI_PATTERNS)
        or first_matching_line(content, ["uses: wemby-1/vibebench-arena", "uses: ./"]),
    )
    for check_id, pattern in OPTIONAL_VIBEBENCH_PATTERNS.items():
        if pattern in lower:
            add_info(
                checks,
                check_id=check_id,
                title=f"Optional command detected: {pattern}",
                message=f"Workflow includes {pattern}.",
                path=workflow_path,
                line=find_line(content, pattern),
            )

    for action_ref, line in unpinned_action_uses(content):
        add_risk_finding(
            checks,
            findings,
            risk_id="unpinned_action",
            title="Workflow action is not pinned to a full commit SHA",
            message=f"Workflow uses {action_ref!r} without a full commit SHA pin.",
            path=workflow_path,
            line=line,
            strict=False,
            advice=(
                "Pin third-party actions to reviewed commit SHAs, or allow an "
                "explicit prefix in workflow_check.policy.allowed_action_prefixes."
            ),
        )

    for risk_id, patterns in RISK_PATTERNS.items():
        line = first_matching_line(content, patterns)
        if line is not None:
            add_risk_finding(
                checks,
                findings,
                risk_id=risk_id,
                title=f"Risky workflow command detected: {risk_id.replace('_', ' ')}",
                message=f"Workflow contains risky automation matching {patterns[0]!r}.",
                path=workflow_path,
                line=line,
                strict=strict,
                advice=(
                    "Keep workflow-template adoption CI review-only; remove "
                    "publishing/deploy/release steps or isolate them in a "
                    "separate reviewed workflow."
                ),
            )
    if any(hint in lower for hint in REPOSITORY_WRITE_HINTS) and not any(
        hint in lower for hint in SAFE_WRITE_HINTS
    ):
        add_risk_finding(
            checks,
            findings,
            risk_id="repository_write",
            title="Workflow appears to write repository files",
            message=(
                "Workflow contains repository write hints such as git add, "
                "commit, or push."
            ),
            path=workflow_path,
            line=first_matching_line(content, REPOSITORY_WRITE_HINTS),
            strict=strict,
            advice=(
                "Keep VibeBench workflow adoption review-only unless repository "
                "writes are explicitly reviewed."
            ),
        )

    return detected_ci_modes


def detect_vibebench_ci_modes(content: str) -> list[str]:
    """Return VibeBench CI modes found in workflow-like text."""
    modes: list[str] = []
    scan_content = "\n".join(
        line for line in content.splitlines() if not line.lstrip().startswith("#")
    )
    for match in VIBEBENCH_CI_COMMAND_RE.finditer(scan_content):
        command = match.group(0).lower()
        if "--adoption-policy" in command:
            modes.append("adoption-policy")
        elif "--adoption" in command:
            modes.append("adoption")
        else:
            modes.append("default")
    if VIBEBENCH_ACTION_USES_RE.search(scan_content):
        for match in VIBEBENCH_ACTION_PRESET_RE.finditer(scan_content):
            preset = match.group(1).lower()
            if preset == "minimal":
                modes.append("adoption")
            elif preset in {"strict", "proof"}:
                modes.append("adoption-policy")
        for match in VIBEBENCH_ACTION_REQUIRED_MODE_RE.finditer(scan_content):
            for item in match.group(1).replace("\n", ",").split(","):
                mode = item.strip()
                if mode in CI_MODE_SET:
                    modes.append(mode)
    return unique_ci_modes(modes)


def unique_ci_modes(modes: list[str]) -> list[str]:
    """Deduplicate VibeBench CI modes in stable reporting order."""
    seen = {mode for mode in modes if mode in CI_MODE_ORDER}
    return [mode for mode in CI_MODE_ORDER if mode in seen]


def normalize_required_ci_modes(modes: list[str], *, source: str) -> list[str]:
    """Validate and normalize required CI mode expectations."""
    seen: set[str] = set()
    normalized: list[str] = []
    for item in modes:
        selected = item.strip()
        if selected not in CI_MODE_SET:
            allowed = ", ".join(CI_MODE_ORDER)
            raise ConfigError(
                f"{source} must be one of: {allowed}. Received {item!r}."
            )
        if selected not in seen:
            seen.add(selected)
            normalized.append(selected)
    return unique_ci_modes(normalized)


def missing_required_ci_modes_for(
    required_ci_modes: list[str],
    detected_ci_modes: list[str],
) -> list[str]:
    """Return required CI modes that were not detected."""
    detected = set(detected_ci_modes)
    return [mode for mode in required_ci_modes if mode not in detected]


def add_required_ci_modes_check(
    checks: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    *,
    required_ci_modes: list[str],
    missing_required_ci_modes: list[str],
    path: Path,
) -> None:
    """Append an explicit required-CI-modes expectation check."""
    required_text = ", ".join(required_ci_modes)
    missing_text = ", ".join(missing_required_ci_modes) or "none"
    add_check(
        checks,
        findings,
        check_id="required_ci_modes",
        title="Required CI modes are present",
        passed=not missing_required_ci_modes,
        strict=True,
        message=f"Required CI modes: {required_text}. Missing: {missing_text}.",
        path=path,
        advice="Update the workflow to run the expected VibeBench CI mode.",
    )


def add_check(
    checks: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    *,
    check_id: str,
    title: str,
    passed: bool,
    strict: bool,
    message: str,
    path: Path,
    advice: str,
    line: int | None = None,
) -> None:
    """Append a check and an actionable finding when it is not passed."""
    status = "passed" if passed else "failed" if strict else "warning"
    severity = "info" if passed else "error" if strict else "warning"
    item = check_item(check_id, title, status, severity, message, path, line, advice)
    checks.append(item)
    if not passed:
        findings.append(item)


def add_info(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    title: str,
    message: str,
    path: Path,
    line: int | None,
) -> None:
    """Append an informational optional-command check."""
    checks.append(
        check_item(
            check_id, title, "passed", "info", message, path, line, "No action needed."
        )
    )


def add_risk_finding(
    checks: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    *,
    risk_id: str,
    title: str,
    message: str,
    path: Path,
    line: int | None,
    strict: bool,
    advice: str,
) -> None:
    """Append a high-risk workflow finding."""
    status = "failed" if strict else "warning"
    severity = "error" if strict else "warning"
    item = check_item(risk_id, title, status, severity, message, path, line, advice)
    checks.append(item)
    findings.append(item)


def check_item(
    check_id: str,
    title: str,
    status: str,
    severity: str,
    message: str,
    path: Path,
    line: int | None,
    advice: str,
) -> dict[str, Any]:
    """Return a JSON-safe check or finding item."""
    return {
        "id": check_id,
        "title": title,
        "status": status,
        "severity": severity,
        "message": message,
        "path": str(path),
        "line": line,
        "advice": advice,
    }


def summarize_checks(checks: list[dict[str, Any]]) -> dict[str, int]:
    """Return deterministic check/finding counts."""
    return {
        "total": len(checks),
        "passed": sum(1 for check in checks if check["status"] == "passed"),
        "warning": sum(1 for check in checks if check["status"] == "warning"),
        "failed": sum(1 for check in checks if check["status"] == "failed"),
    }


def workflow_check_message(status: str, workflow_path: Path | None) -> str:
    """Return a concise workflow-check message."""
    if workflow_path is None:
        return "No workflow file was checked."
    if status == "failed":
        return "Workflow check found blocking issues."
    return "Workflow check completed without blocking issues."


def find_line(content: str, pattern: str) -> int | None:
    """Return a 1-based line number for a case-insensitive pattern."""
    lowered = pattern.lower()
    for index, line in enumerate(content.splitlines(), start=1):
        if lowered in line.lower():
            return index
    return None


def first_matching_line(content: str, patterns: list[str]) -> int | None:
    """Return the first line matching any case-insensitive pattern."""
    for pattern in patterns:
        line = find_line(content, pattern)
        if line is not None:
            return line
    return None



BLOCKING_WORKFLOW_FINDING_IDS = {
    "workflow_exists",
    "workflow_is_file",
    "workflow_readable",
    "workflow_not_empty",
    "workflow_has_name",
    "workflow_has_on",
    "workflow_has_jobs",
    "workflow_has_runs_on",
    "workflow_has_steps",
}


def attach_workflow_check_policy(payload: dict[str, Any], project_root: Path) -> None:
    """Attach workflow-check policy fields to a payload."""
    policy_source, effective_policy, config_exists = resolve_workflow_check_policy(
        project_root
    )
    policy_findings = evaluate_workflow_check_policy(
        payload,
        effective_policy,
        config_exists=config_exists,
    )
    payload["policy_evaluated"] = True
    payload["policy_status"] = "failed" if policy_findings else "passed"
    payload["policy_source"] = policy_source
    payload["policy_findings"] = policy_findings
    payload["effective_policy"] = effective_policy
    if policy_findings:
        payload["status"] = "failed"
        payload["message"] = "Workflow check policy found blocking issues."


def resolve_workflow_check_policy(
    project_root: Path,
) -> tuple[str, dict[str, Any], bool]:
    """Return the effective workflow-check policy, source, and config presence."""
    result = load_effective_config(config_file(project_root))
    policy = result.config.workflow_check.policy.model_dump()
    raw_source = result.sources.get("workflow_check", "built-in defaults")
    source = "config" if raw_source == "config file" else raw_source
    return source, policy, result.config_exists


def evaluate_workflow_check_policy(
    payload: dict[str, Any],
    policy: dict[str, Any],
    *,
    config_exists: bool,
) -> list[dict[str, str]]:
    """Evaluate workflow policy against an existing workflow-check payload."""
    findings: list[dict[str, str]] = []
    workflow_findings = [
        finding for finding in payload.get("findings", []) if isinstance(finding, dict)
    ]
    allowed_prefixes = [
        str(prefix) for prefix in policy.get("allowed_action_prefixes", [])
    ]
    filtered_findings = [
        finding
        for finding in workflow_findings
        if not workflow_finding_allowed_by_prefix(finding, allowed_prefixes)
    ]

    if policy.get("require_config") and not config_exists:
        findings.append(
            workflow_check_policy_finding(
                "config_required",
                "error",
                "VibeBench config is required",
                "No .vibebench/config.yaml file exists for this project.",
                "Run python3 -m vibebench init --profile auto, then config --check.",
                "require_config",
            )
        )

    if policy.get("require_ci_ready") and not payload.get("usable_for_vibebench_ci"):
        findings.append(
            workflow_check_policy_finding(
                "ci_ready_required",
                "error",
                "Workflow must be ready for VibeBench CI",
                "The checked workflow is not currently usable for VibeBench CI.",
                "Fix workflow blockers or add python3 -m vibebench ci.",
                "require_ci_ready",
            )
        )

    policy_required_ci_modes = normalize_required_ci_modes(
        [str(mode) for mode in policy.get("required_ci_modes", [])],
        source="workflow_check.policy.required_ci_modes",
    )
    if policy_required_ci_modes:
        missing_policy_modes = missing_required_ci_modes_for(
            policy_required_ci_modes,
            [str(mode) for mode in payload.get("detected_ci_modes", [])],
        )
        if missing_policy_modes:
            findings.append(
                workflow_check_policy_finding(
                    "required_ci_modes",
                    "error",
                    "Required CI modes are present",
                    (
                        "Policy requires CI modes "
                        f"{', '.join(policy_required_ci_modes)}. Missing: "
                        f"{', '.join(missing_policy_modes)}."
                    ),
                    (
                        "Update the workflow to include the missing modes or relax "
                        "workflow_check.policy.required_ci_modes."
                    ),
                    "required_ci_modes",
                )
            )

    if policy.get("fail_on_blockers"):
        for finding in filtered_findings:
            if str(finding.get("id") or "") in BLOCKING_WORKFLOW_FINDING_IDS:
                findings.append(
                    workflow_check_policy_finding_from_workflow_finding(
                        finding,
                        severity="error",
                        title="Workflow blockers are not allowed",
                        recommendation=(
                            "Fix the workflow structure or relax "
                            "workflow_check.policy.fail_on_blockers."
                        ),
                        rule="fail_on_blockers",
                    )
                )

    if policy.get("fail_on_errors"):
        for finding in filtered_findings:
            if finding.get("severity") == "error":
                findings.append(
                    workflow_check_policy_finding_from_workflow_finding(
                        finding,
                        severity="error",
                        title="Workflow errors are not allowed",
                        recommendation=(
                            "Resolve the workflow error or relax "
                            "workflow_check.policy.fail_on_errors."
                        ),
                        rule="fail_on_errors",
                    )
                )

    if policy.get("fail_on_warnings"):
        for finding in filtered_findings:
            if finding.get("severity") == "warning":
                findings.append(
                    workflow_check_policy_finding_from_workflow_finding(
                        finding,
                        severity="warning",
                        title="Workflow warnings are not allowed",
                        recommendation=(
                            "Resolve the workflow warning or relax "
                            "workflow_check.policy.fail_on_warnings."
                        ),
                        rule="fail_on_warnings",
                    )
                )

    allowed_names = [str(name) for name in policy.get("allowed_workflow_names", [])]
    if allowed_names:
        for workflow_path in payload.get("discovered_paths", []):
            selected_name = workflow_name(Path(str(workflow_path)))
            if selected_name not in allowed_names:
                findings.append(
                    workflow_check_policy_finding(
                        "workflow_name_not_allowed",
                        "error",
                        "Workflow name is not allowed",
                        (
                            f"Workflow name {selected_name or '<missing>'!r} "
                            "is not in the allowed list."
                        ),
                        (
                            "Update workflow_check.policy.allowed_workflow_names "
                            "if intentional."
                        ),
                        "allowed_workflow_names",
                    )
                )
    return findings


def workflow_check_policy_finding(
    finding_id: str,
    severity: str,
    title: str,
    message: str,
    recommendation: str,
    rule: str,
) -> dict[str, str]:
    """Return a deterministic workflow-check policy finding."""
    return {
        "id": finding_id,
        "severity": severity,
        "title": title,
        "message": message,
        "recommendation": recommendation,
        "rule": rule,
    }


def workflow_check_policy_finding_from_workflow_finding(
    finding: dict[str, Any],
    *,
    severity: str,
    title: str,
    recommendation: str,
    rule: str,
) -> dict[str, str]:
    """Lift a workflow finding into a policy finding."""
    return workflow_check_policy_finding(
        str(finding.get("id") or "workflow_finding"),
        severity,
        title,
        str(finding.get("message") or finding.get("title") or "Workflow finding."),
        recommendation,
        rule,
    )


def workflow_finding_allowed_by_prefix(
    finding: dict[str, Any],
    prefixes: list[str],
) -> bool:
    """Return whether an unpinned-action finding is policy-allowed by prefix."""
    if str(finding.get("id") or "") != "unpinned_action":
        return False
    action_ref = extract_action_ref_from_message(str(finding.get("message") or ""))
    if action_ref is None:
        return False
    return any(action_ref.startswith(prefix) for prefix in prefixes)


def extract_action_ref_from_message(message: str) -> str | None:
    """Extract an action reference from the standard unpinned-action message."""
    marker = "Workflow uses "
    if not message.startswith(marker):
        return None
    try:
        return message.split("'", 2)[1]
    except IndexError:
        return None


def unpinned_action_uses(content: str) -> list[tuple[str, int]]:
    """Return action refs that are not pinned to a full commit SHA."""
    matches: list[tuple[str, int]] = []
    for index, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("- uses:"):
            action_ref = stripped.split("- uses:", 1)[1].strip()
        elif stripped.startswith("uses:"):
            action_ref = stripped.split("uses:", 1)[1].strip()
        else:
            continue
        action_ref = action_ref.strip("\"'")
        if action_ref.startswith("./") or action_ref.startswith("../"):
            continue
        if "@" not in action_ref:
            matches.append((action_ref, index))
            continue
        revision = action_ref.rsplit("@", 1)[1]
        if len(revision) == 40 and all(
            char in "0123456789abcdefABCDEF" for char in revision
        ):
            continue
        matches.append((action_ref, index))
    return matches


def workflow_name(path: Path) -> str | None:
    """Return a simple top-level workflow name from YAML-like text."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            return stripped.split("name:", 1)[1].strip().strip("\"'") or None
    return None


def workflow_check_json(payload: dict[str, Any]) -> str:
    """Return pure JSON for workflow-check output."""
    return json.dumps(payload, indent=2, sort_keys=True)


def write_workflow_check_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write workflow-check JSON output."""
    validate_output_path(path, label="JSON output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workflow_check_json(payload) + "\n", encoding="utf-8")
    return path


def write_workflow_check_summary(path: Path, payload: dict[str, Any]) -> Path:
    """Write workflow-check Markdown output."""
    validate_output_path(path, label="Summary output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workflow_check_markdown(payload), encoding="utf-8")
    return path


def workflow_check_markdown(payload: dict[str, Any]) -> str:
    """Render a compact workflow-check Markdown report."""
    summary = payload["summary"]
    detected_modes = payload.get("detected_ci_modes") or []
    detected_modes_text = ", ".join(str(mode) for mode in detected_modes) or "none"
    required_modes = payload.get("required_ci_modes") or []
    missing_required_modes = payload.get("missing_required_ci_modes") or []
    lines = [
        "# VibeBench Workflow Check",
        "",
        f"- Status: {payload['status']}",
        f"- Workflow path: `{payload['workflow_path']}`",
        f"- Strict: {str(payload['strict']).lower()}",
        f"- Detected CI modes: {detected_modes_text}",
        f"- Passed: {summary['passed']}",
        f"- Warnings: {summary['warning']}",
        f"- Failed: {summary['failed']}",
    ]
    if required_modes:
        lines.append(
            "- Required CI modes: "
            + ", ".join(str(mode) for mode in required_modes)
            + " (missing: "
            + (", ".join(str(mode) for mode in missing_required_modes) or "none")
            + ")"
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Status | Severity | Check | Message |",
            "| --- | --- | --- | --- |",
        ]
    )
    for check in payload["checks"]:
        lines.append(
            "| {status} | {severity} | {title} | {message} |".format(
                status=markdown_cell(check["status"]),
                severity=markdown_cell(check["severity"]),
                title=markdown_cell(check["title"]),
                message=markdown_cell(check["message"]),
            )
        )
    lines.extend(
        [
            "",
            "## Findings",
            "",
            "| Severity | Finding | Advice |",
            "| --- | --- | --- |",
        ]
    )
    findings = payload.get("findings") or []
    if findings:
        for finding in findings:
            lines.append(
                "| {severity} | {title} | {advice} |".format(
                    severity=markdown_cell(finding["severity"]),
                    title=markdown_cell(finding["title"]),
                    advice=markdown_cell(finding["advice"]),
                )
            )
    else:
        lines.append("| info | No findings | No action needed. |")
    if payload.get("policy_evaluated"):
        effective_policy = payload.get("effective_policy") or {}
        lines.extend(
            [
                "",
                "## Policy",
                "",
                f"- Status: {payload['policy_status']}",
                f"- Source: {payload['policy_source']}",
                (
                    "- fail_on_blockers: "
                    f"{str(effective_policy.get('fail_on_blockers')).lower()}"
                ),
                (
                    "- fail_on_errors: "
                    f"{str(effective_policy.get('fail_on_errors')).lower()}"
                ),
                (
                    "- fail_on_warnings: "
                    f"{str(effective_policy.get('fail_on_warnings')).lower()}"
                ),
                (
                    "- require_config: "
                    f"{str(effective_policy.get('require_config')).lower()}"
                ),
                (
                    "- require_ci_ready: "
                    f"{str(effective_policy.get('require_ci_ready')).lower()}"
                ),
                (
                    "- required_ci_modes: "
                    + (
                        ", ".join(
                            str(mode)
                            for mode in effective_policy.get("required_ci_modes", [])
                        )
                        or "none"
                    )
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
    lines.extend(
        [
            "",
            "## Advice",
            "",
            "- Use `python3 -m vibebench workflow-template` to preview a "
            "recommended workflow.",
            "- Use `python3 -m vibebench workflow-check --strict` before "
            "relying on CI adoption.",
            "- Use `python3 -m vibebench workflow-check --enforce-policy` "
            "to turn workflow findings into an explicit gate.",
            "- The check is read-only and does not call GitHub or modify workflows.",
            "",
        ]
    )
    return "\n".join(lines)


def markdown_cell(value: object) -> str:
    """Escape Markdown table cell text."""
    return str(value).replace("|", "\\|").replace("\n", " ")


def validate_output_path(path: Path, *, label: str) -> None:
    """Validate a workflow-check output path."""
    if path.exists() and path.is_dir():
        raise ConfigError(f"{label} path is a directory: {path}")
