import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from vibebench import package_check as package_check_module
from vibebench.cli import app
from vibebench.package_check import run_package_check

runner = CliRunner()


def write_ready_project(
    root: Path,
    *,
    version: str = "0.4.0",
    readme: str = "README.md",
) -> None:
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "README.zh-CN.md").write_text("# Demo\n", encoding="utf-8")
    (root / "LICENSE").write_text("Apache-2.0\n", encoding="utf-8")
    (root / "docs" / "quickstart.md").write_text("# Quickstart\n", encoding="utf-8")
    (root / "docs" / "github-actions.md").write_text("# Actions\n", encoding="utf-8")
    (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        f"""
[project]
name = "vibebench-arena"
version = "{version}"
readme = "{readme}"
requires-python = ">=3.11"
license = {{ file = "LICENSE" }}

[project.scripts]
vibebench = "vibebench.cli:main"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_package_check_ready_project_passes(tmp_path: Path) -> None:
    write_ready_project(tmp_path)

    result = runner.invoke(app, ["package-check", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Package readiness" in result.stdout
    assert "ready" in result.stdout


def test_package_check_missing_pyproject_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["package-check", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "pyproject.toml is missing" in result.stdout


def test_package_check_version_mismatch_fails(tmp_path: Path) -> None:
    write_ready_project(tmp_path, version="9.9.9")

    result = run_package_check(tmp_path)

    assert result.status == "not-ready"
    version_check = next(
        check for check in result.checks if check.name == "version_match"
    )
    assert version_check.status == "failed"
    assert "does not match" in version_check.message


def test_package_check_missing_referenced_readme_fails(tmp_path: Path) -> None:
    write_ready_project(tmp_path, readme="MISSING.md")

    result = run_package_check(tmp_path)

    readme_check = next(check for check in result.checks if check.name == "readme")
    assert readme_check.status == "failed"
    assert "missing" in readme_check.message


def test_package_check_missing_license_fails(tmp_path: Path) -> None:
    write_ready_project(tmp_path)
    (tmp_path / "LICENSE").unlink()

    result = run_package_check(tmp_path)

    license_check = next(check for check in result.checks if check.name == "license")
    assert license_check.status == "failed"


def test_package_check_json_output_is_pure_json(tmp_path: Path) -> None:
    write_ready_project(tmp_path)

    result = runner.invoke(
        app,
        ["package-check", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready"
    assert payload["package_name"] == "vibebench-arena"
    assert payload["version"] == "0.4.0"
    assert isinstance(payload["checks"], list)
    assert "build" not in payload
    assert all(check["name"] != "build_readiness" for check in payload["checks"])


def fake_successful_build(
    monkeypatch,
    artifact: str = "demo-0.4.0-py3-none-any.whl",
) -> None:
    def fake_find_spec(name: str):
        return object() if name == "build" else None

    def fake_run(command, cwd, text, capture_output, check, timeout):
        output_dir = Path(command[command.index("--outdir") + 1])
        output_dir.joinpath(artifact).write_text("wheel", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="built", stderr="")

    monkeypatch.setattr(
        package_check_module.importlib.util,
        "find_spec",
        fake_find_spec,
    )
    monkeypatch.setattr(package_check_module.subprocess, "run", fake_run)


def test_package_check_build_success_can_be_faked(tmp_path: Path, monkeypatch) -> None:
    write_ready_project(tmp_path)
    fake_successful_build(monkeypatch)

    result = run_package_check(tmp_path, build=True)

    assert result.status == "ready"
    assert result.build is not None
    assert result.build.requested is True
    assert result.build.tool == "python -m build"
    assert result.build.tool_available is True
    assert result.build.artifacts == ["demo-0.4.0-py3-none-any.whl"]
    assert result.build.output_dir is None
    build_check = next(
        check for check in result.checks if check.name == "build_readiness"
    )
    assert build_check.status == "passed"


def test_package_check_build_json_output_is_pure_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_ready_project(tmp_path)
    fake_successful_build(monkeypatch)

    result = runner.invoke(
        app,
        ["package-check", "--project-root", str(tmp_path), "--build", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready"
    assert payload["build"]["requested"] is True
    assert payload["build"]["status"] == "passed"
    assert payload["build"]["tool_available"] is True
    assert payload["build"]["artifacts"] == ["demo-0.4.0-py3-none-any.whl"]
    assert payload["build"]["output_dir"] is None
    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["build_readiness"]["status"] == "passed"


def test_package_check_build_missing_tool_reports_advice(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_ready_project(tmp_path)
    monkeypatch.setattr(
        package_check_module.importlib.util,
        "find_spec",
        lambda name: None,
    )

    result = run_package_check(tmp_path, build=True, advice=True)

    assert result.status == "not-ready"
    assert result.build is not None
    assert result.build.requested is True
    assert result.build.tool_available is False
    assert result.build.tool is None
    assert "No local build tool" in result.build.message
    assert "rerun package-check --build" in (result.build.advice or "")
    build_check = next(
        check for check in result.checks if check.name == "build_readiness"
    )
    assert build_check.status == "failed"
    assert "advice" in package_check_module.package_check_payload(
        build_check,
        include_advice=True,
    )


def test_package_check_write_json(tmp_path: Path) -> None:
    write_ready_project(tmp_path)
    output_path = tmp_path / "package-check.json"

    result = runner.invoke(
        app,
        [
            "package-check",
            "--project-root",
            str(tmp_path),
            "--write-json",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "ready"
    assert payload["package_name"] == "vibebench-arena"


def test_package_check_write_summary(tmp_path: Path) -> None:
    write_ready_project(tmp_path)
    output_path = tmp_path / "package-check.md"

    result = runner.invoke(
        app,
        [
            "package-check",
            "--project-root",
            str(tmp_path),
            "--write-summary",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    markdown = output_path.read_text(encoding="utf-8")
    assert "# VibeBench Package Check" in markdown
    assert "| Check | Status | Message |" in markdown
    assert "ready" in markdown


def test_package_check_json_stdout_stays_pure_when_writing(tmp_path: Path) -> None:
    write_ready_project(tmp_path)
    output_path = tmp_path / "package-check.json"

    result = runner.invoke(
        app,
        [
            "package-check",
            "--project-root",
            str(tmp_path),
            "--json",
            "--write-json",
            str(output_path),
        ],
    )

    stdout_payload = json.loads(result.stdout)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert stdout_payload == file_payload


def test_package_check_missing_output_parent_fails(tmp_path: Path) -> None:
    write_ready_project(tmp_path)
    output_path = tmp_path / "missing" / "package-check.json"

    result = runner.invoke(
        app,
        [
            "package-check",
            "--project-root",
            str(tmp_path),
            "--write-json",
            str(output_path),
        ],
    )

    assert result.exit_code == 1
    assert "output parent does not exist" in result.output


def test_package_check_output_directory_fails(tmp_path: Path) -> None:
    write_ready_project(tmp_path)

    result = runner.invoke(
        app,
        [
            "package-check",
            "--project-root",
            str(tmp_path),
            "--write-summary",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert "output path is a directory" in result.output


def test_package_check_advice_includes_advice_fields(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["package-check", "--project-root", str(tmp_path), "--json", "--advice"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    failed_checks = [
        check for check in payload["checks"] if check["status"] == "failed"
    ]
    assert failed_checks
    assert all("advice" in check for check in failed_checks)


def test_package_check_does_not_require_network(tmp_path: Path, monkeypatch) -> None:
    write_ready_project(tmp_path)

    def fail_network(*args, **kwargs):
        raise AssertionError("network should not be used")

    monkeypatch.setattr("urllib.request.urlopen", fail_network)

    result = runner.invoke(app, ["package-check", "--project-root", str(tmp_path)])

    assert result.exit_code == 0


def test_existing_pr_comment_help_still_works() -> None:
    result = runner.invoke(app, ["pr-comment", "--help"])

    assert result.exit_code == 0
    assert result.stdout
    assert "Usage" in result.stdout or "pr-comment" in result.stdout
