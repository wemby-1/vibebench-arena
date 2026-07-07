"""Read-only GitHub Actions workflow validation for VibeBench adoption."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vibebench.config import ConfigError

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
) -> dict[str, Any]:
    """Return a deterministic read-only workflow check payload."""
    root = project_root.resolve()
    selected_paths = resolve_workflow_paths(root, path=path, check_all=check_all)
    discovered_paths = [str(item) for item in discover_workflows(root)]
    if path is not None and not discovered_paths:
        discovered_paths = [str(resolve_workflow_path(root, path))]

    checks: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
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
        analyze_workflow_path(
            workflow_path, strict=strict, checks=checks, findings=findings
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
    return {
        "status": status,
        "strict": strict,
        "workflow_path": str(selected_workflow_path)
        if selected_workflow_path
        else None,
        "discovered_paths": discovered_paths,
        "checks": checks,
        "findings": findings,
        "summary": summary,
        "usable_for_vibebench_ci": usable,
        "safe_preview_only": True,
        "message": workflow_check_message(status, selected_workflow_path),
    }


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
) -> None:
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
        return
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
        return
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
        return

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
        return

    lower = content.lower()
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

    has_vibebench_ci = any(pattern in lower for pattern in VIBEBENCH_CI_PATTERNS)
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
            else "Workflow does not run python3 -m vibebench ci."
        ),
        path=workflow_path,
        advice="Add python3 -m vibebench ci to the workflow.",
        line=first_matching_line(content, VIBEBENCH_CI_PATTERNS),
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
    lines = [
        "# VibeBench Workflow Check",
        "",
        f"- Status: {payload['status']}",
        f"- Workflow path: `{payload['workflow_path']}`",
        f"- Strict: {str(payload['strict']).lower()}",
        f"- Passed: {summary['passed']}",
        f"- Warnings: {summary['warning']}",
        f"- Failed: {summary['failed']}",
        "",
        "## Checks",
        "",
        "| Status | Severity | Check | Message |",
        "| --- | --- | --- | --- |",
    ]
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
    lines.extend(
        [
            "",
            "## Advice",
            "",
            "- Use `python3 -m vibebench workflow-template` to preview a "
            "recommended workflow.",
            "- Use `python3 -m vibebench workflow-check --strict` before "
            "relying on CI adoption.",
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
