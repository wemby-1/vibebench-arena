"""Command-line interface for VibeBench Arena."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from vibebench import __version__
from vibebench.clean import CleanResult, clean_runs
from vibebench.compare import CompareResult, compare_runs
from vibebench.config import ConfigError, default_config_yaml, load_config
from vibebench.doctor import DoctorResult, run_doctor
from vibebench.gh_summary import generate_github_summary
from vibebench.history import HistoryResult, HistoryRun, get_history
from vibebench.paths import config_file
from vibebench.pr_comment import generate_pr_comment
from vibebench.report import (
    ReportError,
    generate_report,
    load_metrics,
    recommendation_for,
)
from vibebench.runner import CheckRunResult, run_checks

app = typer.Typer(
    help="Codex-first quality gate for vibe coding projects.",
    no_args_is_help=True,
)
console = Console()

ProjectRootOption = Annotated[
    Path,
    typer.Option(
        "--project-root",
        "-C",
        help="Project directory where VibeBench should run.",
    ),
]


@app.command()
def version() -> None:
    """Show the installed VibeBench version."""
    console.print(f"VibeBench Arena {__version__}")


@app.command()
def init(
    project_root: ProjectRootOption = Path("."),
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite an existing config file.",
        ),
    ] = False,
) -> None:
    """Create a default .vibebench/config.yaml file."""
    target = config_file(project_root)

    if target.exists() and not force:
        console.print(
            f"[yellow]Config already exists:[/] {target}\n"
            "Use --force to overwrite it."
        )
        raise typer.Exit(code=0)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(default_config_yaml(), encoding="utf-8")
    console.print(f"[green]Created VibeBench config:[/] {target}")


@app.command()
def check(project_root: ProjectRootOption = Path(".")) -> None:
    """Run configured checks and write VibeBench metrics."""
    root = project_root.resolve()
    target = config_file(root)

    try:
        config = load_config(target)
    except ConfigError as exc:
        if not target.exists():
            console.print(
                "[red]No .vibebench/config.yaml found. "
                "Run 'vibebench init' first.[/]"
            )
        else:
            console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    result = run_checks(config, root)
    render_check_summary(result)

    if result.overall_status == "failed":
        raise typer.Exit(code=1)


@app.command()
def report(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to render.",
        ),
    ] = None,
) -> None:
    """Generate a static HTML report for a VibeBench run."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()

    try:
        report_path = generate_report(root, selected_run_dir)
        metrics = load_metrics(report_path.parent.parent)
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    recommendation = recommendation_for(metrics)
    console.print("[green]Report generated.[/]")
    console.print(f"Run directory: {report_path.parent.parent}")
    console.print(f"Report path: {report_path}")
    console.print(f"Recommendation: {recommendation}")


@app.command("pr-comment")
def pr_comment(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to summarize.",
        ),
    ] = None,
) -> None:
    """Generate a PR-ready Markdown summary for a VibeBench run."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()

    try:
        comment_path = generate_pr_comment(root, selected_run_dir)
        metrics = load_metrics(comment_path.parent)
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    recommendation = recommendation_for(metrics)
    console.print("[green]PR comment generated.[/]")
    console.print(f"Run directory: {comment_path.parent}")
    console.print(f"Output path: {comment_path}")
    console.print(f"Recommendation: {recommendation}")


@app.command("gh-summary")
def gh_summary(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to summarize.",
        ),
    ] = None,
) -> None:
    """Write a GitHub Actions step summary for a VibeBench run."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()

    try:
        summary_path = generate_github_summary(root, selected_run_dir)
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    console.print("[green]GitHub step summary written.[/]")
    console.print(f"Output path: {summary_path}")


@app.command()
def doctor(
    project_root: ProjectRootOption = Path("."),
) -> None:
    """Diagnose whether this project is ready to run VibeBench."""
    result = run_doctor(project_root)
    render_doctor_summary(result)
    if result.overall_status == "failed":
        raise typer.Exit(code=1)


@app.command()
def clean(
    project_root: ProjectRootOption = Path("."),
    keep: Annotated[
        int,
        typer.Option("--keep", help="Number of newest valid runs to preserve."),
    ] = 20,
    runs_dir: Annotated[
        Path | None,
        typer.Option("--runs-dir", help="Directory containing VibeBench runs."),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Actually delete cleanup candidates."),
    ] = False,
) -> None:
    """Safely clean old VibeBench run directories."""
    root = project_root.resolve()
    try:
        result = clean_runs(root, runs_dir=runs_dir, keep=keep, yes=yes)
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_clean_summary(result)


