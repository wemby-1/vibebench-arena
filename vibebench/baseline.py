"""Save and inspect a VibeBench baseline run."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from vibebench.history import resolve_runs_dir
from vibebench.paths import config_dir
from vibebench.report import ReportError


class BaselineMetadata(BaseModel):
    """Saved baseline metadata."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    run_path: str
    created_at: str | None = None
    project: str | None = None
    status: str
    score: int
    risk_level: str
    metrics_path: str
    saved_at: str


class BaselineStatus(BaseModel):
    """Loaded baseline status with validation details."""

    model_config = ConfigDict(extra="forbid")

    baseline_path: Path
    metadata: BaselineMetadata | None = None
    run_dir: Path | None = None
    metrics_path: Path | None = None
    is_valid: bool = False
    message: str


def baseline_file(project_root: Path) -> Path:
    """Return the baseline metadata path."""
    return config_dir(project_root) / "baseline.json"


def show_baseline(project_root: Path) -> BaselineStatus:
    """Load and validate the saved baseline if it exists."""
    root = project_root.resolve()
    target = baseline_file(root)
    if not target.exists():
        return BaselineStatus(
            baseline_path=target,
            message="No baseline saved. Run 'vibebench baseline --set latest' first.",
        )

    try:
        metadata = BaselineMetadata.model_validate(
            json.loads(target.read_text(encoding="utf-8"))
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ReportError(
            f"Could not read baseline metadata at {target}: {exc}"
        ) from exc

    run_dir = resolve_metadata_path(root, metadata.run_path)
    metrics_path = resolve_metadata_path(root, metadata.metrics_path)
    if not run_dir.exists() or not run_dir.is_dir():
        return BaselineStatus(
            baseline_path=target,
            metadata=metadata,
            run_dir=run_dir,
            metrics_path=metrics_path,
            message=f"Baseline run directory is missing: {run_dir}",
        )
    if not metrics_path.exists():
        return BaselineStatus(
            baseline_path=target,
            metadata=metadata,
            run_dir=run_dir,
            metrics_path=metrics_path,
            message=f"Baseline metrics.json is missing: {metrics_path}",
        )

    return BaselineStatus(
        baseline_path=target,
        metadata=metadata,
        run_dir=run_dir,
        metrics_path=metrics_path,
        is_valid=True,
        message="Baseline is valid.",
    )


def set_baseline(
    project_root: Path,
    run_id: str,
    runs_dir: Path | None = None,
) -> BaselineStatus:
    """Save baseline metadata for a selected run."""
    root = project_root.resolve()
    selected_runs_dir = resolve_runs_dir(root, runs_dir)
    run_dir = select_run(selected_runs_dir, run_id)
    metrics = load_metrics(run_dir)
    metadata = metadata_from_run(root, run_dir, metrics)
    target = baseline_file(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(metadata.model_dump(mode="json"), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return BaselineStatus(
        baseline_path=target,
        metadata=metadata,
        run_dir=run_dir,
        metrics_path=run_dir / "metrics.json",
        is_valid=True,
        message="Baseline saved.",
    )


def select_run(runs_dir: Path, run_id: str) -> Path:
    """Select a run directory by latest, exact id, or unambiguous prefix."""
    if not runs_dir.exists():
        raise ReportError(f"Runs directory does not exist: {runs_dir}")
    if not runs_dir.is_dir():
        raise ReportError(f"Runs path is not a directory: {runs_dir}")

    runs = valid_run_dirs(runs_dir)
    if run_id == "latest":
        if not runs:
            raise ReportError("No VibeBench runs found. Run 'vibebench check' first.")
        return runs[-1]

    exact = [path for path in runs if path.name == run_id]
    if len(exact) == 1:
        return exact[0]

    matches = [path for path in runs if path.name.startswith(run_id)]
    if not matches:
        missing = runs_dir / run_id
        if missing.exists() and not (missing / "metrics.json").exists():
            raise ReportError(f"No metrics.json found in {missing}.")
        raise ReportError(f"No VibeBench run found for run id: {run_id}")
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches[:5])
        raise ReportError(f"Run id '{run_id}' is ambiguous: {names}")
    return matches[0]


def valid_run_dirs(runs_dir: Path) -> list[Path]:
    """Return run directories with metrics.json, sorted oldest to newest."""
    return sorted(
        path
        for path in runs_dir.iterdir()
        if path.is_dir() and (path / "metrics.json").is_file()
    )


def load_metrics(run_dir: Path) -> dict[str, Any]:
    """Load metrics for a run, raising a user-readable error on corruption."""
    metrics_path = run_dir / "metrics.json"
    if not metrics_path.exists():
        raise ReportError(f"No metrics.json found in {run_dir}.")
    try:
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReportError(f"Could not parse metrics.json in {run_dir}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReportError(f"metrics.json in {run_dir} is not an object.")
    return data


def metadata_from_run(
    project_root: Path,
    run_dir: Path,
    metrics: dict[str, Any],
) -> BaselineMetadata:
    """Build baseline metadata from a metrics payload."""
    metrics_path = run_dir / "metrics.json"
    return BaselineMetadata(
        run_id=run_dir.name,
        run_path=relative_or_absolute(project_root, run_dir),
        created_at=text_or_none(metrics.get("created_at")),
        project=text_or_none(metrics.get("project_name")),
        status=text(metrics.get("overall_status", "unknown")),
        score=as_int(metrics.get("score")),
        risk_level=text(metrics.get("risk_level", "unknown")),
        metrics_path=relative_or_absolute(project_root, metrics_path),
        saved_at=datetime.now(UTC).isoformat(),
    )


def resolve_metadata_path(project_root: Path, value: str) -> Path:
    """Resolve a path stored in baseline metadata."""
    path = Path(value)
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


def relative_or_absolute(project_root: Path, path: Path) -> str:
    """Return path relative to project root when possible."""
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path.resolve())


def as_int(value: object, default: int = 0) -> int:
    """Coerce a dynamic value to int safely."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def text(value: object) -> str:
    """Convert a dynamic value to text."""
    if value is None:
        return ""
    return str(value)


def text_or_none(value: object) -> str | None:
    """Convert a dynamic value to optional text."""
    if value is None:
        return None
    return str(value)
