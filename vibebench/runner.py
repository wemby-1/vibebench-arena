"""Run configured VibeBench checks and write metrics."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vibebench.config import VibeBenchConfig
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
    """Aggregate command counts for a check run."""

    model_config = ConfigDict(extra="forbid")

    total_commands: int
    passed_commands: int
    failed_commands: int


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
    summary: CheckSummary
    run_dir: Path
    metrics_path: Path
    log_path: Path


def score_from_failures(failed_commands: int) -> int:
    """Calculate the milestone-2 VibeScore."""
    return max(0, min(100, 100 - (failed_commands * 40)))


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
    timeout_seconds: int = 300,
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
    timestamp = created_at.astimezone().strftime("%Y%m%d_%H%M%S")
    base_dir = config_dir(project_root) / "runs" / timestamp
    run_dir = base_dir
    suffix = 1
    while run_dir.exists():
        run_dir = Path(f"{base_dir}_{suffix}")
        suffix += 1
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def build_result(
    config: VibeBenchConfig,
    command_results: list[CommandResult],
    run_dir: Path,
    created_at: datetime,
) -> CheckRunResult:
    """Build structured metrics from command results."""
    passed_commands = sum(1 for result in command_results if result.status == "passed")
    failed_commands = len(command_results) - passed_commands
    score = score_from_failures(failed_commands)
    overall_status: OverallStatus = "passed" if failed_commands == 0 else "failed"

    return CheckRunResult(
        project_name=config.project.name,
        created_at=created_at,
        overall_status=overall_status,
        score=score,
        risk_level=risk_level_for_score(score),
        command_results=command_results,
        summary=CheckSummary(
            total_commands=len(command_results),
            passed_commands=passed_commands,
            failed_commands=failed_commands,
        ),
        run_dir=run_dir,
        metrics_path=run_dir / "metrics.json",
        log_path=run_dir / "check.log",
    )


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
    ]

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
    timeout_seconds: int = 300,
) -> CheckRunResult:
    """Run all configured checks and persist metrics artifacts."""
    root = project_root.resolve()
    created_at = datetime.now(UTC)
    run_dir = create_run_dir(root, created_at)
    results = [
        run_command(group, command, root, timeout_seconds)
        for group, command in configured_commands(config)
    ]
    check_result = build_result(config, results, run_dir, created_at)
    write_metrics(check_result)
    write_log(check_result)
    return check_result
