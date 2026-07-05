"""Local showcase demo helpers."""

from __future__ import annotations

import filecmp
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SAMPLE_DIR = Path("examples") / "showcase-artifacts" / "sample"

SAMPLE_ARTIFACTS = [
    ("README.md", "markdown"),
    ("ci-summary.md", "markdown"),
    ("ci-plan.json", "json"),
    ("artifact-inventory.json", "json"),
    ("compare-summary.md", "markdown"),
    ("release-audit-summary.md", "markdown"),
    ("manifest.json", "json"),
]

DEMO_COMMANDS = [
    "python3 -m vibebench demo --json",
    "python3 -m vibebench demo --copy-to /tmp/vibebench-demo",
    "python3 -m vibebench ci --dry-run --json",
]

DEMO_DOCS = [
    "README.md",
    "docs/demo.md",
    "docs/artifact-gallery.md",
    "examples/showcase-artifacts/README.md",
    "examples/showcase-artifacts/sample/README.md",
]


class DemoError(Exception):
    """Raised when the local showcase demo cannot complete safely."""


@dataclass(frozen=True)
class DemoCopyResult:
    """Result of copying the checked-in sample artifact pack."""

    output_dir: Path
    copied_files: list[str]
    skipped_files: list[str]
    conflicts: list[str]

    @property
    def copied(self) -> bool:
        return bool(self.copied_files) and not self.conflicts


def sample_dir(project_root: Path) -> Path:
    """Return the checked-in sample artifact directory."""
    return project_root / SAMPLE_DIR


def demo_artifacts(project_root: Path) -> list[dict[str, object]]:
    """Return metadata for sample artifacts."""
    root = project_root.resolve()
    return [
        {
            "name": name,
            "path": (SAMPLE_DIR / name).as_posix(),
            "exists": (root / SAMPLE_DIR / name).is_file(),
            "kind": kind,
        }
        for name, kind in SAMPLE_ARTIFACTS
    ]


def demo_payload(
    project_root: Path,
    *,
    copy_result: DemoCopyResult | None = None,
    conflicts: list[str] | None = None,
) -> dict[str, Any]:
    """Build the local showcase demo JSON payload."""
    root = project_root.resolve()
    source_dir = sample_dir(root)
    available = source_dir.is_dir()
    payload: dict[str, Any] = {
        "status": "available" if available else "missing",
        "project_root": root.as_posix(),
        "demo_name": "local showcase demo",
        "description": (
            "A local showcase demo for browsing the checked-in VibeBench "
            "sample artifact pack."
        ),
        "sample_dir": source_dir.as_posix(),
        "available": available,
        "artifacts": demo_artifacts(root),
        "commands": DEMO_COMMANDS,
        "docs": DEMO_DOCS,
    }
    if not available:
        payload["message"] = "Source-tree sample artifact pack is missing."
    if copy_result is not None:
        payload["copied"] = copy_result.copied
        payload["output_dir"] = copy_result.output_dir.as_posix()
        payload["copied_files"] = copy_result.copied_files
        payload["skipped_files"] = copy_result.skipped_files
        payload["conflicts"] = copy_result.conflicts
        if copy_result.conflicts:
            payload["status"] = "conflict"
    elif conflicts is not None:
        payload["copied"] = False
        payload["conflicts"] = conflicts
    return payload


def copy_sample_pack(
    project_root: Path,
    output_dir: Path,
    *,
    force: bool = False,
) -> DemoCopyResult:
    """Copy the sample artifact pack to an output directory."""
    root = project_root.resolve()
    source_dir = sample_dir(root)
    if not source_dir.is_dir():
        raise DemoError("Source-tree sample artifact pack is missing.")

    target = output_dir if output_dir.is_absolute() else root / output_dir
    target = target.resolve()
    if target.exists() and not target.is_dir():
        raise DemoError(f"Output path exists as a file: {target}")

    conflicts: list[str] = []
    copied_files: list[str] = []
    skipped_files: list[str] = []

    for name, _kind in SAMPLE_ARTIFACTS:
        source = source_dir / name
        destination = target / name
        if destination.exists() and not destination.is_file():
            conflicts.append(name)
            continue
        if destination.exists() and destination.is_file():
            if filecmp.cmp(source, destination, shallow=False):
                skipped_files.append(name)
                continue
            if not force:
                conflicts.append(name)
                continue

    if conflicts and not force:
        return DemoCopyResult(
            output_dir=target,
            copied_files=[],
            skipped_files=skipped_files,
            conflicts=conflicts,
        )

    target.mkdir(parents=True, exist_ok=True)
    for name, _kind in SAMPLE_ARTIFACTS:
        if name in skipped_files:
            continue
        source = source_dir / name
        destination = target / name
        if destination.exists() and destination.is_dir():
            continue
        shutil.copy2(source, destination)
        copied_files.append(name)

    return DemoCopyResult(
        output_dir=target,
        copied_files=copied_files,
        skipped_files=skipped_files,
        conflicts=[],
    )
