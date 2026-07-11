"""Release readiness checks for VibeBench projects."""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from vibebench.artifacts import collect_artifact_inventory
from vibebench.compare import compare_runs
from vibebench.config import ConfigError, load_effective_config
from vibebench.config_check import config_check_payload, config_consistency_checks
from vibebench.doctor import check_required_workflow_ci_modes, run_doctor
from vibebench.explain import find_latest_valid_run
from vibebench.manifest import check_manifest
from vibebench.package_check import run_package_check
from vibebench.paths import config_file
from vibebench.report import ReportError
from vibebench.run_index import build_run_index

RELEASE_CHECK_JSON = "release-check.json"
RELEASE_CHECK_SUMMARY = "release-check.md"
RELEASE_CANDIDATE_JSON = "release-candidate.json"
RELEASE_CANDIDATE_SUMMARY = "release-candidate.md"
TARGET_RELEASE_VERSION = "0.4.0"

ReleaseCheckStatus = Literal["passed", "failed"]
CandidateCheckStatus = Literal["passed", "failed", "skipped", "not_applicable"]


@dataclass(frozen=True)
class ReleaseReadinessCheck:
    """One release readiness check."""

    name: str
    status: ReleaseCheckStatus
    message: str
    detected_ci_modes: list[str] | None = None
    required_ci_modes: list[str] | None = None
    missing_required_ci_modes: list[str] | None = None


@dataclass(frozen=True)
class ReleaseReadinessResult:
    """Complete release readiness result."""

    project_root: Path
    checks: list[ReleaseReadinessCheck]
    latest_run_dir: Path | None
    latest_run_id: str | None

    @property
    def ready(self) -> bool:
        """Return whether every readiness check passed."""
        return all(check.status == "passed" for check in self.checks)

    @property
    def status(self) -> str:
        """Return the release readiness status string."""
        return "ready" if self.ready else "not-ready"


@dataclass(frozen=True)
class ReleaseCandidateCheck:
    """One v0.4.0 release-candidate readiness check."""

    id: str
    name: str
    status: CandidateCheckStatus
    severity: str
    message: str
    evidence: str | None = None
    path: str | None = None
    remediation: str | None = None


@dataclass(frozen=True)
class ReleaseCandidateResult:
    """Complete v0.4.0 release-candidate readiness result."""

    project_root: Path
    target_version: str
    released: bool
    checks: list[ReleaseCandidateCheck]
    artifacts: dict[str, str]

    @property
    def passed(self) -> bool:
        """Return whether every required candidate check passed."""
        return all(
            check.status in {"passed", "not_applicable"} for check in self.checks
        )

    @property
    def status(self) -> str:
        """Return the candidate status string."""
        return "passed" if self.passed else "failed"


def run_release_check(
    project_root: Path,
    *,
    required_workflow_ci_modes: list[str] | None = None,
) -> ReleaseReadinessResult:
    """Run release readiness checks without modifying project files."""
    root = project_root.resolve()
    latest_run_dir: Path | None = None
    latest_run_id: str | None = None

    checks = [
        check_config_consistency(root),
        check_package_readiness(root),
        check_package_build_readiness_opt_in(),
        check_doctor_strict(root),
    ]
    if required_workflow_ci_modes:
        checks.append(
            check_release_workflow_ci_modes(
                root,
                required_ci_modes=required_workflow_ci_modes,
            )
        )

    latest_check, latest_run_dir = check_latest_run(root)
    checks.append(latest_check)
    if latest_run_dir is not None:
        latest_run_id = latest_run_dir.name

    checks.append(check_manifest_consistency(root, latest_run_dir))
    checks.append(check_artifact_inventory(root, latest_run_dir))
    checks.append(check_run_index(root))
    checks.append(check_compare_readiness(root))
    checks.append(check_ci_plan())
    checks.append(check_git_diff_whitespace(root))

    return ReleaseReadinessResult(
        project_root=root,
        checks=checks,
        latest_run_dir=latest_run_dir,
        latest_run_id=latest_run_id,
    )


def run_release_candidate_check(
    project_root: Path,
    *,
    target_version: str = TARGET_RELEASE_VERSION,
) -> ReleaseCandidateResult:
    """Run v0.4.0 release-candidate checks without publishing anything."""
    root = project_root.resolve()
    checks: list[ReleaseCandidateCheck] = []
    checks.extend(candidate_package_checks(root, target_version))
    checks.extend(candidate_action_checks(root))
    checks.extend(candidate_public_evidence_checks(root))
    checks.extend(candidate_documentation_checks(root, target_version))
    checks.extend(candidate_release_state_checks(root, target_version))
    return ReleaseCandidateResult(
        project_root=root,
        target_version=target_version,
        released=False,
        checks=checks,
        artifacts={
            "json": RELEASE_CANDIDATE_JSON,
            "markdown": RELEASE_CANDIDATE_SUMMARY,
            "release_notes": f"RELEASE_NOTES_v{target_version}.md",
            "release_checklist": f"docs/release-checklist-v{target_version}.md",
        },
    )


