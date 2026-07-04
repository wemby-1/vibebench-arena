"""Compare two VibeBench runs and persist comparison artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from vibebench.artifacts import KNOWN_ARTIFACTS
from vibebench.baseline import show_baseline
from vibebench.paths import config_dir
from vibebench.report import ReportError, load_metrics

COMPARE_JSON = "compare.json"
COMPARE_SUMMARY = "compare.md"
Verdict = Literal["improved", "stable", "regressed", "mixed", "insufficient-data"]
RegressionGuardStatus = Literal["passed", "failed", "not_evaluated"]

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

RECOMMENDATIONS: dict[Verdict, str] = {
    "improved": "Quality improved compared with the base run.",
    "stable": "Quality is stable compared with the base run.",
    "regressed": (
        "Review carefully before shipping; this run regressed against the base run."
    ),
    "mixed": "Review the mixed result; some signals improved while others regressed.",
    "insufficient-data": (
        "Run VibeBench at least twice or provide explicit base/head run directories."
    ),
}


class CompareMetric(BaseModel):
    """One metric row in a VibeBench run comparison."""

    model_config = ConfigDict(extra="forbid")

    name: str
    base: str
    head: str
    delta: str

    @property
    def current(self) -> str:
        """Backward-compatible alias for the head value."""
        return self.head


class StatusChange(BaseModel):
    """Status movement for one command slot or command text."""

    model_config = ConfigDict(extra="forbid")

    command: str
    base_status: str
    head_status: str


class ArtifactChange(BaseModel):
    """Availability movement for one known artifact."""

    model_config = ConfigDict(extra="forbid")

    artifact: str
    base_available: bool
    head_available: bool


class RegressionGuard(BaseModel):
    """Opt-in compare regression guard status."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    status: RegressionGuardStatus
    message: str


class RunSnapshot(BaseModel):
    """Small comparable snapshot of one metrics.json payload."""

    model_config = ConfigDict(extra="forbid")

    run_dir: Path
    run_id: str
    created_at: str
    overall_status: str
    score: int
    risk_level: str
    command_count: int
    passed_command_count: int
    failed_command_count: int
    changed_files: int
    added_lines: int
    deleted_lines: int
    patch_lines: int
    risk_findings_count: int
    command_statuses: dict[str, str]
    artifact_availability: dict[str, bool]


