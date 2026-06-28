"""Git diff risk analysis for VibeBench checks."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vibebench.config import RiskConfig, RiskRulesConfig

FindingSeverity = Literal["info", "warning", "high", "critical"]
ChangeStatus = Literal["added", "modified", "deleted", "renamed"]

class DiffFileChange(BaseModel):
    """One changed file reported by git."""

    model_config = ConfigDict(extra="forbid")

    path: str
    status: ChangeStatus
    old_path: str | None = None
    added_lines: int = Field(default=0, ge=0)
    deleted_lines: int = Field(default=0, ge=0)


class RiskFinding(BaseModel):
    """A risk finding from diff analysis."""

    model_config = ConfigDict(extra="forbid")

    severity: FindingSeverity
    code: str
    message: str
    paths: list[str] = Field(default_factory=list)


class DiffAnalysis(BaseModel):
    """Structured git diff analysis for the current working tree."""

    model_config = ConfigDict(extra="forbid")

    git_available: bool
    changed_files: list[str] = Field(default_factory=list)
    deleted_files: list[str] = Field(default_factory=list)
    added_files: list[str] = Field(default_factory=list)
    modified_files: list[str] = Field(default_factory=list)
    renamed_files: list[str] = Field(default_factory=list)
    test_files_changed: list[str] = Field(default_factory=list)
    tests_deleted: list[str] = Field(default_factory=list)
    forbidden_paths_touched: list[str] = Field(default_factory=list)
    secret_like_files_touched: list[str] = Field(default_factory=list)
    lockfiles_changed: list[str] = Field(default_factory=list)
    total_added_lines: int = 0
    total_deleted_lines: int = 0
    total_patch_lines: int = 0
    changed_file_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    file_changes: list[DiffFileChange] = Field(default_factory=list)


def analyze_git_diff(
    project_root: Path,
    rules: RiskConfig | RiskRulesConfig,
    legacy_rules: RiskRulesConfig | None = None,
) -> tuple[DiffAnalysis, list[RiskFinding]]:
    """Analyze the current working tree diff against HEAD."""
    root = project_root.resolve()
    if not is_git_repo(root):
        warning = "Project root is not inside a Git repository; diff analysis skipped."
        return DiffAnalysis(git_available=False, warnings=[warning]), [
            RiskFinding(
                severity="warning",
                code="git_unavailable",
                message=warning,
            )
        ]

    policy = as_risk_config(rules)
    changes = collect_file_changes(root)
    analysis = build_analysis(changes, policy)
    findings = build_findings(analysis, policy, legacy_rules or rules)
    return analysis, findings


def is_git_repo(project_root: Path) -> bool:
    """Return whether project_root is inside a Git work tree."""
    completed = run_git(project_root, "rev-parse", "--is-inside-work-tree")
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def run_git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command in project_root."""
    return subprocess.run(
        ["git", *args],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )


def collect_file_changes(project_root: Path) -> list[DiffFileChange]:
    """Collect tracked and untracked working tree changes."""
    changes: dict[str, DiffFileChange] = {}
    name_status = run_git(project_root, "diff", "--name-status", "HEAD").stdout
    numstat = run_git(project_root, "diff", "--numstat", "HEAD").stdout
    status = run_git(
        project_root,
        "status",
        "--short",
        "--untracked-files=all",
    ).stdout
    parse_name_status(name_status, changes)
    parse_numstat(numstat, changes)
    parse_untracked(status, changes)
    return sorted(changes.values(), key=lambda change: change.path)


def parse_name_status(output: str, changes: dict[str, DiffFileChange]) -> None:
    """Parse git diff --name-status output."""
    for raw_line in output.splitlines():
        parts = raw_line.split("\t")
        if not parts:
            continue
        code = parts[0]
        status = code[0]
        if status == "R" and len(parts) >= 3:
            old_path = normalize_path(parts[1])
            path = normalize_path(parts[2])
            changes[path] = DiffFileChange(
                path=path,
                old_path=old_path,
                status="renamed",
            )
        elif len(parts) >= 2:
            path = normalize_path(parts[1])
            changes[path] = DiffFileChange(path=path, status=map_status(status))


