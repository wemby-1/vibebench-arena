"""Command-line interface for VibeBench Arena."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from vibebench import __version__
from vibebench.config import ConfigError, default_config_yaml, load_config
from vibebench.paths import config_file
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
