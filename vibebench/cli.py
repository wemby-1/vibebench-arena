"""Command-line interface for VibeBench Arena."""

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from vibebench import __version__
from vibebench.annotate import AnnotationResult, generate_annotations
from vibebench.artifacts import (
    ArtifactInventoryResult,
    ArtifactItem,
    collect_artifact_inventory,
    inventory_json,
)
from vibebench.badge import DEFAULT_BADGE_LABEL, BadgeResult, generate_badge
from vibebench.baseline import BaselineStatus, set_baseline, show_baseline
from vibebench.bundle import BundleResult, create_bundle
from vibebench.ci import CiResult, run_ci_pipeline
from vibebench.clean import CleanResult, clean_runs
from vibebench.compare import CompareResult, compare_runs
from vibebench.config import (
    ConfigError,
    EffectiveConfigResult,
    default_config_yaml,
    effective_config_payload,
    load_config,
    load_effective_config,
)
from vibebench.doctor import DoctorResult, run_doctor
from vibebench.explain import ExplainResult, generate_explanation
from vibebench.export import ExportResult, export_run
from vibebench.gate import GateResult, run_gate
from vibebench.gh_summary import generate_github_summary
from vibebench.history import HistoryResult, HistoryRun, get_history
from vibebench.latest import (
    LatestRunResult,
    artifact_label,
    available_artifacts,
    get_latest_run,
    latest_json,
    latest_paths_json,
    select_artifact,
)
from vibebench.manifest import (
    ManifestCheckResult,
    ManifestResult,
    check_manifest,
    generate_manifest,
)
from vibebench.paths import config_file
from vibebench.pr_comment import generate_pr_comment
from vibebench.report import (
    ReportError,
    generate_report,
    load_metrics,
    recommendation_for,
)
from vibebench.runner import CheckRunResult, run_checks
from vibebench.status_block import (
    DEFAULT_STATUS_TITLE,
    ReadmeStatusBlockResult,
    StatusBlockResult,
    generate_status_block,
    update_readme_status_block,
)
from vibebench.trend import (
    TrendResult,
    analyze_trend,
    trend_json,
    write_trend_json,
    write_trend_summary,
)

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

WORKFLOW_RELATIVE_PATH = Path(".github") / "workflows" / "vibebench.yml"

DEFAULT_WORKFLOW = """name: VibeBench

on:
  push:
  pull_request:

jobs:
  vibebench:
    runs-on: ubuntu-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v5

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.11"

      - name: Upgrade pip
        run: python -m pip install --upgrade pip

      - name: Install project and VibeBench
        run: |
          python -m pip install -e ".[dev]"
          python -m pip install git+https://github.com/wemby-1/vibebench-arena.git@main

      - name: Lint
        run: python -m ruff check .

      - name: Test
        run: python -m pytest -q

      - name: Run VibeBench CI pipeline
        run: python -m vibebench ci

      - name: Upload VibeBench artifacts
        if: always()
        uses: actions/upload-artifact@v7
        with:
          name: vibebench-runs
          path: .vibebench/runs
          if-no-files-found: ignore
"""


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
            help="Overwrite existing generated files.",
        ),
    ] = False,
    no_workflow: Annotated[
        bool,
        typer.Option("--no-workflow", help="Create only .vibebench/config.yaml."),
    ] = False,
    workflow_only: Annotated[
        bool,
        typer.Option(
            "--workflow-only",
            help="Create only the GitHub Actions workflow.",
        ),
    ] = False,
) -> None:
    """Bootstrap VibeBench config and GitHub Actions workflow."""
    if no_workflow and workflow_only:
        console.print(
            "[red]--no-workflow and --workflow-only cannot be used together.[/]"
        )
        raise typer.Exit(code=1)

    root = project_root.resolve()
    created: list[Path] = []
    skipped: list[Path] = []

    if not workflow_only:
        config_target = config_file(root)
        write_init_file(
            config_target,
            default_config_yaml(),
            force=force,
            created=created,
            skipped=skipped,
        )

    if not no_workflow:
        workflow_target = root / WORKFLOW_RELATIVE_PATH
        write_init_file(
            workflow_target,
            DEFAULT_WORKFLOW,
            force=force,
            created=created,
            skipped=skipped,
        )

    render_init_summary(created, skipped)