def parse_numstat(output: str, changes: dict[str, DiffFileChange]) -> None:
    """Parse git diff --numstat output."""
    for raw_line in output.splitlines():
        parts = raw_line.split("\t")
        if len(parts) < 3:
            continue
        added = parse_line_count(parts[0])
        deleted = parse_line_count(parts[1])
        path = normalize_numstat_path("\t".join(parts[2:]))
        existing = changes.get(path)
        if existing is None:
            existing = DiffFileChange(path=path, status="modified")
        changes[path] = existing.model_copy(
            update={"added_lines": added, "deleted_lines": deleted}
        )


def parse_untracked(output: str, changes: dict[str, DiffFileChange]) -> None:
    """Parse untracked files from git status --short output."""
    for raw_line in output.splitlines():
        if not raw_line.startswith("?? "):
            continue
        path = normalize_path(raw_line[3:])
        changes.setdefault(path, DiffFileChange(path=path, status="added"))


def parse_line_count(value: str) -> int:
    """Parse git numstat line counts, treating binary markers as zero."""
    if value == "-":
        return 0
    return int(value)


def normalize_numstat_path(path: str) -> str:
    """Normalize a numstat path, including simple rename notation."""
    normalized = normalize_path(path)
    if " => " not in normalized:
        return normalized
    # Git may render renames as dir/{old => new}.py. For this milestone, the
    # name-status parser already records the accurate target path, so this is a
    # fallback for unusual numstat-only entries.
    return normalized.split(" => ")[-1].replace("}", "")


def normalize_path(path: str) -> str:
    """Normalize a git path to POSIX separators."""
    return path.strip().replace("\\", "/")


def map_status(status: str) -> ChangeStatus:
    """Map git status letters to VibeBench statuses."""
    if status == "A":
        return "added"
    if status == "D":
        return "deleted"
    return "modified"


def build_analysis(
    changes: list[DiffFileChange],
    rules: RiskConfig,
) -> DiffAnalysis:
    """Build aggregate diff analysis from file changes."""
    changed_files = sorted({change.path for change in changes})
    deleted_files = sorted(
        change.path for change in changes if change.status == "deleted"
    )
    added_files = sorted(change.path for change in changes if change.status == "added")
    modified_files = sorted(
        change.path for change in changes if change.status == "modified"
    )
    renamed_files = sorted(
        change.path for change in changes if change.status == "renamed"
    )
    test_files_changed = sorted(
        path
        for path in changed_files
        if matches_test_path(path, rules.test_path_patterns)
    )
    tests_deleted = sorted(
        path
        for path in deleted_files
        if matches_test_path(path, rules.test_path_patterns)
    )
    forbidden_paths_touched = sorted(
        path
        for path in changed_files
        if matches_forbidden_path(path, rules.forbidden_paths)
    )
    secret_like_files_touched = sorted(
        path
        for path in changed_files
        if matches_secret_like_path(path, rules.secret_like_paths)
    )
    lockfiles_changed = sorted(
        path for path in changed_files if matches_lockfile(path, rules.lockfiles)
    )
    total_added_lines = sum(change.added_lines for change in changes)
    total_deleted_lines = sum(change.deleted_lines for change in changes)

    return DiffAnalysis(
        git_available=True,
        changed_files=changed_files,
        deleted_files=deleted_files,
        added_files=added_files,
        modified_files=modified_files,
        renamed_files=renamed_files,
        test_files_changed=test_files_changed,
        tests_deleted=tests_deleted,
        forbidden_paths_touched=forbidden_paths_touched,
        secret_like_files_touched=secret_like_files_touched,
        lockfiles_changed=lockfiles_changed,
        total_added_lines=total_added_lines,
        total_deleted_lines=total_deleted_lines,
        total_patch_lines=total_added_lines + total_deleted_lines,
        changed_file_count=len(changed_files),
        file_changes=changes,
    )


