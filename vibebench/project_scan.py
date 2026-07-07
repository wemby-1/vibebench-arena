"""Read-only onboarding readiness scan for VibeBench projects."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from vibebench.config import (
    ConfigError,
    default_config_model,
    load_config,
    load_effective_config,
)
from vibebench.paths import config_file
from vibebench.project_detect import ProjectDetection, detect_project

FindingSeverity = Literal["info", "warning", "error"]
PROJECT_SCAN_JSON = "project-scan.json"
PROJECT_SCAN_SUMMARY = "project-scan.md"


@dataclass(frozen=True)
class ProjectScanFinding:
    """A deterministic project-scan finding."""

    id: str
    severity: FindingSeverity
    title: str
    message: str
    recommendation: str

    def to_json(self) -> dict[str, str]:
        """Return a stable JSON representation."""
        return {
            "id": self.id,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class ProjectScanPolicyFinding:
    """A project-scan policy violation."""

    id: str
    severity: FindingSeverity
    title: str
    message: str
    recommendation: str
    rule: str
    related_finding: str | None = None

    def to_json(self) -> dict[str, str]:
        """Return a stable JSON representation."""
        payload = {
            "id": self.id,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "recommendation": self.recommendation,
            "rule": self.rule,
        }
        if self.related_finding is not None:
            payload["related_finding"] = self.related_finding
        return payload


def run_project_scan(
    project_root: Path,
    *,
    strict: bool = False,
    enforce_policy: bool = False,
) -> dict[str, Any]:
    """Inspect onboarding readiness without writing project artifacts."""
    root = project_root.resolve()
    detection = detect_project(root)
    config_path = config_file(root)
    config_present = config_path.exists()
    config_valid = False
    config_status = "missing"
    config_message = "No .vibebench/config.yaml found."
    command_groups: dict[str, list[str]] = {}

    if config_present and config_path.is_dir():
        config_status = "invalid"
        config_message = f"Config path is a directory: {config_path}"
    elif config_present:
        try:
            config = load_config(config_path)
            config_valid = True
            config_status = "valid"
            config_message = "Existing VibeBench config is valid."
            command_groups = config.checks.model_dump()
        except ConfigError as exc:
            config_status = "invalid"
            config_message = str(exc)

    findings = project_scan_findings(
        detection,
        config_present=config_present,
        config_valid=config_valid,
        config_message=config_message,
    )
    status = readiness_status(
        findings,
        config_present=config_present,
        config_valid=config_valid,
    )
    payload: dict[str, Any] = {
        "status": status,
        "project_root": str(root),
        "recommended_profile": detection.recommended_profile,
        "detected_stacks": detection.detected_stacks,
        "detection_reasons": detection.detection_reasons,
        "config_present": config_present,
        "config_path": str(config_path),
        "config_valid": config_valid,
        "config_status": config_status,
        "config_message": config_message,
        "active_command_groups": command_groups,
        "package_json_present": detection.package_json_present,
        "package_manager_guess": detection.package_manager_guess,
        "node_scripts": detection.node_scripts,
        "has_lint_script": detection.has_lint_script,
        "has_test_script": detection.has_test_script,
        "has_build_script": detection.has_build_script,
        "pyproject_present": detection.pyproject_present,
        "requirements_present": detection.requirements_present,
        "setup_present": detection.setup_present,
        "tests_dir_present": detection.tests_dir_present,
        "pytest_likely": detection.pytest_likely,
        "ruff_likely": detection.ruff_likely,
        "findings": [finding.to_json() for finding in findings],
        "next_steps": project_scan_next_steps(config_present and config_valid),
        "strict": strict,
        "strict_failed": strict and strict_failure(findings),
    }
    if enforce_policy:
        attach_project_scan_policy(payload, root, enforced=True)
    return payload


def project_scan_findings(
    detection: ProjectDetection,
    *,
    config_present: bool,
    config_valid: bool,
    config_message: str,
) -> list[ProjectScanFinding]:
    """Build deterministic scan findings."""
    findings: list[ProjectScanFinding] = []
    if config_present and config_valid:
        findings.append(
            ProjectScanFinding(
                id="existing_config_valid",
                severity="info",
                title="Existing config is valid",
                message="A .vibebench/config.yaml file was found and validated.",
                recommendation="Run python3 -m vibebench ci --dry-run.",
            )
        )
    elif config_present:
        findings.append(
            ProjectScanFinding(
                id="invalid_vibebench_config",
                severity="error",
                title="Existing config is invalid",
                message=config_message,
                recommendation=(
                    "Fix .vibebench/config.yaml, then run "
                    "python3 -m vibebench config --check."
                ),
            )
        )
    else:
        findings.append(
            ProjectScanFinding(
                id="no_vibebench_config",
                severity="info",
                title="No VibeBench config",
                message="No .vibebench/config.yaml file was found.",
                recommendation="Run python3 -m vibebench init --profile auto.",
            )
        )

    if not detection.detected_stacks:
        findings.append(
            ProjectScanFinding(
                id="no_stack_detected",
                severity="warning",
                title="No project stack detected",
                message="No Python or Node project markers were found.",
                recommendation="Use the generic init profile or add project metadata.",
            )
        )
    elif detection.recommended_profile == "fullstack":
        findings.append(
            ProjectScanFinding(
                id="fullstack_detected",
                severity="info",
                title="Fullstack project detected",
                message="Python and Node project markers were both found.",
                recommendation="Use python3 -m vibebench init --profile auto.",
            )
        )

    if detection.package_json_malformed:
        findings.append(
            ProjectScanFinding(
                id="malformed_package_json",
                severity="error",
                title="package.json is malformed",
                message=(
                    detection.package_json_error
                    or "package.json could not be parsed."
                ),
                recommendation=(
                    "Fix package.json before relying on Node script detection."
                ),
            )
        )
    elif detection.package_json_present:
        if not detection.has_test_script:
            findings.append(
                ProjectScanFinding(
                    id="node_without_test_script",
                    severity="warning",
                    title="Node test script missing",
                    message="package.json does not define a test script.",
                    recommendation=(
                        "Add a test script before enabling Node test checks."
                    ),
                )
            )
        if not detection.has_lint_script:
            findings.append(
                ProjectScanFinding(
                    id="node_without_lint_script",
                    severity="warning",
                    title="Node lint script missing",
                    message="package.json does not define a lint script.",
                    recommendation=(
                        "Add a lint script before enabling Node lint checks."
                    ),
                )
            )

    if "python" in detection.detected_stacks and not detection.tests_dir_present:
        findings.append(
            ProjectScanFinding(
                id="python_without_tests_dir",
                severity="warning",
                title="Python tests directory missing",
                message="Python markers were found, but tests/ was not found.",
                recommendation="Add tests/ or adjust generated checks after init.",
            )
        )

    return findings


def readiness_status(
    findings: list[ProjectScanFinding],
    *,
    config_present: bool,
    config_valid: bool,
) -> str:
    """Return a simple deterministic onboarding readiness status."""
    if any(finding.severity == "error" for finding in findings):
        return "blocked"
    if not config_present:
        return "needs_init"
    if config_present and not config_valid:
        return "blocked"
    if any(finding.severity == "warning" for finding in findings):
        return "needs_attention"
    return "ready"


def strict_failure(findings: list[ProjectScanFinding]) -> bool:
    """Return whether strict mode should fail."""
    strict_error_ids = {"invalid_vibebench_config", "malformed_package_json"}
    return any(finding.id in strict_error_ids for finding in findings)


def project_scan_next_steps(config_ready: bool) -> list[str]:
    """Return concise onboarding next steps."""
    if config_ready:
        return [
            "python3 -m vibebench config --check",
            "python3 -m vibebench ci --dry-run",
        ]
    return [
        "python3 -m vibebench init --profile auto",
        "python3 -m vibebench config --check",
        "python3 -m vibebench ci --dry-run",
        "python3 -m vibebench ci",
    ]


def attach_project_scan_policy(
    payload: dict[str, Any],
    project_root: Path,
    *,
    enforced: bool,
) -> None:
    """Attach project-scan policy evaluation fields to a scan payload."""
    policy_source, effective_policy = resolve_project_scan_policy(project_root)
    policy_findings = evaluate_project_scan_policy(payload, effective_policy)
    payload["policy_source"] = policy_source
    payload["effective_policy"] = effective_policy
    payload["policy_status"] = "failed" if policy_findings else "passed"
    payload["policy_findings"] = [finding.to_json() for finding in policy_findings]
    payload["policy_enforced"] = enforced


def resolve_project_scan_policy(project_root: Path) -> tuple[str, dict[str, Any]]:
    """Return the effective project-scan policy and source."""
    try:
        result = load_effective_config(config_file(project_root))
        policy = result.config.project_scan.policy.model_dump()
        source = result.sources.get("project_scan", "built-in defaults")
    except ConfigError:
        policy = default_config_model().project_scan.policy.model_dump()
        source = "built-in defaults"
    return source, policy


def evaluate_project_scan_policy(
    payload: dict[str, Any],
    policy: dict[str, Any],
) -> list[ProjectScanPolicyFinding]:
    """Evaluate project-scan policy against an existing scan payload."""
    findings: list[ProjectScanPolicyFinding] = []
    if policy.get("require_config_valid") and (
        payload.get("config_present") and not payload.get("config_valid")
    ):
        findings.append(
            ProjectScanPolicyFinding(
                id="config_invalid",
                severity="error",
                title="Existing config must be valid",
                message=str(payload.get("config_message") or "Config is invalid."),
                recommendation=(
                    "Fix .vibebench/config.yaml, then run "
                    "python3 -m vibebench config --check."
                ),
                rule="require_config_valid",
            )
        )

    if policy.get("require_supported_stack") and not payload.get("detected_stacks"):
        findings.append(
            ProjectScanPolicyFinding(
                id="unsupported_stack",
                severity="error",
                title="Supported stack required",
                message="No Python or Node project stack was detected.",
                recommendation="Add project metadata or relax project_scan.policy.",
                rule="require_supported_stack",
            )
        )

    allowed_profiles = policy.get("allowed_profiles") or []
    recommended_profile = str(payload.get("recommended_profile") or "")
    if allowed_profiles and recommended_profile not in allowed_profiles:
        findings.append(
            ProjectScanPolicyFinding(
                id="recommended_profile_not_allowed",
                severity="error",
                title="Recommended profile is not allowed",
                message=(
                    f"Recommended profile {recommended_profile!r} is not in "
                    f"allowed_profiles: {', '.join(allowed_profiles)}."
                ),
                recommendation=(
                    "Update project_scan.policy.allowed_profiles if intentional."
                ),
                rule="allowed_profiles",
            )
        )

    scan_findings = [
        finding for finding in payload.get("findings", []) if isinstance(finding, dict)
    ]
    if policy.get("fail_on_error_findings"):
        findings.extend(
            policy_finding_from_scan_finding(finding, rule="fail_on_error_findings")
            for finding in scan_findings
            if finding.get("severity") == "error"
        )
    if policy.get("fail_on_warning_findings"):
        findings.extend(
            policy_finding_from_scan_finding(
                finding, rule="fail_on_warning_findings"
            )
            for finding in scan_findings
            if finding.get("severity") == "warning"
        )

    selected_profile = payload.get("selected_profile")
    if (
        policy.get("require_recommended_profile")
        and selected_profile is not None
        and selected_profile != recommended_profile
    ):
        findings.append(
            ProjectScanPolicyFinding(
                id="selected_profile_not_recommended",
                severity="error",
                title="Selected profile must match recommendation",
                message=(
                    f"Selected profile {selected_profile!r} does not match "
                    f"recommended profile {recommended_profile!r}."
                ),
                recommendation="Use the recommended profile or relax the policy.",
                rule="require_recommended_profile",
            )
        )
    return findings


def policy_finding_from_scan_finding(
    finding: dict[str, Any],
    *,
    rule: str,
) -> ProjectScanPolicyFinding:
    """Promote a project-scan finding into a policy violation."""
    related = str(finding.get("id") or "unknown")
    return ProjectScanPolicyFinding(
        id=f"{rule}:{related}",
        severity=finding_severity(finding),
        title=f"Policy blocks scan finding: {finding.get('title') or related}",
        message=str(finding.get("message") or "Project-scan finding violated policy."),
        recommendation=str(
            finding.get("recommendation") or "Review project-scan output."
        ),
        rule=rule,
        related_finding=related,
    )


def finding_severity(finding: dict[str, Any]) -> FindingSeverity:
    """Return a valid finding severity from arbitrary payload data."""
    severity = finding.get("severity")
    if severity in {"info", "warning", "error"}:
        return severity
    return "error"


def write_project_scan_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write project-scan JSON output."""
    if path.exists() and path.is_dir():
        raise ConfigError(f"JSON output path is a directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_project_scan_summary(path: Path, payload: dict[str, Any]) -> Path:
    """Write project-scan Markdown summary."""
    if path.exists() and path.is_dir():
        raise ConfigError(f"Summary output path is a directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(project_scan_markdown(payload), encoding="utf-8")
    return path


def project_scan_markdown(payload: dict[str, Any]) -> str:
    """Render a compact project-scan Markdown report."""
    stacks = payload.get("detected_stacks") or []
    stack_text = ", ".join(str(stack) for stack in stacks) if stacks else "none"
    lines = [
        "# VibeBench Project Scan",
        "",
        f"- Status: {payload['status']}",
        f"- Recommended profile: {payload['recommended_profile']}",
        f"- Detected stacks: {stack_text}",
        f"- Config status: {payload['config_status']}",
        "",
        "## Findings",
        "",
        "| Severity | Finding | Recommendation |",
        "| --- | --- | --- |",
    ]
    for finding in payload["findings"]:
        lines.append(
            "| {severity} | {title} | {recommendation} |".format(
                severity=finding["severity"],
                title=markdown_cell(finding["title"]),
                recommendation=markdown_cell(finding["recommendation"]),
            )
        )
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
                    "- Default project-scan remains report-only unless "
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
    lines.extend(["", "## Next Steps", ""])
    for step in payload["next_steps"]:
        lines.append(f"- `{step}`")
    return "\n".join(lines) + "\n"


def markdown_cell(value: object) -> str:
    """Escape Markdown table cell text."""
    return str(value).replace("|", "\\|").replace("\n", " ")
