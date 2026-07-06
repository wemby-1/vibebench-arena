"""Zip bundle generation for VibeBench run artifacts."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from vibebench.explain import find_latest_valid_run
from vibebench.report import ReportError, load_metrics

BUNDLE_FILENAME = "vibebench-bundle.zip"

STANDARD_ARTIFACTS = [
    Path("metrics.json"),
    Path("check.log"),
    Path("metrics-check.json"),
    Path("metrics-check.md"),
    Path("metrics-diff.json"),
    Path("metrics-diff.md"),
    Path("manifest.json"),
    Path("config-check.json"),
    Path("config-check.md"),
    Path("package-check.json"),
    Path("package-check.md"),
    Path("ci-plan.json"),
    Path("ci-plan.md"),
    Path("release-check.json"),
    Path("release-check.md"),
    Path("report") / "index.html",
    Path("pr-comment.md"),
    Path("github-step-summary.md"),
    Path("gate-summary.md"),
    Path("explain.md"),
    Path("export.json"),
    Path("badge.json"),
    Path("badge.md"),
    Path("badge-url.txt"),
    Path("status-block.md"),
    Path("trend.md"),
    Path("trend.json"),
    Path("run-index.json"),
    Path("run-index.md"),
    Path("compare.json"),
    Path("compare.md"),
    Path("regression-check.json"),
    Path("regression-check.md"),
    Path("evidence-room") / "index.html",
    Path("evidence-room") / "review-hub.html",
    Path("evidence-room") / "reviewer-guide.md",
    Path("evidence-room") / "trust-center.html",
    Path("evidence-room") / "trust-center.md",
    Path("evidence-room") / "security-questionnaire.html",
    Path("evidence-room") / "security-questionnaire.md",
    Path("evidence-room") / "review-scorecard.html",
    Path("evidence-room") / "review-scorecard.md",
    Path("evidence-room") / "review-scorecard.json",
    Path("evidence-room") / "share-check.json",
    Path("evidence-room") / "share-check.md",
    Path("evidence-room") / "evidence-room.html",
    Path("evidence-room") / "evidence-room.json",
    Path("evidence-room") / "evidence-room.md",
    Path("evidence-room") / "evidence-room.zip",
]


@dataclass(frozen=True)
class BundleResult:
    """Result of creating a run artifact bundle."""

    run_dir: Path
    run_id: str
    output_path: Path
    included_files: list[Path]
    skipped_files: list[Path]
    size_bytes: int


def create_bundle(
    project_root: Path,
    run_dir: Path | None = None,
    output_path: Path | None = None,
    *,
    include_report_assets: bool = False,
    strict: bool = False,
) -> BundleResult:
    """Create a zip bundle for a VibeBench run."""
    selected_run_dir = (run_dir or find_latest_valid_run(project_root)).resolve()
    validate_run_dir(selected_run_dir)
    validate_metrics(selected_run_dir)

    selected_output = (
        output_path.resolve() if output_path else selected_run_dir / BUNDLE_FILENAME
    )
    validate_output_path(selected_output)

    included_files, skipped_files = collect_artifacts(
        selected_run_dir,
        selected_output,
        include_report_assets=include_report_assets,
    )

    missing_required = [path for path in skipped_files if path == Path("metrics.json")]
    if missing_required:
        raise ReportError(f"No metrics.json found in {selected_run_dir}.")
    if strict and skipped_files:
        missing = ", ".join(str(path) for path in skipped_files)
        raise ReportError(f"Missing expected artifact(s): {missing}")

    selected_output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        selected_output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for relative_path in included_files:
            source_path = selected_run_dir / relative_path
            archive.write(source_path, arcname=relative_path.as_posix())

    return BundleResult(
        run_dir=selected_run_dir,
        run_id=selected_run_dir.name,
        output_path=selected_output,
        included_files=included_files,
        skipped_files=skipped_files,
        size_bytes=selected_output.stat().st_size,
    )


def validate_run_dir(run_dir: Path) -> None:
    """Validate that a run directory is usable."""
    if not run_dir.exists():
        raise ReportError(f"Run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise ReportError(f"Run path is not a directory: {run_dir}")


def validate_metrics(run_dir: Path) -> None:
    """Validate that metrics.json exists and can be parsed."""
    try:
        load_metrics(run_dir)
    except json.JSONDecodeError as exc:
        raise ReportError(f"metrics.json in {run_dir} is not valid JSON.") from exc


def validate_output_path(output_path: Path) -> None:
    """Validate a requested output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"Output path is a directory: {output_path}")
    if not output_path.parent.exists():
        message = f"Output parent directory does not exist: {output_path.parent}"
        raise ReportError(message)


def collect_artifacts(
    run_dir: Path,
    output_path: Path,
    *,
    include_report_assets: bool,
) -> tuple[list[Path], list[Path]]:
    """Collect safe artifact paths relative to the run directory."""
    included: list[Path] = []
    skipped: list[Path] = []
    expected = list(STANDARD_ARTIFACTS)

    for relative_path in expected:
        source_path = run_dir / relative_path
        if should_include_file(run_dir, source_path, output_path):
            included.append(relative_path)
        else:
            skipped.append(relative_path)

    if include_report_assets:
        report_dir = run_dir / "report"
        if report_dir.exists() and not report_dir.is_symlink() and report_dir.is_dir():
            for source_path in sorted(report_dir.rglob("*")):
                if source_path.is_file() and should_include_file(
                    run_dir,
                    source_path,
                    output_path,
                ):
                    relative_path = source_path.relative_to(run_dir)
                    if relative_path not in included:
                        included.append(relative_path)

    return included, skipped


def should_include_file(run_dir: Path, source_path: Path, output_path: Path) -> bool:
    """Return whether a source path is a safe regular file to bundle."""
    if not source_path.exists() or not source_path.is_file():
        return False
    if source_path.is_symlink():
        return False
    resolved = source_path.resolve()
    if resolved == output_path.resolve():
        return False
    try:
        resolved.relative_to(run_dir)
    except ValueError:
        return False
    return True