def write_init_file(
    target: Path,
    content: str,
    *,
    force: bool,
    created: list[Path],
    skipped: list[Path],
) -> None:
    """Write an init file unless it exists and force is false."""
    if target.exists() and not force:
        skipped.append(target)
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    created.append(target)


def render_init_summary(created: list[Path], skipped: list[Path]) -> None:
    """Render init result and next steps."""
    table = Table(title="VibeBench init")
    table.add_column("Status")
    table.add_column("Path")
    for path in created:
        table.add_row("created", str(path))
    for path in skipped:
        table.add_row("skipped", str(path))
    if not created and not skipped:
        table.add_row("none", "No files selected")
    console.print(table)
    console.print("Next steps:")
    console.print("  python -m vibebench doctor")
    console.print("  python -m vibebench check")
    console.print("  python -m vibebench gate --write-gate-summary")


@app.command("config")
def config_command(
    project_root: ProjectRootOption = Path("."),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print effective configuration as JSON."),
    ] = False,
    validate_only: Annotated[
        bool,
        typer.Option("--validate", help="Only validate config and print a result."),
    ] = False,
    show_source: Annotated[
        bool,
        typer.Option("--show-source", help="Show config file/default sources."),
    ] = False,
) -> None:
    """Inspect and validate the effective VibeBench configuration."""
    root = project_root.resolve()
    target = config_file(root)
    try:
        result = load_effective_config(target)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if validate_only:
        source = result.config_path if result.config_exists else "built-in defaults"
        console.print(f"[green]VibeBench config is valid.[/] Source: {source}")
        return

    payload = effective_config_payload(result)
    if show_source:
        payload["sources"] = result.sources

    if as_json:
        console.print(json.dumps(payload, indent=2, sort_keys=True))
        return

    render_config_summary(result, show_source=show_source)


def render_config_summary(
    result: EffectiveConfigResult,
    *,
    show_source: bool,
) -> None:
    """Render the effective VibeBench config as Rich tables."""
    source = str(result.config_path) if result.config_exists else "built-in defaults"
    console.print(f"[bold]VibeBench config[/] ({source})")

    payload = effective_config_payload(result)
    for section_name in ["project", "checks", "gate", "risk"]:
        table = Table(title=section_name)
        table.add_column("Key")
        table.add_column("Value")
        if show_source:
            table.add_column("Source")
        section = payload[section_name]
        for key, value in section.items():
            row = [key, format_config_value(value)]
            if show_source:
                row.append(result.sources[section_name])
            table.add_row(*row)
        console.print(table)


