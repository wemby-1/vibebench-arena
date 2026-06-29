"""Machine-readable export generation for VibeBench runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from vibebench.explain import find_latest_valid_run
from vibebench.pr_comment import (
    as_dict,
    as_list,
    cell,
    format_duration,
    inline_code,
    text,
)
from vibebench.report import ReportError, load_metrics

EXPORT_SCHEMA_VERSION = "vibebench.export.v1"
EXPORT_JSON_FILENAME = "export.json"
ExportFormat = Literal["json", "markdown"]


@dataclass(frozen=True)
class ExportResult:
    """Result of exporting one VibeBench run."""

    run_dir: Path
    run_id: str
    format: str
    content: str
    output_path: Path | None = None


def export_run(
    project_root: Path,
    run_dir: Path | None = None,
    output_path: Path | None = None,
    *,
    export_format: str = "json",
    pretty: bool = False,
) -> ExportResult:
    """Export a stable run summary."""
    validate_format(export_format)
    selected_run_dir = (run_dir or find_latest_valid_run(project_root)).resolve()
    if run_dir is not None:
        validate_run_dir(selected_run_dir)

    try:
        metrics = load_metrics(selected_run_dir)
    except json.JSONDecodeError as exc:
        message = f"metrics.json in {selected_run_dir} is not valid JSON."
        raise ReportError(message) from exc

    payload = build_export_payload(metrics, selected_run_dir)
    if export_format == "json":
        content = render_json(payload, pretty=pretty)
    else:
        content = render_markdown(payload)

    selected_output = output_path.resolve() if output_path else None
    if selected_output is not None:
        validate_output_path(selected_output)
        selected_output.write_text(content, encoding="utf-8")

    return ExportResult(
        run_dir=selected_run_dir,
        run_id=selected_run_dir.name,
        format=export_format,
        content=content,
        output_path=selected_output,
    )


def export_json_for_ci(project_root: Path, run_dir: Path | None = None) -> Path:
    """Write export.json for a CI run and return its path."""
    selected_run_dir = (run_dir or find_latest_valid_run(project_root)).resolve()
    output_path = selected_run_dir / EXPORT_JSON_FILENAME
    return export_run(
        project_root,
        selected_run_dir,
        output_path,
        export_format="json",
        pretty=True,
    ).output_path or output_path


def validate_format(value: str) -> None:
    """Validate export format."""
    if value not in {"json", "markdown"}:
        raise ReportError("Unsupported export format. Expected one of: json, markdown.")


def validate_run_dir(run_dir: Path) -> None:
    """Validate an explicitly selected run directory."""
    if not run_dir.exists():
        raise ReportError(f"Run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise ReportError(f"Run path is not a directory: {run_dir}")


def validate_output_path(output_path: Path) -> None:
    """Validate an export output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"Output path is a directory: {output_path}")
    if not output_path.parent.exists():
        message = f"Output parent directory does not exist: {output_path.parent}"
        raise ReportError(message)


def build_export_payload(metrics: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """Build a stable export payload from metrics."""
    diff = as_dict(metrics.get("diff_analysis"))
    findings = as_list(metrics.get("risk_findings"))
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "run_id": run_dir.name,
        "created_at": text(metrics.get("created_at", "")),
        "project": text(metrics.get("project_name", "")),
        "overall_status": text(metrics.get("overall_status", "unknown")),
        "score": int_value(metrics.get("score", 0)),
        "risk_level": text(metrics.get("risk_level", "unknown")),
        "command_results": command_results(metrics),
        "git_diff_risk": git_diff_risk(diff, findings),
        "risk_findings": risk_findings(findings),
        "artifacts": artifact_flags(run_dir),
    }