class CompareResult(BaseModel):
    """Structured result for comparing two VibeBench runs."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str
    verdict: Verdict
    base_run: Path | None
    head_run: Path | None
    base_run_id: str | None
    head_run_id: str | None
    base_created_at: str
    head_created_at: str
    base_status: str
    head_status: str
    score_delta: int | None
    risk_level_change: str
    changed_files_delta: int | None
    added_lines_delta: int | None
    deleted_lines_delta: int | None
    risk_findings_delta: int | None
    metrics: list[CompareMetric]
    command_status_changes: list[StatusChange]
    artifact_availability_changes: list[ArtifactChange]
    recommendation: str
    json_path: Path | None = None
    summary_path: Path | None = None
    skipped_runs: list[str] = []
    regression_guard: RegressionGuard = Field(
        default_factory=lambda: regression_guard_for("stable", enabled=False)
    )

    @property
    def output_path(self) -> Path | None:
        """Backward-compatible alias for the Markdown summary path."""
        return self.summary_path

    @property
    def current_run(self) -> Path | None:
        """Backward-compatible alias for the head run path."""
        return self.head_run

    @property
    def risk_delta(self) -> str:
        """Backward-compatible alias for risk movement."""
        return self.risk_level_change


@dataclass(frozen=True)
class ValidRuns:
    """Readable run directory selection with skip notes."""

    runs_dir: Path
    runs: list[tuple[Path, dict[str, Any]]]
    skipped_runs: list[str]


def find_comparable_runs(
    project_root: Path,
    runs_dir: Path | None = None,
) -> list[Path]:
    """Return run directories with readable metrics.json, sorted by name."""
    result = find_valid_runs(project_root, runs_dir)
    return [run_dir for run_dir, _metrics in result.runs]


def find_valid_runs(project_root: Path, runs_dir: Path | None = None) -> ValidRuns:
    """Find readable run directories without crashing on corrupt old runs."""
    root = project_root.resolve()
    selected_runs_dir = resolve_runs_dir(root, runs_dir)
    if not selected_runs_dir.exists():
        return ValidRuns(selected_runs_dir, [], [])
    if not selected_runs_dir.is_dir():
        raise ReportError(f"Runs path is not a directory: {selected_runs_dir}")

    runs: list[tuple[Path, dict[str, Any]]] = []
    skipped: list[str] = []
    run_dirs = sorted(
        path for path in selected_runs_dir.iterdir() if path.is_dir()
    )
    for run_dir in run_dirs:
        metrics_path = run_dir / "metrics.json"
        if not metrics_path.is_file() or metrics_path.is_symlink():
            skipped.append(f"Skipped {run_dir.name}: metrics.json missing")
            continue
        try:
            metrics = load_metrics(run_dir)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            skipped.append(
                f"Skipped {run_dir.name}: could not read metrics.json: {exc}"
            )
            continue
        runs.append((run_dir.resolve(), metrics))
    return ValidRuns(selected_runs_dir, runs, skipped)


def load_run_snapshot(run_dir: Path) -> RunSnapshot:
    """Load comparable values from a run directory."""
    if not run_dir.exists() or not run_dir.is_dir():
        raise ReportError(f"Run directory does not exist: {run_dir}")
    metrics_path = run_dir / "metrics.json"
    if not metrics_path.exists():
        raise ReportError(f"No metrics.json found in {run_dir}.")
    try:
        metrics = load_metrics(run_dir)
    except json.JSONDecodeError as exc:
        raise ReportError(f"metrics.json in {run_dir} is not valid JSON.") from exc
    return snapshot_from_metrics(run_dir.resolve(), metrics)


def snapshot_from_metrics(run_dir: Path, metrics: dict[str, Any]) -> RunSnapshot:
    """Build a comparable snapshot from metrics data."""
    summary = as_dict(metrics.get("summary"))
    diff = as_dict(metrics.get("diff_analysis"))
    findings = as_list(metrics.get("risk_findings"))
    commands = as_list(metrics.get("command_results"))

    return RunSnapshot(
        run_dir=run_dir,
        run_id=run_dir.name,
        created_at=text(metrics.get("created_at", "")),
        overall_status=text(metrics.get("overall_status", "unknown")),
        score=as_int(metrics.get("score")),
        risk_level=text(metrics.get("risk_level", "unknown")),
        command_count=as_int(summary.get("total_commands"), len(commands)),
        passed_command_count=as_int(summary.get("passed_commands")),
        failed_command_count=as_int(summary.get("failed_commands")),
        changed_files=as_int(diff.get("changed_file_count")),
        added_lines=as_int(diff.get("total_added_lines")),
        deleted_lines=as_int(diff.get("total_deleted_lines")),
        patch_lines=as_int(diff.get("total_patch_lines")),
        risk_findings_count=as_int(summary.get("total_findings"), len(findings)),
        command_statuses=command_status_map(commands),
        artifact_availability=artifact_availability(run_dir),
    )


def compare_runs(
    project_root: Path,
    current_run: Path | None = None,
    base_run: Path | None = None,
    use_baseline: bool = False,
    *,
    runs_dir: Path | None = None,
    head_run: Path | None = None,
    base_run_id: str | None = None,
    head_run_id: str | None = None,
    write_json_path: Path | None = None,
    write_summary_path: Path | None = None,
    write_default_artifacts: bool = True,
    fail_on_regression: bool = False,
) -> CompareResult:
    """Compare two runs and optionally write compare artifacts."""
    root = project_root.resolve()
    selected_head = head_run or current_run
    selection = select_runs(
        root,
        current_run=selected_head,
        base_run=base_run,
        use_baseline=use_baseline,
        runs_dir=runs_dir,
        base_run_id=base_run_id,
        head_run_id=head_run_id,
    )
    if selection.verdict == "insufficient-data":
        result = selection
    else:
        if selection.base_run is None or selection.head_run is None:
            raise ReportError("Compare selection did not include both runs.")
        base = load_run_snapshot(selection.base_run)
        head = load_run_snapshot(selection.head_run)
        result = build_compare_result(base, head, skipped_runs=selection.skipped_runs)

    result.regression_guard = regression_guard_for(
        result.verdict,
        enabled=fail_on_regression,
    )
    write_compare_outputs(
        result,
        write_json_path=write_json_path,
        write_summary_path=write_summary_path,
        write_default_artifacts=write_default_artifacts,
    )
    return result


def select_runs(
    project_root: Path,
    current_run: Path | None,
    base_run: Path | None,
    use_baseline: bool = False,
    *,
    runs_dir: Path | None = None,
    base_run_id: str | None = None,
    head_run_id: str | None = None,
) -> CompareResult:
    """Select base and head run directories or return insufficient-data."""
    if use_baseline:
        if base_run is not None or base_run_id is not None:
            raise ReportError(
                "Use either --baseline or --base/--base-run-dir, not both."
            )
        baseline = show_baseline(project_root)
        if baseline.metadata is None:
            return insufficient_result("No baseline found.")
        if not baseline.is_valid or baseline.run_dir is None:
            raise ReportError(baseline.message)
        if current_run is not None:
            return selected_result(
                baseline.run_dir,
                resolve_run(project_root, current_run),
            )
        valid = find_valid_runs(project_root, runs_dir)
        if not valid.runs:
            return insufficient_result(
                "No valid VibeBench runs found.",
                valid.skipped_runs,
            )
        return selected_result(baseline.run_dir, valid.runs[-1][0], valid.skipped_runs)

    explicit_dirs = current_run is not None or base_run is not None
    explicit_ids = base_run_id is not None or head_run_id is not None
    if explicit_dirs and explicit_ids:
        raise ReportError("Use explicit run dirs or run ids, not both.")
    if explicit_dirs:
        if current_run is not None and base_run is None:
            selected_head = resolve_run(project_root, current_run)
            valid = find_valid_runs(project_root, runs_dir)
            previous = [run for run, _metrics in valid.runs if run != selected_head]
            previous = [run for run in previous if run.name < selected_head.name]
            if not previous:
                return insufficient_result(
                    "Need a previous valid VibeBench run for the selected head run.",
                    valid.skipped_runs,
                    head_run=selected_head,
                )
            return selected_result(previous[-1], selected_head, valid.skipped_runs)
        if current_run is None or base_run is None:
            raise ReportError("Provide --head-run-dir with --base-run-dir, or neither.")
        return selected_result(
            resolve_run(project_root, base_run),
            resolve_run(project_root, current_run),
        )
    if explicit_ids:
        if base_run_id is None or head_run_id is None:
            raise ReportError("Provide both --base and --head, or neither.")
        selected_runs_dir = resolve_runs_dir(project_root, runs_dir)
        return selected_result(
            selected_runs_dir / base_run_id,
            selected_runs_dir / head_run_id,
        )

    valid = find_valid_runs(project_root, runs_dir)
    if len(valid.runs) < 2:
        return insufficient_result(
            "Need at least two valid VibeBench runs with metrics.json.",
            valid.skipped_runs,
        )
    return selected_result(valid.runs[-2][0], valid.runs[-1][0], valid.skipped_runs)


def selected_result(
    base_run: Path,
    head_run: Path,
    skipped_runs: list[str] | None = None,
) -> CompareResult:
    """Return a temporary selected result for internal flow."""
    return CompareResult(
        status="selected",
        verdict="stable",
        base_run=base_run.resolve(),
        head_run=head_run.resolve(),
        base_run_id=base_run.name,
        head_run_id=head_run.name,
        base_created_at="",
        head_created_at="",
        base_status="",
        head_status="",
        score_delta=None,
        risk_level_change="",
        changed_files_delta=None,
        added_lines_delta=None,
        deleted_lines_delta=None,
        risk_findings_delta=None,
        metrics=[],
        command_status_changes=[],
        artifact_availability_changes=[],
        recommendation="",
        skipped_runs=skipped_runs or [],
    )


def insufficient_result(
    message: str,
    skipped_runs: list[str] | None = None,
    *,
    head_run: Path | None = None,
) -> CompareResult:
    """Return a successful insufficient-data comparison."""
    return CompareResult(
        status="insufficient-data",
        verdict="insufficient-data",
        base_run=None,
        head_run=head_run.resolve() if head_run is not None else None,
        base_run_id=None,
        head_run_id=head_run.name if head_run is not None else None,
        base_created_at="",
        head_created_at="",
        base_status="",
        head_status="",
        score_delta=None,
        risk_level_change="n/a",
        changed_files_delta=None,
        added_lines_delta=None,
        deleted_lines_delta=None,
        risk_findings_delta=None,
        metrics=[],
        command_status_changes=[],
        artifact_availability_changes=[],
        recommendation=message or RECOMMENDATIONS["insufficient-data"],
        skipped_runs=skipped_runs or [],
    )


def build_compare_result(
    base: RunSnapshot,
    head: RunSnapshot,
    *,
    skipped_runs: list[str] | None = None,
) -> CompareResult:
    """Build a complete comparison result from two snapshots."""
    verdict = verdict_for(base, head)
    return CompareResult(
        status="ok",
        verdict=verdict,
        base_run=base.run_dir,
        head_run=head.run_dir,
        base_run_id=base.run_id,
        head_run_id=head.run_id,
        base_created_at=base.created_at,
        head_created_at=head.created_at,
        base_status=base.overall_status,
        head_status=head.overall_status,
        score_delta=head.score - base.score,
        risk_level_change=format_risk_delta(base.risk_level, head.risk_level),
        changed_files_delta=head.changed_files - base.changed_files,
        added_lines_delta=head.added_lines - base.added_lines,
        deleted_lines_delta=head.deleted_lines - base.deleted_lines,
        risk_findings_delta=head.risk_findings_count - base.risk_findings_count,
        metrics=metric_rows(base, head),
        command_status_changes=command_status_changes(base, head),
        artifact_availability_changes=artifact_changes_for(base, head),
        recommendation=RECOMMENDATIONS[verdict],
        skipped_runs=skipped_runs or [],
    )


def resolve_runs_dir(project_root: Path, runs_dir: Path | None) -> Path:
    """Resolve a runs directory."""
    if runs_dir is None:
        return config_dir(project_root) / "runs"
    if runs_dir.is_absolute():
        return runs_dir.resolve()
    return (project_root / runs_dir).resolve()


def resolve_run(project_root: Path, run_dir: Path) -> Path:
    """Resolve a run directory relative to the project root."""
    return (run_dir if run_dir.is_absolute() else project_root / run_dir).resolve()


def verdict_for(base: RunSnapshot, current: RunSnapshot) -> Verdict:
    """Return the deterministic comparison verdict."""
    positive = 0
    negative = 0
    score_delta = current.score - base.score
    risk_delta = risk_delta_for(base.risk_level, current.risk_level)
    failed_delta = current.failed_command_count - base.failed_command_count
    findings_delta = current.risk_findings_count - base.risk_findings_count

    if score_delta > 0:
        positive += 1
    elif score_delta < 0:
        negative += 1
    for delta in (risk_delta, failed_delta, findings_delta):
        if delta < 0:
            positive += 1
        elif delta > 0:
            negative += 1

    if positive and negative:
        return "mixed"
    if negative:
        return "regressed"
    if positive:
        return "improved"
    return "stable"


def risk_delta_for(base: str, current: str) -> int:
    """Return risk movement, treating unknown risk values as neutral."""
    base_key = base.lower()
    current_key = current.lower()
    if base_key not in RISK_ORDER or current_key not in RISK_ORDER:
        return 0
    return RISK_ORDER[current_key] - RISK_ORDER[base_key]


def metric_rows(base: RunSnapshot, head: RunSnapshot) -> list[CompareMetric]:
    """Build table rows for comparable metrics."""
    return [
        text_metric("Overall status", base.overall_status, head.overall_status),
        number_metric("VibeScore", base.score, head.score),
        text_metric("Risk level", base.risk_level, head.risk_level),
        number_metric("Changed files", base.changed_files, head.changed_files),
        number_metric("Added lines", base.added_lines, head.added_lines),
        number_metric("Deleted lines", base.deleted_lines, head.deleted_lines),
        number_metric(
            "Risk findings",
            base.risk_findings_count,
            head.risk_findings_count,
        ),
        number_metric("Command count", base.command_count, head.command_count),
        number_metric(
            "Passed command count",
            base.passed_command_count,
            head.passed_command_count,
        ),
        number_metric(
            "Failed command count",
            base.failed_command_count,
            head.failed_command_count,
        ),
        number_metric("Patch lines", base.patch_lines, head.patch_lines),
    ]


def number_metric(name: str, base: int, head: int) -> CompareMetric:
    """Build a numeric metric row."""
    return CompareMetric(
        name=name,
        base=str(base),
        head=str(head),
        delta=format_number_delta(head - base),
    )


def text_metric(name: str, base: str, head: str) -> CompareMetric:
    """Build a text metric row."""
    delta = "unchanged" if base == head else f"{base} -> {head}"
    return CompareMetric(name=name, base=base, head=head, delta=delta)


def command_status_map(commands: list[Any]) -> dict[str, str]:
    """Return command statuses keyed by stable command text or index."""
    statuses: dict[str, str] = {}
    for index, command in enumerate(commands, start=1):
        item = as_dict(command)
        key = text(item.get("command")) or f"command-{index}"
        statuses[key] = text(item.get("status", "unknown"))
    return statuses


def command_status_changes(base: RunSnapshot, head: RunSnapshot) -> list[StatusChange]:
    """Return command status changes."""
    changes = []
    for command in sorted(set(base.command_statuses) | set(head.command_statuses)):
        base_status = base.command_statuses.get(command, "missing")
        head_status = head.command_statuses.get(command, "missing")
        if base_status != head_status:
            changes.append(
                StatusChange(
                    command=command,
                    base_status=base_status,
                    head_status=head_status,
                )
            )
    return changes


def artifact_availability(run_dir: Path) -> dict[str, bool]:
    """Return availability for known artifacts in a run directory."""
    return {
        path.as_posix(): artifact_file_available(run_dir, path)
        for path in KNOWN_ARTIFACTS
    }


def artifact_file_available(run_dir: Path, relative_path: Path) -> bool:
    """Return whether an artifact exists as a regular non-symlink file."""
    artifact_path = run_dir / relative_path
    return artifact_path.is_file() and not artifact_path.is_symlink()


def artifact_changes_for(base: RunSnapshot, head: RunSnapshot) -> list[ArtifactChange]:
    """Return artifact availability changes."""
    changes = []
    artifact_names = sorted(
        set(base.artifact_availability) | set(head.artifact_availability)
    )
    for artifact in artifact_names:
        base_available = base.artifact_availability.get(artifact, False)
        head_available = head.artifact_availability.get(artifact, False)
        if base_available != head_available:
            changes.append(
                ArtifactChange(
                    artifact=artifact,
                    base_available=base_available,
                    head_available=head_available,
                )
            )
    return changes


def compare_json_payload(result: CompareResult) -> dict[str, object]:
    """Return a deterministic JSON payload for a run comparison."""
    artifact_changes = [
        item.model_dump() for item in result.artifact_availability_changes
    ]
    command_changes = [item.model_dump() for item in result.command_status_changes]
    payload: dict[str, object] = {
        "added_lines_delta": result.added_lines_delta,
        "artifact_availability_changes": artifact_changes,
        "base_created_at": result.base_created_at,
        "base_run_dir": str(result.base_run) if result.base_run is not None else None,
        "base_run_id": result.base_run_id,
        "base_status": result.base_status,
        "changed_files_delta": result.changed_files_delta,
        "command_status_changes": command_changes,
        "deleted_lines_delta": result.deleted_lines_delta,
        "head_created_at": result.head_created_at,
        "head_run_dir": str(result.head_run) if result.head_run is not None else None,
        "head_run_id": result.head_run_id,
        "head_status": result.head_status,
        "json_path": str(result.json_path) if result.json_path is not None else None,
        "metrics": [item.model_dump() for item in result.metrics],
        "recommendation": result.recommendation,
        "risk_findings_delta": result.risk_findings_delta,
        "risk_level_change": result.risk_level_change,
        "score_delta": result.score_delta,
        "skipped_runs": result.skipped_runs,
        "status": result.status,
        "summary_path": (
            str(result.summary_path) if result.summary_path is not None else None
        ),
        "verdict": result.verdict,
    }
    if result.regression_guard.enabled:
        payload["regression_guard"] = result.regression_guard.model_dump()
    return payload


def write_compare_json(result: CompareResult, output_path: Path) -> Path:
    """Write comparison JSON to a file."""
    validate_output_path(output_path)
    result.json_path = output_path.resolve()
    output_path.write_text(
        json.dumps(compare_json_payload(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_compare_summary(result: CompareResult, output_path: Path) -> Path:
    """Write comparison Markdown to a file."""
    validate_output_path(output_path)
    result.summary_path = output_path.resolve()
    output_path.write_text(render_markdown(result), encoding="utf-8")
    return output_path


def write_compare_outputs(
    result: CompareResult,
    *,
    write_json_path: Path | None,
    write_summary_path: Path | None,
    write_default_artifacts: bool,
) -> None:
    """Write requested and default compare artifacts."""
    default_dir = result.head_run if result.head_run is not None else None
    if write_default_artifacts and default_dir is not None:
        write_compare_summary(result, default_dir / COMPARE_SUMMARY)
        write_compare_json(result, default_dir / COMPARE_JSON)
    if write_summary_path is not None:
        write_compare_summary(result, write_summary_path)
    if write_json_path is not None:
        write_compare_json(result, write_json_path)


def render_markdown(result: CompareResult) -> str:
    """Render compare.md."""
    lines = [
        "# VibeBench Run Comparison",
        "",
        f"- Verdict: **{result.verdict}**",
        f"- Base run: `{result.base_run_id or 'n/a'}`",
        f"- Head run: `{result.head_run_id or 'n/a'}`",
    ]
    if result.regression_guard.enabled:
        lines.append(f"- Regression guard: **{result.regression_guard.status}**")
    if result.status == "insufficient-data":
        lines.extend(["", f"Recommendation: {result.recommendation}", ""])
        return "\n".join(lines)

    lines.extend([
        f"- Base created at: `{result.base_created_at}`",
        f"- Head created at: `{result.head_created_at}`",
        f"- Base status: `{result.base_status}`",
        f"- Head status: `{result.head_status}`",
        "",
        "## Metric Deltas",
        "",
        "| Metric | Base | Head | Delta |",
        "| --- | ---: | ---: | ---: |",
    ])
    for metric in result.metrics:
        lines.append(
            "| "
            f"{escape_markdown(metric.name)} | "
            f"{escape_markdown(metric.base)} | "
            f"{escape_markdown(metric.head)} | "
            f"{escape_markdown(metric.delta)} |"
        )

    lines.extend(["", "## Command Status Changes", ""])
    if result.command_status_changes:
        lines.extend(["| Command | Base | Head |", "| --- | --- | --- |"])
        for change in result.command_status_changes:
            lines.append(
                "| "
                f"{escape_markdown(change.command)} | "
                f"{escape_markdown(change.base_status)} | "
                f"{escape_markdown(change.head_status)} |"
            )
    else:
        lines.append("No command status changes.")

    lines.extend(["", "## Artifact Availability Changes", ""])
    if result.artifact_availability_changes:
        lines.extend(["| Artifact | Base | Head |", "| --- | --- | --- |"])
        for change in result.artifact_availability_changes:
            lines.append(
                "| "
                f"{escape_markdown(change.artifact)} | "
                f"{availability_text(change.base_available)} | "
                f"{availability_text(change.head_available)} |"
            )
    else:
        lines.append("No artifact availability changes.")

    if result.skipped_runs:
        lines.extend(["", "## Skipped Runs", ""])
        for skipped in result.skipped_runs:
            lines.append(f"- {escape_markdown(skipped)}")

    lines.extend(["", f"Recommendation: {result.recommendation}", ""])
    return "\n".join(lines)


def validate_output_path(output_path: Path) -> None:
    """Validate a requested compare output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"Compare output path is a directory: {output_path}")
    if not output_path.parent.exists():
        raise ReportError(f"Compare output parent does not exist: {output_path.parent}")


