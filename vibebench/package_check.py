"""Local package and installation readiness checks for VibeBench."""

from __future__ import annotations

import importlib
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from vibebench import __version__
from vibebench.report import ReportError

PackageCheckStatus = Literal["passed", "failed"]

REQUIRED_DOCS = [
    "README.md",
    "README.zh-CN.md",
    "docs/quickstart.md",
    "docs/github-actions.md",
    "ROADMAP.md",
]


@dataclass(frozen=True)
class PackageReadinessCheck:
    """One package readiness check."""

    name: str
    status: PackageCheckStatus
    message: str
    advice: str | None = None


@dataclass(frozen=True)
class PackageReadinessResult:
    """Complete package readiness result."""

    project_root: Path
    package_name: str | None
    version: str | None
    checks: list[PackageReadinessCheck]
    advice: bool = False

    @property
    def ready(self) -> bool:
        """Return whether every required package check passed."""
        return all(check.status == "passed" for check in self.checks)

    @property
    def status(self) -> str:
        """Return package readiness status."""
        return "ready" if self.ready else "not-ready"


def run_package_check(
    project_root: Path,
    *,
    advice: bool = False,
) -> PackageReadinessResult:
    """Run local package readiness checks without network access."""
    root = project_root.resolve()
    pyproject_path = root / "pyproject.toml"
    checks: list[PackageReadinessCheck] = []
    metadata: dict[str, Any] | None = None

    if pyproject_path.is_file():
        checks.append(passed("pyproject", "pyproject.toml exists"))
        try:
            payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            checks.append(
                failed("pyproject_parse", f"Unable to parse pyproject.toml: {exc}")
            )
            payload = {}
        project = payload.get("project")
        if isinstance(project, dict):
            metadata = project
            checks.append(passed("project_metadata", "project metadata exists"))
        else:
            checks.append(failed("project_metadata", "[project] metadata is missing"))
    else:
        checks.append(failed("pyproject", "pyproject.toml is missing"))

    package_name = value_as_str(metadata, "name")
    version = value_as_str(metadata, "version")

    if metadata is not None:
        checks.extend(metadata_checks(root, metadata, package_name, version))
    else:
        checks.extend(missing_metadata_checks())

    checks.extend(import_checks())
    checks.extend(documentation_checks(root))

    if advice:
        checks = [with_advice(check) for check in checks]

    return PackageReadinessResult(
        project_root=root,
        package_name=package_name,
        version=version,
        checks=checks,
        advice=advice,
    )


def metadata_checks(
    project_root: Path,
    metadata: dict[str, Any],
    package_name: str | None,
    version: str | None,
) -> list[PackageReadinessCheck]:
    """Return package metadata checks."""
    checks: list[PackageReadinessCheck] = []

    checks.append(
        passed("project_name", f"Project name: {package_name}")
        if package_name
        else failed("project_name", "Project name is missing")
    )
    checks.append(
        passed("project_version", f"Project version: {version}")
        if version
        else failed("project_version", "Project version is missing")
    )
    if version:
        checks.append(
            passed(
                "version_match",
                f"pyproject version matches package version {version}",
            )
            if version == __version__
            else failed(
                "version_match",
                (
                    f"pyproject version {version} does not match "
                    f"vibebench.__version__ {__version__}"
                ),
            )
        )

    checks.append(check_readme(project_root, metadata.get("readme")))
    checks.append(check_license(project_root, metadata.get("license")))
    requires_python = metadata.get("requires-python")
    checks.append(
        passed("requires_python", f"requires-python: {requires_python}")
        if isinstance(requires_python, str) and requires_python.strip()
        else failed("requires_python", "requires-python is missing")
    )
    checks.append(check_console_script(metadata.get("scripts")))
    return checks


def missing_metadata_checks() -> list[PackageReadinessCheck]:
    """Return dependent checks when [project] metadata is unavailable."""
    return [
        failed("project_name", "Project name is missing"),
        failed("project_version", "Project version is missing"),
        failed("readme", "README reference is missing"),
        failed("license", "License reference is missing"),
        failed("requires_python", "requires-python is missing"),
        failed("console_script", "Console script metadata is missing"),
    ]


def check_readme(project_root: Path, readme: object) -> PackageReadinessCheck:
    """Check the pyproject README reference."""
    path: Path | None = None
    if isinstance(readme, str):
        path = project_root / readme
    elif isinstance(readme, dict) and isinstance(readme.get("file"), str):
        path = project_root / str(readme["file"])
    if path is None:
        return failed("readme", "README reference is missing")
    if path.is_file():
        return passed("readme", f"README file exists: {path.name}")
    return failed("readme", f"README file referenced by pyproject is missing: {path}")