def command_results(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Return compact command results."""
    results = []
    for command in as_list(metrics.get("command_results")):
        item = as_dict(command)
        results.append(
            {
                "group": text(item.get("group", "")),
                "command": text(item.get("command", "")),
                "status": text(item.get("status", "unknown")),
                "exit_code": int_value(item.get("exit_code", 0)),
                "duration_seconds": float_value(item.get("duration_seconds", 0.0)),
            }
        )
    return results


def git_diff_risk(diff: dict[str, Any], findings: list[Any]) -> dict[str, Any]:
    """Return compact Git diff risk information."""
    return {
        "changed_files": int_value(diff.get("changed_file_count", 0)),
        "added_lines": int_value(diff.get("total_added_lines", 0)),
        "deleted_lines": int_value(diff.get("total_deleted_lines", 0)),
        "patch_lines": int_value(diff.get("total_patch_lines", 0)),
        "tests_deleted": [text(path) for path in as_list(diff.get("tests_deleted"))],
        "forbidden_paths_touched": [
            text(path) for path in as_list(diff.get("forbidden_paths_touched"))
        ],
        "secret_like_files_touched": [
            text(path) for path in as_list(diff.get("secret_like_files_touched"))
        ],
        "lockfiles_changed": [
            text(path) for path in as_list(diff.get("lockfiles_changed"))
        ],
        "risk_findings_count": len(findings),
    }


def risk_findings(findings: list[Any]) -> list[dict[str, Any]]:
    """Return compact risk findings."""
    results = []
    for finding in findings:
        item = as_dict(finding)
        results.append(
            {
                "severity": text(item.get("severity", "info")),
                "code": text(item.get("code", "unknown")),
                "message": text(item.get("message", "")),
                "paths": [text(path) for path in as_list(item.get("paths"))],
            }
        )
    return results


def artifact_flags(run_dir: Path) -> dict[str, bool]:
    """Return booleans for known run artifacts."""
    return {
        "metrics_json": (run_dir / "metrics.json").is_file(),
        "check_log": (run_dir / "check.log").is_file(),
        "html_report": (run_dir / "report" / "index.html").is_file(),
        "pr_comment": (run_dir / "pr-comment.md").is_file(),
        "github_summary": (run_dir / "github-step-summary.md").is_file(),
        "gate_summary": (run_dir / "gate-summary.md").is_file(),
        "explain": (run_dir / "explain.md").is_file(),
        "bundle_zip": (run_dir / "vibebench-bundle.zip").is_file(),
        "compare": (run_dir / "compare.md").is_file(),
    }


def render_json(payload: dict[str, Any], *, pretty: bool) -> str:
    """Render JSON export."""
    if pretty:
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n"


def render_markdown(payload: dict[str, Any]) -> str:
    """Render compact deterministic Markdown export."""
    commands = as_list(payload.get("command_results"))
    diff = as_dict(payload.get("git_diff_risk"))
    artifacts = as_dict(payload.get("artifacts"))
    lines = [
        "# VibeBench Export",
        "",
        f"- Project: {cell(payload.get('project', ''))}",
        f"- Run id: `{inline_code(payload.get('run_id', ''))}`",
        f"- Status: {cell(payload.get('overall_status', 'unknown'))}",
        f"- Score: {cell(payload.get('score', 0))}",
        f"- Risk: {cell(payload.get('risk_level', 'unknown'))}",
        "",
        "## Command Results",
        "",
        command_table(commands),
        "",
        "## Risk Summary",
        "",
        f"- Changed files: {cell(diff.get('changed_files', 0))}",
        f"- Added lines: {cell(diff.get('added_lines', 0))}",
        f"- Deleted lines: {cell(diff.get('deleted_lines', 0))}",
        f"- Patch lines: {cell(diff.get('patch_lines', 0))}",
        f"- Risk findings: {cell(diff.get('risk_findings_count', 0))}",
        "",
        "## Artifacts",
        "",
        artifact_checklist(artifacts),
        "",
    ]
    return "\n".join(lines)


def command_table(commands: list[Any]) -> str:
    """Render command result table."""
    rows = [
        "| Group | Command | Status | Exit Code | Duration |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not commands:
        rows.append("| - | - | - | - | - |")
        return "\n".join(rows)

    for command in commands:
        item = as_dict(command)
        rows.append(
            "| "
            f"{cell(item.get('group', ''))} | "
            f"`{inline_code(item.get('command', ''))}` | "
            f"{cell(item.get('status', 'unknown'))} | "
            f"{cell(item.get('exit_code', ''))} | "
            f"{cell(format_duration(item.get('duration_seconds', 0)))} |"
        )
    return "\n".join(rows)


def artifact_checklist(artifacts: dict[str, Any]) -> str:
    """Render artifact availability checklist."""
    rows = []
    for name in sorted(artifacts):
        marker = "x" if bool(artifacts[name]) else " "
        rows.append(f"- [{marker}] `{inline_code(name)}`")
    return "\n".join(rows)


def int_value(value: Any) -> int:
    """Convert a metric value to int safely."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def float_value(value: Any) -> float:
    """Convert a metric value to float safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