def format_config_value(value: object) -> str:
    """Format config values for terminal display."""
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


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
def explain(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to explain.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Custom Markdown output path."),
    ] = None,
    no_write: Annotated[
        bool,
        typer.Option(
            "--no-write",
            help="Print explanation without writing explain.md.",
        ),
    ] = False,
) -> None:
    """Explain a VibeBench run in human-readable Markdown."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()

    try:
        result = generate_explanation(
            root,
            selected_run_dir,
            selected_output,
            write=not no_write,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_explain_summary(result, write=not no_write)


@app.command()
def bundle(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to bundle.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Custom zip output path."),
    ] = None,
    include_report_assets: Annotated[
        bool,
        typer.Option(
            "--include-report-assets",
            help="Include the whole report directory recursively.",
        ),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Fail if any standard artifact is missing."),
    ] = False,
) -> None:
    """Package a VibeBench run's artifacts into a zip file."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()

    try:
        result = create_bundle(
            root,
            selected_run_dir,
            selected_output,
            include_report_assets=include_report_assets,
            strict=strict,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_bundle_summary(result)


@app.command()
def badge(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to badge.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write badge output to this file."),
    ] = None,
    badge_format: Annotated[
        str,
        typer.Option("--format", help="Badge format: json, markdown, or url."),
    ] = "json",
    label: Annotated[
        str,
        typer.Option("--label", help="Badge label text."),
    ] = DEFAULT_BADGE_LABEL,
) -> None:
    """Generate a Shields.io-compatible badge artifact."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()

    try:
        result = generate_badge(
            root,
            selected_run_dir,
            selected_output,
            label=label,
            badge_format=badge_format,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_badge_summary(result)


@app.command("status-block")
def status_block(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to summarize.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write status block to this file."),
    ] = None,
    readme: Annotated[
        list[Path] | None,
        typer.Option(
            "--readme",
            help="README file containing VibeBench status markers.",
        ),
    ] = None,
    write_readme: Annotated[
        bool,
        typer.Option("--write-readme", help="Update README content between markers."),
    ] = False,
    check_readme: Annotated[
        bool,
        typer.Option("--check-readme", help="Check README marker content is current."),
    ] = False,
    title: Annotated[
        str,
        typer.Option("--title", help="Markdown heading text."),
    ] = DEFAULT_STATUS_TITLE,
    include_badge: Annotated[
        bool,
        typer.Option("--include-badge/--no-include-badge"),
    ] = True,
    include_artifacts: Annotated[
        bool,
        typer.Option("--include-artifacts/--no-include-artifacts"),
    ] = True,
) -> None:
    """Generate or update a README status block."""
    if write_readme and check_readme:
        console.print(
            "[red]--write-readme and --check-readme cannot be used together.[/]"
        )
        raise typer.Exit(code=1)
    readme_paths = readme or []
    if (write_readme or check_readme) and not readme_paths:
        console.print(
            "[red]--readme is required with --write-readme or --check-readme.[/]"
        )
        raise typer.Exit(code=1)

    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = run_dir if run_dir.is_absolute() else root / run_dir
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()

    try:
        result = generate_status_block(
            root,
            selected_run_dir,
            selected_output,
            title=title,
            include_badge=include_badge,
            include_artifacts=include_artifacts,
        )
        readme_results = update_status_block_readmes(
            root,
            readme_paths,
            result.content,
            write=write_readme,
            check=check_readme,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_status_block_summary(result)
    if readme_results:
        render_status_block_readme_summary(readme_results, check=check_readme)
        if check_readme and not all(item.current for item in readme_results):
            raise typer.Exit(code=1)

@app.command("trend")
def trend_command(
    project_root: ProjectRootOption = Path("."),
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum number of recent valid runs to show."),
    ] = 10,
    runs_dir: Annotated[
        Path | None,
        typer.Option("--runs-dir", help="Directory containing VibeBench run dirs."),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print trend summary as JSON."),
    ] = False,
    write_summary: Annotated[
        bool,
        typer.Option("--write-summary", help="Write trend.md Markdown summary."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write trend summary Markdown to this path."),
    ] = None,
    write_json: Annotated[
        bool,
        typer.Option("--write-json", help="Write trend.json machine-readable data."),
    ] = False,
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Write trend JSON to this path."),
    ] = None,
) -> None:
    """Show quality trend across recent VibeBench runs."""
    root = project_root.resolve()
    selected_runs_dir = None
    if runs_dir:
        selected_runs_dir = (
            runs_dir if runs_dir.is_absolute() else root / runs_dir
        ).resolve()
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()
    selected_json_output = None
    if json_output:
        selected_json_output = (
            json_output if json_output.is_absolute() else root / json_output
        ).resolve()

    try:
        result = analyze_trend(root, selected_runs_dir, limit=limit)
        summary_path = (
            write_trend_summary(result, selected_output) if write_summary else None
        )
        json_path = (
            write_trend_json(result, selected_json_output) if write_json else None
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(json.dumps(trend_json(result), indent=2))
        return

    render_trend_summary(result)
    if summary_path is not None:
        console.print(f"Trend summary: {summary_path}")
    if json_path is not None:
        console.print(f"Trend JSON: {json_path}")

@app.command("latest")
def latest_command(
    project_root: ProjectRootOption = Path("."),
    runs_dir: Annotated[
        Path | None,
        typer.Option("--runs-dir", help="Directory containing VibeBench run dirs."),
    ] = None,
    artifact: Annotated[
        str | None,
        typer.Option("--artifact", help="Show one known artifact by alias."),
    ] = None,
    path_only: Annotated[
        bool,
        typer.Option("--path-only", help="Print only the selected artifact path."),
    ] = False,
    all_paths: Annotated[
        bool,
        typer.Option("--all-paths", help="Print all available artifact paths."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print latest run details as JSON."),
    ] = False,
) -> None:
    """Locate the latest valid VibeBench run and artifacts."""
    root = project_root.resolve()
    selected_runs_dir = None
    if runs_dir:
        selected_runs_dir = (
            runs_dir if runs_dir.is_absolute() else root / runs_dir
        ).resolve()

    if all_paths and artifact is not None:
        console.print("[red]--all-paths cannot be combined with --artifact.[/]")
        raise typer.Exit(code=1)
    if all_paths and path_only:
        console.print("[red]--all-paths cannot be combined with --path-only.[/]")
        raise typer.Exit(code=1)
    if path_only and artifact is None:
        console.print("[red]--path-only requires --artifact NAME.[/]")
        raise typer.Exit(code=1)

    try:
        result = get_latest_run(root, selected_runs_dir)
        selected_artifact = select_artifact(result, artifact) if artifact else None
        if path_only:
            if selected_artifact is None:
                raise ReportError("--path-only requires --artifact NAME.")
            if not selected_artifact.available:
                raise ReportError(
                    f"Artifact '{artifact}' is unavailable for run {result.run_id}."
                )
            print(selected_artifact.display_path.as_posix())
            return
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if all_paths:
        if as_json:
            print(json.dumps(latest_paths_json(result), indent=2))
            return
        render_latest_paths(result)
        return

    if as_json:
        print(json.dumps(latest_json(result, selected_artifact), indent=2))
        return

    render_latest_summary(result, selected_artifact)

@app.command("manifest")
def manifest_command(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to manifest.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write manifest output to this file."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Validate the manifest can be read."),
    ] = False,
    check: Annotated[
        bool,
        typer.Option("--check", help="Check existing manifest consistency."),
    ] = False,
) -> None:
    """Write or check a machine-readable manifest for a VibeBench run."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()

    try:
        if check:
            check_result = check_manifest(
                root,
                selected_run_dir,
                selected_output,
                strict=strict,
            )
            render_manifest_check_summary(check_result)
            if not check_result.passed:
                raise typer.Exit(code=1)
            return

        result = generate_manifest(
            root,
            selected_run_dir,
            selected_output,
            strict=strict,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_manifest_summary(result)

@app.command("artifacts")
def artifacts_command(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to inspect.",
        ),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print artifact inventory as JSON."),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Fail if any known artifact is missing."),
    ] = False,
    only_available: Annotated[
        bool,
        typer.Option("--only-available", help="Show only available artifacts."),
    ] = False,
) -> None:
    """List known artifacts for a VibeBench run."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()

    try:
        result = collect_artifact_inventory(
            root,
            selected_run_dir,
            only_available=only_available,
            strict=strict,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(json.dumps(inventory_json(result), indent=2))
        return

    render_artifacts_summary(result)

@app.command("export")
def export_command(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to export.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write export output to this file."),
    ] = None,
    export_format: Annotated[
        str,
        typer.Option("--format", help="Export format: json or markdown."),
    ] = "json",
    pretty: Annotated[
        bool,
        typer.Option("--pretty", help="Pretty-print JSON output."),
    ] = False,
) -> None:
    """Export a machine-readable VibeBench run summary."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()
    selected_output = None
    if output:
        selected_output = (output if output.is_absolute() else root / output).resolve()

    try:
        result = export_run(
            root,
            selected_run_dir,
            selected_output,
            export_format=export_format,
            pretty=pretty,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_export_summary(result)


@app.command()
def annotate(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Specific .vibebench/runs/<timestamp> directory to annotate.",
        ),
    ] = None,
    min_severity: Annotated[
        str,
        typer.Option("--min-severity", help="Minimum finding severity to emit."),
    ] = "warning",
    github_actions: Annotated[
        bool,
        typer.Option(
            "--github-actions/--no-github-actions",
            help="Emit GitHub workflow commands or plain text.",
        ),
    ] = True,
) -> None:
    """Emit GitHub Actions annotations for a VibeBench run."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()

    try:
        result = generate_annotations(
            root,
            selected_run_dir,
            min_severity=min_severity,
            github_actions=github_actions,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_annotation_summary(result)


@app.command("ci")
def ci_command(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            help="Existing .vibebench/runs/<timestamp> directory to process.",
        ),
    ] = None,
    skip_report: Annotated[
        bool,
        typer.Option("--skip-report", help="Skip HTML report generation."),
    ] = False,
    skip_pr_comment: Annotated[
        bool,
        typer.Option("--skip-pr-comment", help="Skip PR comment generation."),
    ] = False,
    skip_explain: Annotated[
        bool,
        typer.Option("--skip-explain", help="Skip run explanation generation."),
    ] = False,
    skip_bundle: Annotated[
        bool,
        typer.Option("--skip-bundle", help="Skip artifact bundle generation."),
    ] = False,
    skip_export: Annotated[
        bool,
        typer.Option("--skip-export", help="Skip machine-readable export generation."),
    ] = False,
    skip_badge: Annotated[
        bool,
        typer.Option("--skip-badge", help="Skip badge artifact generation."),
    ] = False,
    skip_status_block: Annotated[
        bool,
        typer.Option(
            "--skip-status-block",
            help="Skip README status block generation.",
        ),
    ] = False,
    skip_trend: Annotated[
        bool,
        typer.Option("--skip-trend", help="Skip trend summary generation."),
    ] = False,
    skip_manifest: Annotated[
        bool,
        typer.Option("--skip-manifest", help="Skip run manifest generation."),
    ] = False,
    skip_annotate: Annotated[
        bool,
        typer.Option("--skip-annotate", help="Skip GitHub annotation output."),
    ] = False,
    skip_gh_summary: Annotated[
        bool,
        typer.Option("--skip-gh-summary", help="Skip GitHub summary generation."),
    ] = False,
    bundle_include_report_assets: Annotated[
        bool,
        typer.Option(
            "--bundle-include-report-assets",
            help="Include report assets recursively in the bundle.",
        ),
    ] = False,
    bundle_strict: Annotated[
        bool,
        typer.Option("--bundle-strict", help="Fail bundle on missing artifacts."),
    ] = False,
    min_score: Annotated[
        int | None,
        typer.Option("--min-score", help="Override minimum acceptable VibeScore."),
    ] = None,
    max_risk: Annotated[
        str | None,
        typer.Option("--max-risk", help="Override maximum acceptable risk level."),
    ] = None,
    allow_findings: Annotated[
        int | None,
        typer.Option("--allow-findings", help="Override allowed finding count."),
    ] = None,
    require_status_passed: Annotated[
        bool | None,
        typer.Option("--require-status-passed/--no-require-status-passed"),
    ] = None,
) -> None:
    """Run the full VibeBench CI pipeline."""
    root = project_root.resolve()
    selected_run_dir = None
    if run_dir:
        selected_run_dir = (
            run_dir if run_dir.is_absolute() else root / run_dir
        ).resolve()

    try:
        result = run_ci_pipeline(
            root,
            run_dir=selected_run_dir,
            skip_report=skip_report,
            skip_pr_comment=skip_pr_comment,
            skip_explain=skip_explain,
            skip_bundle=skip_bundle,
            skip_export=skip_export,
            skip_badge=skip_badge,
            skip_status_block=skip_status_block,
            skip_trend=skip_trend,
            skip_manifest=skip_manifest,
            skip_annotate=skip_annotate,
            skip_gh_summary=skip_gh_summary,
            bundle_include_report_assets=bundle_include_report_assets,
            bundle_strict=bundle_strict,
            min_score=min_score,
            max_risk=max_risk,
            allow_findings=allow_findings,
            require_status_passed=require_status_passed,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_ci_summary(result)
    if not result.passed:
        raise typer.Exit(code=1)


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
def gate(
    project_root: ProjectRootOption = Path("."),
    run_dir: Annotated[
        Path | None,
        typer.Option("--run-dir", help="Specific run directory to evaluate."),
    ] = None,
    min_score: Annotated[
        int | None,
        typer.Option("--min-score", help="Override minimum acceptable VibeScore."),
    ] = None,
    max_risk: Annotated[
        str | None,
        typer.Option("--max-risk", help="Override maximum acceptable risk level."),
    ] = None,
    allow_findings: Annotated[
        int | None,
        typer.Option("--allow-findings", help="Override allowed risk finding count."),
    ] = None,
    require_status_passed: Annotated[
        bool | None,
        typer.Option("--require-status-passed/--no-require-status-passed"),
    ] = None,
    baseline: Annotated[
        bool,
        typer.Option("--baseline", help="Fail on regression against saved baseline."),
    ] = False,
    write_gate_summary: Annotated[
        bool,
        typer.Option("--write-gate-summary", help="Write gate-summary.md."),
    ] = False,
) -> None:
    """Evaluate a run against an explicit quality gate."""
    root = project_root.resolve()
    try:
        result = run_gate(
            root,
            run_dir=run_dir,
            min_score=min_score,
            max_risk=max_risk,
            allow_findings=allow_findings,
            require_status_passed=require_status_passed,
            use_baseline=baseline,
            write_gate_summary=write_gate_summary,
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_gate_summary(result)
    if not result.passed:
        raise typer.Exit(code=1)


@app.command()
def baseline(
    project_root: ProjectRootOption = Path("."),
    set_run: Annotated[
        str | None,
        typer.Option(
            "--set",
            help="Save baseline to 'latest' or a specific run id.",
        ),
    ] = None,
    runs_dir: Annotated[
        Path | None,
        typer.Option("--runs-dir", help="Directory containing VibeBench runs."),
    ] = None,
) -> None:
    """Show or set the project baseline run."""
    root = project_root.resolve()
    try:
        result = (
            set_baseline(root, set_run, runs_dir=runs_dir)
            if set_run is not None
            else show_baseline(root)
        )
    except ReportError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    render_baseline_summary(result)
    if result.metadata is not None and not result.is_valid:
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
    baseline: Annotated[
        bool,
        typer.Option(
            "--baseline",
            help="Compare the saved baseline against the latest or current run.",
        ),
    ] = False,
) -> None:
    """Compare VibeBench runs."""
    root = project_root.resolve()
    try:
        result = compare_runs(
            root,
            current_run=current_run,
            base_run=base_run,
            use_baseline=baseline,
        )
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


def render_status_block_summary(result: StatusBlockResult) -> None:
    """Render a concise status block command summary."""
    console.print("Status block generated.")
    console.print(f"Run directory: {result.run_dir}")
    console.print(f"Output path: {result.output_path}")
    console.print(f"Title: {result.title}")


def update_status_block_readmes(
    project_root: Path,
    readme_paths: list[Path],
    status_content: str,
    *,
    write: bool,
    check: bool,
) -> list[ReadmeStatusBlockResult]:
    """Update or check requested README status blocks."""
    if not write and not check:
        return []

    results = []
    for readme_path in readme_paths:
        selected_path = (
            readme_path if readme_path.is_absolute() else project_root / readme_path
        ).resolve()
        results.append(
            update_readme_status_block(
                selected_path,
                status_content,
                write=write,
            )
        )
    return results


def render_status_block_readme_summary(
    results: list[ReadmeStatusBlockResult],
    *,
    check: bool,
) -> None:
    """Render README update/check results."""
    table = Table(title="README status block")
    table.add_column("README")
    table.add_column("Status")
    for result in results:
        if check:
            status = "current" if result.current else "stale"
        else:
            status = "updated" if result.changed else "already current"
        table.add_row(str(result.readme_path), status)
    console.print(table)


def render_trend_summary(result: TrendResult) -> None:
    """Render trend runs and aggregate summary."""
    console.print(f"Runs directory: {result.runs_dir}")
    if result.skipped_runs:
        for warning in result.skipped_runs:
            console.print(f"[yellow]{warning}[/]")
    if not result.runs:
        console.print("No valid VibeBench runs found.")
        return

    table = Table(title="VibeBench trend")
    table.add_column("Run")
    table.add_column("Status")
    table.add_column("Score", justify="right")
    table.add_column("Risk")
    table.add_column("Findings", justify="right")
    table.add_column("Files", justify="right")
    table.add_column("Patch", justify="right")
    for run in result.runs:
        table.add_row(
            run.run_id,
            run.overall_status,
            str(run.score),
            run.risk_level,
            str(run.risk_findings_count),
            str(run.changed_files),
            str(run.patch_lines),
        )
    console.print(table)

    summary = result.summary
    summary_table = Table(title="Trend summary")
    summary_table.add_column("Field")
    summary_table.add_column("Value")
    summary_table.add_row("Valid runs", str(summary.valid_run_count))
    summary_table.add_row("Pass rate", f"{summary.pass_rate * 100:.1f}%")
    summary_table.add_row("Latest score", optional_text(summary.latest_score))
    summary_table.add_row("Oldest score", optional_text(summary.oldest_score))
    summary_table.add_row("Score delta", optional_delta(summary.score_delta))
    summary_table.add_row("Best score", optional_text(summary.best_score))
    summary_table.add_row("Worst score", optional_text(summary.worst_score))
    summary_table.add_row("Highest risk", optional_text(summary.highest_risk_level))
    summary_table.add_row(
        "Latest findings", optional_text(summary.latest_finding_count)
    )
    summary_table.add_row(
        "Oldest findings", optional_text(summary.oldest_finding_count)
    )
    summary_table.add_row(
        "Finding delta", optional_delta(summary.finding_count_delta)
    )
    summary_table.add_row("Verdict", summary.verdict)
    console.print(summary_table)
    console.print(summary.message)


def optional_text(value: object) -> str:
    """Render an optional summary value."""
    return "n/a" if value is None else str(value)


def optional_delta(value: int | None) -> str:
    """Render an optional signed delta."""
    if value is None:
        return "n/a"
    if value > 0:
        return f"+{value}"
    return str(value)


def render_latest_paths(result: LatestRunResult) -> None:
    """Render available artifact paths for copy/paste use."""
    for item in available_artifacts(result):
        console.print(f"{artifact_label(item)}: {item.display_path.as_posix()}")


def render_latest_summary(
    result: LatestRunResult,
    selected_artifact: ArtifactItem | None,
) -> None:
    """Render latest run details."""
    console.print("\n[bold]VibeBench latest[/]")
    console.print(f"Run id: {result.run_id}")
    console.print(f"Run directory: {result.run_dir}")
    console.print(f"Status: {result.status}")
    console.print(f"VibeScore: {result.score}")
    console.print(f"Risk: {result.risk}")
    if result.created_at:
        console.print(f"Created at: {result.created_at}")
    if result.skipped_runs:
        console.print(f"Skipped corrupt runs: {len(result.skipped_runs)}")

    table = Table(title="Artifacts")
    table.add_column("Artifact")
    table.add_column("Path")
    table.add_column("Availability")
    table.add_column("Size")
    artifacts = (
        [selected_artifact]
        if selected_artifact is not None
        else result.inventory.artifacts
    )
    for item in artifacts:
        availability = "available" if item.available else "missing"
        size = (
            artifact_size_text(item.size_bytes)
            if item.size_bytes is not None
            else ""
        )
        table.add_row(item.name, item.display_path.as_posix(), availability, size)
    console.print(table)


def render_manifest_summary(result: ManifestResult) -> None:
    """Render a concise manifest command summary."""
    console.print("Manifest written.")
    console.print(f"Run id: {result.run_id}")
    console.print(f"Run directory: {result.run_dir}")
    console.print(f"Output path: {result.output_path}")
    console.print(f"Status: {result.payload.get('status', 'unknown')}")
    console.print(f"Score: {result.payload.get('score', 0)}")
    console.print(f"Available artifacts: {result.available_artifact_count}")


def render_manifest_check_summary(result: ManifestCheckResult) -> None:
    """Render a concise manifest consistency check summary."""
    if result.passed:
        console.print(f"Manifest is consistent: {result.manifest_path}")
        return

    console.print("[red]Manifest drift detected:[/]")
    for difference in result.differences:
        console.print(f"- {difference}")


def render_artifacts_summary(result: ArtifactInventoryResult) -> None:
    """Render an artifact inventory table."""
    table = Table(title="VibeBench artifacts")
    table.add_column("Artifact")
    table.add_column("Path")
    table.add_column("Availability")
    table.add_column("Size")
    for item in result.artifacts:
        availability = "available" if item.available else "missing"
        size = (
            artifact_size_text(item.size_bytes)
            if item.size_bytes is not None
            else ""
        )
        table.add_row(
            item.name,
            item.display_path.as_posix(),
            availability,
            size,
        )
    console.print(f"Run directory: {result.run_dir}")
    console.print(table)


def artifact_size_text(size_bytes: int) -> str:
    """Format an artifact byte count for terminal output."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    size_kib = size_bytes / 1024
    if size_kib < 1024:
        return f"{size_kib:.1f} KiB"
    return f"{size_kib / 1024:.1f} MiB"


