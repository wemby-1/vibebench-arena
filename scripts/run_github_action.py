#!/usr/bin/env python3
"""Runner for the repository-root VibeBench composite GitHub Action."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALLOWED_PRESETS = {"minimal", "strict", "proof"}
ALLOWED_FAIL_ON = {"quality", "regression", "none"}
DEFAULT_ARTIFACT_NAME = "vibebench-evidence"
MAX_RETENTION_DAYS = 90
MIN_RETENTION_DAYS = 1


class ActionInputError(ValueError):
    """Raised when GitHub Action input validation fails."""


@dataclass(frozen=True)
class ActionInputs:
    """Normalized GitHub Action inputs."""

    preset: str
    config: Path | None
    workspace: Path
    working_directory: Path
    fail_on: frozenset[str]
    required_modes: tuple[str, ...]
    upload_artifacts: bool
    artifact_name: str
    retention_days: int
    python_command: tuple[str, ...]
    action_path: Path


@dataclass(frozen=True)
class ActionResult:
    """Structured action result derived from generated artifacts."""

    exit_code: int
    quality_failed: bool
    infrastructure_failed: bool
    outputs: dict[str, str]
    artifact_paths: list[Path]
    diagnostic: str


def main(argv: list[str] | None = None) -> int:
    """Run the action runner."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        inputs = read_inputs()
        if args.install_only:
            install_from_action_path(inputs)
            return 0
        result = run_action(inputs)
        write_github_outputs(result.outputs)
        append_step_summary(inputs, result)
        return result.exit_code
    except ActionInputError as exc:
        print(f"VibeBench action input error: {exc}", file=sys.stderr)
        write_github_outputs({"status": "infrastructure-failed"})
        append_step_summary_error(str(exc))
        return 2
    except Exception as exc:  # pragma: no cover - last-resort CI diagnostic
        print(f"VibeBench action infrastructure error: {exc}", file=sys.stderr)
        write_github_outputs({"status": "infrastructure-failed"})
        append_step_summary_error(str(exc))
        return 2


def read_inputs(env: dict[str, str] | None = None) -> ActionInputs:
    """Read and validate action inputs from the environment."""
    source = env or os.environ
    workspace = resolve_workspace(source.get("GITHUB_WORKSPACE", "."))
    action_path = Path(source.get("GITHUB_ACTION_PATH", ".")).resolve()
    preset = normalize_preset(source.get("INPUT_PRESET", "minimal"))
    working_directory = resolve_inside_workspace(
        workspace,
        source.get("INPUT_WORKING_DIRECTORY", "") or ".",
        field="working-directory",
    )
    config_value = (source.get("INPUT_CONFIG", "") or "").strip()
    config = (
        resolve_inside_workspace(workspace, config_value, field="config")
        if config_value
        else None
    )
    if config is not None and not config.is_file():
        raise ActionInputError(f"config does not exist or is not a file: {config}")
    return ActionInputs(
        preset=preset,
        config=config,
        workspace=workspace,
        working_directory=working_directory,
        fail_on=parse_fail_on(source.get("INPUT_FAIL_ON", "quality")),
        required_modes=parse_required_modes(source.get("INPUT_REQUIRED_MODE", "")),
        upload_artifacts=parse_bool(
            source.get("INPUT_UPLOAD_ARTIFACTS", "false"),
            "upload-artifacts",
        ),
        artifact_name=parse_artifact_name(
            source.get("INPUT_ARTIFACT_NAME", DEFAULT_ARTIFACT_NAME)
        ),
        retention_days=parse_retention_days(source.get("INPUT_RETENTION_DAYS", "14")),
        python_command=parse_python_command(
            source.get("INPUT_PYTHON_COMMAND", "python3")
        ),
        action_path=action_path,
    )


def normalize_preset(value: str) -> str:
    """Normalize and validate a preset."""
    preset = value.strip().lower()
    if preset not in ALLOWED_PRESETS:
        allowed = ", ".join(sorted(ALLOWED_PRESETS))
        raise ActionInputError(f"preset must be one of {allowed}; got {value!r}")
    return preset


