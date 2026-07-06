"""Save and inspect VibeBench baseline runs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from vibebench.history import resolve_runs_dir
from vibebench.metrics_check import validate_score_risk_values
from vibebench.paths import config_dir
from vibebench.report import ReportError

BaselineVerifyStatus = Literal["passed", "warning", "failed"]
BaselineCheckStatus = Literal["passed", "warning", "failed"]


class BaselineVerificationCheck(BaseModel):
    """One baseline verification check."""

    model_config = ConfigDict(extra="forbid")

    name: str
    status: BaselineCheckStatus
    message: str


class BaselineVerificationResult(BaseModel):
    """Structured baseline verification result."""

    model_config = ConfigDict(extra="forbid")

    status: BaselineVerifyStatus
    label: str | None = None
    run_id: str | None = None
    baseline_path: str
    baseline_source: str | None = None
    live_metrics_available: bool = False
    snapshot_available: bool = False
    portable: bool = False
    usable_for_regression: bool = False
    checks: list[BaselineVerificationCheck]
    advice: list[str]
    message: str


class BaselineMetricsSnapshot(BaseModel):
    """Portable metrics used by regression-check when a run is unavailable."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    score: int
    risk_level: str
    status: str | None = None
    project: str | None = None
    created_at: str | None = None


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
    metrics_snapshot: BaselineMetricsSnapshot | None = None


class BaselineStatus(BaseModel):
    """Loaded baseline status with validation details."""

    model_config = ConfigDict(extra="forbid")

    baseline_path: Path
    metadata: BaselineMetadata | None = None
    run_dir: Path | None = None
    metrics_path: Path | None = None
    is_valid: bool = False
    live_metrics_available: bool = False
    snapshot_available: bool = False
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
        live_metrics_available=True,
        snapshot_available=metadata.metrics_snapshot is not None,
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
        live_metrics_available=True,
        snapshot_available=metadata.metrics_snapshot is not None,
        message="Pinned baseline saved.",
    )



def verify_pinned_baseline(
    project_root: Path,
    *,
    label: str = "default",
    strict: bool = False,
    require_portable: bool = False,
    require_live_metrics: bool = False,
) -> BaselineVerificationResult:
    """Verify a labeled pinned baseline for regression readiness."""
    root = project_root.resolve()
    selected_label = normalize_label(label)
    target = pinned_baseline_file(root, selected_label)
    if not target.exists():
        return verification_result(
            label=selected_label,
            baseline_path=target,
            source=None,
            checks=[
                BaselineVerificationCheck(
                    name="baseline_file_exists",
                    status="failed",
                    message=(
                        f"No pinned baseline saved for label '{selected_label}'. "
                        "Run 'vibebench baseline --set-latest' first."
                    ),
                )
            ],
            strict=strict,
            advice=["Pin or import a baseline before running regression gates."],
        )
    checks = [
        BaselineVerificationCheck(
            name="baseline_file_exists",
            status="passed",
            message="Pinned baseline file exists.",
        )
    ]
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        checks.append(
            BaselineVerificationCheck(
                name="json_shape",
                status="failed",
                message=f"Could not parse pinned baseline JSON: {exc}",
            )
        )
        return verification_result(
            label=selected_label,
            baseline_path=target,
            source=None,
            checks=checks,
            strict=strict,
            advice=["Recreate or re-import the pinned baseline file."],
        )
    try:
        metadata = BaselineMetadata.model_validate(raw)
    except ValueError as exc:
        checks.append(
            BaselineVerificationCheck(
                name="json_shape",
                status="failed",
                message=f"Pinned baseline metadata is invalid: {exc}",
            )
        )
        return verification_result(
            label=selected_label,
            baseline_path=target,
            source=None,
            checks=checks,
            strict=strict,
            advice=["Recreate or re-import the pinned baseline file."],
        )
    checks.append(
        BaselineVerificationCheck(
            name="json_shape",
            status="passed",
            message="Baseline JSON shape is valid.",
        )
    )
    status = validate_baseline_metadata(root, target, metadata)
    checks.extend(
        metadata_verification_checks(
            root,
            metadata,
            target,
            expected_label=selected_label,
            live_metrics_available=status.live_metrics_available,
            require_portable=require_portable,
            require_live_metrics=require_live_metrics,
        )
    )
    return verification_result(
        label=selected_label,
        baseline_path=target,
        source=metadata.source,
        metadata=metadata,
        live_metrics_available=status.live_metrics_available,
        checks=checks,
        strict=strict,
    )


