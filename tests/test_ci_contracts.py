import importlib
import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from vibebench.ci import plan_ci_pipeline
from vibebench.cli import app
from vibebench.config import default_config_yaml

runner = CliRunner()

CANONICAL_CI_STEPS = [
    "check",
    "gate",
    "config-check",
    "report",
    "pr-comment",
    "explain",
    "export",
    "badge",
    "status-block",
    "trend",
    "manifest",
    "manifest-check",
    "release-check",
    "annotate",
    "bundle",
    "gh-summary",
]


def write_config(root: Path) -> None:
    config_path = root / ".vibebench" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = default_config_yaml()
    config = config.replace("pytest -q", "python -c 'print(1)'")
    config = config.replace("ruff check .", "python -c 'print(2)'")
    config_path.write_text(config, encoding="utf-8")


def test_import_smoke_for_cli_ci_and_release_check() -> None:
    assert importlib.import_module("vibebench.cli") is not None
    assert importlib.import_module("vibebench.ci") is not None
    assert importlib.import_module("vibebench.release_check") is not None


def test_module_help_smoke_commands() -> None:
    commands = [
        [sys.executable, "-m", "vibebench", "--help"],
        [sys.executable, "-m", "vibebench", "ci", "--help"],
        [sys.executable, "-m", "vibebench", "release-check", "--help"],
    ]
    for command in commands:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        assert result.returncode == 0
        assert "Usage:" in result.stdout


def test_ci_dry_run_human_contract(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path), "--dry-run"])

    assert result.exit_code == 0
    assert "VibeBench CI plan" in result.output
    positions = [result.output.index(step) for step in CANONICAL_CI_STEPS]
    assert positions == sorted(positions)


def test_ci_dry_run_json_contract(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "planned"
    assert payload["dry_run"] is True
    assert [step["name"] for step in payload["steps"]] == CANONICAL_CI_STEPS


def test_ci_dry_run_skip_flag_contract(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--json",
            "--skip-config-check",
            "--skip-manifest",
            "--skip-release-check",
            "--skip-bundle",
            "--skip-gh-summary",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    expected_skips = {
        "config-check": "--skip-config-check",
        "manifest": "--skip-manifest",
        "manifest-check": "--skip-manifest",
        "release-check": "--skip-release-check",
        "bundle": "--skip-bundle",
        "gh-summary": "--skip-gh-summary",
    }
    for step_name, flag_name in expected_skips.items():
        assert steps[step_name]["status"] == "skipped"
        assert steps[step_name]["message"] == f"Skipped by {flag_name}"


def test_plan_ci_pipeline_default_contract() -> None:
    result = plan_ci_pipeline()
    step_names = [step.name for step in result.steps]

    assert result.dry_run is True
    assert step_names == CANONICAL_CI_STEPS
    assert len(step_names) == len(set(step_names))
    steps = {step.name: step for step in result.steps}
    assert steps["release-check"].status == "planned"


def test_plan_ci_pipeline_skip_contract() -> None:
    result = plan_ci_pipeline(skip_release_check=True, skip_manifest=True)
    steps = {step.name: step for step in result.steps}

    assert steps["release-check"].status == "skipped"
    assert steps["release-check"].message == "Skipped by --skip-release-check"
    assert steps["manifest"].status == "skipped"
    assert steps["manifest-check"].status == "skipped"
    assert steps["manifest"].message == "Skipped by --skip-manifest"
    assert steps["manifest-check"].message == "Skipped by --skip-manifest"


def test_ci_release_check_circular_import_regression() -> None:
    ci = importlib.import_module("vibebench.ci")
    release_check = importlib.import_module("vibebench.release_check")
    assert ci is not None
    assert release_check is not None

    importlib.invalidate_caches()
    release_check_again = importlib.import_module("vibebench.release_check")
    ci_again = importlib.import_module("vibebench.ci")
    assert release_check_again is release_check
    assert ci_again is ci
