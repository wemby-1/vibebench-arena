"""Save and inspect VibeBench baseline runs."""

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

    schema_version: str = "1.0"
    label: str = "default"
    run_id: str
    run_path: str
    run_dir: str | None = None
    created_at: str | None = None
    project: str | None = None
    status: str
    score: int
    risk_level: str
    metrics_path: str
    source: str = "legacy"
    pinned_at: str | None = None
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
    """Return the legacy baseline metadata path."""
    return config_dir(project_root) / "baseline.json"


def baselines_dir(project_root: Path) -> Path:
    """Return the labeled pinned baseline directory."""
    return config_dir(project_root) / "baselines"


def pinned_baseline_file(project_root: Path, label: str = "default") -> Path:
    """Return a labeled pinned baseline metadata path."""
    return baselines_dir(project_root) / f"{normalize_label(label)}.json"


def normalize_label(label: str) -> str:
    """Validate and normalize a baseline label for local file storage."""
    selected = label.strip() or "default"
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if selected in {".", ".."} or any(char not in allowed for char in selected):
        raise ReportError(
            "Baseline label may only contain letters, numbers, '.', '_', or '-'."
        )
    return selected


def show_baseline(project_root: Path) -> BaselineStatus:
    """Load and validate the legacy saved baseline if it exists."""
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

    return validate_baseline_metadata(root, target, metadata)


def show_pinned_baseline(
    project_root: Path,
    *,
    label: str = "default",
) -> BaselineStatus:
    """Load and validate a labeled pinned baseline if it exists."""
    root = project_root.resolve()
    selected_label = normalize_label(label)
    target = pinned_baseline_file(root, selected_label)
    if not target.exists():
        return BaselineStatus(
            baseline_path=target,
            message=(
                f"No pinned baseline saved for label '{selected_label}'. "
                "Run 'vibebench baseline --set-latest' first."
            ),
        )

    try:
        metadata = BaselineMetadata.model_validate(
            json.loads(target.read_text(encoding="utf-8"))
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ReportError(
            f"Could not read pinned baseline metadata at {target}: {exc}"
        ) from exc

    return validate_baseline_metadata(root, target, metadata)


def set_baseline(
    project_root: Path,
    run_id: str,
    runs_dir: Path | None = None,
) -> BaselineStatus:
    """Save legacy baseline metadata for a selected run."""
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


def set_pinned_baseline(
    project_root: Path,
    run_id: str,
    *,
    label: str = "default",
    runs_dir: Path | None = None,
    source: str = "set-run",
) -> BaselineStatus:
    """Save labeled pinned baseline metadata for a selected run."""
    root = project_root.resolve()
    selected_label = normalize_label(label)
    selected_runs_dir = resolve_runs_dir(root, runs_dir)
    run_dir = select_run(selected_runs_dir, run_id)
    metrics = load_metrics(run_dir)
    metadata = metadata_from_run(
        root,
        run_dir,
        metrics,
        label=selected_label,
        source=source,
        runs_dir=selected_runs_dir,
    )
    target = pinned_baseline_file(root, selected_label)
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
        message="Pinned baseline saved.",
    )


def clear_pinned_baseline(
    project_root: Path,
    *,
    label: str = "default",
) -> BaselineStatus:
    """Clear a labeled pinned baseline if it exists."""
    root = project_root.resolve()
    selected_label = normalize_label(label)
    target = pinned_baseline_file(root, selected_label)
    if target.exists():
        target.unlink()
        message = f"Cleared pinned baseline '{selected_label}'."
    else:
        message = f"No pinned baseline saved for label '{selected_label}'."
    return BaselineStatus(baseline_path=target, message=message)


def list_pinned_baselines(project_root: Path) -> list[BaselineStatus]:
    """List all labeled pinned baselines."""
    root = project_root.resolve()
    directory = baselines_dir(root)
    if not directory.exists():
        return []
    results: list[BaselineStatus] = []
    for path in sorted(directory.glob("*.json")):
        try:
            results.append(show_pinned_baseline(root, label=path.stem))
        except ReportError as exc:
            results.append(BaselineStatus(baseline_path=path, message=str(exc)))
    return results


