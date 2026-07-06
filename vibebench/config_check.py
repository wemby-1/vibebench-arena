"""Config consistency diagnostics and artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vibebench.config import ConfigError, EffectiveConfigResult

CONFIG_CHECK_JSON = "config-check.json"
CONFIG_CHECK_SUMMARY = "config-check.md"


def config_consistency_checks(
    result: EffectiveConfigResult,
    *,
    include_advice: bool = False,
) -> list[dict[str, str]]:
    """Return user-facing consistency checks for the active config file."""
    config = result.config
    checks: list[dict[str, str]] = [
        {
            "name": "config_file_exists",
            "status": "passed" if result.config_exists else "failed",
            "message": f"Config file found at {result.config_path}"
            if result.config_exists
            else f"No config file found at {result.config_path}",
        },
        {
            "name": "config_validates",
            "status": "passed",
            "message": "Config parses and validates successfully",
        },
        {
            "name": "project_name",
            "status": "passed" if config.project.name.strip() else "failed",
            "message": "Project name is present"
            if config.project.name.strip()
            else "Project name is empty",
        },
    ]

    if include_advice and not config.project.name.strip():
        checks[-1]["advice"] = (
            "Set project.name to a non-empty project name in .vibebench/config.yaml."
        )

    command_groups = config.checks.model_dump()
    non_empty_groups = {
        group: commands for group, commands in command_groups.items() if commands
    }
    command_group_check = {
        "name": "command_groups",
        "status": "passed" if non_empty_groups else "failed",
        "message": f"{len(non_empty_groups)} command group(s) contain commands"
        if non_empty_groups
        else "At least one command group must contain commands",
    }
    if include_advice and not non_empty_groups:
        command_group_check["advice"] = (
            "Add at least one command under checks.test or checks.lint in "
            ".vibebench/config.yaml."
        )
    checks.append(command_group_check)

    empty_commands = [
        group
        for group, commands in command_groups.items()
        for command in commands
        if not command.strip()
    ]
    command_string_check = {
        "name": "command_strings",
        "status": "passed" if not empty_commands else "failed",
        "message": "All configured command strings are non-empty"
        if not empty_commands
        else "Empty command string found in: " + ", ".join(empty_commands),
    }
    if include_advice and empty_commands:
        command_string_check["advice"] = (
            "Replace empty command entries with real shell commands, for example "
            "pytest -q or ruff check ."
        )
    checks.append(command_string_check)

    gate = config.gate
    checks.append(
        {
            "name": "gate_policy",
            "status": "passed",
            "message": (
                "Gate policy is internally consistent "
                f"(min_score={gate.min_score}, max_risk={gate.max_risk}, "
                f"allow_findings={gate.allow_findings})"
            ),
        }
    )

    risk = config.effective_risk()
    checks.append(
        {
            "name": "risk_policy",
            "status": "passed",
            "message": (
                "Risk policy is internally consistent "
                f"(max_changed_files={risk.max_changed_files}, "
                f"max_patch_lines={risk.max_patch_lines})"
            ),
        }
    )

    regression = config.regression
    regression_check = {
        "name": "regression_policy",
        "status": "passed",
        "message": (
            "Regression policy is internally consistent "
            f"(enabled={str(regression.enabled).lower()}, "
            f"baseline_label={regression.baseline_label or 'none'}, "
            f"require_baseline={str(regression.require_baseline).lower()}, "
            f"max_score_drop={regression.max_score_drop:g}, "
            f"max_risk_increase={regression.max_risk_increase:g})"
        ),
    }
    if include_advice and not regression.enabled:
        regression_check["advice"] = (
            "For a stable pinned regression gate, run "
            "`python3 -m vibebench baseline --set-latest --label stable`, "
            "then set regression.enabled=true, regression.baseline_label=stable, "
            "and regression.require_baseline=true in .vibebench/config.yaml."
        )
    checks.append(regression_check)
    return checks


def config_check_payload(
    result: EffectiveConfigResult,
    checks: list[dict[str, str]],
    *,
    include_advice: bool = False,
) -> dict[str, Any]:
    """Return stable JSON-safe config consistency output."""
    has_errors = any(check["status"] == "failed" for check in checks)
    payload: dict[str, Any] = {
        "config_path": str(result.config_path),
        "overall_status": "failed" if has_errors else "passed",
        "checks": checks,
    }
    if include_advice:
        payload["advice"] = True
    return payload


def config_check_markdown(
    result: EffectiveConfigResult,
    checks: list[dict[str, str]],
    *,
    include_advice: bool = False,
) -> str:
    """Render a human-readable Markdown config check summary."""
    payload = config_check_payload(result, checks, include_advice=include_advice)
    lines = [
        "# VibeBench Config Check",
        "",
        f"- Config path: `{escape_markdown(str(result.config_path))}`",
        f"- Overall status: `{payload['overall_status']}`",
        f"- Advice mode: `{'enabled' if include_advice else 'disabled'}`",
        "",
        "| Check | Status | Message |",
        "| --- | --- | --- |",
    ]
    for check in checks:
        lines.append(
            "| "
            f"{escape_markdown(check['name'])} | "
            f"{escape_markdown(check['status'])} | "
            f"{escape_markdown(check['message'])} |"
        )

    advice_rows = [check for check in checks if "advice" in check]
    if advice_rows:
        lines.extend(["", "## Advice", ""])
        for check in advice_rows:
            lines.append(
                f"- `{escape_markdown(check['name'])}`: "
                f"{escape_markdown(check['advice'])}"
            )
    return "\n".join(lines) + "\n"


def write_config_check_json(
    result: EffectiveConfigResult,
    checks: list[dict[str, str]],
    output_path: Path,
    *,
    include_advice: bool = False,
) -> Path:
    """Write config check JSON to a selected path."""
    validate_output_path(output_path)
    output_path.write_text(
        json.dumps(
            config_check_payload(result, checks, include_advice=include_advice),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output_path


def write_config_check_summary(
    result: EffectiveConfigResult,
    checks: list[dict[str, str]],
    output_path: Path,
    *,
    include_advice: bool = False,
) -> Path:
    """Write config check Markdown to a selected path."""
    validate_output_path(output_path)
    output_path.write_text(
        config_check_markdown(result, checks, include_advice=include_advice),
        encoding="utf-8",
    )
    return output_path


def validate_output_path(output_path: Path) -> None:
    """Validate a requested config check artifact output path."""
    if output_path.exists() and output_path.is_dir():
        raise ConfigError(f"Output path is a directory: {output_path}")
    if not output_path.parent.exists():
        message = f"Output parent directory does not exist: {output_path.parent}"
        raise ConfigError(message)


def advice_for_config_error(exc: ConfigError) -> str:
    """Return concise advice for a config loading error."""
    message = str(exc)
    if "No VibeBench config found" in message:
        return "Run `python -m vibebench init` to create one."
    return (
        "Run `python -m vibebench config --validate` and check "
        "`.vibebench/config.yaml`."
    )


def escape_markdown(value: object) -> str:
    """Escape Markdown table-sensitive characters."""
    return str(value).replace("|", "\\|").replace("\n", " ")
