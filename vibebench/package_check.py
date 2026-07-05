"""Local package and installation readiness checks for VibeBench."""

from __future__ import annotations

import base64
import hashlib
import importlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from vibebench import __version__
from vibebench.report import ReportError

PackageCheckStatus = Literal["passed", "failed"]
PACKAGE_CHECK_JSON = "package-check.json"
PACKAGE_CHECK_SUMMARY = "package-check.md"

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
class PackageBuildReadiness:
    """Local package build readiness details."""

    requested: bool
    status: PackageCheckStatus
    tool: str | None
    tool_available: bool
    artifacts: list[str]
    output_dir: Path | None
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
    build: PackageBuildReadiness | None = None

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
    build: bool = False,
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

    build_result: PackageBuildReadiness | None = None
    if build:
        build_result = run_build_readiness_check(root)
        checks.append(
            PackageReadinessCheck(
                name="build_readiness",
                status=build_result.status,
                message=build_result.message,
                advice=build_result.advice,
            )
        )

    if advice:
        checks = [with_advice(check) for check in checks]

    return PackageReadinessResult(
        project_root=root,
        package_name=package_name,
        version=version,
        checks=checks,
        advice=advice,
        build=build_result,
    )


def run_build_readiness_check(project_root: Path) -> PackageBuildReadiness:
    """Run an opt-in local-only build readiness check."""
    tools = select_build_tools(project_root)
    if not tools:
        message = "No local build tool is available"
        return PackageBuildReadiness(
            requested=True,
            status="failed",
            tool=None,
            tool_available=False,
            artifacts=[],
            output_dir=None,
            message=message,
            advice=(
                "Install local build tooling such as the 'build' module and the "
                "project build backend, then rerun package-check --build."
            ),
        )

    last_failure: PackageBuildReadiness | None = None
    with tempfile.TemporaryDirectory(prefix="vibebench-package-build-") as temp_dir:
        output_dir = Path(temp_dir)
        for tool in tools:
            if tool == "stdlib wheel":
                return run_stdlib_wheel_build(project_root, output_dir, last_failure)
            result = run_subprocess_build_tool(project_root, output_dir, tool)
            if result.status == "passed":
                return result
            last_failure = result
            if not can_try_stdlib_after_failure(result):
                return result

    return last_failure or PackageBuildReadiness(
        requested=True,
        status="failed",
        tool=None,
        tool_available=False,
        artifacts=[],
        output_dir=None,
        message="No local build tool is available",
        advice="Install local build tooling and rerun package-check --build.",
    )


def select_build_tools(project_root: Path) -> list[str]:
    """Select local-only build commands to try in preference order."""
    tools: list[str] = []
    if importlib.util.find_spec("build") is not None:
        tools.append("python -m build")
    if importlib.util.find_spec("pip") is not None:
        tools.append("python -m pip wheel")
    if supports_stdlib_wheel_build(project_root):
        tools.append("stdlib wheel")
    return tools