def candidate_package_checks(
    project_root: Path,
    target_version: str,
) -> list[ReleaseCandidateCheck]:
    """Check package metadata, version sources, and CLI entry point."""
    checks: list[ReleaseCandidateCheck] = []
    pyproject = project_root / "pyproject.toml"
    init_file = project_root / "vibebench" / "__init__.py"
    payload = read_toml_file(pyproject)
    project = payload.get("project") if isinstance(payload, dict) else None
    project = project if isinstance(project, dict) else {}
    package_version = project.get("version")
    init_version = read_init_version(init_file)
    versions = {
        "pyproject.toml": package_version,
        "vibebench/__init__.py": init_version,
    }
    if package_version == init_version == target_version:
        checks.append(
            candidate_pass(
                "package.version_consistency",
                "Package version consistency",
                f"Package version sources agree on {target_version}.",
                path="pyproject.toml",
                evidence=json.dumps(versions, sort_keys=True),
            )
        )
    else:
        checks.append(
            candidate_fail(
                "package.version_consistency",
                "Package version consistency",
                (
                    "Authoritative version sources must agree with target "
                    f"{target_version}; found {versions}."
                ),
                path="pyproject.toml",
                remediation=(
                    "Update the existing authoritative version sources together, "
                    "or document why final release bumps the package later."
                ),
            )
        )

    package_result = run_package_check(project_root)
    checks.append(
        candidate_pass(
            "package.metadata",
            "Package metadata",
            "Package metadata and import readiness passed.",
            path="pyproject.toml",
        )
        if package_result.ready
        else candidate_fail(
            "package.metadata",
            "Package metadata",
            "; ".join(
                f"{check.name}: {check.message}"
                for check in package_result.checks
                if check.status == "failed"
            )
            or "Package metadata readiness failed.",
            path="pyproject.toml",
            remediation="Run python3 -m vibebench package-check and fix failures.",
        )
    )

    scripts = project.get("scripts") if isinstance(project, dict) else None
    entry = scripts.get("vibebench") if isinstance(scripts, dict) else None
    checks.append(
        candidate_pass(
            "package.console_entry",
            "Console entry point",
            "The vibebench console entry point is declared.",
            path="pyproject.toml",
            evidence=str(entry),
        )
        if entry == "vibebench.cli:main"
        else candidate_fail(
            "package.console_entry",
            "Console entry point",
            "The vibebench console entry point is missing or unexpected.",
            path="pyproject.toml",
            remediation="Declare [project.scripts].vibebench = 'vibebench.cli:main'.",
        )
    )
    return checks


def candidate_action_checks(project_root: Path) -> list[ReleaseCandidateCheck]:
    """Check reusable GitHub Action metadata and smoke topology."""
    checks: list[ReleaseCandidateCheck] = []
    action_path = project_root / "action.yml"
    action = read_yaml_file(action_path)
    if not isinstance(action, dict):
        return [
            candidate_fail(
                "action.metadata",
                "Reusable Action metadata",
                "action.yml is missing or does not parse as a mapping.",
                path="action.yml",
                remediation="Restore a valid repository-root composite action.yml.",
            )
        ]

    checks.append(check_action_metadata(action))
    checks.append(check_action_inputs_outputs(action))
    checks.append(check_action_runner(project_root, action))
    checks.append(check_action_smoke(project_root))
    checks.append(check_action_docs(project_root))
    checks.append(check_action_source_mutation_protection(project_root))
    return checks


def check_action_metadata(action: dict[str, Any]) -> ReleaseCandidateCheck:
    """Validate Marketplace-compatible action metadata."""
    branding = action.get("branding")
    valid_colors = {
        "white",
        "yellow",
        "blue",
        "green",
        "orange",
        "red",
        "purple",
        "gray-dark",
    }
    failures: list[str] = []
    if not string_value(action.get("name")):
        failures.append("name")
    if not string_value(action.get("description")):
        failures.append("description")
    if not string_value(action.get("author")):
        failures.append("author")
    if not isinstance(branding, dict):
        failures.append("branding")
    else:
        if not string_value(branding.get("icon")):
            failures.append("branding.icon")
        if branding.get("color") not in valid_colors:
            failures.append("branding.color")
    if failures:
        return candidate_fail(
            "action.metadata",
            "Reusable Action metadata",
            "Marketplace metadata is incomplete: " + ", ".join(failures),
            path="action.yml",
            remediation="Add stable name, description, author, and valid branding.",
        )
    return candidate_pass(
        "action.metadata",
        "Reusable Action metadata",
        "action.yml includes stable Marketplace-compatible metadata.",
        path="action.yml",
    )


def check_action_inputs_outputs(action: dict[str, Any]) -> ReleaseCandidateCheck:
    """Validate action input/output descriptions and preset defaults."""
    failures: list[str] = []
    inputs = action.get("inputs")
    outputs = action.get("outputs")
    if not isinstance(inputs, dict):
        failures.append("inputs")
        inputs = {}
    if not isinstance(outputs, dict):
        failures.append("outputs")
        outputs = {}
    for name, metadata in inputs.items():
        if not isinstance(metadata, dict) or not string_value(
            metadata.get("description")
        ):
            failures.append(f"input:{name}")
    for name, metadata in outputs.items():
        if not isinstance(metadata, dict) or not string_value(
            metadata.get("description")
        ):
            failures.append(f"output:{name}")
    preset = inputs.get("preset") if isinstance(inputs, dict) else None
    if not isinstance(preset, dict) or preset.get("default") not in {
        "minimal",
        "strict",
        "proof",
    }:
        failures.append("preset.default")
    if failures:
        return candidate_fail(
            "action.input_output_metadata",
            "Action input/output contract",
            "Input/output metadata is malformed: " + ", ".join(failures),
            path="action.yml",
            remediation="Document every input and output; keep preset default valid.",
        )
    return candidate_pass(
        "action.input_output_metadata",
        "Action input/output contract",
        "Every action input and output has metadata and the preset default is valid.",
        path="action.yml",
    )


def check_action_runner(
    project_root: Path,
    action: dict[str, Any],
) -> ReleaseCandidateCheck:
    """Validate action runner shape and source/workspace boundary."""
    runner = project_root / "scripts" / "run_github_action.py"
    text = runner.read_text(encoding="utf-8") if runner.is_file() else ""
    runs = action.get("runs")
    failures: list[str] = []
    if not runner.is_file():
        failures.append("missing runner")
    if not isinstance(runs, dict) or runs.get("using") != "composite":
        failures.append("runs.using")
    if "GITHUB_ACTION_PATH/scripts/run_github_action.py" not in yaml_dump(action):
        failures.append("GITHUB_ACTION_PATH invocation")
    for marker in [
        "resolve_inside_workspace",
        "collect_upload_paths",
        "inputs.action_path",
        "inputs.workspace",
    ]:
        if marker not in text:
            failures.append(marker)
    if failures:
        return candidate_fail(
            "action.runner_boundary",
            "Action runner boundary",
            "Action runner/source boundary checks failed: " + ", ".join(failures),
            path="scripts/run_github_action.py",
            remediation=(
                "Keep installation sourced from GITHUB_ACTION_PATH and caller paths "
                "constrained to GITHUB_WORKSPACE."
            ),
        )
    return candidate_pass(
        "action.runner_boundary",
        "Action runner boundary",
        (
            "Action runner separates action source from caller workspace "
            "and constrains paths."
        ),
        path="scripts/run_github_action.py",
    )


