"""Reusable GitHub Action preset and workflow snippet helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibebench.config import ConfigError

ACTION_REF = "wemby-1/vibebench-arena@main"
ACTION_PREVIEW_WARNING = (
    "Preview/development action reference: @main is not a stable release. "
    "Production consumers should pin a future stable tag or a reviewed commit SHA."
)
ACTION_WORKFLOW_NAME = "VibeBench"
ACTION_WORKFLOW_PATH = Path(".github") / "workflows" / "vibebench.yml"
ACTION_PRESETS = ("minimal", "strict", "proof")


@dataclass(frozen=True)
class ActionPreset:
    """One stable external-consumer action preset."""

    name: str
    description: str
    ci_args: tuple[str, ...]
    required_mode: str
    uploads_by_default: bool


PRESETS: dict[str, ActionPreset] = {
    "minimal": ActionPreset(
        name="minimal",
        description=(
            "First-adoption preset: runs the core VibeBench CI flow with a small "
            "artifact footprint."
        ),
        ci_args=(
            "ci",
            "--skip-report",
            "--skip-pr-comment",
            "--skip-badge",
            "--skip-status-block",
            "--skip-trend",
            "--skip-run-index",
            "--skip-compare",
            "--skip-evidence-room",
            "--skip-release-check",
            "--skip-package-check",
        ),
        required_mode="adoption",
        uploads_by_default=False,
    ),
    "strict": ActionPreset(
        name="strict",
        description=(
            "Policy-oriented preset: runs adoption-policy evidence and enforces "
            "configured readiness policies."
        ),
        ci_args=(
            "ci",
            "--adoption-policy",
            "--require-adoption-workflow",
            "--skip-package-check",
        ),
        required_mode="adoption-policy",
        uploads_by_default=True,
    ),
    "proof": ActionPreset(
        name="proof",
        description=(
            "Review preset: strict checks plus the standard manifest, bundle, "
            "and proof-oriented evidence paths."
        ),
        ci_args=(
            "ci",
            "--adoption-policy",
            "--require-adoption-workflow",
            "--bundle-include-report-assets",
            "--skip-package-check",
        ),
        required_mode="adoption-policy",
        uploads_by_default=True,
    ),
}


def normalize_action_preset(value: str | None) -> ActionPreset:
    """Return a known action preset or raise a clear config error."""
    preset = (value or "minimal").strip().lower()
    if preset not in PRESETS:
        allowed = ", ".join(ACTION_PRESETS)
        raise ConfigError(f"Unknown GitHub Action preset '{value}'. Choose: {allowed}.")
    return PRESETS[preset]


def action_workflow_payload(
    *,
    preset: str = "minimal",
    config: str = "",
    required_mode: str = "",
    upload_artifacts: bool | None = None,
    action_ref: str = ACTION_REF,
) -> dict[str, Any]:
    """Return deterministic external-consumer workflow snippet data."""
    selected = normalize_action_preset(preset)
    upload = (
        selected.uploads_by_default
        if upload_artifacts is None
        else upload_artifacts
    )
    workflow = render_action_workflow(
        preset=selected.name,
        config=config,
        required_mode=required_mode or selected.required_mode,
        upload_artifacts=upload,
        action_ref=action_ref,
    )
    return {
        "status": "ready",
        "schema_version": "vibebench.github_action.v1",
        "preset": selected.name,
        "description": selected.description,
        "config": config,
        "required_mode": required_mode or selected.required_mode,
        "upload_artifacts": upload,
        "artifact_name": "vibebench-evidence",
        "action_ref": action_ref,
        "preview_warning": ACTION_PREVIEW_WARNING,
        "workflow_path": ACTION_WORKFLOW_PATH.as_posix(),
        "workflow": workflow,
        "presets": [
            {
                "name": item.name,
                "description": item.description,
                "required_mode": item.required_mode,
                "uploads_by_default": item.uploads_by_default,
                "ci_args": list(item.ci_args),
            }
            for item in PRESETS.values()
        ],
    }


def render_action_workflow(
    *,
    preset: str,
    config: str = "",
    required_mode: str = "",
    upload_artifacts: bool = False,
    action_ref: str = ACTION_REF,
) -> str:
    """Render a concise external-consumer workflow using the composite action."""
    selected = normalize_action_preset(preset)
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
        "",
        "      - name: Run VibeBench",
        "        uses: " + action_ref,
        "        with:",
        f"          preset: {selected.name}",
    ]
    if config:
        lines.append(f"          config: {config}")
    if required_mode:
        lines.append(f"          required-mode: {required_mode}")
    lines.extend(
        [
            f"          upload-artifacts: {str(upload_artifacts).lower()}",
            "          artifact-name: vibebench-evidence",
        ]
    )
    return "\n".join(lines) + "\n"


def action_workflow_json(payload: dict[str, Any]) -> str:
    """Serialize an action workflow payload as stable JSON."""
    return json.dumps(payload, indent=2, sort_keys=True)
