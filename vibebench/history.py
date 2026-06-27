"""Read recent VibeBench run history."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from vibebench.paths import config_dir
from vibebench.report import ReportError


class HistoryRun(BaseModel):
    """One row in VibeBench run history."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    run_dir: Path
    overall_status: str
    score: int
    risk_level: str
    changed_files: int
    patch_lines: int
    risk_findings_count: int
    has_report: bool
    has_pr_comment: bool
    has_github_summary: bool
    has_compare: bool


class HistoryResult(BaseModel):
    """VibeBench run history result."""

    model_config = ConfigDict(extra="forbid")

    runs_dir: Path
    runs: list[HistoryRun]
    warnings: list[str]


def get_history(
    project_root: Path,
    runs_dir: Path | None = None,
    limit: int = 10,
) -> HistoryResult:
    """Load recent VibeBench runs from metrics.json files."""
    if limit < 1:
        raise ReportError("--limit must be greater than 0.")

    root = project_root.resolve()
    selected_runs_dir = resolve_runs_dir(root, runs_dir)
    if not selected_runs_dir.exists():
        if runs_dir is not None:
            raise ReportError(f"Runs directory does not exist: {selected_runs_dir}")
        return HistoryResult(runs_dir=selected_runs_dir, runs=[], warnings=[])
    if not selected_runs_dir.is_dir():
        raise ReportError(f"Runs path is not a directory: {selected_runs_dir}")

    run_dirs = sorted(
        (
            path
            for path in selected_runs_dir.iterdir()
            if path.is_dir() and (path / "metrics.json").exists()
        ),
        reverse=True,
    )
    if not run_dirs:
        return HistoryResult(runs_dir=selected_runs_dir, runs=[], warnings=[])

    rows: list[HistoryRun] = []
    warnings: list[str] = []
    for run_dir in run_dirs:
        try:
            rows.append(load_history_run(run_dir))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            warnings.append(
                f"Skipped {run_dir.name}: could not read metrics.json: {exc}"
            )
        if len(rows) >= limit:
            break

    if not rows and warnings:
        raise ReportError(
            "No valid VibeBench runs found; all metrics.json files were unreadable "
            "or corrupt."
        )

    return HistoryResult(runs_dir=selected_runs_dir, runs=rows, warnings=warnings)


def resolve_runs_dir(project_root: Path, runs_dir: Path | None) -> Path:
    """Resolve a runs directory relative to the project root."""
    if runs_dir is not None:
        if runs_dir.is_absolute():
            return runs_dir.resolve()
        return (project_root / runs_dir).resolve()
    return config_dir(project_root) / "runs"


def load_history_run(run_dir: Path) -> HistoryRun:
    """Load one history row from a run directory."""
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    summary = as_dict(metrics.get("summary"))
    diff = as_dict(metrics.get("diff_analysis"))
    findings = as_list(metrics.get("risk_findings"))

    return HistoryRun(
        run_id=run_dir.name,
        run_dir=run_dir,
        overall_status=text(metrics.get("overall_status", "unknown")),
        score=as_int(metrics.get("score")),
        risk_level=text(metrics.get("risk_level", "unknown")),
        changed_files=as_int(diff.get("changed_file_count")),
        patch_lines=as_int(diff.get("total_patch_lines")),
        risk_findings_count=as_int(summary.get("total_findings"), len(findings)),
        has_report=(run_dir / "report" / "index.html").exists(),
        has_pr_comment=(run_dir / "pr-comment.md").exists(),
        has_github_summary=(run_dir / "github-step-summary.md").exists(),
        has_compare=(run_dir / "compare.md").exists(),
    )


def as_dict(value: object) -> dict[str, Any]:
    """Return value as a dict if possible."""
    return value if isinstance(value, dict) else {}


def as_list(value: object) -> list[Any]:
    """Return value as a list if possible."""
    return value if isinstance(value, list) else []


def as_int(value: object, default: int = 0) -> int:
    """Coerce a dynamic JSON value to int safely."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def text(value: object) -> str:
    """Convert a dynamic JSON value to text."""
    if value is None:
        return ""
    return str(value)
