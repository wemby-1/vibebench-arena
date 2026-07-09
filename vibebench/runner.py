"""Run configured VibeBench checks and write metrics."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vibebench.config import VibeBenchConfig
from vibebench.gitdiff import DiffAnalysis, RiskFinding, analyze_git_diff
from vibebench.paths import config_dir

CommandStatus = Literal["passed", "failed"]
OverallStatus = Literal["passed", "failed"]
RiskLevel = Literal["low", "medium", "high", "critical"]


class CommandResult(BaseModel):
    """Result from one configured command."""

    model_config = ConfigDict(extra="forbid")

    group: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float = Field(ge=0)
    status: CommandStatus


class CheckSummary(BaseModel):
    """Aggregate command and finding counts for a check run."""

    model_config = ConfigDict(extra="forbid")

    total_commands: int
    passed_commands: int
    failed_commands: int
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    warning_findings: int = 0
    info_findings: int = 0


class CheckRunResult(BaseModel):
    """Structured metrics for one VibeBench check run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    project_name: str
    created_at: datetime
    overall_status: OverallStatus
    score: int
    risk_level: RiskLevel
    command_results: list[CommandResult]
    diff_analysis: DiffAnalysis
    risk_findings: list[RiskFinding]
    summary: CheckSummary
    run_dir: Path
    metrics_path: Path
    log_path: Path


def score_from_failures(
    failed_commands: int,
    risk_findings: list[RiskFinding] | None = None,
) -> int:
    """Calculate the VibeScore from commands and risk findings."""
    score = 100 - (failed_commands * 40)
    for finding in risk_findings or []:
        if finding.severity == "critical":
            score -= 30
        elif finding.severity == "high":
            score -= 20
        elif finding.severity == "warning":
            score -= 8
    return max(0, min(100, score))


def risk_level_for_score(score: int) -> RiskLevel:
    """Return the risk level for a score."""
    if score >= 85:
        return "low"
    if score >= 65:
        return "medium"
    if score >= 40:
        return "high"
    return "critical"


def configured_commands(config: VibeBenchConfig) -> list[tuple[str, str]]:
    """Flatten configured check groups into ordered commands."""
    commands: list[tuple[str, str]] = []
    for command in config.checks.test:
        commands.append(("test", command))
    for command in config.checks.lint:
        commands.append(("lint", command))
    return commands


def run_command(
    group: str,
    command: str,
    project_root: Path,
    timeout_seconds: int = 900,
) -> CommandResult:
    """Run one configured command and capture its result."""
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=project_root,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        stderr = f"{stderr}\nCommand timed out after {timeout_seconds} seconds.".strip()

    duration = round(time.perf_counter() - start, 3)
    status: CommandStatus = "passed" if exit_code == 0 else "failed"

    return CommandResult(
        group=group,
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=duration,
        status=status,
    )


def create_run_dir(project_root: Path, created_at: datetime) -> Path:
    """Create the timestamped VibeBench run directory."""
    timestamp = next_run_timestamp(config_dir(project_root) / "runs", created_at)
    base_dir = config_dir(project_root) / "runs" / timestamp
    run_dir = base_dir
    suffix = 1
    while run_dir.exists():
        run_dir = Path(f"{base_dir}_{suffix}")
        suffix += 1
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def next_run_timestamp(runs_dir: Path, created_at: datetime) -> str:
    """Return a run timestamp that sorts after existing timestamped runs."""
    timestamp = created_at.astimezone().strftime("%Y%m%d_%H%M%S")
    if not runs_dir.exists():
        return timestamp

    latest_timestamp = timestamp
    for path in runs_dir.iterdir():
        if not path.is_dir():
            continue
        try:
            parsed = datetime.strptime(path.name[:15], "%Y%m%d_%H%M%S").replace(
                tzinfo=created_at.tzinfo or UTC
            )
        except ValueError:
            continue
        if path.name[:15] > latest_timestamp:
            latest_timestamp = (parsed + timedelta(seconds=1)).strftime(
                "%Y%m%d_%H%M%S"
            )
    return latest_timestamp