def render_badge_summary(result: BadgeResult) -> None:
    """Render a concise badge command summary."""
    console.print("Badge generated.")
    console.print(f"Run directory: {result.run_dir}")
    console.print(f"Output path: {result.output_path}")
    console.print(
        "Badge: "
        f"{result.label} | {result.message} | {result.color} | {result.format}"
    )


def render_export_summary(result: ExportResult) -> None:
    """Render export output or a concise write summary."""
    if result.output_path is None:
        print(result.content, end="")
        return
    console.print("Export written.")
    console.print(f"Run directory: {result.run_dir}")
    console.print(f"Output path: {result.output_path}")


def render_annotation_summary(result: AnnotationResult) -> None:
    """Render annotation output."""
    console.print(result.output, markup=False)


def render_ci_summary(result: CiResult) -> None:
    """Render a concise CI pipeline summary."""
    console.print()
    console.print("[bold]VibeBench CI[/]")
    if result.run_dir is not None:
        console.print(f"Run directory: {result.run_dir}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Step")
    table.add_column("Status")
    table.add_column("Exit")
    table.add_column("Artifact")
    table.add_column("Message")
    status_style = {"passed": "green", "failed": "red", "skipped": "yellow"}
    for step in result.steps:
        table.add_row(
            step.name,
            f"[{status_style[step.status]}]{step.status}[/]",
            str(step.exit_code),
            str(step.artifact_path) if step.artifact_path else "",
            step.message,
        )
    console.print(table)

    verdict = "passed" if result.passed else "failed"
    style = "green" if result.passed else "red"
    console.print(f"Final CI verdict: [{style}]{verdict}[/]")


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



