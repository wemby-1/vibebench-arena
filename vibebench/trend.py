"""Trend analysis for recent VibeBench runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from vibebench.compare import as_dict, as_int, as_list, risk_rank, text
from vibebench.paths import config_dir
from vibebench.report import ReportError

TrendVerdict = Literal["improved", "stable", "regressed"]
TREND_SUMMARY_FILENAME = "trend.md"


class TrendRun(BaseModel):
    """One run row in a VibeBench trend result."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    run_dir: Path
    overall_status: str
    score: int
    risk_level: str
    risk_findings_count: int
    changed_files: int
    patch_lines: int


class TrendSummary(BaseModel):
    """Aggregate trend metrics across selected runs."""

    model_config = ConfigDict(extra="forbid")

    valid_run_count: int
    pass_rate: float
    latest_score: int | None
    oldest_score: int | None
    score_delta: int | None
    best_score: int | None
    worst_score: int | None
    highest_risk_level: str | None
    latest_finding_count: int | None
    oldest_finding_count: int | None
    finding_count_delta: int | None
    verdict: TrendVerdict
    message: str


class TrendResult(BaseModel):
    """Structured VibeBench trend result."""

    model_config = ConfigDict(extra="forbid")

    runs_dir: Path
    limit: int
    runs: list[TrendRun]
    skipped_runs: list[str]
    summary: TrendSummary

    @property
    def verdict(self) -> TrendVerdict:
        """Return the trend verdict."""
        return self.summary.verdict


def analyze_trend(
    project_root: Path,
    runs_dir: Path | None = None,
    limit: int = 10,
) -> TrendResult:
    """Analyze recent VibeBench run trends."""
    if limit < 1:
        raise ReportError("--limit must be greater than 0.")

    root = project_root.resolve()
    selected_runs_dir = resolve_runs_dir(root, runs_dir)
    if not selected_runs_dir.exists():
        if runs_dir is not None:
            raise ReportError(f"Runs directory does not exist: {selected_runs_dir}")
        return TrendResult(
            runs_dir=selected_runs_dir,
            limit=limit,
            runs=[],
            skipped_runs=[],
            summary=empty_summary(),
        )
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
        return TrendResult(
            runs_dir=selected_runs_dir,
            limit=limit,
            runs=[],
            skipped_runs=[],
            summary=empty_summary(),
        )

    runs: list[TrendRun] = []
    skipped_runs: list[str] = []
    for run_dir in run_dirs:
        try:
            runs.append(load_trend_run(run_dir))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            skipped_runs.append(
                f"Skipped {run_dir.name}: could not read metrics.json: {exc}"
            )
        if len(runs) >= limit:
            break

    if not runs and skipped_runs:
        raise ReportError(
            "No valid VibeBench runs found; all metrics.json files were unreadable "
            "or corrupt."
        )

    return TrendResult(
        runs_dir=selected_runs_dir,
        limit=limit,
        runs=runs,
        skipped_runs=skipped_runs,
        summary=summarize_runs(runs),
    )


def resolve_runs_dir(project_root: Path, runs_dir: Path | None) -> Path:
    """Resolve a runs directory relative to the project root."""
    if runs_dir is not None:
        if runs_dir.is_absolute():
            return runs_dir.resolve()
        return (project_root / runs_dir).resolve()
    return config_dir(project_root) / "runs"


def load_trend_run(run_dir: Path) -> TrendRun:
    """Load trend values from one metrics.json file."""
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    summary = as_dict(metrics.get("summary"))
    diff = as_dict(metrics.get("diff_analysis"))
    findings = as_list(metrics.get("risk_findings"))

    return TrendRun(
        run_id=run_dir.name,
        run_dir=run_dir,
        overall_status=text(metrics.get("overall_status", "unknown")),
        score=as_int(metrics.get("score")),
        risk_level=text(metrics.get("risk_level", "unknown")),
        risk_findings_count=as_int(summary.get("total_findings"), len(findings)),
        changed_files=as_int(diff.get("changed_file_count")),
        patch_lines=as_int(diff.get("total_patch_lines")),
    )


def empty_summary() -> TrendSummary:
    """Return an empty trend summary."""
    return TrendSummary(
        valid_run_count=0,
        pass_rate=0.0,
        latest_score=None,
        oldest_score=None,
        score_delta=None,
        best_score=None,
        worst_score=None,
        highest_risk_level=None,
        latest_finding_count=None,
        oldest_finding_count=None,
        finding_count_delta=None,
        verdict="stable",
        message="No valid VibeBench runs found.",
    )


def summarize_runs(runs: list[TrendRun]) -> TrendSummary:
    """Summarize selected runs newest first."""
    if not runs:
        return empty_summary()

    latest = runs[0]
    oldest = runs[-1]
    passed_count = sum(1 for run in runs if run.overall_status == "passed")
    score_delta = latest.score - oldest.score
    finding_delta = latest.risk_findings_count - oldest.risk_findings_count
    verdict = verdict_for(latest, oldest, score_delta, finding_delta)

    return TrendSummary(
        valid_run_count=len(runs),
        pass_rate=round(passed_count / len(runs), 4),
        latest_score=latest.score,
        oldest_score=oldest.score,
        score_delta=score_delta,
        best_score=max(run.score for run in runs),
        worst_score=min(run.score for run in runs),
        highest_risk_level=highest_risk(runs),
        latest_finding_count=latest.risk_findings_count,
        oldest_finding_count=oldest.risk_findings_count,
        finding_count_delta=finding_delta,
        verdict=verdict,
        message=summary_message(len(runs), verdict),
    )