def build_result(
    config: VibeBenchConfig,
    command_results: list[CommandResult],
    diff_analysis: DiffAnalysis,
    risk_findings: list[RiskFinding],
    run_dir: Path,
    created_at: datetime,
) -> CheckRunResult:
    """Build structured metrics from command and diff results."""
    passed_commands = sum(1 for result in command_results if result.status == "passed")
    failed_commands = len(command_results) - passed_commands
    critical_findings = count_findings(risk_findings, "critical")
    high_findings = count_findings(risk_findings, "high")
    warning_findings = count_findings(risk_findings, "warning")
    info_findings = count_findings(risk_findings, "info")
    score = score_from_failures(failed_commands, risk_findings)
    overall_status: OverallStatus = (
        "failed" if failed_commands > 0 or critical_findings > 0 else "passed"
    )

    return CheckRunResult(
        project_name=config.project.name,
        created_at=created_at,
        overall_status=overall_status,
        score=score,
        risk_level=risk_level_for_score(score),
        command_results=command_results,
        diff_analysis=diff_analysis,
        risk_findings=risk_findings,
        summary=CheckSummary(
            total_commands=len(command_results),
            passed_commands=passed_commands,
            failed_commands=failed_commands,
            total_findings=len(risk_findings),
            critical_findings=critical_findings,
            high_findings=high_findings,
            warning_findings=warning_findings,
            info_findings=info_findings,
        ),
        run_dir=run_dir,
        metrics_path=run_dir / "metrics.json",
        log_path=run_dir / "check.log",
    )


def count_findings(findings: list[RiskFinding], severity: str) -> int:
    """Count findings by severity."""
    return sum(1 for finding in findings if finding.severity == severity)


def write_metrics(result: CheckRunResult) -> None:
    """Write metrics.json for a check run."""
    payload = result.model_dump(mode="json")
    result.metrics_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_log(result: CheckRunResult) -> None:
    """Write a readable check.log for a check run."""
    lines = [
        f"VibeBench check run: {result.project_name}",
        f"Created at: {result.created_at.isoformat()}",
        f"Overall status: {result.overall_status}",
        f"Score: {result.score}",
        f"Risk level: {result.risk_level}",
        "",
        "Git diff analysis:",
        f"Git available: {result.diff_analysis.git_available}",
        f"Changed files: {result.diff_analysis.changed_file_count}",
        f"Total added lines: {result.diff_analysis.total_added_lines}",
        f"Total deleted lines: {result.diff_analysis.total_deleted_lines}",
        f"Total patch lines: {result.diff_analysis.total_patch_lines}",
        "Warnings:",
        *(result.diff_analysis.warnings or ["(none)"]),
        "",
        "Risk findings:",
    ]

    if result.risk_findings:
        for finding in result.risk_findings:
            paths = ", ".join(finding.paths) if finding.paths else "(none)"
            lines.extend(
                [
                    f"- {finding.severity.upper()} {finding.code}: {finding.message}",
                    f"  Paths: {paths}",
                ]
            )
    else:
        lines.append("(none)")

    lines.append("")

    for index, command in enumerate(result.command_results, start=1):
        lines.extend(
            [
                f"[{index}] {command.group}: {command.command}",
                f"Status: {command.status}",
                f"Exit code: {command.exit_code}",
                f"Duration seconds: {command.duration_seconds:.3f}",
                "STDOUT:",
                command.stdout.rstrip() or "(empty)",
                "STDERR:",
                command.stderr.rstrip() or "(empty)",
                "",
            ]
        )

    result.log_path.write_text("\n".join(lines), encoding="utf-8")


def run_checks(
    config: VibeBenchConfig,
    project_root: Path,
    timeout_seconds: int = 900,
) -> CheckRunResult:
    """Run all configured checks and persist metrics artifacts."""
    root = project_root.resolve()
    created_at = datetime.now(UTC)
    run_dir = create_run_dir(root, created_at)
    command_results = [
        run_command(group, command, root, timeout_seconds)
        for group, command in configured_commands(config)
    ]
    diff_analysis, risk_findings = analyze_git_diff(
        root, config.effective_risk(), config.risk_rules
    )
    check_result = build_result(
        config,
        command_results,
        diff_analysis,
        risk_findings,
        run_dir,
        created_at,
    )
    write_metrics(check_result)
    write_log(check_result)
    return check_result