def check_action_smoke(project_root: Path) -> ReleaseCandidateCheck:
    """Validate the action-smoke workflow matrix and failure behavior."""
    path = project_root / ".github" / "workflows" / "action-smoke.yml"
    payload = read_yaml_file(path)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    try:
        presets = payload["jobs"]["action-smoke"]["strategy"]["matrix"]["preset"]
    except (TypeError, KeyError):
        presets = None
    failures: list[str] = []
    if presets != ["minimal", "strict", "proof"]:
        failures.append("matrix preset must be minimal, strict, proof")
    if "continue-on-error" in text:
        failures.append("continue-on-error is present")
    if "uses: ./" not in text:
        failures.append("local action use is missing")
    if "working-directory: examples/action-consumer" not in text:
        failures.append("consumer working-directory fixture is missing")
    if failures:
        return candidate_fail(
            "action.smoke_matrix",
            "Action smoke matrix",
            "; ".join(failures),
            path=".github/workflows/action-smoke.yml",
            remediation="Restore the isolated minimal/strict/proof smoke matrix.",
        )
    return candidate_pass(
        "action.smoke_matrix",
        "Action smoke matrix",
        "Action smoke retains minimal, strict, and proof without hidden failures.",
        path=".github/workflows/action-smoke.yml",
    )


def check_action_docs(project_root: Path) -> ReleaseCandidateCheck:
    """Validate the dedicated GitHub Action contract document."""
    path = project_root / "docs" / "github-action.md"
    if not path.is_file():
        return candidate_fail(
            "action.docs",
            "Action contract documentation",
            "docs/github-action.md is missing.",
            path="docs/github-action.md",
            remediation="Add the dedicated reusable Action guide.",
        )
    text = path.read_text(encoding="utf-8")
    required = [
        "minimal",
        "strict",
        "proof",
        "input contract",
        "output contract",
        "exit-code",
        "GITHUB_WORKSPACE",
        "GITHUB_ACTION_PATH",
        "permissions",
        "@main",
        "@v0",
        "commit SHA",
        "unsupported",
    ]
    missing = [item for item in required if item.lower() not in text.lower()]
    if missing:
        return candidate_fail(
            "action.docs",
            "Action contract documentation",
            "Action guide is missing required topics: " + ", ".join(missing),
            path="docs/github-action.md",
            remediation=(
                "Document presets, contracts, refs, permissions, and boundaries."
            ),
        )
    return candidate_pass(
        "action.docs",
        "Action contract documentation",
        "Dedicated Action guide covers presets, contracts, refs, and boundaries.",
        path="docs/github-action.md",
    )


def check_action_source_mutation_protection(
    project_root: Path,
) -> ReleaseCandidateCheck:
    """Check smoke workflow protects the action checkout from consumer writes."""
    path = project_root / ".github" / "workflows" / "action-smoke.yml"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if "test ! -d .vibebench/runs" in text and "git diff --exit-code" in text:
        return candidate_pass(
            "action.source_mutation",
            "Action source mutation protection",
            (
                "Smoke workflow checks the action checkout is not mutated "
                "by consumer runs."
            ),
            path=".github/workflows/action-smoke.yml",
        )
    return candidate_fail(
        "action.source_mutation",
        "Action source mutation protection",
        "Smoke workflow does not prove the action source checkout stays clean.",
        path=".github/workflows/action-smoke.yml",
        remediation=(
            "Keep the root .vibebench/runs absence and git diff hygiene checks."
        ),
    )


def candidate_public_evidence_checks(project_root: Path) -> list[ReleaseCandidateCheck]:
    """Check public proof, demo, Pages, and Trust Center readiness."""
    checks = [
        check_builder_current(
            project_root,
            "public.proof_packet",
            "Public proof packet",
            ["python3", "scripts/build_public_proof_packet.py", "--check"],
            "examples/showcase-artifacts/public-proof",
        ),
        check_builder_current(
            project_root,
            "public.demo",
            "Public demo portal",
            ["python3", "scripts/build_public_demo.py", "--check"],
            "examples/showcase-artifacts/public-demo",
        ),
        check_builder_current(
            project_root,
            "public.pages_site",
            "GitHub Pages launch site",
            [
                "python3",
                "scripts/build_pages_site.py",
                "--output-dir",
                "_site",
                "--check",
            ],
            "scripts/build_pages_site.py",
        ),
        check_pages_workflow(project_root),
        check_trust_center_offline_safe(project_root),
    ]
    return checks


