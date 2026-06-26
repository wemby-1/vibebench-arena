"""Command-line interface for VibeBench Arena."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from vibebench import __version__
from vibebench.config import default_config_yaml
from vibebench.paths import config_file

app = typer.Typer(
    help="Codex-first quality gate for vibe coding projects.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Show the installed VibeBench version."""
    console.print(f"VibeBench Arena {__version__}")


@app.command()
def init(
    project_root: Annotated[
        Path,
        typer.Option(
            "--project-root",
            "-C",
            help="Project directory where .vibebench/config.yaml should be created.",
        ),
    ] = Path("."),
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


def main() -> None:
    """CLI entry point."""
    app()