def verify_baseline_input(
    project_root: Path,
    input_path: Path,
    *,
    expected_label: str | None = None,
    strict: bool = False,
    require_portable: bool = False,
    require_live_metrics: bool = False,
    allow_label_override: bool = False,
) -> BaselineVerificationResult:
    """Verify a standalone exported baseline without writing local state."""
    root = project_root.resolve()
    target = input_path if input_path.is_absolute() else root / input_path
    checks: list[BaselineVerificationCheck] = []
    if not target.exists():
        checks.append(
            BaselineVerificationCheck(
                name="baseline_file_exists",
                status="failed",
                message=f"Baseline input file does not exist: {target}",
            )
        )
        return verification_result(
            label=expected_label,
            baseline_path=target,
            source=None,
            checks=checks,
            strict=strict,
            advice=["Provide an existing exported baseline JSON file."],
        )
    if not target.is_file():
        checks.append(
            BaselineVerificationCheck(
                name="baseline_file_exists",
                status="failed",
                message=f"Baseline input path is not a file: {target}",
            )
        )
        return verification_result(
            label=expected_label,
            baseline_path=target,
            source=None,
            checks=checks,
            strict=strict,
            advice=["Use a baseline JSON file, not a directory."],
        )
    checks.append(
        BaselineVerificationCheck(
            name="baseline_file_exists",
            status="passed",
            message="Baseline input file exists.",
        )
    )
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        checks.append(
            BaselineVerificationCheck(
                name="json_shape",
                status="failed",
                message=f"Could not parse baseline JSON: {exc}",
            )
        )
        return verification_result(
            label=expected_label,
            baseline_path=target,
            source=None,
            checks=checks,
            strict=strict,
            advice=["Export a fresh baseline JSON file and retry."],
        )
    if not isinstance(raw, dict):
        checks.append(
            BaselineVerificationCheck(
                name="json_shape",
                status="failed",
                message="Baseline JSON must be an object.",
            )
        )
        return verification_result(
            label=expected_label,
            baseline_path=target,
            source=None,
            checks=checks,
            strict=strict,
        )
    if "baseline" in raw and isinstance(raw["baseline"], dict):
        raw = raw["baseline"]
    try:
        metadata = BaselineMetadata.model_validate(raw)
    except ValueError as exc:
        checks.append(
            BaselineVerificationCheck(
                name="json_shape",
                status="failed",
                message=f"Baseline metadata is invalid: {exc}",
            )
        )
        return verification_result(
            label=expected_label,
            baseline_path=target,
            source=None,
            checks=checks,
            strict=strict,
            advice=["Use a baseline exported by this VibeBench version."],
        )
    checks.append(
        BaselineVerificationCheck(
            name="json_shape",
            status="passed",
            message="Baseline JSON shape is valid.",
        )
    )
    label_for_check = None if allow_label_override else expected_label
    live_metrics_available = live_metrics_exists(root, metadata)
    checks.extend(
        metadata_verification_checks(
            root,
            metadata,
            target,
            expected_label=label_for_check,
            live_metrics_available=live_metrics_available,
            require_portable=require_portable,
            require_live_metrics=require_live_metrics,
            input_file=True,
        )
    )
    return verification_result(
        label=expected_label or metadata.label,
        baseline_path=target,
        source=metadata.source,
        metadata=metadata,
        live_metrics_available=live_metrics_available,
        checks=checks,
        strict=strict,
    )