def run_subprocess_build_tool(
    project_root: Path,
    output_dir: Path,
    tool: str,
) -> PackageBuildReadiness:
    """Run a subprocess-backed local build command."""
    command = build_command(tool, output_dir)
    try:
        completed = subprocess.run(
            command,
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return PackageBuildReadiness(
            requested=True,
            status="failed",
            tool=tool,
            tool_available=True,
            artifacts=[],
            output_dir=None,
            message=f"Local build failed with {tool}: {exc}",
            advice=build_failure_advice(tool),
        )

    artifacts = sorted(path.name for path in output_dir.iterdir() if path.is_file())
    if completed.returncode != 0:
        detail = build_failure_detail(completed)
        return PackageBuildReadiness(
            requested=True,
            status="failed",
            tool=tool,
            tool_available=True,
            artifacts=artifacts,
            output_dir=None,
            message=f"Local build failed with {tool}: {detail}",
            advice=build_failure_advice(tool),
        )
    if not artifacts:
        return PackageBuildReadiness(
            requested=True,
            status="failed",
            tool=tool,
            tool_available=True,
            artifacts=[],
            output_dir=None,
            message=f"Local build with {tool} produced no artifacts",
            advice=(
                "Check pyproject build configuration and rerun "
                "package-check --build."
            ),
        )

    artifact_text = ", ".join(artifacts)
    return PackageBuildReadiness(
        requested=True,
        status="passed",
        tool=tool,
        tool_available=True,
        artifacts=artifacts,
        output_dir=None,
        message=(
            f"Local build produced {artifact_text}; temporary output was cleaned up"
        ),
    )


def build_command(tool: str, output_dir: Path) -> list[str]:
    """Return the local-only build command for the selected tool."""
    if tool == "python -m build":
        return [
            sys.executable,
            "-m",
            "build",
            "--sdist",
            "--wheel",
            "--outdir",
            str(output_dir),
            "--no-isolation",
        ]
    return [
        sys.executable,
        "-m",
        "pip",
        "wheel",
        ".",
        "--no-deps",
        "--no-index",
        "--no-build-isolation",
        "--wheel-dir",
        str(output_dir),
    ]


def build_failure_detail(completed: subprocess.CompletedProcess[str]) -> str:
    """Return a concise build failure detail."""
    output = (completed.stderr or completed.stdout or "").strip()
    if output:
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if lines:
            return f"exit code {completed.returncode}; {lines[-1]}"
    return f"exit code {completed.returncode}"


def build_failure_advice(tool: str) -> str:
    """Return advice for a local build failure."""
    if tool == "python -m build":
        return (
            "Ensure the 'build' module and pyproject build backend are installed "
            "locally; package-check --build uses --no-isolation and will not "
            "install missing tools."
        )
    return (
        "Ensure pip and the pyproject build backend are installed locally; the "
        "pip fallback uses --no-index and --no-build-isolation, so it will not "
        "download or install missing build tools."
    )


def can_try_stdlib_after_failure(result: PackageBuildReadiness) -> bool:
    """Return whether a backend/tooling failure can fall back to stdlib wheel."""
    if result.status == "passed":
        return False
    message = result.message.lower()
    backend_missing = "cannot import" in message or "no module named" in message
    return backend_missing and result.tool in {"python -m build", "python -m pip wheel"}


def supports_stdlib_wheel_build(project_root: Path) -> bool:
    """Return whether the project has enough metadata for a stdlib wheel build."""
    try:
        payload = tomllib.loads(
            project_root.joinpath("pyproject.toml").read_text(encoding="utf-8")
        )
    except (OSError, tomllib.TOMLDecodeError):
        return False
    metadata = payload.get("project")
    if not isinstance(metadata, dict):
        return False
    return bool(
        value_as_str(metadata, "name")
        and wheel_package_paths(project_root, payload)
    )


def run_stdlib_wheel_build(
    project_root: Path,
    output_dir: Path,
    previous_failure: PackageBuildReadiness | None,
) -> PackageBuildReadiness:
    """Build a pure-Python wheel with stdlib packaging primitives."""
    try:
        artifact = build_stdlib_wheel(project_root, output_dir)
    except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
        return PackageBuildReadiness(
            requested=True,
            status="failed",
            tool="stdlib wheel",
            tool_available=True,
            artifacts=[],
            output_dir=None,
            message=f"Local stdlib wheel build failed: {exc}",
            advice="Install pyproject build tooling and rerun package-check --build.",
        )

    note = ""
    if previous_failure is not None:
        note = f" after {previous_failure.tool} was unavailable locally"
    return PackageBuildReadiness(
        requested=True,
        status="passed",
        tool="stdlib wheel",
        tool_available=True,
        artifacts=[artifact.name],
        output_dir=None,
        message=(
            f"Local stdlib wheel build produced {artifact.name}{note}; "
            "temporary output was cleaned up"
        ),
    )


def build_stdlib_wheel(project_root: Path, output_dir: Path) -> Path:
    """Create a minimal pure-Python wheel without network or installed tooling."""
    payload = tomllib.loads(
        project_root.joinpath("pyproject.toml").read_text(encoding="utf-8")
    )
    metadata = payload.get("project")
    if not isinstance(metadata, dict):
        raise ValueError("[project] metadata is missing")
    package_name = value_as_str(metadata, "name")
    version = value_as_str(metadata, "version")
    if not package_name or not version:
        raise ValueError("project name and version are required")

    packages = wheel_package_paths(project_root, payload)
    if not packages:
        raise ValueError("no pure-Python package paths are available")

    wheel_name = f"{wheel_safe_name(package_name)}-{version}-py3-none-any.whl"
    output_path = output_dir / wheel_name
    dist_info = f"{wheel_safe_name(package_name)}-{version}.dist-info"
    records: list[str] = []

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as wheel:
        for package_path in packages:
            for file_path in sorted(package_path.rglob("*.py")):
                relative = file_path.relative_to(project_root).as_posix()
                write_wheel_file(wheel, records, relative, file_path.read_bytes())
        write_wheel_file(
            wheel,
            records,
            f"{dist_info}/METADATA",
            wheel_metadata(metadata).encode("utf-8"),
        )
        write_wheel_file(
            wheel,
            records,
            f"{dist_info}/WHEEL",
            wheel_file_metadata().encode("utf-8"),
        )
        scripts = metadata.get("scripts")
        if isinstance(scripts, dict) and scripts:
            write_wheel_file(
                wheel,
                records,
                f"{dist_info}/entry_points.txt",
                wheel_entry_points(scripts).encode("utf-8"),
            )
        record_path = f"{dist_info}/RECORD"
        records.append(f"{record_path},,")
        wheel.writestr(record_path, "\n".join(records) + "\n")
    return output_path


def wheel_package_paths(project_root: Path, pyproject: dict[str, Any]) -> list[Path]:
    """Return package directories for the stdlib wheel fallback."""
    packages = hatch_wheel_packages(pyproject)
    if not packages:
        project = pyproject.get("project")
        if isinstance(project, dict):
            name = value_as_str(project, "name")
            if name:
                packages = [name.replace("-", "_")]
    paths = [project_root / package for package in packages]
    return [path for path in paths if path.is_dir()]


def hatch_wheel_packages(pyproject: dict[str, Any]) -> list[str]:
    """Return hatch wheel package paths when configured."""
    tool = pyproject.get("tool")
    if not isinstance(tool, dict):
        return []
    hatch = tool.get("hatch")
    if not isinstance(hatch, dict):
        return []
    build = hatch.get("build")
    if not isinstance(build, dict):
        return []
    targets = build.get("targets")
    if not isinstance(targets, dict):
        return []
    wheel = targets.get("wheel")
    if not isinstance(wheel, dict):
        return []
    packages = wheel.get("packages")
    if not isinstance(packages, list):
        return []
    return [package for package in packages if isinstance(package, str)]


def write_wheel_file(
    wheel: zipfile.ZipFile,
    records: list[str],
    path: str,
    data: bytes,
) -> None:
    """Write one wheel file and append its RECORD entry."""
    wheel.writestr(path, data)
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest())
    encoded_digest = digest.rstrip(b"=").decode("ascii")
    records.append(f"{path},sha256={encoded_digest},{len(data)}")


