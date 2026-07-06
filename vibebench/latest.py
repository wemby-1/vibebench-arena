"""Latest VibeBench run locator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibebench.artifacts import (
    ArtifactInventoryResult,
    ArtifactItem,
    collect_artifact_inventory,
)
from vibebench.bundle import BUNDLE_FILENAME
from vibebench.paths import config_dir
from vibebench.report import ReportError, load_metrics

ARTIFACT_ALIASES = {
    "metrics": Path("metrics.json"),
    "check-log": Path("check.log"),
    "manifest": Path("manifest.json"),
    "config-check-json": Path("config-check.json"),
    "config-check-md": Path("config-check.md"),
    "package-check-json": Path("package-check.json"),
    "package-check-md": Path("package-check.md"),
    "ci-plan-json": Path("ci-plan.json"),
    "ci-plan-md": Path("ci-plan.md"),
    "release-check-json": Path("release-check.json"),
    "release-check-md": Path("release-check.md"),
    "report": Path("report") / "index.html",
    "pr-comment": Path("pr-comment.md"),
    "explain": Path("explain.md"),
    "export": Path("export.json"),
    "badge-json": Path("badge.json"),
    "badge-md": Path("badge.md"),
    "status-block": Path("status-block.md"),
    "trend-md": Path("trend.md"),
    "trend-json": Path("trend.json"),
    "run-index-json": Path("run-index.json"),
    "run-index-md": Path("run-index.md"),
    "compare-json": Path("compare.json"),
    "compare-md": Path("compare.md"),
    "evidence-room-index-html": Path("evidence-room") / "index.html",
    "evidence-room-review-hub-html": Path("evidence-room") / "review-hub.html",
    "evidence-room-reviewer-guide-md": Path("evidence-room") / "reviewer-guide.md",
    "evidence-room-html": Path("evidence-room") / "evidence-room.html",
    "evidence-room-json": Path("evidence-room") / "evidence-room.json",
    "evidence-room-md": Path("evidence-room") / "evidence-room.md",
    "evidence-room-zip": Path("evidence-room") / "evidence-room.zip",
    "evidence-room-dir": Path("evidence-room"),
    "gate-summary": Path("gate-summary.md"),
    "bundle": Path(BUNDLE_FILENAME),
}
ARTIFACT_NAMES_BY_PATH = {path: name for name, path in ARTIFACT_ALIASES.items()}


@dataclass(frozen=True)
class LatestRunResult:
    """Latest valid run and artifact inventory."""

    run_dir: Path
    run_id: str
    metrics: dict[str, Any]
    inventory: ArtifactInventoryResult
    skipped_runs: list[str]

    @property
    def status(self) -> str:
        """Return the overall status from metrics."""
        return text(self.metrics.get("overall_status", "unknown"))

    @property
    def score(self) -> int:
        """Return the VibeScore from metrics."""
        try:
            return int(self.metrics.get("score", 0))
        except (TypeError, ValueError):
            return 0

    @property
    def risk(self) -> str:
        """Return the risk level from metrics."""
        return text(self.metrics.get("risk_level", "unknown"))

    @property
    def created_at(self) -> str:
        """Return the run timestamp from metrics when available."""
        return text(self.metrics.get("created_at", ""))


def get_latest_run(
    project_root: Path,
    runs_dir: Path | None = None,
) -> LatestRunResult:
    """Return latest valid run details."""
    root = project_root.resolve()
    selected_runs_dir = resolve_runs_dir(root, runs_dir)
    run_dir, metrics, skipped_runs = find_latest_readable_run(selected_runs_dir)
    inventory = collect_artifact_inventory(root, run_dir=run_dir)
    return LatestRunResult(
        run_dir=run_dir,
        run_id=run_dir.name,
        metrics=metrics,
        inventory=inventory,
        skipped_runs=skipped_runs,
    )


def resolve_runs_dir(project_root: Path, runs_dir: Path | None) -> Path:
    """Resolve a runs directory."""
    if runs_dir is None:
        return config_dir(project_root) / "runs"
    if runs_dir.is_absolute():
        return runs_dir.resolve()
    return (project_root / runs_dir).resolve()


def find_latest_readable_run(runs_dir: Path) -> tuple[Path, dict[str, Any], list[str]]:
    """Find the newest run with readable metrics.json."""
    if not runs_dir.exists():
        raise ReportError("No VibeBench runs found. Run 'vibebench check' first.")
    if not runs_dir.is_dir():
        raise ReportError(f"Runs path is not a directory: {runs_dir}")

    candidates = sorted(
        (
            path
            for path in runs_dir.iterdir()
            if path.is_dir() and path.joinpath("metrics.json").exists()
        ),
        reverse=True,
    )
    if not candidates:
        raise ReportError("No valid VibeBench runs found. Run 'vibebench check' first.")

    skipped_runs: list[str] = []
    for run_dir in candidates:
        try:
            return run_dir.resolve(), load_metrics(run_dir), skipped_runs
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            skipped_runs.append(
                f"Skipped {run_dir.name}: could not read metrics.json: {exc}"
            )

    raise ReportError(
        "No valid VibeBench runs found; all metrics.json files were unreadable "
        "or corrupt."
    )


def select_artifact(result: LatestRunResult, artifact_name: str) -> ArtifactItem:
    """Return one artifact by supported alias."""
    relative_path = ARTIFACT_ALIASES.get(artifact_name)
    if relative_path is None:
        valid = ", ".join(sorted(ARTIFACT_ALIASES))
        raise ReportError(f"Unknown artifact '{artifact_name}'. Valid choices: {valid}")

    for item in result.inventory.artifacts:
        if item.relative_path == relative_path:
            return item

    raise ReportError(f"Artifact '{artifact_name}' is not tracked by VibeBench.")


def latest_json(
    result: LatestRunResult,
    artifact: ArtifactItem | None = None,
) -> dict[str, object]:
    """Return a deterministic latest-run JSON payload."""
    artifacts = [artifact_payload(artifact)] if artifact else [
        artifact_payload(item) for item in result.inventory.artifacts
    ]
    return {
        "run_id": result.run_id,
        "run_dir": str(result.run_dir),
        "status": result.status,
        "score": result.score,
        "risk": result.risk,
        "created_at": result.created_at,
        "artifacts": artifacts,
        "skipped_runs": result.skipped_runs,
    }


def available_artifacts(result: LatestRunResult) -> list[ArtifactItem]:
    """Return all available known artifacts for a latest run."""
    return [item for item in result.inventory.artifacts if item.available]


def artifact_label(item: ArtifactItem) -> str:
    """Return a user-facing artifact alias when one exists."""
    return ARTIFACT_NAMES_BY_PATH.get(item.relative_path, item.name)


def artifact_payload(item: ArtifactItem) -> dict[str, object]:
    """Return JSON-safe artifact details."""
    return {
        "name": item.name,
        "path": item.display_path.as_posix(),
        "available": item.available,
        "size_bytes": item.size_bytes,
    }


def artifact_path_payload(item: ArtifactItem) -> dict[str, object]:
    """Return JSON-safe available artifact path details."""
    return {
        "name": artifact_label(item),
        "path": item.display_path.as_posix(),
        "size_bytes": item.size_bytes,
    }


def latest_paths_json(result: LatestRunResult) -> dict[str, object]:
    """Return deterministic JSON for available artifact paths."""
    return {
        "run_id": result.run_id,
        "run_dir": str(result.run_dir),
        "paths": [artifact_path_payload(item) for item in available_artifacts(result)],
    }


def text(value: object) -> str:
    """Return a stable text value."""
    return "" if value is None else str(value)
