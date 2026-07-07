"""Read-only project stack detection helpers."""

import json
from dataclasses import dataclass
from pathlib import Path

PYTHON_PROJECT_MARKERS = (
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "tests",
)
NODE_PROJECT_MARKERS = (
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lockb",
    "tsconfig.json",
)
NODE_GLOB_MARKERS = ("vite.config.*", "next.config.*")


@dataclass(frozen=True)
class ProjectDetection:
    """Static project detection result."""

    detected_stacks: list[str]
    detection_reasons: list[str]
    recommended_profile: str
    package_json_present: bool
    package_json_malformed: bool
    package_json_error: str | None
    package_manager_guess: str | None
    node_scripts: list[str]
    has_lint_script: bool
    has_test_script: bool
    has_build_script: bool
    pyproject_present: bool
    requirements_present: bool
    setup_present: bool
    tests_dir_present: bool
    pytest_likely: bool
    ruff_likely: bool


def detect_project(project_root: Path) -> ProjectDetection:
    """Detect stack and tool signals without writing or running project tools."""
    detected_stacks, detection_reasons = detect_project_stacks(project_root)
    scripts, malformed, error = read_package_json_scripts(project_root)
    package_json_present = (project_root / "package.json").is_file()
    pyproject_present = (project_root / "pyproject.toml").is_file()
    requirements_present = (project_root / "requirements.txt").is_file()
    setup_present = any(
        (project_root / marker).is_file() for marker in ("setup.py", "setup.cfg")
    )
    tests_dir_present = (project_root / "tests").is_dir()
    return ProjectDetection(
        detected_stacks=detected_stacks,
        detection_reasons=detection_reasons,
        recommended_profile=select_profile_for_stacks(detected_stacks),
        package_json_present=package_json_present,
        package_json_malformed=malformed,
        package_json_error=error,
        package_manager_guess=package_manager_guess(project_root)
        if "node" in detected_stacks or package_json_present
        else None,
        node_scripts=scripts,
        has_lint_script="lint" in scripts,
        has_test_script="test" in scripts,
        has_build_script="build" in scripts,
        pyproject_present=pyproject_present,
        requirements_present=requirements_present,
        setup_present=setup_present,
        tests_dir_present=tests_dir_present,
        pytest_likely=python_tool_likely(project_root, "pytest") or tests_dir_present,
        ruff_likely=python_tool_likely(project_root, "ruff"),
    )


def detect_project_stacks(project_root: Path) -> tuple[list[str], list[str]]:
    """Detect likely project stacks from filesystem markers."""
    detected: list[str] = []
    reasons: list[str] = []
    for marker in PYTHON_PROJECT_MARKERS:
        if (project_root / marker).exists():
            if "python" not in detected:
                detected.append("python")
            reasons.append(f"python:{marker}")
    for marker in NODE_PROJECT_MARKERS:
        if (project_root / marker).exists():
            if "node" not in detected:
                detected.append("node")
            reasons.append(f"node:{marker}")
    for pattern in NODE_GLOB_MARKERS:
        for path in sorted(project_root.glob(pattern)):
            if "node" not in detected:
                detected.append("node")
            reasons.append(f"node:{path.name}")
    return detected, reasons


def select_profile_for_stacks(detected_stacks: list[str]) -> str:
    """Select the recommended init profile from detected stacks."""
    has_python = "python" in detected_stacks
    has_node = "node" in detected_stacks
    if has_python and has_node:
        return "fullstack"
    if has_node:
        return "node"
    if has_python:
        return "python"
    return "generic"


def read_package_json_scripts(project_root: Path) -> tuple[list[str], bool, str | None]:
    """Return package.json script names and parse status."""
    package_json = project_root / "package.json"
    if not package_json.exists() or not package_json.is_file():
        return [], False, None
    try:
        payload = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], True, str(exc)
    if not isinstance(payload, dict):
        return [], True, "package.json must contain a JSON object"
    scripts = payload.get("scripts")
    if not isinstance(scripts, dict):
        return [], False, None
    return (
        sorted(
            key
            for key, value in scripts.items()
            if isinstance(key, str) and isinstance(value, str)
        ),
        False,
        None,
    )


def package_json_scripts(project_root: Path) -> list[str]:
    """Return valid package.json script names."""
    scripts, _malformed, _error = read_package_json_scripts(project_root)
    return scripts


def package_manager_guess(project_root: Path) -> str:
    """Guess the package manager from lockfiles without creating any files."""
    if (project_root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (project_root / "yarn.lock").exists():
        return "yarn"
    if (project_root / "package-lock.json").exists():
        return "npm"
    if (project_root / "bun.lockb").exists():
        return "bun"
    return "npm"


def python_tool_likely(project_root: Path, tool: str) -> bool:
    """Use conservative text signals to infer whether a Python tool is configured."""
    for path in [
        project_root / "pyproject.toml",
        project_root / "requirements.txt",
        project_root / "setup.cfg",
        project_root / "setup.py",
    ]:
        if not path.is_file():
            continue
        try:
            if tool in path.read_text(encoding="utf-8").lower():
                return True
        except OSError:
            continue
    if tool == "ruff":
        return (project_root / "ruff.toml").is_file() or (
            project_root / ".ruff.toml"
        ).is_file()
    return False