def check_builder_current(
    project_root: Path,
    check_id: str,
    name: str,
    command: list[str],
    evidence_path: str,
) -> ReleaseCandidateCheck:
    """Run an established deterministic builder in check mode."""
    script = project_root / command[1]
    if not script.is_file():
        return candidate_fail(
            check_id,
            name,
            f"Builder script is missing: {command[1]}",
            path=command[1],
            remediation="Restore the deterministic builder.",
        )
    completed = subprocess.run(
        command,
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode == 0:
        return candidate_pass(
            check_id,
            name,
            f"{' '.join(command)} passed.",
            path=evidence_path,
        )
    detail = (completed.stderr or completed.stdout or "check failed").strip()
    return candidate_fail(
        check_id,
        name,
        detail.splitlines()[0],
        path=evidence_path,
        remediation=(
            f"Run {' '.join(command[:-1])} --write if the committed surface "
            "is intentionally stale."
        ),
    )


def check_pages_workflow(project_root: Path) -> ReleaseCandidateCheck:
    """Validate Pages workflow publishes only the generated site directory."""
    path = project_root / ".github" / "workflows" / "pages.yml"
    payload = read_yaml_file(path)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    failures: list[str] = []
    if not isinstance(payload, dict):
        failures.append("workflow parse")
    if "actions/upload-pages-artifact@v4" not in text:
        failures.append("upload-pages-artifact")
    if "path: _site" not in text:
        failures.append("artifact path must be _site")
    if "scripts/build_pages_site.py --output-dir _site --check" not in text:
        failures.append("Pages deterministic check")
    if failures:
        return candidate_fail(
            "public.pages_workflow",
            "Pages workflow boundary",
            "Pages workflow boundary failed: " + ", ".join(failures),
            path=".github/workflows/pages.yml",
            remediation="Keep Pages publishing constrained to checked _site output.",
        )
    return candidate_pass(
        "public.pages_workflow",
        "Pages workflow boundary",
        "Pages workflow builds, checks, and uploads only the intended _site output.",
        path=".github/workflows/pages.yml",
    )


def check_trust_center_offline_safe(project_root: Path) -> ReleaseCandidateCheck:
    """Check Trust Center stays safe for offline evidence-room copies."""
    path = project_root / "docs" / "trust-center.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    prohibited = [
        "https://wemby-1.github.io/vibebench-arena/",
        "http://",
        "https://",
        "/tmp/",
        "/data/code/",
        "/home/",
    ]
    matches = [item for item in prohibited if item in text]
    if matches:
        return candidate_fail(
            "public.trust_center_offline",
            "Trust Center offline safety",
            "Trust Center contains prohibited hosted/path markers: "
            + ", ".join(matches),
            path="docs/trust-center.md",
            remediation="Keep Trust Center evidence-room copies offline-safe.",
        )
    return candidate_pass(
        "public.trust_center_offline",
        "Trust Center offline safety",
        (
            "Trust Center avoids raw hosted URLs, temp paths, and remote "
            "runtime dependencies."
        ),
        path="docs/trust-center.md",
    )


def candidate_documentation_checks(
    project_root: Path,
    target_version: str,
) -> list[ReleaseCandidateCheck]:
    """Check release-candidate documentation, links, and placeholders."""
    checks: list[ReleaseCandidateCheck] = []
    required_docs = [
        "README.md",
        "README.zh-CN.md",
        "docs/github-action.md",
        "docs/marketplace-readiness.md",
        f"RELEASE_NOTES_v{target_version}.md",
        f"docs/release-checklist-v{target_version}.md",
        "docs/public-proof-packet.md",
        "docs/showcase.md",
        "docs/trust-center.md",
    ]
    missing = [path for path in required_docs if not (project_root / path).is_file()]
    if missing:
        checks.append(
            candidate_fail(
                "docs.required",
                "Required release docs",
                "Missing required release docs: " + ", ".join(missing),
                remediation="Add the v0.4.0 candidate docs and navigation.",
            )
        )
    else:
        checks.append(
            candidate_pass(
                "docs.required",
                "Required release docs",
                (
                    "Required release candidate, Action, Marketplace, proof, "
                    "and trust docs exist."
                ),
            )
        )

    checks.append(check_docs_navigation(project_root, target_version))
    checks.append(check_docs_placeholders(project_root))
    checks.append(check_markdown_links(project_root, required_docs))
    checks.append(check_release_materials_non_publication(project_root, target_version))
    return checks


def check_docs_navigation(
    project_root: Path,
    target_version: str,
) -> ReleaseCandidateCheck:
    """Check README surfaces the candidate adoption path without @main stability."""
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [project_root / "README.md", project_root / "README.zh-CN.md"]
        if path.is_file()
    )
    required = [
        "docs/github-action.md",
        "docs/marketplace-readiness.md",
        f"RELEASE_NOTES_v{target_version}.md",
        f"docs/release-checklist-v{target_version}.md",
        "release-check --candidate",
    ]
    missing = [item for item in required if item not in combined]
    if missing:
        return candidate_fail(
            "docs.navigation",
            "README release-candidate navigation",
            "README navigation is missing: " + ", ".join(missing),
            path="README.md",
            remediation=(
                "Expose the candidate gate, Action guide, Marketplace guide, "
                "notes, and checklist."
            ),
        )
    return candidate_pass(
        "docs.navigation",
        "README release-candidate navigation",
        "English and Chinese READMEs expose the v0.4.0 candidate adoption path.",
        path="README.md",
    )


def check_docs_placeholders(project_root: Path) -> ReleaseCandidateCheck:
    """Scan release-critical docs for placeholders."""
    release_docs = [
        project_root / "README.md",
        project_root / "README.zh-CN.md",
        project_root / "docs" / "github-action.md",
        project_root / "docs" / "marketplace-readiness.md",
        project_root / f"RELEASE_NOTES_v{TARGET_RELEASE_VERSION}.md",
        project_root / f"docs/release-checklist-v{TARGET_RELEASE_VERSION}.md",
    ]
    pattern = re.compile(r"\b(TODO|TBD|FIXME|PLACEHOLDER|COMING SOON)\b", re.I)
    matches = []
    for path in release_docs:
        if path.is_file() and pattern.search(path.read_text(encoding="utf-8")):
            matches.append(path.relative_to(project_root).as_posix())
    if matches:
        return candidate_fail(
            "docs.placeholders",
            "Release-critical placeholder scan",
            "Release-critical placeholders found in: " + ", ".join(matches),
            remediation="Replace placeholders with final candidate wording.",
        )
    return candidate_pass(
        "docs.placeholders",
        "Release-critical placeholder scan",
        "Release-critical docs contain no TODO/TBD/FIXME placeholders.",
    )