def metadata_verification_checks(
    project_root: Path,
    metadata: BaselineMetadata,
    baseline_path: Path,
    *,
    expected_label: str | None,
    live_metrics_available: bool,
    require_portable: bool,
    require_live_metrics: bool,
    input_file: bool = False,
) -> list[BaselineVerificationCheck]:
    """Return checks for parsed baseline metadata."""
    checks: list[BaselineVerificationCheck] = []
    if expected_label is not None and metadata.label != expected_label:
        checks.append(
            BaselineVerificationCheck(
                name="label_matches",
                status="failed",
                message=(
                    f"Baseline label {metadata.label!r} does not match "
                    f"requested label {expected_label!r}."
                ),
            )
        )
    else:
        checks.append(
            BaselineVerificationCheck(
                name="label_matches",
                status="passed",
                message="Baseline label matches the requested label.",
            )
        )
    checks.append(
        BaselineVerificationCheck(
            name="run_id_present",
            status="passed" if metadata.run_id else "failed",
            message="Baseline run_id is present."
            if metadata.run_id
            else "Baseline run_id is missing.",
        )
    )
    unsafe_paths = unsafe_metadata_paths(metadata)
    checks.append(
        BaselineVerificationCheck(
            name="path_safety",
            status="failed" if unsafe_paths else "passed",
            message="Unsafe path metadata: " + ", ".join(unsafe_paths)
            if unsafe_paths
            else "Baseline path metadata is safe to inspect.",
        )
    )
    checks.append(
        BaselineVerificationCheck(
            name="live_metrics_available",
            status="passed" if live_metrics_available else "warning",
            message="Live metrics are available."
            if live_metrics_available
            else "Live metrics are unavailable; snapshot fallback is required.",
        )
    )
    snapshot = metadata.metrics_snapshot
    snapshot_result = (
        validate_score_risk_values(snapshot.score, snapshot.risk_level)
        if snapshot is not None
        else None
    )
    snapshot_ok = snapshot_result.usable if snapshot_result is not None else False
    checks.append(
        BaselineVerificationCheck(
            name="metrics_snapshot_available",
            status="passed" if snapshot_ok else "warning",
            message="Portable metrics snapshot includes usable score and risk_level."
            if snapshot_ok
            else "Portable metrics snapshot is missing or incomplete.",
        )
    )
    usable = (live_metrics_available or snapshot_ok) and not unsafe_paths
    checks.append(
        BaselineVerificationCheck(
            name="usable_for_regression",
            status="passed" if usable else "failed",
            message="Baseline can be used by regression-check."
            if usable
            else "Baseline cannot be used by regression-check.",
        )
    )
    if require_portable and not snapshot_ok:
        checks.append(
            BaselineVerificationCheck(
                name="require_portable",
                status="failed",
                message="--require-portable needs a valid metrics_snapshot.",
            )
        )
    elif require_portable:
        checks.append(
            BaselineVerificationCheck(
                name="require_portable",
                status="passed",
                message="Portable snapshot requirement is satisfied.",
            )
        )
    if require_live_metrics and not live_metrics_available:
        checks.append(
            BaselineVerificationCheck(
                name="require_live_metrics",
                status="failed",
                message="--require-live-metrics needs live metrics.json.",
            )
        )
    elif require_live_metrics:
        checks.append(
            BaselineVerificationCheck(
                name="require_live_metrics",
                status="passed",
                message="Live metrics requirement is satisfied.",
            )
        )
    return checks


def verification_result(
    *,
    label: str | None,
    baseline_path: Path,
    source: str | None,
    checks: list[BaselineVerificationCheck],
    strict: bool,
    metadata: BaselineMetadata | None = None,
    live_metrics_available: bool = False,
    advice: list[str] | None = None,
) -> BaselineVerificationResult:
    """Build final verification status and advice."""
    snapshot_available = metadata.metrics_snapshot is not None if metadata else False
    portable = snapshot_available
    usable_for_regression = any(
        check.name == "usable_for_regression" and check.status == "passed"
        for check in checks
    )
    has_failed = any(check.status == "failed" for check in checks)
    has_warning = any(check.status == "warning" for check in checks)
    if strict and has_warning:
        checks = [
            *checks,
            BaselineVerificationCheck(
                name="strict",
                status="failed",
                message="--strict treats baseline verification warnings as failures.",
            ),
        ]
        has_failed = True
    status: BaselineVerifyStatus = "passed"
    if has_failed:
        status = "failed"
    elif has_warning:
        status = "warning"
    final_advice = list(advice or [])
    if has_failed:
        final_advice.append(
            "Fix failed checks before using this baseline for required "
            "regression gates."
        )
    elif has_warning:
        final_advice.append(
            "Review warnings; use --strict to make warnings fail in automation."
        )
    message = (
        "Baseline verification passed."
        if status == "passed"
        else "Baseline verification completed with warnings."
        if status == "warning"
        else "Baseline verification failed."
    )
    return BaselineVerificationResult(
        status=status,
        label=label or (metadata.label if metadata else None),
        run_id=metadata.run_id if metadata else None,
        baseline_path=str(baseline_path),
        baseline_source=source,
        live_metrics_available=live_metrics_available,
        snapshot_available=snapshot_available,
        portable=portable,
        usable_for_regression=usable_for_regression and status != "failed",
        checks=checks,
        advice=final_advice,
        message=message,
    )