def resolve_workspace(value: str) -> Path:
    """Resolve the caller workspace."""
    workspace = Path(value or ".").resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise ActionInputError(f"GITHUB_WORKSPACE is not a directory: {workspace}")
    return workspace


def resolve_inside_workspace(workspace: Path, value: str, *, field: str) -> Path:
    """Resolve a path and require it to stay inside the caller workspace."""
    raw = Path(value)
    candidate = (raw if raw.is_absolute() else workspace / raw).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise ActionInputError(
            f"{field} must resolve inside GITHUB_WORKSPACE: {value!r}"
        ) from exc
    if field == "working-directory" and (
        not candidate.exists() or not candidate.is_dir()
    ):
        raise ActionInputError(f"working-directory is not a directory: {candidate}")
    return candidate


def parse_bool(value: str, field: str) -> bool:
    """Parse a GitHub-style boolean input."""
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off", ""}:
        return False
    raise ActionInputError(f"{field} must be true or false; got {value!r}")


def parse_retention_days(value: str) -> int:
    """Parse and bound artifact retention days."""
    try:
        days = int(value.strip())
    except ValueError as exc:
        raise ActionInputError("retention-days must be an integer") from exc
    if days < MIN_RETENTION_DAYS or days > MAX_RETENTION_DAYS:
        raise ActionInputError(
            f"retention-days must be between {MIN_RETENTION_DAYS} and "
            f"{MAX_RETENTION_DAYS}"
        )
    return days


def parse_required_modes(value: str) -> tuple[str, ...]:
    """Parse comma/newline separated required CI adoption modes."""
    modes = []
    for chunk in value.replace("\n", ",").split(","):
        mode = chunk.strip()
        if mode:
            modes.append(mode)
    return tuple(dict.fromkeys(modes))


def parse_fail_on(value: str) -> frozenset[str]:
    """Parse the fail-on policy input."""
    selected = {
        item.strip().lower()
        for item in value.replace("\n", ",").split(",")
        if item.strip()
    }
    if not selected:
        selected = {"quality"}
    invalid = selected - ALLOWED_FAIL_ON
    if invalid:
        allowed = ", ".join(sorted(ALLOWED_FAIL_ON))
        raise ActionInputError(f"fail-on supports {allowed}; got {sorted(invalid)}")
    if "none" in selected and len(selected) > 1:
        raise ActionInputError("fail-on=none cannot be combined with other values")
    return frozenset(selected)


def parse_artifact_name(value: str) -> str:
    """Validate a deterministic artifact name."""
    name = value.strip() or DEFAULT_ARTIFACT_NAME
    if any(char in name for char in "\r\n"):
        raise ActionInputError("artifact-name must be a single line")
    return name


def parse_python_command(value: str) -> tuple[str, ...]:
    """Parse a python command without enabling shell execution."""
    try:
        parts = tuple(shlex.split(value.strip() or "python3"))
    except ValueError as exc:
        raise ActionInputError(f"python-command is not parseable: {exc}") from exc
    if not parts:
        raise ActionInputError("python-command must not be empty")
    unsafe = {";", "&&", "||", "|", ">", "<", "`", "$("}
    if any(part in unsafe or "$(" in part or "`" in part for part in parts):
        raise ActionInputError("python-command contains shell control syntax")
    return parts


def install_from_action_path(inputs: ActionInputs) -> None:
    """Install VibeBench from the checked-out action source."""
    if not (inputs.action_path / "pyproject.toml").is_file():
        raise ActionInputError(
            f"GITHUB_ACTION_PATH does not look like VibeBench source: "
            f"{inputs.action_path}"
        )
    run_command(
        [*inputs.python_command, "-m", "pip", "install", "-e", str(inputs.action_path)],
        cwd=inputs.workspace,
    )


