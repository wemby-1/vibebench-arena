"""Run index generation for VibeBench runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from vibebench.artifacts import KNOWN_ARTIFACTS, collect_artifact_inventory
from vibebench.bundle import BUNDLE_FILENAME
from vibebench.paths import config_dir
from vibebench.report import ReportError, load_metrics

RUN_INDEX_JSON = "run-index.json"
RUN_INDEX_SUMMARY = "run-index.md"


@dataclass(frozen=True)
class RunIndexItem:
    """One run directory row in the run index."""

    run_id: str
    path: Path
    status: str
    score: int | None
    risk_level: str
    created_at: str
    metrics_available: bool
    manifest_available: bool
    bundle_available: bool
    report_available: bool
    available_artifacts: int
    total_artifacts: int
    message: str


@dataclass(frozen=True)
class RunIndexResult:
    """Run index for recent VibeBench run directories."""

    status: str
    project_root: Path
    runs_dir: Path
    limit: int
    total_runs_seen: int
    runs: list[RunIndexItem]
    generated_at: str


def build_run_index(
    project_root: Path,
    runs_dir: Path | None = None,
    limit: int = 10,
) -> RunIndexResult:
    """Build a tolerant index of recent VibeBench run directories."""
    if limit < 1:
        raise ReportError("--limit must be greater than 0.")

    root = project_root.resolve()
    selected_runs_dir = resolve_runs_dir(root, runs_dir)
    generated_at = datetime.now(UTC).isoformat()

    if not selected_runs_dir.exists():
        return RunIndexResult(
            status="empty",
            project_root=root,
            runs_dir=selected_runs_dir,
            limit=limit,
            total_runs_seen=0,
            runs=[],
            generated_at=generated_at,
        )
    if not selected_runs_dir.is_dir():
        raise ReportError(f"Runs path is not a directory: {selected_runs_dir}")

    run_dirs = sorted(
        (path for path in selected_runs_dir.iterdir() if path.is_dir()),
        reverse=True,
    )
    runs = [load_run_index_item(root, run_dir) for run_dir in run_dirs[:limit]]
    return RunIndexResult(
        status="ok" if runs else "empty",
        project_root=root,
        runs_dir=selected_runs_dir,
        limit=limit,
        total_runs_seen=len(run_dirs),
        runs=runs,
        generated_at=generated_at,
    )


def resolve_runs_dir(project_root: Path, runs_dir: Path | None) -> Path:
    """Resolve a runs directory relative to the project root."""
    if runs_dir is not None:
        if runs_dir.is_absolute():
            return runs_dir.resolve()
        return (project_root / runs_dir).resolve()
    return config_dir(project_root) / "runs"


def load_run_index_item(project_root: Path, run_dir: Path) -> RunIndexItem:
    """Load one run index item without crashing on partial/corrupt runs."""
    metrics_path = run_dir / "metrics.json"
    metrics_available = metrics_path.is_file() and not metrics_path.is_symlink()
    available_artifacts, total_artifacts = artifact_counts(run_dir)
    base = {
        "run_id": run_dir.name,
        "path": display_path(project_root, run_dir),
        "manifest_available": artifact_available(run_dir, Path("manifest.json")),
        "bundle_available": artifact_available(run_dir, Path(BUNDLE_FILENAME)),
        "report_available": artifact_available(run_dir, Path("report") / "index.html"),
    }

    if not metrics_available:
        return RunIndexItem(
            **base,
            status="unknown",
            score=None,
            risk_level="unknown",
            created_at="",
            metrics_available=False,
            available_artifacts=available_artifacts,
            total_artifacts=total_artifacts,
            message="metrics.json missing",
        )

    try:
        metrics = load_metrics(run_dir)
        inventory = collect_artifact_inventory(project_root, run_dir)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return RunIndexItem(
            **base,
            status="invalid",
            score=None,
            risk_level="unknown",
            created_at="",
            metrics_available=True,
            available_artifacts=available_artifacts,
            total_artifacts=total_artifacts,
            message=f"metrics.json unreadable: {exc}",
        )

    return RunIndexItem(
        **base,
        status=text(metrics.get("overall_status", "unknown")),
        score=optional_int(metrics.get("score")),
        risk_level=text(metrics.get("risk_level", "unknown")),
        created_at=text(metrics.get("created_at", "")),
        metrics_available=True,
        available_artifacts=sum(1 for item in inventory.artifacts if item.available),
        total_artifacts=len(inventory.artifacts),
        message="ok",
    )


def artifact_counts(run_dir: Path) -> tuple[int, int]:
    """Return available and total known artifact counts without validating metrics."""
    available = sum(1 for path in KNOWN_ARTIFACTS if artifact_available(run_dir, path))
    return available, len(KNOWN_ARTIFACTS)


def artifact_available(run_dir: Path, relative_path: Path) -> bool:
    """Return whether a known artifact exists as a regular file."""
    artifact_path = run_dir / relative_path
    return artifact_path.is_file() and not artifact_path.is_symlink()


def run_index_payload(result: RunIndexResult) -> dict[str, object]:
    """Return a deterministic JSON payload for the run index."""
    return {
        "generated_at": result.generated_at,
        "limit": result.limit,
        "project_root": str(result.project_root),
        "runs": [run_item_payload(item) for item in result.runs],
        "runs_dir": str(result.runs_dir),
        "status": result.status,
        "total_runs_seen": result.total_runs_seen,
    }


def run_item_payload(item: RunIndexItem) -> dict[str, object]:
    """Return a JSON-safe run index item."""
    return {
        "available_artifacts": item.available_artifacts,
        "bundle_available": item.bundle_available,
        "created_at": item.created_at,
        "manifest_available": item.manifest_available,
        "message": item.message,
        "metrics_available": item.metrics_available,
        "path": item.path.as_posix(),
        "report_available": item.report_available,
        "risk_level": item.risk_level,
        "run_id": item.run_id,
        "score": item.score,
        "status": item.status,
        "total_artifacts": item.total_artifacts,
    }


def write_run_index_json(result: RunIndexResult, output_path: Path) -> Path:
    """Write run index JSON to a file."""
    validate_output_path(output_path)
    output_path.write_text(
        json.dumps(run_index_payload(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_run_index_summary(result: RunIndexResult, output_path: Path) -> Path:
    """Write run index Markdown to a file."""
    validate_output_path(output_path)
    output_path.write_text(render_markdown(result), encoding="utf-8")
    return output_path


def render_markdown(result: RunIndexResult) -> str:
    """Render a human-readable Markdown run index."""
    lines = [
        "# VibeBench Run Index",
        "",
        f"- Generated at: {result.generated_at}",
        f"- Runs directory: {result.runs_dir}",
        f"- Total run directories seen: {result.total_runs_seen}",
        f"- Limit: {result.limit}",
        "",
        "| Run | Status | Score | Risk | Artifacts | Path | Message |",
        "| --- | --- | ---: | --- | ---: | --- | --- |",
    ]
    for index, item in enumerate(result.runs):
        run_id = f"{item.run_id} (latest)" if index == 0 else item.run_id
        score = "" if item.score is None else str(item.score)
        artifacts = f"{item.available_artifacts}/{item.total_artifacts}"
        lines.append(
            "| "
            f"{markdown_cell(run_id)} | "
            f"{markdown_cell(item.status)} | "
            f"{score} | "
            f"{markdown_cell(item.risk_level)} | "
            f"{artifacts} | "
            f"{markdown_cell(item.path.as_posix())} | "
            f"{markdown_cell(item.message)} |"
        )
    if not result.runs:
        lines.append("| _No run directories found._ |  |  |  |  |  |  |")
    notes = [item for item in result.runs if item.message != "ok"]
    if notes:
        lines.extend(["", "## Notes", ""])
        for item in notes:
            lines.append(f"- {item.run_id}: {item.message}")
    lines.append("")
    return "\n".join(lines)


def validate_output_path(output_path: Path) -> None:
    """Validate a requested run-index output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"Run-index output path is a directory: {output_path}")
    if not output_path.parent.exists():
        raise ReportError(
            f"Run-index output parent does not exist: {output_path.parent}"
        )


def display_path(project_root: Path, path: Path) -> Path:
    """Return a stable display path relative to project root when possible."""
    try:
        return path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return path.resolve()


def optional_int(value: object) -> int | None:
    """Return an int when value is int-like, otherwise None."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def text(value: object) -> str:
    """Return value as text."""
    if value is None:
        return ""
    return str(value)


def markdown_cell(value: object) -> str:
    """Escape a Markdown table cell."""
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")
