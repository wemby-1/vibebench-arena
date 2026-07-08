"""Safe GitHub Actions workflow template generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vibebench.config import ConfigError
from vibebench.project_detect import detect_project

WORKFLOW_RELATIVE_PATH = Path(".github") / "workflows" / "vibebench.yml"
WORKFLOW_TEMPLATE_JSON = "workflow-template.json"
WORKFLOW_TEMPLATE_SUMMARY = "workflow-template.md"
WORKFLOW_TEMPLATE_YAML = "workflow-template.yml"
WORKFLOW_PROFILES = {"generic", "python", "node", "fullstack", "auto"}
WORKFLOW_CI_MODES = {"basic", "adoption", "adoption-policy", "strict"}
DEFAULT_WORKFLOW_INSTALL_COMMAND = "python3 -m pip install -e ."


def workflow_template_payload(
    project_root: Path,
    output_path: Path,
    *,
    profile: str,
    ci_mode: str,
    install_command: str,
    write: bool,
    dry_run: bool,
    force: bool,
) -> dict[str, Any]:
    """Plan or write a safe GitHub Actions workflow template."""
    if profile not in WORKFLOW_PROFILES:
        allowed = ", ".join(sorted(WORKFLOW_PROFILES))
        raise ConfigError(
            f"Unknown workflow profile '{profile}'. Choose one of: {allowed}."
        )
    if ci_mode not in WORKFLOW_CI_MODES:
        allowed = ", ".join(sorted(WORKFLOW_CI_MODES))
        raise ConfigError(f"Unknown CI mode '{ci_mode}'. Choose one of: {allowed}.")
    if not install_command.strip():
        raise ConfigError("Install command must not be empty.")
    if output_path.exists() and output_path.is_dir():
        raise ConfigError(f"Workflow output path is a directory: {output_path}")

    detection = detect_project(project_root)
    resolved_profile = detection.recommended_profile if profile == "auto" else profile
    commands = workflow_template_commands(ci_mode)
    warnings = workflow_template_warnings(resolved_profile, install_command)
    workflow_yaml = render_workflow_yaml(
        resolved_profile=resolved_profile,
        install_command=install_command,
        commands=commands,
    )
    validate_workflow_yaml(workflow_yaml)

    exists = output_path.exists()
    would_write = bool(write and not dry_run and (force or not exists))
    blocked = bool(write and not dry_run and exists and not force)
    status = "blocked" if blocked else "planned"
    workflow_written = False
    if blocked:
        raise ConfigError(
            f"Workflow already exists at {output_path}. "
            "Use --force to overwrite it intentionally."
        )
    if would_write:
        write_workflow_template_file(output_path, workflow_yaml)
        workflow_written = True
        status = "written" if not exists else "overwritten"

    message = workflow_template_message(
        write=write,
        dry_run=dry_run,
        workflow_written=workflow_written,
        exists=exists,
    )
    return {
        "status": status,
        "workflow_name": "VibeBench",
        "project_root": str(project_root),
        "target_path": str(output_path),
        "output_path": str(output_path),
        "would_write": bool(write and (force or not exists)),
        "exists": exists,
        "profile": profile,
        "resolved_profile": resolved_profile,
        "ci_mode": ci_mode,
        "dry_run": dry_run,
        "write": write,
        "force": force,
        "workflow_written": workflow_written,
        "detected_stacks": detection.detected_stacks if profile == "auto" else [],
        "detection_reasons": detection.detection_reasons if profile == "auto" else [],
        "install_command": install_command,
        "commands": commands,
        "template": workflow_yaml,
        "workflow_yaml": workflow_yaml,
        "warnings": warnings,
        "next_steps": workflow_template_next_steps(output_path),
        "message": message,
    }


def workflow_template_error_payload(
    project_root: Path,
    output_path: Path,
    *,
    profile: str,
    ci_mode: str,
    install_command: str,
    write: bool,
    dry_run: bool,
    force: bool,
    message: str,
) -> dict[str, Any]:
    """Return JSON-safe workflow-template error details."""
    return {
        "status": "failed",
        "workflow_name": "VibeBench",
        "project_root": str(project_root),
        "target_path": str(output_path),
        "output_path": str(output_path),
        "would_write": False,
        "exists": output_path.exists(),
        "profile": profile,
        "resolved_profile": None,
        "ci_mode": ci_mode,
        "dry_run": dry_run,
        "write": write,
        "force": force,
        "workflow_written": False,
        "detected_stacks": [],
        "detection_reasons": [],
        "install_command": install_command,
        "commands": [],
        "template": "",
        "workflow_yaml": "",
        "warnings": [],
        "next_steps": workflow_template_next_steps(output_path),
        "message": message,
    }


def workflow_template_commands(ci_mode: str) -> list[str]:
    """Return the VibeBench commands included in a workflow CI mode."""
    if ci_mode == "basic":
        return [
            "python3 -m vibebench config --check",
            "python3 -m vibebench ci",
        ]
    if ci_mode == "adoption":
        return [
            "python3 -m vibebench ci --adoption",
        ]
    if ci_mode == "adoption-policy":
        return [
            "python3 -m vibebench ci --adoption-policy",
        ]
    if ci_mode == "strict":
        return [
            "python3 -m vibebench config --check",
            "python3 -m vibebench project-scan --enforce-policy --json",
            "python3 -m vibebench onboard --enforce-policy --json",
            "python3 -m vibebench ci --project-scan-policy --onboard-policy",
        ]
    raise ConfigError(f"Unknown CI mode '{ci_mode}'.")


def workflow_template_warnings(
    resolved_profile: str, install_command: str
) -> list[str]:
    """Return deterministic workflow-template warnings."""
    warnings = [
        "Review the install command before committing the workflow.",
        (
            "The command only generates files; it does not call GitHub "
            "or change repository settings."
        ),
    ]
    if install_command == DEFAULT_WORKFLOW_INSTALL_COMMAND:
        warnings.append(
            "Default install command assumes VibeBench is available from this "
            "checkout; customize with --install-command if needed."
        )
    if resolved_profile in {"node", "fullstack"}:
        warnings.append(
            "Node setup is included, but package install/test commands remain "
            "controlled by your VibeBench config."
        )
    return warnings


def workflow_template_next_steps(output_path: Path) -> list[str]:
    """Return standard workflow-template next steps."""
    return [
        "python3 -m vibebench workflow-template",
        "python3 -m vibebench workflow-template --ci-mode adoption --write",
        f"Review {output_path} before committing it.",
    ]


def render_workflow_yaml(
    *,
    resolved_profile: str,
    install_command: str,
    commands: list[str],
) -> str:
    """Render the conservative GitHub Actions workflow YAML."""
    lines = [
        "name: VibeBench",
        "",
        "on:",
        "  pull_request:",
        "  push:",
        "    branches:",
        "      - main",
        "",
        "permissions:",
        "  contents: read",
        "",
        "jobs:",
        "  vibebench:",
        "    runs-on: ubuntu-latest",
        "",
        "    steps:",
        "      - name: Check out repository",
        "        uses: actions/checkout@v5",
        "",
        "      - name: Set up Python",
        "        uses: actions/setup-python@v6",
        "        with:",
        '          python-version: "3.11"',
    ]
    if resolved_profile in {"node", "fullstack"}:
        lines.extend(
            [
                "",
                "      - name: Set up Node",
                "        uses: actions/setup-node@v5",
                "        with:",
                '          node-version: "20"',
            ]
        )
    lines.extend(
        [
            "",
            "      - name: Install project and VibeBench",
            "        run: |",
            "          # Customize this install command for your repository.",
        ]
    )
    lines.extend(f"          {line}" for line in install_command.splitlines())
    for command in commands:
        lines.extend(
            [
                "",
                f"      - name: {workflow_step_name(command)}",
                f"        run: {command}",
            ]
        )
    return "\n".join(lines) + "\n"


def workflow_step_name(command: str) -> str:
    """Return a readable workflow step name for a VibeBench command."""
    if "config --check" in command:
        return "Check VibeBench config"
    if " vibebench ci" in command:
        return "Run VibeBench CI"
    if "project-scan" in command:
        return "Run project scan"
    if "onboard" in command:
        return "Generate onboarding plan"
    return "Run VibeBench command"


def validate_workflow_yaml(workflow_yaml: str) -> None:
    """Catch empty, malformed, or unsafe workflow template generation."""
    required = [
        "name: VibeBench",
        "on:",
        "  pull_request:",
        "  push:",
        "permissions:",
        "  contents: read",
        "runs-on: ubuntu-latest",
        "actions/checkout",
        "actions/setup-python",
    ]
    missing = [item for item in required if item not in workflow_yaml]
    if missing:
        raise ConfigError("Generated workflow is missing required YAML content.")
    forbidden = [
        "secrets.",
        "GITHUB_TOKEN",
        "gh ",
        "deploy-pages",
        "pages: write",
        "upload-release",
        "create-release",
        "npm publish",
        "twine upload",
        "pypi",
        "repository settings",
    ]
    lowered = workflow_yaml.lower()
    found = [item for item in forbidden if item.lower() in lowered]
    if found:
        raise ConfigError("Generated workflow includes unsafe automation content.")
    for line in workflow_yaml.splitlines():
        if line.rstrip() != line:
            raise ConfigError("Generated workflow contains trailing whitespace.")


def workflow_template_message(
    *,
    write: bool,
    dry_run: bool,
    workflow_written: bool,
    exists: bool,
) -> str:
    """Return a concise workflow-template message."""
    if workflow_written:
        return "Workflow file written. Review it before committing."
    if dry_run:
        return "Dry run only; no workflow file was written."
    if write and exists:
        return "Workflow exists and would require --force to overwrite."
    return "Preview only; no workflow file was written."


def write_workflow_template_file(output_path: Path, workflow_yaml: str) -> Path:
    """Atomically write a workflow template file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(output_path.name + ".tmp")
    try:
        temp_path.write_text(workflow_yaml, encoding="utf-8")
        validate_workflow_yaml(temp_path.read_text(encoding="utf-8"))
        temp_path.replace(output_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return output_path


def workflow_template_json(payload: dict[str, Any]) -> str:
    """Return pure JSON for a workflow template payload."""
    return json.dumps(payload, indent=2, sort_keys=True)


def write_workflow_template_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write workflow-template JSON output."""
    validate_workflow_output_path(path, label="JSON output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workflow_template_json(payload) + "\n", encoding="utf-8")
    return path


def write_workflow_template_summary(path: Path, payload: dict[str, Any]) -> Path:
    """Write workflow-template Markdown summary."""
    validate_workflow_output_path(path, label="Summary output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workflow_template_markdown(payload), encoding="utf-8")
    return path


def workflow_template_markdown(payload: dict[str, Any]) -> str:
    """Render a workflow template payload as compact Markdown."""
    lines = [
        "# VibeBench Workflow Template",
        "",
        f"- Target workflow path: `{payload['output_path']}`",
        f"- Would write: {format_bool(payload['would_write'])}",
        f"- Workflow written: {format_bool(payload['workflow_written'])}",
        f"- Profile: {payload['profile']}",
        f"- Resolved profile: {payload['resolved_profile']}",
        f"- CI mode: {payload['ci_mode']}",
        "",
        "## Commands Included",
        "",
    ]
    for command in payload.get("commands", []):
        lines.append(f"- `{command}`")
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
    lines.extend(["", "## Next Steps", ""])
    for step in payload.get("next_steps", []):
        lines.append(f"- `{step}`")
    lines.extend(
        [
            "",
            "## Workflow YAML",
            "",
            "```yaml",
            str(payload.get("workflow_yaml") or payload.get("template") or "").rstrip(),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def validate_workflow_output_path(path: Path, *, label: str) -> None:
    """Validate a requested workflow-template output path."""
    if path.exists() and path.is_dir():
        raise ConfigError(f"{label} path is a directory: {path}")


def format_bool(value: object) -> str:
    """Format booleans for concise text output."""
    return "yes" if value else "no"