def run_action(inputs: ActionInputs) -> ActionResult:
    """Run the selected VibeBench preset and collect structured outputs."""
    command = build_vibebench_command(inputs)
    env = os.environ.copy()
    if inputs.config is not None:
        env["VIBEBENCH_CONFIG_PATH"] = str(inputs.config)
    completed = run_command(
        command,
        cwd=inputs.working_directory,
        check=False,
        env=env,
    )
    run_dir = latest_run_dir(inputs.working_directory)
    proof_completed = None
    if inputs.preset == "proof" and run_dir is not None:
        proof_completed = run_command(
            [
                *inputs.python_command,
                "-m",
                "vibebench",
                "proof",
                "--output-dir",
                ".vibebench/proof-packet",
                "--zip",
            ],
            cwd=inputs.working_directory,
            check=False,
            env=env,
        )
    outputs = collect_outputs(inputs, run_dir)
    proof_path = (
        inputs.working_directory / ".vibebench" / "proof-packet" / "proof.zip"
    )
    artifact_paths = collect_upload_paths(
        run_dir,
        proof_path=proof_path,
    )
    outputs["artifact-count"] = str(len(artifact_paths))
    outputs["artifact-paths"] = "\n".join(path.as_posix() for path in artifact_paths)
    outputs["artifact-name"] = inputs.artifact_name
    outputs["retention-days"] = str(inputs.retention_days)

    proof_failed = proof_completed is not None and proof_completed.returncode != 0
    infrastructure_failed = (
        run_dir is None and completed.returncode != 0
    ) or proof_failed
    quality_failed = completed.returncode != 0 and not infrastructure_failed
    if infrastructure_failed:
        outputs["status"] = "infrastructure-failed"
        exit_code = 2
    elif quality_failed:
        outputs["status"] = "failed"
        exit_code = 1 if "quality" in inputs.fail_on else 0
    else:
        outputs.setdefault("status", "passed")
        exit_code = 0
    return ActionResult(
        exit_code=exit_code,
        quality_failed=quality_failed,
        infrastructure_failed=infrastructure_failed,
        outputs=outputs,
        artifact_paths=artifact_paths,
        diagnostic=(
            (proof_completed.stderr.strip() or proof_completed.stdout.strip())
            if proof_failed and proof_completed is not None
            else completed.stderr.strip() or completed.stdout.strip()
        ),
    )


def build_vibebench_command(inputs: ActionInputs) -> list[str]:
    """Build the VibeBench command as argv, never as shell text."""
    args = {
        "minimal": [
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
        ],
        "strict": ["ci", "--adoption-policy", "--require-adoption-workflow"],
        "proof": [
            "ci",
            "--adoption-policy",
            "--require-adoption-workflow",
            "--bundle-include-report-assets",
        ],
    }[inputs.preset]
    command = [*inputs.python_command, "-m", "vibebench", *args]
    for mode in inputs.required_modes:
        command.extend(["--workflow-check-require-ci-mode", mode])
        command.extend(["--preflight-require-ci-mode", mode])
    if "regression" in inputs.fail_on:
        command.append("--fail-on-regression")
    return command