def wheel_metadata(metadata: dict[str, Any]) -> str:
    """Return minimal wheel METADATA content."""
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {value_as_str(metadata, 'name') or ''}",
        f"Version: {value_as_str(metadata, 'version') or ''}",
    ]
    description = value_as_str(metadata, "description")
    if description:
        lines.append(f"Summary: {description}")
    requires_python = value_as_str(metadata, "requires-python")
    if requires_python:
        lines.append(f"Requires-Python: {requires_python}")
    return "\n".join(lines) + "\n"


def wheel_file_metadata() -> str:
    """Return minimal WHEEL metadata."""
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: vibebench package-check",
            "Root-Is-Purelib: true",
            "Tag: py3-none-any",
            "",
        ]
    )


def wheel_entry_points(scripts: dict[object, object]) -> str:
    """Return console script entry points."""
    lines = ["[console_scripts]"]
    for name, target in sorted(scripts.items()):
        if isinstance(name, str) and isinstance(target, str):
            lines.append(f"{name} = {target}")
    lines.append("")
    return "\n".join(lines)


def wheel_safe_name(name: str) -> str:
    """Return a wheel filename-safe distribution name."""
    return re.sub(r"[^A-Za-z0-9.]+", "_", name).strip("_")


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
    payload: dict[str, object] = {
        "status": result.status,
        "project_root": str(result.project_root),
        "package_name": result.package_name,
        "version": result.version,
        "checks": [
            package_check_payload(check, include_advice=result.advice)
            for check in result.checks
        ],
    }
    if result.build is not None:
        payload["build"] = package_build_payload(result.build)
    return payload


