"""Machine-readable run manifest generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vibebench.artifacts import ArtifactInventoryResult, collect_artifact_inventory
from vibebench.explain import find_latest_valid_run
from vibebench.pr_comment import as_dict, as_list, text
from vibebench.report import ReportError, load_metrics

MANIFEST_FILENAME = "manifest.json"
MANIFEST_SCHEMA_VERSION = "vibebench.manifest.v1"
MAX_SIZE_STABILIZATION_ATTEMPTS = 5


@dataclass(frozen=True)
class ManifestResult:
    """Result of writing a VibeBench run manifest."""

    run_dir: Path
    run_id: str
    output_path: Path
    payload: dict[str, Any]
    available_artifact_count: int


@dataclass(frozen=True)
class ManifestCheckResult:
    """Result of checking an existing VibeBench run manifest."""

    run_dir: Path
    run_id: str
    manifest_path: Path
    differences: list[str]

    @property
    def passed(self) -> bool:
        """Return whether the manifest matches the current run directory."""
        return not self.differences


def generate_manifest(
    project_root: Path,
    run_dir: Path | None = None,
    output_path: Path | None = None,
    *,
    strict: bool = False,
) -> ManifestResult:
    """Write a manifest JSON artifact for a VibeBench run."""
    root = project_root.resolve()
    selected_run_dir = (run_dir or find_latest_valid_run(root)).resolve()
    validate_run_dir(selected_run_dir)
    metrics = load_manifest_metrics(selected_run_dir)
    selected_output = (
        output_path.resolve()
        if output_path is not None
        else selected_run_dir / MANIFEST_FILENAME
    )
    validate_output_path(selected_output)

    generated_at = datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {}
    previous_size: int | None = None

    if selected_output == selected_run_dir / MANIFEST_FILENAME:
        selected_output.write_text("{}\n", encoding="utf-8")

    for _ in range(MAX_SIZE_STABILIZATION_ATTEMPTS):
        inventory = collect_artifact_inventory(root, selected_run_dir)
        payload = manifest_payload(
            root,
            selected_run_dir,
            metrics,
            inventory,
            generated_at,
        )
        manifest_text = json.dumps(payload, indent=2) + "\n"
        selected_output.write_text(manifest_text, encoding="utf-8")
        current_size = selected_output.stat().st_size
        if current_size == previous_size:
            break
        previous_size = current_size

    if strict:
        validate_written_manifest(selected_output)

    available_count = sum(
        1 for item in payload.get("artifacts", []) if as_dict(item).get("available")
    )
    return ManifestResult(
        run_dir=selected_run_dir,
        run_id=selected_run_dir.name,
        output_path=selected_output,
        payload=payload,
        available_artifact_count=available_count,
    )


def check_manifest(
    project_root: Path,
    run_dir: Path | None = None,
    manifest_path: Path | None = None,
    *,
    strict: bool = False,
) -> ManifestCheckResult:
    """Check that an existing manifest matches current run artifacts."""
    root = project_root.resolve()
    selected_run_dir = (run_dir or find_latest_valid_run(root)).resolve()
    validate_run_dir(selected_run_dir)
    metrics = load_manifest_metrics(selected_run_dir)
    selected_manifest_path = (
        manifest_path.resolve()
        if manifest_path is not None
        else selected_run_dir / MANIFEST_FILENAME
    )
    stored_payload = load_existing_manifest(selected_manifest_path)
    if strict:
        validate_written_manifest(selected_manifest_path)

    generated_at = text(stored_payload.get("generated_at", ""))
    inventory = collect_artifact_inventory(root, selected_run_dir)
    current_payload = manifest_payload(
        root,
        selected_run_dir,
        metrics,
        inventory,
        generated_at,
    )
    differences = compare_manifest_payload(stored_payload, current_payload)
    return ManifestCheckResult(
        run_dir=selected_run_dir,
        run_id=selected_run_dir.name,
        manifest_path=selected_manifest_path,
        differences=differences,
    )


def validate_run_dir(run_dir: Path) -> None:
    """Validate a selected run directory."""
    if not run_dir.exists():
        raise ReportError(f"Run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise ReportError(f"Run path is not a directory: {run_dir}")


def load_manifest_metrics(run_dir: Path) -> dict[str, Any]:
    """Load metrics with a manifest-specific corrupt JSON message."""
    try:
        return load_metrics(run_dir)
    except json.JSONDecodeError as exc:
        raise ReportError(f"metrics.json in {run_dir} is not valid JSON.") from exc




def load_existing_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load an existing manifest for consistency checking."""
    if not manifest_path.exists():
        message = (
            f"No manifest.json found at {manifest_path}. "
            "Run 'vibebench manifest' first."
        )
        raise ReportError(message)
    if manifest_path.is_dir():
        raise ReportError(f"Manifest path is a directory: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        message = f"manifest.json in {manifest_path} is not valid JSON."
        raise ReportError(message) from exc
    if not isinstance(payload, dict):
        message = f"manifest.json in {manifest_path} must contain a JSON object."
        raise ReportError(message)
    return payload


def validate_output_path(output_path: Path) -> None:
    """Validate a requested manifest output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"Output path is a directory: {output_path}")
    if not output_path.parent.exists():
        message = f"Output parent directory does not exist: {output_path.parent}"
        raise ReportError(message)


def validate_written_manifest(output_path: Path) -> None:
    """Validate that the written manifest can be read back."""
    try:
        json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        message = f"Generated manifest is not valid JSON: {output_path}"
        raise ReportError(message) from exc
    except OSError as exc:
        raise ReportError(f"Generated manifest cannot be read: {output_path}") from exc


def manifest_payload(
    project_root: Path,
    run_dir: Path,
    metrics: dict[str, Any],
    inventory: ArtifactInventoryResult,
    generated_at: str,
) -> dict[str, Any]:
    """Build a deterministic manifest payload."""
    summary = as_dict(metrics.get("summary"))
    diff = as_dict(metrics.get("diff_analysis"))
    findings = as_list(metrics.get("risk_findings"))
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": generated_at,
        "run_id": run_dir.name,
        "run_dir": display_path(project_root, run_dir).as_posix(),
        "project": text(metrics.get("project_name", "")),
        "created_at": text(metrics.get("created_at", "")),
        "status": text(metrics.get("overall_status", "unknown")),
        "score": number(metrics.get("score")),
        "risk_level": text(metrics.get("risk_level", "unknown")),
        "findings_count": number(summary.get("total_findings"), len(findings)),
        "changed_files": number(diff.get("changed_file_count")),
        "patch_lines": number(diff.get("total_patch_lines")),
        "artifacts": [
            {
                "name": item.name,
                "path": item.display_path.as_posix(),
                "available": item.available,
                "size_bytes": item.size_bytes,
            }
            for item in inventory.artifacts
        ],
    }




STABLE_MANIFEST_FIELDS = [
    "schema_version",
    "run_id",
    "run_dir",
    "project",
    "created_at",
    "status",
    "score",
    "risk_level",
    "findings_count",
    "changed_files",
    "patch_lines",
]
ARTIFACT_FIELDS = ["path", "available", "size_bytes"]


def compare_manifest_payload(
    stored: dict[str, Any],
    current: dict[str, Any],
) -> list[str]:
    """Return stable differences between stored and current manifests."""
    differences: list[str] = []
    for field in STABLE_MANIFEST_FIELDS:
        if stored.get(field) != current.get(field):
            differences.append(
                f"{field}: expected {format_value(stored.get(field))}, "
                f"actual {format_value(current.get(field))}"
            )

    stored_artifacts = artifacts_by_name(stored.get("artifacts"))
    current_artifacts = artifacts_by_name(current.get("artifacts"))
    for name in sorted(current_artifacts):
        if name not in stored_artifacts:
            if artifact_missing_but_unavailable(current_artifacts[name]):
                continue
            differences.append(f"artifact {name}: missing entry")
            continue
        stored_item = stored_artifacts[name]
        current_item = current_artifacts[name]
        for field in ARTIFACT_FIELDS:
            if manifest_self_size_drift(name, field):
                continue
            if stored_item.get(field) != current_item.get(field):
                differences.append(
                    f"artifact {name} {field}: "
                    f"expected {format_value(stored_item.get(field))}, "
                    f"actual {format_value(current_item.get(field))}"
                )
    for name in sorted(set(stored_artifacts) - set(current_artifacts)):
        differences.append(f"artifact {name}: unexpected entry")
    return differences


def artifacts_by_name(value: object) -> dict[str, dict[str, Any]]:
    """Return artifact entries keyed by name."""
    artifacts: dict[str, dict[str, Any]] = {}
    if not isinstance(value, list):
        return artifacts
    for item in value:
        artifact = as_dict(item)
        name = text(artifact.get("name", ""))
        if name:
            artifacts[name] = artifact
    return artifacts


def artifact_missing_but_unavailable(artifact: dict[str, Any]) -> bool:
    """Return whether a missing old manifest entry is harmless compatibility drift."""
    return artifact.get("available") is False and artifact.get("size_bytes") is None


def manifest_self_size_drift(name: str, field: str) -> bool:
    """Return whether an artifact drift is the manifest tracking its own size."""
    return name == MANIFEST_FILENAME and field == "size_bytes"


def format_value(value: object) -> str:
    """Format a manifest value for concise drift output."""
    return json.dumps(value, sort_keys=True)


def display_path(project_root: Path, path: Path) -> Path:
    """Return a stable display path when possible."""
    try:
        return path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return path.resolve()


def number(value: object, default: int = 0) -> int:
    """Return an integer value with a safe default."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