def run_command(
    command: list[str],
    *,
    cwd: Path,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess without a shell."""
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if check and completed.returncode != 0:
        raise ActionInputError(
            f"command failed with exit code {completed.returncode}: "
            f"{shlex.join(command)}"
        )
    return completed


def latest_run_dir(root: Path) -> Path | None:
    """Return the newest VibeBench run directory if one exists."""
    runs = root / ".vibebench" / "runs"
    if not runs.is_dir():
        return None
    candidates = [path for path in runs.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def collect_outputs(inputs: ActionInputs, run_dir: Path | None) -> dict[str, str]:
    """Derive action outputs from generated machine-readable artifacts."""
    outputs = {
        "status": "",
        "score": "",
        "risk": "",
        "run-id": "",
        "run-dir": "",
        "summary-path": "",
        "manifest-path": "",
        "bundle-path": "",
        "proof-path": "",
    }
    if run_dir is None:
        return outputs
    outputs["run-id"] = run_dir.name
    outputs["run-dir"] = display_path(inputs.workspace, run_dir)
    metrics = load_json(run_dir / "metrics.json")
    if metrics:
        outputs["status"] = str(metrics.get("overall_status", ""))
        outputs["score"] = str(metrics.get("score", ""))
        outputs["risk"] = str(metrics.get("risk_level", ""))
    manifest = run_dir / "manifest.json"
    if manifest.is_file():
        outputs["manifest-path"] = display_path(inputs.workspace, manifest)
    summary = run_dir / "github-step-summary.md"
    github_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_summary:
        outputs["summary-path"] = str(Path(github_summary).resolve())
    elif summary.is_file():
        outputs["summary-path"] = display_path(inputs.workspace, summary)
    bundle = run_dir / "vibebench-bundle.zip"
    if bundle.is_file():
        outputs["bundle-path"] = display_path(inputs.workspace, bundle)
    proof = inputs.working_directory / ".vibebench" / "proof-packet" / "proof.zip"
    if proof.is_file():
        outputs["proof-path"] = display_path(inputs.workspace, proof)
    return outputs


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object or return an empty object."""
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def collect_upload_paths(
    run_dir: Path | None,
    *,
    proof_path: Path | None = None,
) -> list[Path]:
    """Return safe evidence paths intended for optional artifact upload."""
    if run_dir is None:
        if proof_path is not None and proof_path.is_file():
            return [proof_path.resolve()]
        return []
    allowed = [
        "metrics.json",
        "check.log",
        "manifest.json",
        "vibebench-bundle.zip",
        "github-step-summary.md",
        "gate-summary.md",
        "config-check.json",
        "config-check.md",
        "package-check.json",
        "package-check.md",
        "release-check.json",
        "release-check.md",
        "workflow-check.json",
        "workflow-check.md",
        "preflight.json",
        "preflight.md",
        "onboard.json",
        "onboard.md",
        "project-scan.json",
        "project-scan.md",
        "report/index.html",
        "export.json",
        "explain.md",
    ]
    paths = []
    for relative in allowed:
        path = (run_dir / relative).resolve()
        if path.is_file() and not path.is_symlink():
            try:
                path.relative_to(run_dir.resolve())
            except ValueError:
                continue
            paths.append(path)
    if proof_path is not None and proof_path.is_file() and not proof_path.is_symlink():
        paths.append(proof_path.resolve())
    return paths


def display_path(root: Path, path: Path) -> str:
    """Return a workspace-relative path when possible."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def write_github_outputs(outputs: dict[str, str]) -> None:
    """Write newline-safe GitHub Action outputs."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            safe_key = key.strip()
            text = value or ""
            if "\n" in text:
                delimiter = f"vibebench_{safe_key}_EOF"
                while delimiter in text:
                    delimiter += "_"
                handle.write(f"{safe_key}<<{delimiter}\n{text}\n{delimiter}\n")
            else:
                handle.write(f"{safe_key}={text}\n")


def append_step_summary(inputs: ActionInputs, result: ActionResult) -> None:
    """Append a concise action summary when GitHub provides a summary file."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = [
        "## VibeBench Action",
        "",
        f"- Preset: `{inputs.preset}`",
        f"- Status: `{result.outputs.get('status', '')}`",
        f"- Score: `{result.outputs.get('score', '')}`",
        f"- Risk: `{result.outputs.get('risk', '')}`",
        f"- Run directory: `{result.outputs.get('run-dir', '')}`",
        f"- Manifest: `{result.outputs.get('manifest-path', '')}`",
        f"- Bundle: `{result.outputs.get('bundle-path', '')}`",
        f"- Upload paths: `{len(result.artifact_paths)}`",
        "",
        (
            "Quality failures use the VibeBench CI exit code. Infrastructure "
            "failures use exit code 2."
        ),
        "",
    ]
    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def append_step_summary_error(message: str) -> None:
    """Append an infrastructure error summary if possible."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write(
            "\n".join(
                [
                    "## VibeBench Action",
                    "",
                    "- Status: `infrastructure-failed`",
                    f"- Diagnostic: `{message.replace('`', '')}`",
                    "",
                ]
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