def check_license(project_root: Path, license_value: object) -> PackageReadinessCheck:
    """Check the pyproject license reference and repository LICENSE file."""
    if isinstance(license_value, dict) and isinstance(license_value.get("file"), str):
        path = project_root / str(license_value["file"])
        if path.is_file():
            return passed("license", f"License file exists: {path.name}")
        return failed(
            "license",
            f"License file referenced by pyproject is missing: {path}",
        )
    if (project_root / "LICENSE").is_file():
        return passed("license", "LICENSE exists")
    return failed("license", "LICENSE is missing")


def check_console_script(scripts: object) -> PackageReadinessCheck:
    """Check that the vibebench console script is defined."""
    if not isinstance(scripts, dict):
        return failed("console_script", "[project.scripts] is missing")
    entrypoint = scripts.get("vibebench")
    if entrypoint == "vibebench.cli:main":
        return passed("console_script", "Console script vibebench = vibebench.cli:main")
    return failed(
        "console_script",
        "Console script vibebench = vibebench.cli:main is missing",
    )


def import_checks() -> list[PackageReadinessCheck]:
    """Check package and CLI imports."""
    checks: list[PackageReadinessCheck] = []
    checks.append(check_import("package_import", "vibebench"))
    checks.append(check_import("cli_import", "vibebench.cli"))
    return checks


def check_import(name: str, module: str) -> PackageReadinessCheck:
    """Check that a module can be imported."""
    try:
        importlib.import_module(module)
    except Exception as exc:  # noqa: BLE001 - report import readiness without crashing.
        return failed(name, f"Unable to import {module}: {exc}")
    return passed(name, f"Imported {module}")


def documentation_checks(project_root: Path) -> list[PackageReadinessCheck]:
    """Check key documentation files."""
    return [
        passed(f"doc:{relative_path}", f"Documentation exists: {relative_path}")
        if (project_root / relative_path).is_file()
        else failed(
            f"doc:{relative_path}",
            f"Documentation file is missing: {relative_path}",
        )
        for relative_path in REQUIRED_DOCS
    ]


def package_check_json_payload(result: PackageReadinessResult) -> dict[str, object]:
    """Return a deterministic JSON payload for package readiness."""
    return {
        "status": result.status,
        "project_root": str(result.project_root),
        "package_name": result.package_name,
        "version": result.version,
        "checks": [
            package_check_payload(check, include_advice=result.advice)
            for check in result.checks
        ],
    }


def package_check_payload(
    check: PackageReadinessCheck,
    *,
    include_advice: bool,
) -> dict[str, object]:
    """Return a JSON-safe package readiness check payload."""
    payload: dict[str, object] = {
        "name": check.name,
        "status": check.status,
        "message": check.message,
    }
    if include_advice and check.advice:
        payload["advice"] = check.advice
    return payload


def with_advice(check: PackageReadinessCheck) -> PackageReadinessCheck:
    """Attach actionable advice for failed checks."""
    if check.status == "passed":
        return check
    return PackageReadinessCheck(
        name=check.name,
        status=check.status,
        message=check.message,
        advice=advice_for_check(check),
    )


def advice_for_check(check: PackageReadinessCheck) -> str:
    """Return concise advice for a failed package check."""
    if check.name == "pyproject":
        return "Create pyproject.toml with a [project] section."
    if check.name == "pyproject_parse":
        return "Fix pyproject.toml syntax and rerun package-check."
    if check.name == "project_metadata":
        return "Add a [project] table to pyproject.toml."
    if check.name == "project_name":
        return "Set project.name in pyproject.toml."
    if check.name == "project_version":
        return "Set project.version in pyproject.toml."
    if check.name == "version_match":
        return "Keep pyproject.toml version and vibebench.__version__ in sync."
    if check.name == "readme":
        return "Ensure the pyproject readme path exists, usually README.md."
    if check.name == "license":
        return "Add a LICENSE file and reference it from pyproject.toml."
    if check.name == "requires_python":
        return "Set requires-python, for example >=3.11."
    if check.name == "console_script":
        return "Define vibebench = vibebench.cli:main under [project.scripts]."
    if check.name.endswith("_import"):
        return "Fix import errors before packaging or installing VibeBench."
    if check.name.startswith("doc:"):
        return "Restore the missing documentation file or update the docs checklist."
    return "Fix this package metadata issue and rerun package-check."


def passed(name: str, message: str) -> PackageReadinessCheck:
    """Build a passing package readiness check."""
    return PackageReadinessCheck(name=name, status="passed", message=message)


def failed(name: str, message: str) -> PackageReadinessCheck:
    """Build a failing package readiness check."""
    return PackageReadinessCheck(name=name, status="failed", message=message)


def value_as_str(metadata: dict[str, Any] | None, key: str) -> str | None:
    """Return a non-empty metadata string value."""
    if metadata is None:
        return None
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def ensure_package_ready(result: PackageReadinessResult) -> None:
    """Raise ReportError when package readiness failed."""
    if result.ready:
        return
    failed_checks = [check for check in result.checks if check.status == "failed"]
    message = "; ".join(f"{check.name}: {check.message}" for check in failed_checks)
    raise ReportError(message or "Package readiness failed")