def build_findings(
    analysis: DiffAnalysis,
    rules: RiskConfig,
    legacy_rules: RiskRulesConfig | RiskConfig | None = None,
) -> list[RiskFinding]:
    """Create risk findings from a diff analysis."""
    findings: list[RiskFinding] = []

    if analysis.forbidden_paths_touched:
        findings.append(
            RiskFinding(
                severity="critical",
                code="forbidden_paths_touched",
                message="Forbidden paths were touched.",
                paths=analysis.forbidden_paths_touched,
            )
        )
    if analysis.secret_like_files_touched:
        findings.append(
            RiskFinding(
                severity="high",
                code="secret_like_files_touched",
                message="Secret-like file paths were touched.",
                paths=analysis.secret_like_files_touched,
            )
        )
    warn_if_tests_deleted = getattr(legacy_rules, "warn_if_tests_deleted", True)
    warn_if_lockfiles_changed = getattr(
        legacy_rules, "warn_if_lockfiles_changed", True
    )

    if warn_if_tests_deleted and analysis.tests_deleted:
        findings.append(
            RiskFinding(
                severity="high",
                code="tests_deleted",
                message="Test files were deleted.",
                paths=analysis.tests_deleted,
            )
        )
    if analysis.test_files_changed:
        findings.append(
            RiskFinding(
                severity="info",
                code="test_files_changed",
                message="Test files changed.",
                paths=analysis.test_files_changed,
            )
        )
    if warn_if_lockfiles_changed and analysis.lockfiles_changed:
        findings.append(
            RiskFinding(
                severity="warning",
                code="lockfiles_changed",
                message="Lockfiles changed.",
                paths=analysis.lockfiles_changed,
            )
        )
    if analysis.total_patch_lines > rules.max_patch_lines:
        findings.append(
            RiskFinding(
                severity="warning",
                code="large_patch",
                message=(
                    "Patch is larger than configured threshold "
                    f"({analysis.total_patch_lines} > {rules.max_patch_lines})."
                ),
            )
        )
    if analysis.changed_file_count > rules.max_changed_files:
        findings.append(
            RiskFinding(
                severity="warning",
                code="many_files_changed",
                message=(
                    f"Many files changed "
                    f"({analysis.changed_file_count} > {rules.max_changed_files})."
                ),
                paths=analysis.changed_files,
            )
        )

    return findings


def matches_forbidden_path(path: str, patterns: list[str]) -> bool:
    """Return whether path matches configured forbidden path rules."""
    for pattern in patterns:
        normalized = normalize_path(pattern)
        if normalized.endswith("/") and path.startswith(normalized):
            return True
        if path == normalized:
            return True
        if fnmatch.fnmatch(path, normalized):
            return True
    return False


def matches_secret_like_path(path: str, patterns: list[str]) -> bool:
    """Return whether a path matches configured secret-like patterns."""
    return matches_any_path_pattern(path, patterns, case_sensitive=False)


def matches_lockfile(path: str, patterns: list[str]) -> bool:
    """Return whether a path matches configured lockfile patterns."""
    return matches_any_path_pattern(path, patterns, case_sensitive=True)


def matches_test_path(path: str, patterns: list[str]) -> bool:
    """Return whether path matches configured test path patterns."""
    return matches_any_path_pattern(path, patterns, case_sensitive=True)


def matches_any_path_pattern(
    path: str,
    patterns: list[str],
    *,
    case_sensitive: bool,
) -> bool:
    """Match a path against simple directory, glob, name, or substring patterns."""
    normalized = normalize_path(path)
    path_value = normalized if case_sensitive else normalized.lower()
    name = Path(normalized).name
    name_value = name if case_sensitive else name.lower()
    for raw_pattern in patterns:
        pattern = normalize_path(raw_pattern)
        pattern_value = pattern if case_sensitive else pattern.lower()
        if pattern_value.endswith("/") and (
            path_value.startswith(pattern_value) or f"/{pattern_value}" in path_value
        ):
            return True
        if any(char in pattern_value for char in "*?["):
            if fnmatch.fnmatch(path_value, pattern_value):
                return True
            if fnmatch.fnmatch(name_value, pattern_value):
                return True
        elif path_value == pattern_value or name_value == pattern_value:
            return True
        elif pattern_value in path_value:
            return True
    return False


def as_risk_config(rules: RiskConfig | RiskRulesConfig) -> RiskConfig:
    """Convert legacy risk rules to the active risk config model."""
    if isinstance(rules, RiskConfig):
        return rules
    return RiskConfig(
        max_patch_lines=rules.large_patch_lines,
        forbidden_paths=rules.forbidden_paths,
    )
