"""Safely clean old VibeBench run directories."""

from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from vibebench.history import resolve_runs_dir
from vibebench.report import ReportError


class CleanCandidate(BaseModel):
    """One run directory selected for cleanup."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    path: Path
    size_bytes: int


class CleanResult(BaseModel):
    """Result of a VibeBench cleanup plan or deletion."""

    model_config = ConfigDict(extra="forbid")

    runs_dir: Path
    keep: int
    total_valid_runs: int
    preserved_count: int
    candidates: list[CleanCandidate]
    total_candidate_size_bytes: int
    dry_run: bool
    deleted_count: int = 0


def clean_runs(
    project_root: Path,
    runs_dir: Path | None = None,
    keep: int = 20,
    yes: bool = False,
) -> CleanResult:
    """Plan or delete old VibeBench run directories."""
    if keep < 0:
        raise ReportError("--keep must be 0 or greater.")

    root = project_root.resolve()
    selected_runs_dir = resolve_runs_dir(root, runs_dir)
    if not selected_runs_dir.exists():
        return CleanResult(
            runs_dir=selected_runs_dir,
            keep=keep,
            total_valid_runs=0,
            preserved_count=0,
            candidates=[],
            total_candidate_size_bytes=0,
            dry_run=not yes,
        )
    if not selected_runs_dir.is_dir():
        raise ReportError(f"Runs path is not a directory: {selected_runs_dir}")

    run_dirs = valid_run_dirs(selected_runs_dir)
    preserved = run_dirs[:keep]
    candidate_dirs = run_dirs[keep:]
    candidates = [candidate_for(selected_runs_dir, path) for path in candidate_dirs]
    result = CleanResult(
        runs_dir=selected_runs_dir,
        keep=keep,
        total_valid_runs=len(run_dirs),
        preserved_count=len(preserved),
        candidates=candidates,
        total_candidate_size_bytes=sum(
            candidate.size_bytes for candidate in candidates
        ),
        dry_run=not yes,
    )

    if yes:
        deleted = 0
        for candidate in candidates:
            delete_candidate(selected_runs_dir, candidate.path)
            deleted += 1
        result = result.model_copy(update={"deleted_count": deleted})

    return result


def valid_run_dirs(runs_dir: Path) -> list[Path]:
    """Return direct child run directories with metrics.json, newest first."""
    return sorted(
        (
            path
            for path in runs_dir.iterdir()
            if path.is_dir()
            and not path.is_symlink()
            and (path / "metrics.json").is_file()
        ),
        reverse=True,
    )


def candidate_for(runs_dir: Path, run_dir: Path) -> CleanCandidate:
    """Build a cleanup candidate after safety checks."""
    ensure_safe_child(runs_dir, run_dir)
    return CleanCandidate(
        run_id=run_dir.name,
        path=run_dir,
        size_bytes=directory_size(run_dir),
    )


def delete_candidate(runs_dir: Path, run_dir: Path) -> None:
    """Delete one safe candidate directory without following symlinks."""
    ensure_safe_child(runs_dir, run_dir)
    if run_dir.is_symlink():
        raise ReportError(f"Refusing to delete symlink: {run_dir}")
    if not (run_dir / "metrics.json").is_file():
        raise ReportError(f"Refusing to delete non-run directory: {run_dir}")
    shutil.rmtree(run_dir)


def ensure_safe_child(runs_dir: Path, run_dir: Path) -> None:
    """Ensure run_dir is a direct child of runs_dir."""
    resolved_runs_dir = runs_dir.resolve()
    resolved_run_dir = run_dir.resolve()
    if resolved_run_dir.parent != resolved_runs_dir:
        raise ReportError(f"Refusing unsafe cleanup path: {run_dir}")


def directory_size(path: Path) -> int:
    """Return an approximate directory size in bytes without following symlinks."""
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_symlink():
                continue
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total