def regression_guard_for(
    verdict: Verdict,
    *,
    enabled: bool,
) -> RegressionGuard:
    """Return deterministic regression guard status for a compare verdict."""
    if not enabled:
        return RegressionGuard(
            enabled=False,
            status="not_evaluated",
            message="Regression guard disabled.",
        )
    if verdict == "regressed":
        return RegressionGuard(
            enabled=True,
            status="failed",
            message="Regression guard failed: comparison verdict is regressed.",
        )
    return RegressionGuard(
        enabled=True,
        status="passed",
        message=f"Regression guard passed: comparison verdict is {verdict}.",
    )


def format_risk_delta(base: str, current: str) -> str:
    """Format risk movement between two runs."""
    return "unchanged" if base == current else f"{base} -> {current}"


def risk_rank(value: str) -> int:
    """Return a safe comparable rank for risk level."""
    return RISK_ORDER.get(value.lower(), len(RISK_ORDER))


def format_number_delta(value: int) -> str:
    """Format a signed numeric delta."""
    if value > 0:
        return f"+{value}"
    return str(value)


def availability_text(value: bool) -> str:
    """Format artifact availability for Markdown."""
    return "available" if value else "missing"


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


def escape_markdown(value: object) -> str:
    """Escape table-sensitive Markdown characters."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\n", " ")
    )