def render_gate_summary(result: GateResult) -> None:
    """Render a concise quality gate summary."""
    status_style = "green" if result.passed else "red"
    console.print()
    console.print("[bold]VibeBench gate[/]")
    console.print(f"Run directory: {result.run_dir}")
    gate_status = "passed" if result.passed else "failed"
    console.print(f"Result: [{status_style}]{gate_status}[/]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Actual")
    table.add_column("Gate")
    table.add_row("Status", result.snapshot.overall_status, "passed")
    table.add_row(
        "Score",
        str(result.snapshot.score),
        f">= {result.thresholds.min_score}",
    )
    table.add_row(
        "Risk",
        result.snapshot.risk_level,
        f"<= {result.thresholds.max_risk}",
    )
    table.add_row(
        "Findings",
        str(result.snapshot.risk_findings_count),
        f"<= {result.thresholds.allow_findings}",
    )
    console.print(table)

    if result.baseline_used and result.baseline_snapshot is not None:
        baseline = result.baseline_snapshot
        console.print(
            "Baseline: "
            f"score {baseline.score}, risk {baseline.risk_level}, "
            f"findings {baseline.risk_findings_count}"
        )

    if result.reasons:
        reason_table = Table(
            show_header=True,
            header_style="bold",
            title="Gate Failures",
        )
        reason_table.add_column("Reason")
        for reason in result.reasons:
            reason_table.add_row(reason)
        console.print(reason_table)

    if result.summary_path is not None:
        console.print(f"Gate summary: {result.summary_path}")