def check_markdown_links(
    project_root: Path,
    doc_paths: list[str],
) -> ReleaseCandidateCheck:
    """Resolve local Markdown links in the release-critical doc set."""
    missing: list[str] = []
    for relative in doc_paths:
        path = project_root / relative
        if not path.is_file():
            continue
        for link in markdown_links(path.read_text(encoding="utf-8")):
            if is_external_or_anchor(link):
                continue
            target_part = link.split("#", 1)[0]
            if not target_part:
                continue
            target = (path.parent / target_part).resolve()
            try:
                target.relative_to(project_root)
            except ValueError:
                continue
            if not target.exists():
                missing.append(f"{relative} -> {link}")
    if missing:
        return candidate_fail(
            "docs.relative_links",
            "Relative Markdown links",
            "Broken relative Markdown links: " + "; ".join(missing[:8]),
            remediation="Fix or remove broken release-critical Markdown links.",
        )
    return candidate_pass(
        "docs.relative_links",
        "Relative Markdown links",
        "Release-critical relative Markdown links resolve.",
    )


def check_release_materials_non_publication(
    project_root: Path,
    target_version: str,
) -> ReleaseCandidateCheck:
    """Check release docs explicitly say candidate work did not publish."""
    paths = [
        project_root / f"RELEASE_NOTES_v{target_version}.md",
        project_root / f"docs/release-checklist-v{target_version}.md",
        project_root / "docs" / "marketplace-readiness.md",
    ]
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in paths if path.is_file()
    ).lower()
    required = [
        "no tag",
        "no github release",
        "no package publication",
        "no marketplace publication",
        "released=false",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        return candidate_fail(
            "docs.non_publication",
            "Explicit non-publication state",
            "Release materials are missing non-publication statements: "
            + ", ".join(missing),
            remediation=(
                "State that M160 performs no tag, release, package, or "
                "Marketplace publication."
            ),
        )
    return candidate_pass(
        "docs.non_publication",
        "Explicit non-publication state",
        "Release materials explicitly preserve candidate-only non-publication state.",
    )


def candidate_release_state_checks(
    project_root: Path,
    target_version: str,
) -> list[ReleaseCandidateCheck]:
    """Check local release state and false stable-ref claims."""
    checks: list[ReleaseCandidateCheck] = []
    checks.append(check_local_tag_absent(project_root, target_version))
    checks.append(check_stable_ref_claims(project_root, target_version))
    checks.append(
        candidate_pass(
            "release.released_false",
            "Candidate release state",
            "Candidate schema reports released=false and performs no publication.",
            evidence="released=false",
        )
    )
    return checks


def check_local_tag_absent(
    project_root: Path,
    target_version: str,
) -> ReleaseCandidateCheck:
    """Check no local v0.4.0 tag exists as a side effect."""
    tag = f"v{target_version}"
    completed = subprocess.run(
        ["git", "tag", "--list", tag],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.stdout.strip():
        return candidate_fail(
            "release.local_tag_absent",
            "Local release tag absent",
            f"Local tag {tag} exists, but M160 must not create a release tag.",
            remediation=(
                "Do not tag during candidate preparation; investigate local "
                "tag state."
            ),
        )
    return candidate_pass(
        "release.local_tag_absent",
        "Local release tag absent",
        f"No local {tag} tag exists.",
    )


def check_stable_ref_claims(
    project_root: Path,
    target_version: str,
) -> ReleaseCandidateCheck:
    """Check docs label stable refs as post-release examples."""
    docs = [
        project_root / "README.md",
        project_root / "docs" / "github-action.md",
        project_root / "docs" / "marketplace-readiness.md",
        project_root / f"RELEASE_NOTES_v{target_version}.md",
    ]
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in docs if path.is_file()
    ).lower()
    suspicious = [
        r"stable production release (?:at|is|uses)\s+@main",
        r"@main\s+is\s+(?:a\s+)?stable",
        r"@main\s+(?:stable|production)\s+(?:ref|reference|release)",
        r"marketplace publication completed",
        r"(?:has been|is now|was)\s+published to github marketplace",
        r"package (?:has been|is now|was)\s+published",
        r"github release (?:is live|has been published|was published)",
    ]
    matches = [pattern for pattern in suspicious if re.search(pattern, combined)]
    if matches:
        return candidate_fail(
            "release.false_stable_claims",
            "False stable release claims",
            "Potential false stable/publication claims found: " + ", ".join(matches),
            remediation=(
                "Label @main as development preview and stable refs as "
                "post-release only."
            ),
        )
    return candidate_pass(
        "release.false_stable_claims",
        "False stable release claims",
        "@main is not presented as stable and publication is not claimed.",
    )


def check_config_consistency(project_root: Path) -> ReleaseReadinessCheck:
    """Run config load and consistency diagnostics."""
    try:
        result = load_effective_config(config_file(project_root))
        checks = config_consistency_checks(result)
        payload = config_check_payload(result, checks)
    except ConfigError as exc:
        return ReleaseReadinessCheck("config", "failed", str(exc))

    status = "passed" if payload["overall_status"] == "passed" else "failed"
    failed = [check for check in checks if check["status"] == "failed"]
    message = (
        "Config consistency check passed"
        if not failed
        else "; ".join(check["message"] for check in failed)
    )
    return ReleaseReadinessCheck("config", status, message)


def check_package_readiness(project_root: Path) -> ReleaseReadinessCheck:
    """Run package metadata and install readiness diagnostics."""
    result = run_package_check(project_root)
    if result.ready:
        return ReleaseReadinessCheck(
            "package_check",
            "passed",
            "Package readiness check passed",
        )
    failed = [check for check in result.checks if check.status == "failed"]
    message = "; ".join(f"{check.name}: {check.message}" for check in failed)
    return ReleaseReadinessCheck(
        "package_check",
        "failed",
        message or "Package readiness check failed",
    )


def check_package_build_readiness_opt_in() -> ReleaseReadinessCheck:
    """Report that local build readiness is an explicit package-check opt-in."""
    return ReleaseReadinessCheck(
        "package_build",
        "passed",
        (
            "Local package build readiness is opt-in; run "
            "python -m vibebench package-check --build before publishing."
        ),
    )


def check_doctor_strict(project_root: Path) -> ReleaseReadinessCheck:
    """Run strict doctor diagnostics."""
    result = run_doctor(project_root, strict=True)
    non_blocking_without_run = {
        "strict_runs_directory",
        "strict_latest_run",
    }
    failed = [
        check
        for check in result.checks
        if check.status == "failed"
        and check.category not in non_blocking_without_run
    ]
    if not failed:
        return ReleaseReadinessCheck("doctor_strict", "passed", "Strict doctor passed")
    message = "; ".join(f"{check.category}: {check.message}" for check in failed)
    return ReleaseReadinessCheck("doctor_strict", "failed", message)


def check_release_workflow_ci_modes(
    project_root: Path,
    *,
    required_ci_modes: list[str],
) -> ReleaseReadinessCheck:
    """Check that release readiness includes the required workflow CI modes."""
    doctor_check = check_required_workflow_ci_modes(
        project_root,
        required_ci_modes=required_ci_modes,
    )
    return ReleaseReadinessCheck(
        "workflow_ci_modes",
        "passed" if doctor_check.status == "passed" else "failed",
        doctor_check.message,
        detected_ci_modes=doctor_check.detected_ci_modes,
        required_ci_modes=doctor_check.required_ci_modes,
        missing_required_ci_modes=doctor_check.missing_required_ci_modes,
    )


def check_latest_run(project_root: Path) -> tuple[ReleaseReadinessCheck, Path | None]:
    """Find the latest valid run."""
    try:
        run_dir = find_latest_valid_run(project_root)
    except ReportError as exc:
        return (
            ReleaseReadinessCheck(
                "latest_run",
                "passed",
                f"No latest run found; local run evidence is optional: {exc}",
            ),
            None,
        )
    return (
        ReleaseReadinessCheck(
            "latest_run",
            "passed",
            f"Latest valid run: {run_dir.name}",
        ),
        run_dir,
    )


def check_manifest_consistency(
    project_root: Path,
    latest_run_dir: Path | None,
) -> ReleaseReadinessCheck:
    """Check latest run manifest consistency."""
    if latest_run_dir is None:
        return ReleaseReadinessCheck(
            "manifest",
            "passed",
            "No latest run available; manifest check skipped",
        )
    try:
        result = check_manifest(project_root, latest_run_dir)
    except ReportError as exc:
        return ReleaseReadinessCheck("manifest", "failed", str(exc))
    if result.passed:
        return ReleaseReadinessCheck("manifest", "passed", "Manifest is consistent")
    return ReleaseReadinessCheck(
        "manifest",
        "failed",
        "; ".join(result.differences[:3]),
    )


def check_artifact_inventory(
    project_root: Path,
    latest_run_dir: Path | None,
) -> ReleaseReadinessCheck:
    """Check that artifact inventory can be generated."""
    if latest_run_dir is None:
        return ReleaseReadinessCheck(
            "artifacts",
            "passed",
            "No latest run available; artifact inventory skipped",
        )
    try:
        result = collect_artifact_inventory(project_root, latest_run_dir)
    except ReportError as exc:
        return ReleaseReadinessCheck("artifacts", "failed", str(exc))
    available = sum(1 for artifact in result.artifacts if artifact.available)
    return ReleaseReadinessCheck(
        "artifacts",
        "passed",
        f"Artifact inventory generated ({available} available)",
    )


def check_run_index(project_root: Path) -> ReleaseReadinessCheck:
    """Check that a useful run index can be generated."""
    try:
        result = build_run_index(project_root)
    except ReportError as exc:
        return ReleaseReadinessCheck("run_index", "failed", str(exc))
    return ReleaseReadinessCheck(
        "run_index",
        "passed",
        (
            f"Run index generated ({len(result.runs)} indexed, "
            f"{result.total_runs_seen} seen)"
        ),
    )


def check_compare_readiness(project_root: Path) -> ReleaseReadinessCheck:
    """Check that run comparison can be produced without requiring two runs."""
    try:
        result = compare_runs(project_root, write_default_artifacts=False)
    except ReportError as exc:
        return ReleaseReadinessCheck("compare", "failed", str(exc))
    if result.verdict == "insufficient-data":
        return ReleaseReadinessCheck(
            "compare",
            "passed",
            "Compare readiness checked; insufficient data is non-fatal",
        )
    return ReleaseReadinessCheck(
        "compare",
        "passed",
        f"Compare readiness checked ({result.base_run_id} -> {result.head_run_id})",
    )


def check_ci_plan() -> ReleaseReadinessCheck:
    """Check that a dry-run CI plan can be produced."""
    from vibebench.ci import plan_ci_pipeline

    result = plan_ci_pipeline()
    if result.dry_run and result.steps:
        return ReleaseReadinessCheck("ci_plan", "passed", "CI dry-run plan produced")
    return ReleaseReadinessCheck("ci_plan", "failed", "CI dry-run plan was empty")


def check_git_diff_whitespace(project_root: Path) -> ReleaseReadinessCheck:
    """Run git diff --check as a whitespace/readiness check."""
    try:
        completed = subprocess.run(
            ["git", "diff", "--check"],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return ReleaseReadinessCheck("git_diff_check", "failed", str(exc))
    if completed.returncode == 0:
        return ReleaseReadinessCheck(
            "git_diff_check",
            "passed",
            "git diff --check passed",
        )
    message = (
        completed.stdout or completed.stderr or "git diff --check failed"
    ).strip()
    return ReleaseReadinessCheck("git_diff_check", "failed", message)


def release_check_json_payload(result: ReleaseReadinessResult) -> dict[str, object]:
    """Return a deterministic JSON-safe release readiness payload."""
    return {
        "status": result.status,
        "project_root": str(result.project_root),
        "latest_run_dir": str(result.latest_run_dir) if result.latest_run_dir else None,
        "latest_run_id": result.latest_run_id,
        "checks": [
            release_check_item_payload(check)
            for check in result.checks
        ],
    }


def release_candidate_json_payload(
    result: ReleaseCandidateResult,
) -> dict[str, object]:
    """Return deterministic JSON-safe v0.4.0 candidate readiness payload."""
    passed = [check for check in result.checks if check.status == "passed"]
    failed = [check for check in result.checks if check.status == "failed"]
    skipped = [
        check
        for check in result.checks
        if check.status in {"skipped", "not_applicable"}
    ]
    categories = sorted({check.id.split(".", 1)[0] for check in result.checks})
    return {
        "schema_version": 1,
        "status": result.status,
        "candidate": True,
        "target_version": result.target_version,
        "released": result.released,
        "checks": [
            release_candidate_item_payload(check)
            for check in sorted(result.checks, key=lambda item: item.id)
        ],
        "summary": {
            "total": len(result.checks),
            "passed": len(passed),
            "failed": len(failed),
            "skipped": len(skipped),
            "categories": categories,
        },
        "artifacts": result.artifacts,
    }


def release_candidate_json(result: ReleaseCandidateResult) -> str:
    """Return pretty deterministic JSON for candidate readiness."""
    return json.dumps(
        release_candidate_json_payload(result),
        indent=2,
        sort_keys=True,
    )


def release_candidate_item_payload(
    check: ReleaseCandidateCheck,
) -> dict[str, object]:
    """Return one JSON-safe candidate check payload."""
    payload: dict[str, object] = {
        "id": check.id,
        "name": check.name,
        "status": check.status,
        "severity": check.severity,
        "message": check.message,
    }
    if check.evidence:
        payload["evidence"] = check.evidence
    if check.path:
        payload["path"] = check.path
    if check.remediation:
        payload["remediation"] = check.remediation
    return payload


def release_candidate_markdown(result: ReleaseCandidateResult) -> str:
    """Render a deterministic Markdown v0.4.0 candidate report."""
    blockers = [check for check in result.checks if check.status == "failed"]
    lines = [
        "# VibeBench v0.4.0 Release Candidate",
        "",
        f"- Target version: `{escape_markdown(result.target_version)}`",
        f"- Candidate status: `{escape_markdown(result.status)}`",
        f"- Released: `{str(result.released).lower()}`",
        (
            "- Publication state: no release/tag/package publication occurred; "
            "no GitHub Marketplace publication occurred."
        ),
        "",
        "## Summary",
        "",
        "| Area | Status | Evidence |",
        "| --- | --- | --- |",
    ]
    area_status = candidate_area_statuses(result.checks)
    area_labels = {
        "package": "Package/version consistency",
        "action": "Reusable Action readiness",
        "public": "Pages/public-demo/proof status",
        "docs": "Documentation readiness",
        "release": "Release state",
    }
    for area in ["package", "action", "public", "docs", "release"]:
        lines.append(
            "| "
            f"{escape_markdown(area_labels.get(area, area))} | "
            f"{escape_markdown(area_status.get(area, 'not_applicable'))} | "
            f"{escape_markdown(area_evidence(result.checks, area))} |"
        )
    lines.extend(
        [
            "",
            "## Security, Privacy, and Supply-chain Boundaries",
            "",
            "- The candidate gate does not call the GitHub API.",
            (
                "- The candidate gate does not create tags, GitHub Releases, "
                "package uploads, or Marketplace publication."
            ),
            (
                "- Action paths are checked for GITHUB_WORKSPACE and "
                "GITHUB_ACTION_PATH separation."
            ),
            (
                "- Public static surfaces are checked for deterministic "
                "builders and offline-safe Trust Center boundaries."
            ),
            "",
            "## Action Smoke Matrix Requirements",
            "",
            (
                "- `minimal`, `strict`, and `proof` must remain in "
                "`.github/workflows/action-smoke.yml`."
            ),
            "- `continue-on-error` must not hide matrix failures.",
            (
                "- The consumer fixture must run from `examples/action-consumer` "
                "without mutating the action source checkout."
            ),
            "",
            "## Unresolved Blockers",
            "",
        ]
    )
    if blockers:
        for check in sorted(blockers, key=lambda item: item.id):
            lines.append(
                f"- `{escape_markdown(check.id)}`: {escape_markdown(check.message)}"
            )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Exact Next Release Actions",
            "",
            (
                "1. Confirm the real GitHub Action smoke run has minimal, "
                "strict, and proof passing."
            ),
            (
                "2. Rerun the candidate command and full verification chain "
                "from a clean checkout."
            ),
            "3. Create the intended annotated `v0.4.0` tag only after approval.",
            "4. Draft and publish the GitHub Release only after final approval.",
            "5. Publish any package only if separately approved.",
            (
                "6. Decide whether to draft or publish GitHub Marketplace "
                "listing after the stable ref exists."
            ),
            "",
            "## Evidence Paths",
            "",
            "| Check | Status | Path | Message |",
            "| --- | --- | --- | --- |",
        ]
    )
    for check in sorted(result.checks, key=lambda item: item.id):
        lines.append(
            "| "
            f"{escape_markdown(check.id)} | "
            f"{escape_markdown(check.status)} | "
            f"{escape_markdown(check.path or check.evidence or '')} | "
            f"{escape_markdown(check.message)} |"
        )
    return "\n".join(lines) + "\n"