def live_metrics_exists(project_root: Path, metadata: BaselineMetadata) -> bool:
    """Return whether metadata points to an available live metrics file."""
    run_dir = resolve_metadata_path(project_root, metadata.run_dir or metadata.run_path)
    if not run_dir.exists() and metadata.run_dir is not None:
        run_dir = resolve_metadata_path(project_root, metadata.run_path)
    metrics_path = resolve_metadata_path(project_root, metadata.metrics_path)
    return run_dir.exists() and run_dir.is_dir() and metrics_path.is_file()


def unsafe_metadata_paths(metadata: BaselineMetadata) -> list[str]:
    """Return unsafe relative path fields in portable baseline metadata."""
    unsafe: list[str] = []
    for field_name in ["run_path", "run_dir", "metrics_path"]:
        value = getattr(metadata, field_name)
        if value is None:
            continue
        path = Path(value)
        if any(part == ".." for part in path.parts):
            unsafe.append(field_name)
    return unsafe


def baseline_verification_payload(
    result: BaselineVerificationResult,
) -> dict[str, object]:
    """Return JSON-compatible baseline verification output."""
    return result.model_dump(mode="json")


def baseline_verification_json(result: BaselineVerificationResult) -> str:
    """Render baseline verification JSON."""
    return json.dumps(baseline_verification_payload(result), indent=2, sort_keys=True)


def baseline_verification_markdown(result: BaselineVerificationResult) -> str:
    """Render baseline verification Markdown."""
    lines = [
        "# VibeBench Baseline Verification",
        "",
        f"- Status: `{result.status}`",
        f"- Label: `{result.label or 'none'}`",
        f"- Run id: `{result.run_id or 'none'}`",
        f"- Baseline path: `{result.baseline_path}`",
        f"- Source: `{result.baseline_source or 'none'}`",
        f"- Live metrics available: `{str(result.live_metrics_available).lower()}`",
        f"- Snapshot available: `{str(result.snapshot_available).lower()}`",
        f"- Portable: `{str(result.portable).lower()}`",
        f"- Usable for regression: `{str(result.usable_for_regression).lower()}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Message |",
        "| --- | --- | --- |",
    ]
    for check in result.checks:
        lines.append(
            "| "
            f"{markdown_cell(check.name)} | "
            f"{markdown_cell(check.status)} | "
            f"{markdown_cell(check.message)} |"
        )
    lines.extend(["", "## Advice", ""])
    if result.advice:
        for item in result.advice:
            lines.append(f"- {item}")
    else:
        lines.append("No advice.")
    lines.append("")
    return "\n".join(lines)