def validate_baseline_metadata(
    project_root: Path,
    target: Path,
    metadata: BaselineMetadata,
) -> BaselineStatus:
    """Validate stored baseline metadata against local run files."""
    run_dir = resolve_metadata_path(project_root, metadata.run_dir or metadata.run_path)
    if not run_dir.exists() and metadata.run_dir is not None:
        run_dir = resolve_metadata_path(project_root, metadata.run_path)
    metrics_path = resolve_metadata_path(project_root, metadata.metrics_path)
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


def select_run(runs_dir: Path, run_id: str) -> Path:
    """Select a run directory by latest, exact id, prefix, or path."""
    if not runs_dir.exists():
        raise ReportError(f"Runs directory does not exist: {runs_dir}")
    if not runs_dir.is_dir():
        raise ReportError(f"Runs path is not a directory: {runs_dir}")

    explicit = Path(run_id)
    if explicit.is_absolute() or explicit.parts[:-1]:
        if explicit.is_absolute():
            selected = explicit
        else:
            selected = runs_dir.parent.parent / explicit
        selected = selected.resolve()
        has_metrics = (selected / "metrics.json").is_file()
        if selected.exists() and selected.is_dir() and has_metrics:
            return selected
        if selected.exists() and selected.is_dir():
            raise ReportError(f"No metrics.json found in {selected}.")

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
    *,
    label: str = "default",
    source: str = "legacy",
    runs_dir: Path | None = None,
) -> BaselineMetadata:
    """Build baseline metadata from a metrics payload."""
    metrics_path = run_dir / "metrics.json"
    saved_at = datetime.now(UTC).isoformat()
    run_path = relative_or_absolute(project_root, run_dir)
    stored_run_dir = (
        relative_or_absolute(runs_dir, run_dir) if runs_dir is not None else run_path
    )
    return BaselineMetadata(
        schema_version="1.0",
        label=label,
        run_id=run_dir.name,
        run_path=run_path,
        run_dir=stored_run_dir,
        created_at=text_or_none(metrics.get("created_at")),
        project=text_or_none(metrics.get("project_name")),
        status=text(metrics.get("overall_status", "unknown")),
        score=as_int(metrics.get("score")),
        risk_level=text(metrics.get("risk_level", "unknown")),
        metrics_path=relative_or_absolute(project_root, metrics_path),
        source=source,
        pinned_at=saved_at if source != "legacy" else None,
        saved_at=saved_at,
    )


def resolve_metadata_path(project_root: Path, value: str) -> Path:
    """Resolve a path stored in baseline metadata."""
    path = Path(value)
    if path.is_absolute():
        return path
    if len(path.parts) == 1:
        run_path = config_dir(project_root) / "runs" / path
        if run_path.exists():
            return run_path.resolve()
    return (project_root / path).resolve()


def relative_or_absolute(project_root: Path, path: Path) -> str:
    """Return path relative to project root when possible."""
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path.resolve())


def baseline_status_payload(result: BaselineStatus) -> dict[str, object]:
    """Return JSON-compatible baseline status."""
    metadata = result.metadata.model_dump(mode="json") if result.metadata else None
    if result.is_valid:
        status = "valid"
    elif result.metadata is None:
        status = "missing"
    else:
        status = "stale"
    return {
        "status": status,
        "baseline_path": str(result.baseline_path),
        "label": (
            result.metadata.label if result.metadata else result.baseline_path.stem
        ),
        "run_dir": str(result.run_dir) if result.run_dir else None,
        "metrics_path": str(result.metrics_path) if result.metrics_path else None,
        "is_valid": result.is_valid,
        "message": result.message,
        "baseline": metadata,
    }


def baseline_list_payload(results: list[BaselineStatus]) -> dict[str, object]:
    """Return JSON-compatible pinned baseline list."""
    return {
        "status": "listed",
        "baselines": [baseline_status_payload(result) for result in results],
    }


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