@app.command()
def history(
    project_root: ProjectRootOption = Path("."),
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            help="Maximum number of recent runs to show.",
        ),
    ] = 10,
    runs_dir: Annotated[
        Path | None,
        typer.Option(
            "--runs-dir",
            help="Specific directory containing VibeBench run directories.",
        ),
    ] = None,
) -> None:
    """Show recent VibeBench run history."""
    root = project_root.resolve()
    try:
        result = get_history(root, runs_dir=runs_dir, limit=limit)
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_history_summary(result)


@app.command()
def compare(
    project_root: ProjectRootOption = Path("."),
    current_run: Annotated[
        Path | None,
        typer.Option(
            "--current-run",
            help="Current .vibebench/runs/<timestamp> directory.",
        ),
    ] = None,
    base_run: Annotated[
        Path | None,
        typer.Option(
            "--base-run",
            help="Base .vibebench/runs/<timestamp> directory.",
        ),
    ] = None,
) -> None:
    """Compare the latest VibeBench run with the previous run."""
    root = project_root.resolve()
    try:
        result = compare_runs(root, current_run=current_run, base_run=base_run)
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_compare_summary(result)


def render_check_summary(result: CheckRunResult) -> None:
    """Render a concise Rich summary for a check run."""
    status_style = "green" if result.overall_status == "passed" else "red"
    risk_style = {
        "low": "green",
        "medium": "yellow",
        "high": "magenta",
        "critical": "red",
    }[result.risk_level]

    console.print()
    console.print(f"[bold]VibeBench check:[/] {result.project_name}")
    console.print(f"Status: [{status_style}]{result.overall_status}[/]")
    console.print(f"Score: [bold]{result.score}[/]")
    console.print(f"Risk: [{risk_style}]{result.risk_level}[/]")
    console.print(
        "Diff: "
        f"{result.diff_analysis.changed_file_count} files, "
        f"{result.diff_analysis.total_patch_lines} patch lines"
    )
    console.print(
        "Findings: "
        f"{result.summary.critical_findings} critical, "
        f"{result.summary.high_findings} high, "
        f"{result.summary.warning_findings} warning, "
        f"{result.summary.info_findings} info"
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("Group")
    table.add_column("Command")
    table.add_column("Status")
    table.add_column("Exit")
    table.add_column("Duration")

    for command in result.command_results:
        command_style = "green" if command.status == "passed" else "red"
        table.add_row(
            command.group,
            command.command,
            f"[{command_style}]{command.status}[/]",
            str(command.exit_code),
            f"{command.duration_seconds:.3f}s",
        )

    console.print(table)
    render_findings(result)
    console.print(f"Metrics: {result.metrics_path}")


def render_doctor_summary(result: DoctorResult) -> None:
    """Render a concise Rich summary for doctor diagnostics."""
    console.print()
    console.print("[bold]VibeBench Doctor[/]")
    console.print(f"Project root: {result.project_root}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")
    status_style = {"passed": "green", "warning": "yellow", "failed": "red"}
    for check in result.checks:
        table.add_row(
            check.category,
            f"[{status_style[check.status]}]{check.status}[/]",
            check.message,
        )
    console.print(table)



def render_clean_summary(result: CleanResult) -> None:
    """Render a safe cleanup summary."""
    console.print()
    console.print("[bold]VibeBench clean[/]")
    console.print(f"Runs directory: {result.runs_dir}")
    console.print(f"Mode: {'dry-run' if result.dry_run else 'delete'}")
    console.print(f"Keep count: {result.keep}")
    console.print(f"Total valid runs: {result.total_valid_runs}")
    console.print(f"Preserved count: {result.preserved_count}")
    console.print(f"Cleanup candidates: {len(result.candidates)}")
    console.print(
        f"Approximate candidate size: "
        f"{format_bytes(result.total_candidate_size_bytes)}"
    )

    if not result.candidates:
        console.print("[green]Nothing to clean.[/]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Run", no_wrap=True)
    table.add_column("Size")
    table.add_column("Path")
    for candidate in result.candidates:
        table.add_row(
            candidate.run_id,
            format_bytes(candidate.size_bytes),
            str(candidate.path),
        )
    console.print(table)

    if result.dry_run:
        console.print(
            "[yellow]Dry run only. "
            "Re-run with --yes to delete these runs.[/]"
        )
    else:
        console.print(f"[green]Deleted {result.deleted_count} run(s).[/]")


def format_bytes(value: int) -> str:
    """Format a byte count for terminal output."""
    units = ["B", "KiB", "MiB", "GiB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"

def render_history_summary(result: HistoryResult) -> None:
    """Render a concise Rich table for recent run history."""
    console.print()
    console.print("[bold]VibeBench history[/]")
    console.print(f"Runs directory: {result.runs_dir}")

    if not result.runs:
        console.print(
            "[yellow]No VibeBench runs found. "
            "Run 'vibebench check' first.[/]"
        )
        return

    for warning in result.warnings:
        console.print(f"[yellow]Warning:[/] {warning}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Run", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Score")
    table.add_column("Risk", no_wrap=True)
    table.add_column("Files")
    table.add_column("Patch")
    table.add_column("Find")
    table.add_column("Artifacts")

    status_style = {"passed": "green", "failed": "red"}
    risk_style = {
        "low": "green",
        "medium": "yellow",
        "high": "magenta",
        "critical": "red",
    }
    for run in result.runs:
        table.add_row(
            run.run_id,
            f"[{status_style.get(run.overall_status, 'white')}]"
            f"{run.overall_status}[/]",
            str(run.score),
            f"[{risk_style.get(run.risk_level, 'white')}]{run.risk_level}[/]",
            str(run.changed_files),
            str(run.patch_lines),
            str(run.risk_findings_count),
            artifact_flags(run),
        )
    console.print(table)


def artifact_flags(run: HistoryRun) -> str:
    """Format generated artifact markers."""
    return " ".join(
        [
            f"report:{plain_yes_no(run.has_report)}",
            f"pr:{plain_yes_no(run.has_pr_comment)}",
            f"gh:{plain_yes_no(run.has_github_summary)}",
            f"cmp:{plain_yes_no(run.has_compare)}",
        ]
    )


def plain_yes_no(value: bool) -> str:
    """Format a boolean artifact marker."""
    return "yes" if value else "no"


def render_compare_summary(result: CompareResult) -> None:
    """Render a concise Rich summary for a run comparison."""
    verdict_style = {
        "improved": "green",
        "stable": "blue",
        "regressed": "red",
    }[result.verdict]

    console.print()
    console.print("[bold]VibeBench compare[/]")
    console.print(f"Base run: {result.base_run}")
    console.print(f"Current run: {result.current_run}")
    console.print(f"Verdict: [{verdict_style}]{result.verdict}[/]")
    console.print(f"Score delta: {format_signed(result.score_delta)}")
    console.print(f"Risk delta: {result.risk_delta}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Base")
    table.add_column("Current")
    table.add_column("Delta")
    for metric in result.metrics:
        table.add_row(metric.name, metric.base, metric.current, metric.delta)
    console.print(table)
    console.print(f"Recommendation: {result.recommendation}")
    console.print(f"Comparison: {result.output_path}")


def format_signed(value: int) -> str:
    """Format a signed integer for terminal output."""
    if value > 0:
        return f"+{value}"
    return str(value)


def render_findings(result: CheckRunResult) -> None:
    """Render concise risk findings."""
    visible_findings = [
        finding
        for finding in result.risk_findings
        if finding.severity in {"critical", "high", "warning"}
    ]
    if not visible_findings:
        return

    table = Table(show_header=True, header_style="bold", title="Risk Findings")
    table.add_column("Severity")
    table.add_column("Code")
    table.add_column("Message")
    table.add_column("Paths")

    severity_style = {"critical": "red", "high": "magenta", "warning": "yellow"}
    for finding in visible_findings:
        paths = ", ".join(finding.paths[:3]) if finding.paths else ""
        if len(finding.paths) > 3:
            paths = f"{paths}, +{len(finding.paths) - 3} more"
        table.add_row(
            f"[{severity_style[finding.severity]}]{finding.severity}[/]",
            finding.code,
            finding.message,
            paths,
        )

    console.print(table)


def main() -> None:
    """CLI entry point."""
    app()