def markdown_cell(value: object) -> str:
    """Escape Markdown table cell content."""
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def export_pinned_baseline(
    project_root: Path,
    *,
    label: str = "default",
    output: Path,
    include_local_paths: bool = False,
) -> dict[str, object]:
    """Export a labeled baseline as a portable JSON file."""
    root = project_root.resolve()
    selected_label = normalize_label(label)
    status = show_pinned_baseline(root, label=selected_label)
    if status.metadata is None:
        raise ReportError(status.message)
    if status.metadata.metrics_snapshot is None:
        raise ReportError(
            "Baseline cannot be exported portably because it has no metrics snapshot."
        )
    if output.exists() and output.is_dir():
        raise ReportError(f"Baseline export output is a directory: {output}")
    if not output.parent.exists():
        raise ReportError(
            f"Baseline export parent directory does not exist: {output.parent}"
        )

    exported = portable_baseline_metadata(
        status.metadata,
        label=selected_label,
        include_local_paths=include_local_paths,
    )
    payload = {
        "status": "exported",
        "label": selected_label,
        "output": str(output),
        "include_local_paths": include_local_paths,
        "snapshot_available": exported.metrics_snapshot is not None,
        "portable": exported.metrics_snapshot is not None,
        "baseline": exported.model_dump(mode="json"),
        "message": "Portable baseline exported.",
    }
    output.write_text(
        json.dumps(payload["baseline"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def import_pinned_baseline(
    project_root: Path,
    *,
    label: str = "default",
    input_path: Path,
) -> dict[str, object]:
    """Import a portable pinned baseline JSON file."""
    root = project_root.resolve()
    selected_label = normalize_label(label)
    target_input = input_path if input_path.is_absolute() else root / input_path
    verification = verify_baseline_input(
        root,
        target_input,
        expected_label=selected_label,
        require_portable=True,
        allow_label_override=True,
    )
    if verification.status == "failed":
        failed_messages = [
            check.message for check in verification.checks if check.status == "failed"
        ]
        raise ReportError("; ".join(failed_messages) or verification.message)
    try:
        raw = json.loads(target_input.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReportError(f"Could not parse baseline import file: {exc}") from exc
    if "baseline" in raw and isinstance(raw["baseline"], dict):
        raw = raw["baseline"]
    metadata = BaselineMetadata.model_validate(raw)
    metadata = portable_baseline_metadata(
        metadata,
        label=selected_label,
        include_local_paths=False,
    )
    target = pinned_baseline_file(root, selected_label)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(metadata.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    status = validate_baseline_metadata(root, target, metadata)
    return {
        "status": "imported",
        "label": selected_label,
        "input": str(target_input),
        "baseline_path": str(target),
        "snapshot_available": status.snapshot_available,
        "live_metrics_available": status.live_metrics_available,
        "portable": status.snapshot_available,
        "verification_status": verification.status,
        "verification": baseline_verification_payload(verification),
        "baseline": metadata.model_dump(mode="json"),
        "message": "Portable baseline imported.",
    }


def portable_baseline_metadata(
    metadata: BaselineMetadata,
    *,
    label: str,
    include_local_paths: bool = False,
) -> BaselineMetadata:
    """Return metadata suitable for moving between workspaces."""
    data = metadata.model_dump(mode="json")
    data["label"] = normalize_label(label)
    if not include_local_paths:
        run_id = str(data["run_id"])
        data["run_path"] = f".vibebench/runs/{run_id}"
        data["run_dir"] = f".vibebench/runs/{run_id}"
        data["metrics_path"] = f".vibebench/runs/{run_id}/metrics.json"
    return BaselineMetadata.model_validate(data)


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
    """Validate stored baseline metadata against local run files or snapshot."""
    run_dir = resolve_metadata_path(project_root, metadata.run_dir or metadata.run_path)
    if not run_dir.exists() and metadata.run_dir is not None:
        run_dir = resolve_metadata_path(project_root, metadata.run_path)
    metrics_path = resolve_metadata_path(project_root, metadata.metrics_path)
    live_metrics_available = (
        run_dir.exists()
        and run_dir.is_dir()
        and metrics_path.exists()
        and metrics_path.is_file()
    )
    snapshot_available = metadata.metrics_snapshot is not None
    if not run_dir.exists() or not run_dir.is_dir():
        if snapshot_available:
            return BaselineStatus(
                baseline_path=target,
                metadata=metadata,
                run_dir=run_dir,
                metrics_path=metrics_path,
                is_valid=True,
                live_metrics_available=False,
                snapshot_available=True,
                message=(
                    "Baseline live run directory is missing; portable metrics "
                    "snapshot is available."
                ),
            )
        return BaselineStatus(
            baseline_path=target,
            metadata=metadata,
            run_dir=run_dir,
            metrics_path=metrics_path,
            message=f"Baseline run directory is missing: {run_dir}",
        )
    if not metrics_path.exists():
        if snapshot_available:
            return BaselineStatus(
                baseline_path=target,
                metadata=metadata,
                run_dir=run_dir,
                metrics_path=metrics_path,
                is_valid=True,
                live_metrics_available=False,
                snapshot_available=True,
                message=(
                    "Baseline live metrics.json is missing; portable metrics "
                    "snapshot is available."
                ),
            )
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
        live_metrics_available=live_metrics_available,
        snapshot_available=snapshot_available,
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
        metrics_snapshot=(
            metrics_snapshot_from_metrics(metrics) if source != "legacy" else None
        ),
    )


def metrics_snapshot_from_metrics(
    metrics: dict[str, Any],
) -> BaselineMetricsSnapshot | None:
    """Build the minimal portable metrics snapshot used by regression-check."""
    if "score" not in metrics or "risk_level" not in metrics:
        return None
    return BaselineMetricsSnapshot(
        schema_version="1.0",
        score=as_int(metrics.get("score")),
        risk_level=text(metrics.get("risk_level", "unknown")),
        status=text_or_none(metrics.get("overall_status")),
        project=text_or_none(metrics.get("project_name")),
        created_at=text_or_none(metrics.get("created_at")),
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
    snapshot_available = result.snapshot_available
    live_metrics_available = result.live_metrics_available
    portable = snapshot_available
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
        "snapshot_available": snapshot_available,
        "live_metrics_available": live_metrics_available,
        "portable": portable,
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