def verdict_for(
    latest: TrendRun,
    oldest: TrendRun,
    score_delta: int,
    finding_delta: int,
) -> TrendVerdict:
    """Return a trend verdict from newest and oldest selected runs."""
    latest_risk = risk_rank(latest.risk_level)
    oldest_risk = risk_rank(oldest.risk_level)
    if score_delta <= -5 or latest_risk > oldest_risk or finding_delta > 0:
        return "regressed"
    if score_delta >= 5 or latest_risk < oldest_risk or finding_delta < 0:
        return "improved"
    return "stable"


def highest_risk(runs: list[TrendRun]) -> str:
    """Return the highest risk level seen across runs."""
    return max(runs, key=lambda run: risk_rank(run.risk_level)).risk_level


def summary_message(run_count: int, verdict: TrendVerdict) -> str:
    """Return a human-readable trend message."""
    if run_count == 1:
        return "Trend needs at least two valid runs; showing the latest run only."
    if verdict == "improved":
        return "Recent VibeBench quality is improving."
    if verdict == "regressed":
        return "Recent VibeBench quality is regressing; review before shipping."
    return "Recent VibeBench quality is stable."


def write_trend_summary(
    result: TrendResult,
    output_path: Path | None = None,
) -> Path | None:
    """Write a Markdown trend summary artifact."""
    selected_output = output_path
    if selected_output is None:
        if not result.runs:
            return None
        selected_output = result.runs[0].run_dir / TREND_SUMMARY_FILENAME
    selected_output = selected_output.resolve()
    validate_output_path(selected_output)
    selected_output.write_text(render_markdown(result), encoding="utf-8")
    return selected_output


def validate_output_path(output_path: Path) -> None:
    """Validate a requested trend summary output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"Output path is a directory: {output_path}")
    if not output_path.parent.exists():
        raise ReportError(
            f"Output parent directory does not exist: {output_path.parent}"
        )


def render_markdown(result: TrendResult) -> str:
    """Render a human-readable Markdown trend summary."""
    summary = result.summary
    lines = [
        "# VibeBench Trend Summary",
        "",
        f"- Runs directory: `{result.runs_dir}`",
        f"- Valid run count: {summary.valid_run_count}",
        f"- Skipped run count: {len(result.skipped_runs)}",
        f"- Pass rate: {summary.pass_rate * 100:.1f}%",
        f"- Latest score: {optional_markdown(summary.latest_score)}",
        f"- Oldest score: {optional_markdown(summary.oldest_score)}",
        f"- Score delta: {optional_delta(summary.score_delta)}",
        f"- Best score: {optional_markdown(summary.best_score)}",
        f"- Worst score: {optional_markdown(summary.worst_score)}",
        f"- Highest risk: {optional_markdown(summary.highest_risk_level)}",
        f"- Latest finding count: {optional_markdown(summary.latest_finding_count)}",
        f"- Oldest finding count: {optional_markdown(summary.oldest_finding_count)}",
        f"- Finding count delta: {optional_delta(summary.finding_count_delta)}",
        f"- Verdict: **{summary.verdict}**",
        "",
        summary.message,
        "",
    ]
    if result.skipped_runs:
        lines.extend(["## Skipped Runs", ""])
        lines.extend(f"- {escape_markdown(warning)}" for warning in result.skipped_runs)
        lines.append("")
    lines.extend(
        [
            "## Recent Runs",
            "",
            "| Run | Status | Score | Risk | Findings | Changed Files | Patch Lines |",
            "| --- | --- | ---: | --- | ---: | ---: | ---: |",
        ]
    )
    if not result.runs:
        lines.append("| - | - | - | - | - | - | - |")
    else:
        for run in result.runs:
            lines.append(
                "| "
                f"{escape_markdown(run.run_id)} | "
                f"{escape_markdown(run.overall_status)} | "
                f"{run.score} | "
                f"{escape_markdown(run.risk_level)} | "
                f"{run.risk_findings_count} | "
                f"{run.changed_files} | "
                f"{run.patch_lines} |"
            )
    lines.append("")
    return "\n".join(lines)


def optional_markdown(value: object) -> str:
    """Render an optional Markdown scalar."""
    return "n/a" if value is None else escape_markdown(str(value))


def optional_delta(value: int | None) -> str:
    """Render an optional signed delta."""
    if value is None:
        return "n/a"
    if value > 0:
        return f"+{value}"
    return str(value)


def escape_markdown(value: str) -> str:
    """Escape Markdown table-sensitive text."""
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def trend_json(result: TrendResult) -> dict[str, object]:
    """Return deterministic JSON payload for trend output."""
    return {
        "runs_dir": str(result.runs_dir),
        "limit": result.limit,
        "valid_run_count": len(result.runs),
        "skipped_run_count": len(result.skipped_runs),
        "runs": [run_payload(run) for run in result.runs],
        "summary": result.summary.model_dump(),
        "verdict": result.verdict,
    }


def run_payload(run: TrendRun) -> dict[str, object]:
    """Return JSON-safe run payload."""
    return {
        "run_id": run.run_id,
        "run_dir": str(run.run_dir),
        "overall_status": run.overall_status,
        "score": run.score,
        "risk_level": run.risk_level,
        "risk_findings_count": run.risk_findings_count,
        "changed_files": run.changed_files,
        "patch_lines": run.patch_lines,
    }
