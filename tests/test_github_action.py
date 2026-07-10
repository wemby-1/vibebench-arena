import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.github_action import action_workflow_payload
from vibebench.workflow_check import workflow_check_payload

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_github_action.py"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

_SPEC = importlib.util.spec_from_file_location("run_github_action", RUNNER_PATH)
assert _SPEC is not None
action_runner = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
sys.modules[_SPEC.name] = action_runner
_SPEC.loader.exec_module(action_runner)

runner = CliRunner()


def test_action_metadata_shape_and_contract() -> None:
    payload = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))

    assert payload["runs"]["using"] == "composite"
    assert payload["branding"]["icon"] == "check-circle"
    assert "actions/upload-artifact@v7" in (ROOT / "action.yml").read_text(
        encoding="utf-8"
    )
    for name in [
        "preset",
        "config",
        "working-directory",
        "fail-on",
        "required-mode",
        "upload-artifacts",
        "artifact-name",
        "retention-days",
        "python-command",
    ]:
        assert name in payload["inputs"]
    for name in [
        "status",
        "score",
        "risk",
        "run-id",
        "run-dir",
        "summary-path",
        "manifest-path",
        "bundle-path",
        "proof-path",
        "artifact-count",
    ]:
        assert name in payload["outputs"]


def test_runner_input_validation_and_safe_command(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".vibebench").mkdir()
    config = workspace / ".vibebench" / "config.yaml"
    config.write_text("project:\n  name: demo\n", encoding="utf-8")
    env = {
        "GITHUB_WORKSPACE": str(workspace),
        "GITHUB_ACTION_PATH": str(ROOT),
        "INPUT_PRESET": "strict",
        "INPUT_CONFIG": ".vibebench/config.yaml",
        "INPUT_WORKING_DIRECTORY": ".",
        "INPUT_FAIL_ON": "quality,regression",
        "INPUT_REQUIRED_MODE": "adoption-policy, adoption",
        "INPUT_UPLOAD_ARTIFACTS": "false",
        "INPUT_ARTIFACT_NAME": "vibebench-evidence",
        "INPUT_RETENTION_DAYS": "7",
        "INPUT_PYTHON_COMMAND": sys.executable,
    }

    inputs = action_runner.read_inputs(env)
    command = action_runner.build_vibebench_command(inputs)

    assert inputs.preset == "strict"
    assert inputs.config == config.resolve()
    assert "--adoption-policy" in command
    assert "--fail-on-regression" in command
    assert ";" not in command


def test_runner_rejects_invalid_inputs_and_traversal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    base_env = {
        "GITHUB_WORKSPACE": str(workspace),
        "GITHUB_ACTION_PATH": str(ROOT),
        "INPUT_PRESET": "minimal",
        "INPUT_WORKING_DIRECTORY": ".",
        "INPUT_UPLOAD_ARTIFACTS": "maybe",
        "INPUT_RETENTION_DAYS": "14",
        "INPUT_PYTHON_COMMAND": "python3",
    }

    try:
        action_runner.read_inputs(base_env)
    except action_runner.ActionInputError as exc:
        assert "upload-artifacts" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid boolean accepted")

    base_env["INPUT_UPLOAD_ARTIFACTS"] = "false"
    base_env["INPUT_WORKING_DIRECTORY"] = ".."
    try:
        action_runner.read_inputs(base_env)
    except action_runner.ActionInputError as exc:
        assert "inside GITHUB_WORKSPACE" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("workspace traversal accepted")