def render_explain_summary(result: ExplainResult, *, write: bool) -> None:
    """Render a concise explanation command summary."""
    console.print()
    console.print("[bold]VibeBench explain[/]")
    console.print(f"Run directory: {result.run_dir}")
    if write and result.output_path is not None:
        console.print(f"Explanation: {result.output_path}")
    else:
        console.print("[yellow]Explanation was not written (--no-write).[/]")
        console.print()
        console.print(result.markdown)
    console.print(f"Recommendation: {result.recommendation}")


def render_bundle_summary(result: BundleResult) -> None:
    """Render a concise bundle command summary."""
    console.print()
    console.print("[bold]VibeBench bundle[/]")
    console.print(f"Run: {result.run_id}")
    console.print(f"Output: {result.output_path}")
    console.print(f"Size: {format_bytes(result.size_bytes)}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Included files")
    if result.included_files:
        for relative_path in result.included_files:
            table.add_row(str(relative_path))
    else:
        table.add_row("none")
    console.print(table)

    skipped_table = Table(show_header=True, header_style="bold")
    skipped_table.add_column("Skipped missing optional files")
    if result.skipped_files:
        for relative_path in result.skipped_files:
            skipped_table.add_row(str(relative_path))
    else:
        skipped_table.add_row("none")
    console.print(skipped_table)


def render_baseline_summary(result: BaselineStatus) -> None:
    """Render saved baseline metadata."""
    console.print()
    console.print("[bold]VibeBench baseline[/]")
    console.print(f"Baseline file: {result.baseline_path}")

    if result.metadata is None:
        console.print(f"[yellow]{result.message}[/]")
        return

    status_style = "green" if result.is_valid else "red"
    console.print(f"Status: [{status_style}]{result.message}[/]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    metadata = result.metadata
    table.add_row("Run", metadata.run_id)
    table.add_row("Run path", metadata.run_path)
    table.add_row("Metrics", metadata.metrics_path)
    table.add_row("Project", metadata.project or "")
    table.add_row("Created at", metadata.created_at or "")
    table.add_row("Overall status", metadata.status)
    table.add_row("Score", str(metadata.score))
    table.add_row("Risk", metadata.risk_level)
    table.add_row("Saved at", metadata.saved_at)
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