def package_build_payload(build: PackageBuildReadiness) -> dict[str, object]:
    """Return a JSON-safe package build readiness payload."""
    return {
        "requested": build.requested,
        "status": build.status,
        "tool": build.tool,
        "tool_available": build.tool_available,
        "artifacts": build.artifacts,
        "output_dir": str(build.output_dir) if build.output_dir else None,
        "message": build.message,
        "advice": build.advice,
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


def write_package_check_json(
    result: PackageReadinessResult,
    output_path: Path,
) -> Path:
    """Write package readiness JSON to a file."""
    validate_output_path(output_path)
    output_path.write_text(
        json.dumps(package_check_json_payload(result), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return output_path


def write_package_check_summary(
    result: PackageReadinessResult,
    output_path: Path,
) -> Path:
    """Write a human-readable package readiness Markdown summary."""
    validate_output_path(output_path)
    output_path.write_text(render_package_check_markdown(result), encoding="utf-8")
    return output_path


def validate_output_path(output_path: Path) -> None:
    """Validate a requested package-check output path."""
    if output_path.exists() and output_path.is_dir():
        raise ReportError(f"Package-check output path is a directory: {output_path}")
    if not output_path.parent.exists():
        raise ReportError(
            f"Package-check output parent does not exist: {output_path.parent}"
        )


def render_package_check_markdown(result: PackageReadinessResult) -> str:
    """Render a human-readable package readiness summary."""
    lines = [
        "# VibeBench Package Check",
        "",
        f"- Project root: {result.project_root}",
        f"- Package name: {result.package_name or ''}",
        f"- Version: {result.version or ''}",
        f"- Status: {result.status}",
        "",
        "| Check | Status | Message |",
        "| --- | --- | --- |",
    ]
    for check in result.checks:
        lines.append(
            "| "
            f"{markdown_cell(check.name)} | "
            f"{markdown_cell(check.status)} | "
            f"{markdown_cell(check.message)} |"
        )
    advice_items = [check for check in result.checks if check.advice]
    if advice_items:
        lines.extend(["", "## Advice", ""])
        for check in advice_items:
            lines.append(f"- {check.name}: {check.advice}")
    lines.append("")
    return "\n".join(lines)


def markdown_cell(value: object) -> str:
    """Escape a Markdown table cell."""
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def with_advice(check: PackageReadinessCheck) -> PackageReadinessCheck:
    """Attach actionable advice for failed checks."""
    if check.status == "passed":
        return check
    return PackageReadinessCheck(
        name=check.name,
        status=check.status,
        message=check.message,
        advice=check.advice or advice_for_check(check),
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
    if check.name == "build_readiness":
        return (
            check.advice
            or "Install local build tooling and rerun package-check --build."
        )
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