def test_github_output_multiline_format(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "github-output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    action_runner.write_github_outputs({"status": "passed", "artifact-paths": "a\nb"})

    text = output.read_text(encoding="utf-8")
    assert "status=passed" in text
    assert "artifact-paths<<" in text
    assert "\na\nb\n" in text


def test_upload_allowlist_includes_only_evidence_and_optional_proof(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / ".vibebench" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "metrics.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "source.py").write_text("print('not uploaded')\n", encoding="utf-8")
    proof = tmp_path / ".vibebench" / "proof-packet" / "proof.zip"
    proof.parent.mkdir(parents=True)
    proof.write_bytes(b"proof")

    paths = action_runner.collect_upload_paths(run_dir, proof_path=proof)
    relative = [path.relative_to(tmp_path).as_posix() for path in paths]

    assert ".vibebench/runs/run-1/metrics.json" in relative
    assert ".vibebench/runs/run-1/manifest.json" in relative
    assert ".vibebench/proof-packet/proof.zip" in relative
    assert "source.py" not in relative


def test_generated_action_workflows_are_deterministic() -> None:
    payload = action_workflow_payload(
        preset="proof",
        config=".vibebench/config.yaml",
        required_mode="adoption-policy",
        upload_artifacts=True,
    )

    workflow = payload["workflow"]
    assert "uses: wemby-1/vibebench-arena@main" in workflow
    assert "preset: proof" in workflow
    assert "upload-artifacts: true" in workflow
    assert "@main is not a stable release" in payload["preview_warning"]
    assert payload == action_workflow_payload(
        preset="proof",
        config=".vibebench/config.yaml",
        required_mode="adoption-policy",
        upload_artifacts=True,
    )


def test_cli_github_action_json_and_output_file(tmp_path: Path) -> None:
    output = tmp_path / "vibebench.yml"
    result = runner.invoke(
        app,
        [
            "github-action",
            "--preset",
            "minimal",
            "--json",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["workflow_written"] is True
    assert output.read_text(encoding="utf-8") == payload["workflow"]


def test_workflow_check_detects_reusable_action_fixture() -> None:
    payload = workflow_check_payload(
        ROOT / "examples" / "action-consumer",
        check_all=True,
        required_ci_modes=["adoption-policy"],
    )

    assert payload["status"] == "passed"
    assert "adoption-policy" in payload["detected_ci_modes"]
    assert payload["usable_for_vibebench_ci"] is True


def test_action_smoke_workflow_structure() -> None:
    payload = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "action-smoke.yml").read_text(
            encoding="utf-8"
        )
    )
    text = (ROOT / ".github" / "workflows" / "action-smoke.yml").read_text(
        encoding="utf-8"
    )

    assert "uses: ./" in text
    assert "working-directory: examples/action-consumer" in text
    assert payload["jobs"]["action-smoke"]["strategy"]["matrix"]["preset"] == [
        "minimal",
        "strict",
        "proof",
    ]


def test_action_consumer_fixture_has_no_generated_runs() -> None:
    fixture = ROOT / "examples" / "action-consumer"

    assert (fixture / ".vibebench" / "config.yaml").is_file()
    assert not (fixture / ".vibebench" / "runs").exists()
    assert "demonstration/reference" in (fixture / "README.md").read_text(
        encoding="utf-8"
    )


def test_runner_local_minimal_preset_outputs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(ROOT / "examples" / "action-consumer", workspace)
    root_runs_before = snapshot_tree(ROOT / ".vibebench" / "runs")
    subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.invalid"],
        cwd=workspace,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Fixture"],
        cwd=workspace,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=workspace, check=True)
    subprocess.run(
        ["git", "commit", "-m", "fixture"],
        cwd=workspace,
        check=True,
        capture_output=True,
    )
    github_output = tmp_path / "outputs.txt"
    github_summary = tmp_path / "summary.md"
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(ROOT),
            "GITHUB_WORKSPACE": str(workspace),
            "GITHUB_ACTION_PATH": str(ROOT),
            "GITHUB_OUTPUT": str(github_output),
            "GITHUB_STEP_SUMMARY": str(github_summary),
            "INPUT_PRESET": "minimal",
            "INPUT_WORKING_DIRECTORY": ".",
            "INPUT_FAIL_ON": "quality",
            "INPUT_UPLOAD_ARTIFACTS": "false",
            "INPUT_RETENTION_DAYS": "14",
            "INPUT_PYTHON_COMMAND": sys.executable,
        }
    )

    result = subprocess.run(
        [sys.executable, str(RUNNER_PATH)],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "status=passed" in github_output.read_text(encoding="utf-8")
    assert "run-dir=.vibebench/runs/" in github_output.read_text(encoding="utf-8")
    assert "VibeBench Action" in github_summary.read_text(encoding="utf-8")
    assert (workspace / ".vibebench" / "runs").is_dir()
    assert snapshot_tree(ROOT / ".vibebench" / "runs") == root_runs_before


def test_ci_workflow_left_unchanged_snapshot() -> None:
    assert CI_WORKFLOW.read_text(encoding="utf-8").startswith("name: CI\n")


def snapshot_tree(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(item.relative_to(path).as_posix() for item in path.rglob("*"))