def write_release_candidate_json(
    result: ReleaseCandidateResult,
    output_path: Path,
) -> Path:
    """Write release-candidate JSON to a selected path."""
    validate_output_path(output_path, create_parent=True)
    output_path.write_text(release_candidate_json(result) + "\n", encoding="utf-8")
    return output_path


def write_release_candidate_summary(
    result: ReleaseCandidateResult,
    output_path: Path,
) -> Path:
    """Write release-candidate Markdown to a selected path."""
    validate_output_path(output_path, create_parent=True)
    output_path.write_text(release_candidate_markdown(result), encoding="utf-8")
    return output_path


def candidate_area_statuses(
    checks: list[ReleaseCandidateCheck],
) -> dict[str, str]:
    """Return aggregate status by check id prefix."""
    statuses: dict[str, str] = {}
    for check in checks:
        area = check.id.split(".", 1)[0]
        current = statuses.get(area)
        if check.status == "failed":
            statuses[area] = "failed"
        elif current != "failed":
            statuses[area] = "passed"
    return statuses


def area_evidence(checks: list[ReleaseCandidateCheck], area: str) -> str:
    """Return compact evidence paths for an area."""
    values = [
        check.path or check.evidence
        for check in checks
        if check.id.startswith(f"{area}.") and (check.path or check.evidence)
    ]
    return ", ".join(dict.fromkeys(value for value in values if value))


