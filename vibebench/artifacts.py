"""Artifact inventory for VibeBench runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from vibebench.bundle import BUNDLE_FILENAME, STANDARD_ARTIFACTS
from vibebench.explain import find_latest_valid_run
from vibebench.report import ReportError, load_metrics


@dataclass(frozen=True)
class ArtifactSpec:
    """Known artifact name and run-relative path."""

    name: str
    relative_path: Path


EVIDENCE_ROOM_ARTIFACT_NAMES = {
    Path("evidence-room") / "index.html": "evidence-room-index-html",
    Path("evidence-room") / "review-hub.html": "evidence-room-review-hub-html",
    Path("evidence-room") / "reviewer-guide.md": "evidence-room-reviewer-guide-md",
    Path("evidence-room") / "trust-center.html": "evidence-room-trust-center-html",
    Path("evidence-room") / "trust-center.md": "evidence-room-trust-center-md",
    Path("evidence-room")
    / "security-questionnaire.html": "evidence-room-security-questionnaire-html",
    Path("evidence-room")
    / "security-questionnaire.md": "evidence-room-security-questionnaire-md",
    Path("evidence-room") / "review-scorecard.html": "evidence-room-scorecard-html",
    Path("evidence-room") / "review-scorecard.md": "evidence-room-scorecard-md",
    Path("evidence-room") / "review-scorecard.json": "evidence-room-scorecard-json",
    Path("evidence-room") / "share-check.json": "evidence-room-share-check-json",
    Path("evidence-room") / "share-check.md": "evidence-room-share-check-md",
    Path("evidence-room") / "evidence-room.html": "evidence-room-html",
    Path("evidence-room") / "evidence-room.json": "evidence-room-json",
    Path("evidence-room") / "evidence-room.md": "evidence-room-md",
    Path("evidence-room") / "evidence-room.zip": "evidence-room-zip",
}
ARTIFACT_NAMES = {
    Path("metrics-check.json"): "metrics-check-json",
    Path("metrics-check.md"): "metrics-check-md",
    Path("metrics-diff.json"): "metrics-diff-json",
    Path("metrics-diff.md"): "metrics-diff-md",
    Path("regression-check.json"): "regression-check-json",
    Path("regression-check.md"): "regression-check-md",
    **EVIDENCE_ROOM_ARTIFACT_NAMES,
}

KNOWN_ARTIFACTS = [*STANDARD_ARTIFACTS, Path(BUNDLE_FILENAME)]

KNOWN_ARTIFACT_SPECS = [
    ArtifactSpec(
        ARTIFACT_NAMES.get(relative_path, relative_path.as_posix()),
        relative_path,
    )
    for relative_path in [*STANDARD_ARTIFACTS, Path(BUNDLE_FILENAME)]
]
KNOWN_ARTIFACT_SPECS.append(ArtifactSpec("evidence-room-dir", Path("evidence-room")))


@dataclass(frozen=True)
class ArtifactItem:
    """One known artifact in a VibeBench run."""

    name: str
    relative_path: Path
    display_path: Path
    available: bool
    size_bytes: int | None


@dataclass(frozen=True)
class ArtifactInventoryResult:
    """Artifact inventory for one VibeBench run."""

    run_dir: Path
    run_id: str
    artifacts: list[ArtifactItem]
    missing_count: int


def collect_artifact_inventory(
    project_root: Path,
    run_dir: Path | None = None,
    *,
    only_available: bool = False,
    strict: bool = False,
) -> ArtifactInventoryResult:
    """Collect known artifact availability for a run."""
    selected_run_dir = (run_dir or find_latest_valid_run(project_root)).resolve()
    validate_run_dir(selected_run_dir)
    validate_metrics(selected_run_dir)

    artifacts = []
    for spec in KNOWN_ARTIFACT_SPECS:
        relative_path = spec.relative_path
        artifact_path = selected_run_dir / relative_path
        available = (
            artifact_path.exists()
            and not artifact_path.is_symlink()
            and (artifact_path.is_file() or artifact_path.is_dir())
        )
        if only_available and not available:
            continue
        size_bytes = (
            artifact_path.stat().st_size
            if available and artifact_path.is_file()
            else None
        )
        artifacts.append(
            ArtifactItem(
                name=spec.name,
                relative_path=relative_path,
                display_path=display_path(project_root, artifact_path),
                available=available,
                size_bytes=size_bytes,
            )
        )

    missing_count = sum(1 for item in artifacts if not item.available)
    if strict and missing_count:
        missing = ", ".join(item.name for item in artifacts if not item.available)
        raise ReportError(f"Missing expected artifact(s): {missing}")

    return ArtifactInventoryResult(
        run_dir=selected_run_dir,
        run_id=selected_run_dir.name,
        artifacts=artifacts,
        missing_count=missing_count,
    )


def validate_run_dir(run_dir: Path) -> None:
    """Validate a selected run directory."""
    if not run_dir.exists():
        raise ReportError(f"Run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise ReportError(f"Run path is not a directory: {run_dir}")


def validate_metrics(run_dir: Path) -> None:
    """Validate that metrics.json exists and can be parsed."""
    try:
        load_metrics(run_dir)
    except json.JSONDecodeError as exc:
        raise ReportError(f"metrics.json in {run_dir} is not valid JSON.") from exc


def display_path(project_root: Path, artifact_path: Path) -> Path:
    """Return a stable display path for an artifact."""
    try:
        return artifact_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return artifact_path.resolve()


def inventory_json(result: ArtifactInventoryResult) -> dict[str, object]:
    """Return a stable JSON payload for an artifact inventory."""
    return {
        "run_dir": str(result.run_dir),
        "run_id": result.run_id,
        "artifacts": [
            {
                "name": item.name,
                "path": item.display_path.as_posix(),
                "available": item.available,
                "size_bytes": item.size_bytes,
            }
            for item in result.artifacts
        ],
    }