def release_check_json(result: ReleaseReadinessResult) -> str:
    """Return pretty deterministic JSON for release readiness."""
    return json.dumps(release_check_json_payload(result), indent=2, sort_keys=True)


def release_check_item_payload(check: ReleaseReadinessCheck) -> dict[str, object]:
    """Return a JSON-safe release readiness check payload."""
    payload: dict[str, object] = {
        "name": check.name,
        "status": check.status,
        "message": check.message,
    }
    if check.detected_ci_modes is not None:
        payload["detected_ci_modes"] = check.detected_ci_modes
    if check.required_ci_modes is not None:
        payload["required_ci_modes"] = check.required_ci_modes
    if check.missing_required_ci_modes is not None:
        payload["missing_required_ci_modes"] = check.missing_required_ci_modes
    return payload


def release_check_markdown(result: ReleaseReadinessResult) -> str:
    """Render a human-readable Markdown release readiness summary."""
    lines = [
        "# VibeBench Release Check",
        "",
        f"- Project root: `{escape_markdown(result.project_root)}`",
        f"- Status: `{escape_markdown(result.status)}`",
        f"- Latest run: `{escape_markdown(result.latest_run_id or 'none')}`",
        "",
        "| Check | Status | Message |",
        "| --- | --- | --- |",
    ]
    for check in result.checks:
        lines.append(
            "| "
            f"{escape_markdown(check.name)} | "
            f"{escape_markdown(check.status)} | "
            f"{escape_markdown(check.message)} |"
        )
    return "\n".join(lines) + "\n"


def write_release_check_json(
    result: ReleaseReadinessResult,
    output_path: Path,
) -> Path:
    """Write release readiness JSON to a selected path."""
    validate_output_path(output_path)
    output_path.write_text(release_check_json(result) + "\n", encoding="utf-8")
    return output_path


def write_release_check_summary(
    result: ReleaseReadinessResult,
    output_path: Path,
) -> Path:
    """Write release readiness Markdown to a selected path."""
    validate_output_path(output_path)
    output_path.write_text(release_check_markdown(result), encoding="utf-8")
    return output_path


def validate_output_path(output_path: Path, *, create_parent: bool = False) -> None:
    """Validate a requested release check artifact output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"Output path is a directory: {output_path}")
    if not output_path.parent.exists():
        if create_parent:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            return
        message = f"Output parent directory does not exist: {output_path.parent}"
        raise ReportError(message)


def escape_markdown(value: object) -> str:
    """Escape Markdown table-sensitive characters."""
    return str(value).replace("|", "\\|").replace("\n", " ")


def candidate_pass(
    check_id: str,
    name: str,
    message: str,
    *,
    evidence: str | None = None,
    path: str | None = None,
) -> ReleaseCandidateCheck:
    """Return a passing candidate check."""
    return ReleaseCandidateCheck(
        id=check_id,
        name=name,
        status="passed",
        severity="required",
        message=message,
        evidence=evidence,
        path=path,
    )


def candidate_fail(
    check_id: str,
    name: str,
    message: str,
    *,
    evidence: str | None = None,
    path: str | None = None,
    remediation: str | None = None,
) -> ReleaseCandidateCheck:
    """Return a failing candidate check."""
    return ReleaseCandidateCheck(
        id=check_id,
        name=name,
        status="failed",
        severity="blocker",
        message=message,
        evidence=evidence,
        path=path,
        remediation=remediation,
    )


def read_toml_file(path: Path) -> dict[str, Any]:
    """Read TOML as a mapping, returning an empty mapping on failure."""
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def read_yaml_file(path: Path) -> Any:
    """Read YAML safely, returning None on failure."""
    if not path.is_file():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None


def yaml_dump(value: object) -> str:
    """Return a deterministic YAML-ish dump for structural substring checks."""
    try:
        return yaml.safe_dump(value, sort_keys=True)
    except yaml.YAMLError:
        return str(value)


def read_init_version(path: Path) -> str | None:
    """Read vibebench.__version__ without importing an arbitrary checkout."""
    if not path.is_file():
        return None
    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        path.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    return match.group(1) if match else None


def string_value(value: object) -> bool:
    """Return whether a value is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())


def markdown_links(text: str) -> list[str]:
    """Return inline Markdown links without image links."""
    return [
        match.group(1).strip()
        for match in re.finditer(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", text)
        if match.group(1).strip()
    ]


def is_external_or_anchor(link: str) -> bool:
    """Return whether a Markdown link is external, mail, or pure anchor."""
    normalized = link.strip().lower()
    return normalized.startswith(
        (
            "#",
            "http://",
            "https://",
            "mailto:",
            "tel:",
        )
    )
