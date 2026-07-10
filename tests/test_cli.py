import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from tests.cli_help_utils import strip_ansi
from vibebench.cli import app
from vibebench.config import load_config

runner = CliRunner()


def test_cli_help_works() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Codex-first quality gate" in result.output
    assert "version" in result.output
    assert "init" in result.output
    assert "preflight" in result.output
    assert "public-demo" in result.output


def config_path(root: Path) -> Path:
    return root / ".vibebench" / "config.yaml"


def workflow_path(root: Path) -> Path:
    return root / ".github" / "workflows" / "vibebench.yml"


def write_package_json(root: Path, scripts: dict[str, str] | None = None) -> None:
    payload = {"scripts": scripts or {}}
    root.joinpath("package.json").write_text(json.dumps(payload), encoding="utf-8")


def test_init_creates_config_yaml(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert config_path(tmp_path).exists()
    assert not workflow_path(tmp_path).exists()
    assert not (tmp_path / ".vibebench" / "runs").exists()
    assert not (tmp_path / ".vibebench" / "baselines").exists()
    assert "Selected profile:" in result.output
    assert "python3 -m vibebench config --check" in result.output


def test_init_generated_config_passes_config_check(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--project-root", str(tmp_path)])
    check = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--check"])

    assert result.exit_code == 0
    assert check.exit_code == 0
    config = load_config(config_path(tmp_path))
    assert config.project.name == "vibebench-project"


def test_init_refuses_existing_config_by_default(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("existing: true\n", encoding="utf-8")

    result = runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "Config already exists" in result.output
    assert "--force" in result.output
    assert config_path(tmp_path).read_text(encoding="utf-8") == "existing: true\n"


def test_init_force_overwrites_only_config_file(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    runs = tmp_path / ".vibebench" / "runs"
    baselines = tmp_path / ".vibebench" / "baselines"
    runs.mkdir()
    baselines.mkdir()
    runs.joinpath("keep.txt").write_text("run", encoding="utf-8")
    baselines.joinpath("stable.json").write_text("{}", encoding="utf-8")
    config_path(tmp_path).write_text("existing: true\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "init",
            "--project-root",
            str(tmp_path),
            "--profile",
            "python",
            "--force",
        ],
    )

    generated = config_path(tmp_path).read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert "existing: true" not in generated
    assert "python3 -m pytest -q" in generated
    assert runs.joinpath("keep.txt").read_text(encoding="utf-8") == "run"
    assert baselines.joinpath("stable.json").read_text(encoding="utf-8") == "{}"


def test_init_dry_run_writes_nothing(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--project-root", str(tmp_path), "--profile", "generic", "--dry-run"],
    )

    assert result.exit_code == 0
    assert not config_path(tmp_path).exists()
    assert not config_path(tmp_path).parent.exists()
    assert "Dry run only" in result.output


def test_init_json_stdout_is_pure_json(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--project-root",
            str(tmp_path),
            "--profile",
            "generic",
            "--dry-run",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert payload["status"] == "planned"
    assert payload["dry_run"] is True
    assert payload["selected_profile"] == "generic"
    assert payload["detected_stacks"] == []
    assert payload["detection_reasons"] == []
    assert payload["created"] is False


def test_init_json_output_writes_file_with_human_stdout(tmp_path: Path) -> None:
    output = tmp_path / "init-result.json"

    result = runner.invoke(
        app,
        [
            "init",
            "--project-root",
            str(tmp_path),
            "--profile",
            "generic",
            "--json-output",
            str(output),
        ],
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert "VibeBench init" in result.output
    assert not result.output.lstrip().startswith("{")
    assert payload["status"] == "created"
    assert payload["detected_stacks"] == []
    assert payload["detection_reasons"] == []
    assert payload["created"] is True


def test_init_profile_python(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["init", "--project-root", str(tmp_path), "--profile", "python"]
    )

    generated = config_path(tmp_path).read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert "python3 -m ruff check ." in generated
    assert "python3 -m pytest -q" in generated


def test_init_profile_generic(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["init", "--project-root", str(tmp_path), "--profile", "generic"]
    )

    generated = config_path(tmp_path).read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert "python3 -m pytest -q" not in generated
    assert "python3 -m ruff check ." not in generated
    assert "vibebench generic check" in generated


def test_init_profile_auto_detects_python_project(tmp_path: Path) -> None:
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname='demo'\n")

    result = runner.invoke(
        app,
        ["init", "--project-root", str(tmp_path), "--profile", "auto", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["requested_profile"] == "auto"
    assert payload["selected_profile"] == "python"
    assert "python3 -m pytest -q" in config_path(tmp_path).read_text(encoding="utf-8")


def test_init_profile_auto_falls_back_to_generic(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--project-root", str(tmp_path), "--profile", "auto", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["selected_profile"] == "generic"


def test_init_profile_node_uses_existing_package_scripts(tmp_path: Path) -> None:
    write_package_json(
        tmp_path,
        {
            "lint": "eslint .",
            "test": "vitest run",
            "build": "vite build",
        },
    )

    result = runner.invoke(
        app, ["init", "--project-root", str(tmp_path), "--profile", "node", "--json"]
    )

    payload = json.loads(result.output)
    generated = config_path(tmp_path).read_text(encoding="utf-8")
    config = load_config(config_path(tmp_path))
    assert result.exit_code == 0
    assert payload["selected_profile"] == "node"
    assert payload["detected_stacks"] == ["node"]
    assert "node:package.json" in payload["detection_reasons"]
    assert "Build script detected" in "\n".join(payload["next_steps"])
    assert config.checks.lint == ["npm run lint"]
    assert config.checks.test == ["npm test"]
    assert "npm run build" not in generated


def test_init_profile_node_without_scripts_uses_safe_placeholder(
    tmp_path: Path,
) -> None:
    write_package_json(tmp_path)

    result = runner.invoke(
        app, ["init", "--project-root", str(tmp_path), "--profile", "node", "--json"]
    )

    payload = json.loads(result.output)
    generated = config_path(tmp_path).read_text(encoding="utf-8")
    check = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--check"])
    assert result.exit_code == 0
    assert check.exit_code == 0
    assert "npm test" not in generated
    assert "npm run lint" not in generated
    assert "vibebench generic check" in generated
    assert "Add package.json lint/test scripts" in "\n".join(payload["next_steps"])


def test_init_profile_fullstack_includes_python_and_node_checks(
    tmp_path: Path,
) -> None:
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname='demo'\n")
    write_package_json(tmp_path, {"lint": "eslint .", "test": "vitest run"})

    result = runner.invoke(
        app, ["init", "--project-root", str(tmp_path), "--profile", "fullstack"]
    )

    config = load_config(config_path(tmp_path))
    check = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--check"])
    assert result.exit_code == 0
    assert check.exit_code == 0
    assert config.checks.lint == ["python3 -m ruff check .", "npm run lint"]
    assert config.checks.test == ["python3 -m pytest -q", "npm test"]


def test_init_profile_auto_detects_node_project(tmp_path: Path) -> None:
    write_package_json(tmp_path, {"test": "vitest run"})

    result = runner.invoke(
        app,
        ["init", "--project-root", str(tmp_path), "--profile", "auto", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["selected_profile"] == "node"
    assert payload["detected_stacks"] == ["node"]
    assert "node:package.json" in payload["detection_reasons"]


def test_init_profile_auto_detects_fullstack_project(tmp_path: Path) -> None:
    tmp_path.joinpath("tests").mkdir()
    write_package_json(tmp_path, {"lint": "eslint ."})

    result = runner.invoke(
        app,
        ["init", "--project-root", str(tmp_path), "--profile", "auto", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["selected_profile"] == "fullstack"
    assert payload["detected_stacks"] == ["python", "node"]
    assert "python:tests" in payload["detection_reasons"]
    assert "node:package.json" in payload["detection_reasons"]


def test_init_dry_run_writes_nothing_for_stack_profiles(tmp_path: Path) -> None:
    for profile in ["node", "fullstack", "auto"]:
        root = tmp_path / profile
        root.mkdir()
        write_package_json(root, {"test": "vitest run"})
        if profile in {"fullstack", "auto"}:
            root.joinpath("pyproject.toml").write_text("[project]\nname='demo'\n")

        result = runner.invoke(
            app,
            [
                "init",
                "--project-root",
                str(root),
                "--profile",
                profile,
                "--dry-run",
                "--json",
            ],
        )
        payload = json.loads(result.output)

        assert result.exit_code == 0
        assert payload["dry_run"] is True
        assert not config_path(root).exists()
        assert not config_path(root).parent.exists()
        assert not (root / ".vibebench" / "runs").exists()
        assert not (root / ".vibebench" / "baselines").exists()


def test_init_json_output_includes_stack_metadata(tmp_path: Path) -> None:
    write_package_json(tmp_path, {"lint": "eslint ."})
    output = tmp_path / "init" / "result.json"

    result = runner.invoke(
        app,
        [
            "init",
            "--project-root",
            str(tmp_path),
            "--profile",
            "auto",
            "--json-output",
            str(output),
        ],
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert payload["selected_profile"] == "node"
    assert payload["detected_stacks"] == ["node"]
    assert "node:package.json" in payload["detection_reasons"]


def test_init_invalid_profile_fails_clearly(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["init", "--project-root", str(tmp_path), "--profile", "ruby"]
    )

    assert result.exit_code == 1
    assert "Unknown init profile" in result.output
    assert not config_path(tmp_path).exists()


def test_init_does_not_create_runs_or_baselines(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert not (tmp_path / ".vibebench" / "runs").exists()
    assert not (tmp_path / ".vibebench" / "baselines").exists()


def test_init_generated_config_can_be_used_with_config_check(tmp_path: Path) -> None:
    init_result = runner.invoke(
        app, ["init", "--project-root", str(tmp_path), "--profile", "generic"]
    )
    check = runner.invoke(
        app, ["config", "--project-root", str(tmp_path), "--check", "--json"]
    )
    payload = json.loads(check.output)

    assert init_result.exit_code == 0
    assert check.exit_code == 0
    assert payload["overall_status"] == "passed"


def onboard_payload_for(root: Path, *extra: str) -> dict[str, object]:
    result = runner.invoke(
        app,
        ["onboard", "--project-root", str(root), "--json", *extra],
    )
    assert result.output.lstrip().startswith("{")
    assert result.exit_code == 0
    return json.loads(result.output)


def preflight_payload_for(root: Path, *extra: str) -> dict[str, object]:
    result = runner.invoke(
        app,
        ["preflight", "--project-root", str(root), "--json", *extra],
    )
    assert result.output.lstrip().startswith("{")
    assert result.exit_code == 0
    return json.loads(result.output)


def test_preflight_help_works() -> None:
    result = runner.invoke(app, ["preflight", "--help"])
    output = strip_ansi(result.output)

    assert result.exit_code == 0
    assert "--json" in output
    assert "--json-output" in output
    assert "--summary-output" in output
    assert "--strict" in output
    assert "--profile" in output


def test_preflight_human_output(tmp_path: Path) -> None:
    result = runner.invoke(app, ["preflight", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "VibeBench preflight" in result.output
    assert "Detected stacks: none" in result.output
    assert "Config status: missing" in result.output
    assert "python3 -m vibebench init --profile auto" in result.output


def test_preflight_json_stdout_is_pure_json(tmp_path: Path) -> None:
    payload = preflight_payload_for(tmp_path)

    assert payload["status"] == "unknown"
    assert payload["strict"] is False
    assert payload["detected_stacks"] == []
    assert payload["config"]["exists"] is False
    assert payload["workflow_check"]["workflow_count"] == 0
    assert "required_ci_modes" not in payload["workflow_check"]
    assert "missing_required_ci_modes" not in payload["workflow_check"]
    assert payload["commands"][0] == "python3 -m vibebench init --profile auto"
    assert payload["generated_at"].endswith("Z")


def test_preflight_json_output_writes_file_with_human_stdout(tmp_path: Path) -> None:
    output = tmp_path / "preflight" / "result.json"

    result = runner.invoke(
        app,
        ["preflight", "--project-root", str(tmp_path), "--json-output", str(output)],
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert "VibeBench preflight" in result.output
    assert not result.output.lstrip().startswith("{")
    assert payload["status"] == "unknown"


def test_preflight_summary_output_writes_markdown(tmp_path: Path) -> None:
    output = tmp_path / "preflight.md"

    result = runner.invoke(
        app,
        ["preflight", "--project-root", str(tmp_path), "--summary-output", str(output)],
    )
    markdown = output.read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert markdown.startswith("# VibeBench Preflight")
    assert "## Recommendations" in markdown
    assert "python3 -m vibebench init --profile auto" in markdown


def test_preflight_json_and_summary_keep_stdout_json(tmp_path: Path) -> None:
    summary = tmp_path / "preflight.md"
    json_output = tmp_path / "preflight.json"

    result = runner.invoke(
        app,
        [
            "preflight",
            "--project-root",
            str(tmp_path),
            "--json",
            "--json-output",
            str(json_output),
            "--summary-output",
            str(summary),
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert payload == json.loads(json_output.read_text(encoding="utf-8"))
    assert summary.exists()




def write_preflight_policy_config(root: Path, policy_yaml: str) -> None:
    config_path(root).parent.mkdir(parents=True, exist_ok=True)
    config_path(root).write_text(
        f"""project:
  name: demo
checks:
  test:
    - python3 -c 'print(1)'
  lint: []
preflight:
  policy:
{policy_yaml}
""",
        encoding="utf-8",
    )


def test_preflight_default_remains_report_only_without_policy_fields(
    tmp_path: Path,
) -> None:
    write_preflight_policy_config(tmp_path, "    require_config: true\n")

    payload = preflight_payload_for(tmp_path)

    assert "policy_status" not in payload
    assert "policy_findings" not in payload


def test_preflight_enforce_policy_passes_with_safe_policy(
    tmp_path: Path,
) -> None:
    write_preflight_policy_config(
        tmp_path,
        """    require_onboard_ready: false
    require_workflow_check_ready: true
""",
    )

    payload = preflight_payload_for(tmp_path, "--enforce-policy")

    assert payload["policy_enforced"] is True
    assert payload["policy_status"] == "passed"
    assert payload["policy_source"] == "config"
    assert payload["policy_findings"] == []


def test_preflight_enforce_policy_fails_when_config_required(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        app,
        [
            "preflight",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert result.output.lstrip().startswith("{")
    assert payload["policy_status"] == "failed"
    assert "config_required" in {
        finding["id"] for finding in payload["policy_findings"]
    }


def test_preflight_policy_markdown_only_when_enforced(tmp_path: Path) -> None:
    report_only = tmp_path / "report-only.md"
    enforced = tmp_path / "enforced.md"
    write_preflight_policy_config(tmp_path, "    require_onboard_ready: false\n")

    first = runner.invoke(
        app,
        [
            "preflight",
            "--project-root",
            str(tmp_path),
            "--summary-output",
            str(report_only),
        ],
    )
    second = runner.invoke(
        app,
        [
            "preflight",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--summary-output",
            str(enforced),
        ],
    )

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "## Policy" not in report_only.read_text(encoding="utf-8")
    enforced_text = enforced.read_text(encoding="utf-8")
    assert "## Policy" in enforced_text
    assert "Default preflight remains report-only" in enforced_text


def test_preflight_empty_project_behavior(tmp_path: Path) -> None:
    payload = preflight_payload_for(tmp_path)

    assert payload["status"] == "unknown"
    assert payload["actionable_project_signal"] is False
    assert payload["project_scan"]["status"] == "needs_init"
    assert payload["workflow_check"]["workflow_count"] == 0
    assert payload["recommendations"][0].startswith(
        "Add Python or Node project markers"
    )


def test_preflight_python_project_behavior(tmp_path: Path) -> None:
    tmp_path.joinpath("tests").mkdir()
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname='demo'\n")

    payload = preflight_payload_for(tmp_path)

    assert payload["status"] == "needs_init"
    assert payload["detected_stacks"] == ["python"]
    assert payload["resolved_profile"] == "python"
    assert "python:pyproject.toml" in payload["detection_reasons"]


def test_preflight_node_project_behavior(tmp_path: Path) -> None:
    write_package_json(tmp_path, {"lint": "eslint .", "test": "vitest run"})

    payload = preflight_payload_for(tmp_path)

    assert payload["status"] == "needs_init"
    assert payload["detected_stacks"] == ["node"]
    assert payload["resolved_profile"] == "node"


def test_preflight_fullstack_project_behavior(tmp_path: Path) -> None:
    tmp_path.joinpath("tests").mkdir()
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname='demo'\n")
    write_package_json(tmp_path, {"lint": "eslint .", "test": "vitest run"})

    payload = preflight_payload_for(tmp_path)

    assert payload["status"] == "needs_init"
    assert payload["detected_stacks"] == ["python", "node"]
    assert payload["resolved_profile"] == "fullstack"


def test_preflight_invalid_config_behavior(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("project:\n  name: ''\n", encoding="utf-8")

    payload = preflight_payload_for(tmp_path)

    assert payload["status"] == "blocked"
    assert payload["config"]["exists"] is True
    assert payload["config"]["valid"] is False
    assert "Fix .vibebench/config.yaml" in payload["recommendations"][0]


def test_preflight_strict_fails_without_actionable_signal(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["preflight", "--project-root", str(tmp_path), "--strict", "--json"],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["strict_failed"] is True
    assert payload["status"] == "unknown"


def test_preflight_strict_fails_on_invalid_config(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("project:\n  name: ''\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["preflight", "--project-root", str(tmp_path), "--strict", "--json"],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["strict_failed"] is True
    assert payload["status"] == "blocked"


def test_preflight_strict_fails_on_existing_workflow_blockers(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--project-root", str(tmp_path), "--profile", "python"])
    write_workflow(
        tmp_path,
        minimal_vibebench_workflow().replace(
            "python3 -m vibebench ci", "python3 -m pytest -q"
        ),
    )

    result = runner.invoke(
        app,
        ["preflight", "--project-root", str(tmp_path), "--strict", "--json"],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["strict_failed"] is True
    assert payload["workflow_check"]["workflow_count"] == 1
    assert payload["workflow_check"]["strict_status"] == "failed"


def test_preflight_require_ci_mode_default_reports_present_mode(
    tmp_path: Path,
) -> None:
    write_workflow(tmp_path, minimal_vibebench_workflow())

    payload = preflight_payload_for(
        tmp_path,
        "--require-ci-mode",
        "default",
    )

    workflow_check = payload["workflow_check"]
    assert workflow_check["detected_ci_modes"] == ["default"]
    assert workflow_check["required_ci_modes"] == ["default"]
    assert workflow_check["missing_required_ci_modes"] == []


def test_preflight_require_ci_mode_adoption_reports_missing_mode(
    tmp_path: Path,
) -> None:
    write_workflow(tmp_path, minimal_vibebench_workflow())

    payload = preflight_payload_for(
        tmp_path,
        "--require-ci-mode",
        "adoption",
    )

    workflow_check = payload["workflow_check"]
    assert workflow_check["detected_ci_modes"] == ["default"]
    assert workflow_check["required_ci_modes"] == ["adoption"]
    assert workflow_check["missing_required_ci_modes"] == ["adoption"]


def test_preflight_require_ci_mode_adoption_strict_exits_nonzero(
    tmp_path: Path,
) -> None:
    write_workflow(tmp_path, minimal_vibebench_workflow())

    result = runner.invoke(
        app,
        [
            "preflight",
            "--project-root",
            str(tmp_path),
            "--require-ci-mode",
            "adoption",
            "--strict",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["strict_failed"] is True
    assert payload["workflow_check"]["missing_required_ci_modes"] == ["adoption"]


def test_preflight_require_ci_mode_dedupes_in_stable_order(
    tmp_path: Path,
) -> None:
    write_workflow(
        tmp_path,
        workflow_with_command("python3 -m vibebench ci --adoption-policy")
        + "      - run: python3 -m vibebench ci --adoption\n",
    )

    payload = preflight_payload_for(
        tmp_path,
        "--require-ci-mode",
        "adoption-policy",
        "--require-ci-mode",
        "adoption",
        "--require-ci-mode",
        "adoption-policy",
    )

    workflow_check = payload["workflow_check"]
    assert workflow_check["required_ci_modes"] == ["adoption", "adoption-policy"]
    assert workflow_check["missing_required_ci_modes"] == []


def test_preflight_require_ci_mode_invalid_value_fails_clearly(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        app,
        [
            "preflight",
            "--project-root",
            str(tmp_path),
            "--require-ci-mode",
            "preview",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert "--require-ci-mode must be one of" in result.output


def test_preflight_require_ci_mode_human_output_reports_required_modes(
    tmp_path: Path,
) -> None:
    write_workflow(tmp_path, minimal_vibebench_workflow())

    result = runner.invoke(
        app,
        [
            "preflight",
            "--project-root",
            str(tmp_path),
            "--require-ci-mode",
            "default",
        ],
    )

    assert result.exit_code == 0
    assert "Required CI modes: default" in result.output
    assert "Missing required CI modes: none" in result.output


def test_preflight_require_ci_mode_markdown_reports_required_modes(
    tmp_path: Path,
) -> None:
    output = tmp_path / "preflight.md"
    write_workflow(tmp_path, minimal_vibebench_workflow())

    result = runner.invoke(
        app,
        [
            "preflight",
            "--project-root",
            str(tmp_path),
            "--require-ci-mode",
            "adoption",
            "--summary-output",
            str(output),
        ],
    )
    markdown = output.read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert "- Required CI modes: adoption" in markdown
    assert "- Missing required CI modes: adoption" in markdown


def test_preflight_creates_no_runs_baselines_workflows_or_config(
    tmp_path: Path,
) -> None:
    result = runner.invoke(app, ["preflight", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert not config_path(tmp_path).exists()
    assert not (tmp_path / ".vibebench" / "runs").exists()
    assert not (tmp_path / ".vibebench" / "baselines").exists()
    assert not (tmp_path / ".github").exists()


def test_preflight_profile_auto_reuses_shared_detector(tmp_path: Path) -> None:
    tmp_path.joinpath("tests").mkdir()
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname='demo'\n")

    payload = preflight_payload_for(tmp_path, "--profile", "auto")

    assert payload["requested_profile"] == "auto"
    assert payload["resolved_profile"] == "python"
    assert payload["workflow_template"]["resolved_profile"] == "python"


def test_onboard_human_output(tmp_path: Path) -> None:
    result = runner.invoke(app, ["onboard", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "VibeBench onboarding plan" in result.output
    assert "Recommended init profile: generic" in result.output
    assert "python3 -m vibebench init --profile auto" in result.output


def test_onboard_json_stdout_is_pure_json(tmp_path: Path) -> None:
    payload = onboard_payload_for(tmp_path)

    assert payload["recommended_profile"] == "generic"
    assert payload["config_exists"] is False
    assert payload["next_step"] == "python3 -m vibebench init --profile auto"


def test_onboard_json_output_writes_file_with_human_stdout(tmp_path: Path) -> None:
    output = tmp_path / "onboard" / "plan.json"

    result = runner.invoke(
        app,
        ["onboard", "--project-root", str(tmp_path), "--json-output", str(output)],
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert "VibeBench onboarding plan" in result.output
    assert not result.output.lstrip().startswith("{")
    assert payload["recommended_profile"] == "generic"


def test_onboard_summary_output_writes_markdown(tmp_path: Path) -> None:
    output = tmp_path / "onboard.md"

    result = runner.invoke(
        app,
        ["onboard", "--project-root", str(tmp_path), "--summary-output", str(output)],
    )
    markdown = output.read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert markdown.startswith("# VibeBench Onboarding Plan")
    assert "python3 -m vibebench init --profile auto" in markdown


def test_onboard_empty_project_detection(tmp_path: Path) -> None:
    payload = onboard_payload_for(tmp_path)

    assert payload["recommended_profile"] == "generic"
    assert payload["detected_stacks"] == []
    assert payload["scan_status"] == "needs_init"
    assert "No VibeBench config exists yet." in payload["warnings"]


def test_onboard_python_project_detection(tmp_path: Path) -> None:
    tmp_path.joinpath("tests").mkdir()
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname='demo'\n")

    payload = onboard_payload_for(tmp_path)

    assert payload["recommended_profile"] == "python"
    assert payload["detected_stacks"] == ["python"]
    assert "python:pyproject.toml" in payload["detection_reasons"]


def test_onboard_node_project_detection(tmp_path: Path) -> None:
    write_package_json(tmp_path, {"lint": "eslint .", "test": "vitest run"})

    payload = onboard_payload_for(tmp_path)

    assert payload["recommended_profile"] == "node"
    assert payload["detected_stacks"] == ["node"]


def test_onboard_fullstack_project_detection(tmp_path: Path) -> None:
    tmp_path.joinpath("tests").mkdir()
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname='demo'\n")
    write_package_json(tmp_path, {"lint": "eslint ."})

    payload = onboard_payload_for(tmp_path)

    assert payload["recommended_profile"] == "fullstack"
    assert payload["detected_stacks"] == ["python", "node"]


def test_onboard_config_exists_true_false(tmp_path: Path) -> None:
    missing = onboard_payload_for(tmp_path)
    init = runner.invoke(app, ["init", "--project-root", str(tmp_path)])
    present = onboard_payload_for(tmp_path)

    assert init.exit_code == 0
    assert missing["config_exists"] is False
    assert present["config_exists"] is True
    assert present["next_step"] == "python3 -m vibebench config --check"


def test_onboard_strict_passes_when_config_is_valid(tmp_path: Path) -> None:
    init = runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    result = runner.invoke(
        app,
        ["onboard", "--project-root", str(tmp_path), "--strict", "--json"],
    )
    payload = json.loads(result.output)

    assert init.exit_code == 0
    assert result.exit_code == 0
    assert payload["strict_failed"] is False


def test_onboard_strict_fails_without_config(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["onboard", "--project-root", str(tmp_path), "--strict", "--json"],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["strict_failed"] is True
    assert payload["message"] == "Onboarding is not ready for immediate CI adoption."


def test_onboard_creates_no_runs_baselines_or_config(tmp_path: Path) -> None:
    result = runner.invoke(app, ["onboard", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert not config_path(tmp_path).exists()
    assert not (tmp_path / ".vibebench" / "runs").exists()
    assert not (tmp_path / ".vibebench" / "baselines").exists()


def test_onboard_json_and_summary_keep_stdout_json(tmp_path: Path) -> None:
    summary = tmp_path / "onboard.md"
    json_output = tmp_path / "onboard.json"

    result = runner.invoke(
        app,
        [
            "onboard",
            "--project-root",
            str(tmp_path),
            "--json",
            "--json-output",
            str(json_output),
            "--summary-output",
            str(summary),
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert payload == json.loads(json_output.read_text(encoding="utf-8"))
    assert summary.exists()


def test_onboard_default_omits_policy_fields(tmp_path: Path) -> None:
    payload = onboard_payload_for(tmp_path)

    assert "policy_status" not in payload
    assert "policy_findings" not in payload


def test_onboard_enforce_policy_passes_on_healthy_project(tmp_path: Path) -> None:
    tmp_path.joinpath("tests").mkdir()
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname=demo\n")
    init = runner.invoke(
        app,
        ["init", "--project-root", str(tmp_path), "--profile", "python"],
    )

    result = runner.invoke(
        app,
        [
            "onboard",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert init.exit_code == 0
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert payload["policy_enforced"] is True
    assert payload["policy_status"] == "passed"
    assert payload["policy_findings"] == []


def test_onboard_enforce_policy_fails_without_config(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "onboard",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert result.output.lstrip().startswith("{")
    assert payload["policy_status"] == "failed"
    assert "config_required" in {
        finding["id"] for finding in payload["policy_findings"]
    }


def test_onboard_enforce_policy_summary_includes_policy_section(
    tmp_path: Path,
) -> None:
    output = tmp_path / "onboard-policy.md"

    result = runner.invoke(
        app,
        [
            "onboard",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--summary-output",
            str(output),
        ],
    )
    markdown = output.read_text(encoding="utf-8")

    assert result.exit_code == 1
    assert "## Policy" in markdown
    assert "Default onboard remains report-only" in markdown


def project_scan_payload(root: Path, *extra: str) -> dict[str, object]:
    result = runner.invoke(
        app,
        ["project-scan", "--project-root", str(root), "--json", *extra],
    )
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    return json.loads(result.output)


def finding_ids(payload: dict[str, object]) -> set[str]:
    findings = payload["findings"]
    assert isinstance(findings, list)
    return {finding["id"] for finding in findings}


def test_project_scan_empty_project_recommends_generic(tmp_path: Path) -> None:
    payload = project_scan_payload(tmp_path)

    assert payload["recommended_profile"] == "generic"
    assert payload["detected_stacks"] == []
    assert payload["status"] == "needs_init"
    assert "no_vibebench_config" in finding_ids(payload)
    assert "no_stack_detected" in finding_ids(payload)
    assert not config_path(tmp_path).exists()
    assert not config_path(tmp_path).parent.exists()


def test_project_scan_python_project_recommends_python(tmp_path: Path) -> None:
    tmp_path.joinpath("tests").mkdir()
    tmp_path.joinpath("pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n[tool.ruff]\n",
        encoding="utf-8",
    )

    payload = project_scan_payload(tmp_path)

    assert payload["recommended_profile"] == "python"
    assert payload["detected_stacks"] == ["python"]
    assert "python:pyproject.toml" in payload["detection_reasons"]
    assert payload["tests_dir_present"] is True
    assert payload["pytest_likely"] is True
    assert payload["ruff_likely"] is True


def test_project_scan_node_project_recommends_node(tmp_path: Path) -> None:
    write_package_json(tmp_path, {"lint": "eslint .", "test": "vitest run"})

    payload = project_scan_payload(tmp_path)

    assert payload["recommended_profile"] == "node"
    assert payload["detected_stacks"] == ["node"]
    assert payload["package_json_present"] is True
    assert payload["package_manager_guess"] == "npm"
    assert payload["node_scripts"] == ["lint", "test"]
    assert payload["has_lint_script"] is True
    assert payload["has_test_script"] is True


def test_project_scan_fullstack_project_recommends_fullstack(tmp_path: Path) -> None:
    tmp_path.joinpath("tests").mkdir()
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname='demo'\n")
    write_package_json(tmp_path, {"lint": "eslint ."})

    payload = project_scan_payload(tmp_path)

    assert payload["recommended_profile"] == "fullstack"
    assert payload["detected_stacks"] == ["python", "node"]
    assert "fullstack_detected" in finding_ids(payload)


def test_project_scan_package_manager_guess(tmp_path: Path) -> None:
    cases = [
        ("package-lock.json", "npm"),
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("bun.lockb", "bun"),
    ]
    for lockfile, expected in cases:
        root = tmp_path / expected
        root.mkdir()
        write_package_json(root, {"test": "vitest run"})
        root.joinpath(lockfile).write_text("", encoding="utf-8")

        payload = project_scan_payload(root)

        assert payload["package_manager_guess"] == expected


def test_project_scan_package_json_scripts_detected(tmp_path: Path) -> None:
    write_package_json(
        tmp_path,
        {"build": "vite build", "lint": "eslint .", "test": "vitest run"},
    )

    payload = project_scan_payload(tmp_path)

    assert payload["node_scripts"] == ["build", "lint", "test"]
    assert payload["has_build_script"] is True
    assert payload["has_lint_script"] is True
    assert payload["has_test_script"] is True


def test_project_scan_package_json_without_scripts_warns_without_writes(
    tmp_path: Path,
) -> None:
    write_package_json(tmp_path)

    payload = project_scan_payload(tmp_path)

    assert {"node_without_test_script", "node_without_lint_script"} <= finding_ids(
        payload
    )
    assert not config_path(tmp_path).exists()
    assert not (tmp_path / ".vibebench" / "runs").exists()
    assert not (tmp_path / ".vibebench" / "baselines").exists()


def test_project_scan_malformed_package_json_reports_finding(tmp_path: Path) -> None:
    tmp_path.joinpath("package.json").write_text("{not-json", encoding="utf-8")

    payload = project_scan_payload(tmp_path)

    assert payload["recommended_profile"] == "node"
    assert "malformed_package_json" in finding_ids(payload)
    assert payload["status"] == "blocked"


def test_project_scan_strict_fails_on_malformed_package_json(
    tmp_path: Path,
) -> None:
    tmp_path.joinpath("package.json").write_text("{not-json", encoding="utf-8")

    result = runner.invoke(
        app,
        ["project-scan", "--project-root", str(tmp_path), "--strict", "--json"],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["strict_failed"] is True
    assert "malformed_package_json" in finding_ids(payload)


def test_project_scan_existing_valid_config_reported_valid(tmp_path: Path) -> None:
    init_result = runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    payload = project_scan_payload(tmp_path)

    assert init_result.exit_code == 0
    assert payload["config_present"] is True
    assert payload["config_valid"] is True
    assert payload["config_status"] == "valid"
    assert payload["active_command_groups"]["test"]
    assert "existing_config_valid" in finding_ids(payload)


def test_project_scan_existing_invalid_config_reported_invalid(
    tmp_path: Path,
) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("project:\n  name: ''\n", encoding="utf-8")

    payload = project_scan_payload(tmp_path)

    assert payload["config_present"] is True
    assert payload["config_valid"] is False
    assert payload["config_status"] == "invalid"
    assert "invalid_vibebench_config" in finding_ids(payload)


def test_project_scan_strict_fails_on_invalid_config(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("project:\n  name: ''\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["project-scan", "--project-root", str(tmp_path), "--strict", "--json"],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["strict_failed"] is True
    assert "invalid_vibebench_config" in finding_ids(payload)


def test_project_scan_json_output_writes_file_with_human_stdout(
    tmp_path: Path,
) -> None:
    output = tmp_path / "scan" / "result.json"

    result = runner.invoke(
        app,
        ["project-scan", "--project-root", str(tmp_path), "--json-output", str(output)],
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert "VibeBench project scan" in result.output
    assert not result.output.lstrip().startswith("{")
    assert payload["recommended_profile"] == "generic"


def test_project_scan_summary_output_writes_markdown(tmp_path: Path) -> None:
    output = tmp_path / "scan.md"

    result = runner.invoke(
        app,
        [
            "project-scan",
            "--project-root",
            str(tmp_path),
            "--summary-output",
            str(output),
        ],
    )
    markdown = output.read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert markdown.startswith("# VibeBench Project Scan")
    assert "| Severity | Finding | Recommendation |" in markdown
    assert "python3 -m vibebench init --profile auto" in markdown


def test_project_scan_json_and_summary_keep_stdout_json(tmp_path: Path) -> None:
    output = tmp_path / "scan.md"

    result = runner.invoke(
        app,
        [
            "project-scan",
            "--project-root",
            str(tmp_path),
            "--summary-output",
            str(output),
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert payload["recommended_profile"] == "generic"
    assert output.exists()


def test_project_scan_creates_no_runs_baselines_or_config(tmp_path: Path) -> None:
    result = runner.invoke(app, ["project-scan", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert not config_path(tmp_path).exists()
    assert not (tmp_path / ".vibebench" / "runs").exists()
    assert not (tmp_path / ".vibebench" / "baselines").exists()


def write_project_scan_policy_config(root: Path, policy_yaml: str) -> None:
    config_path(root).parent.mkdir(parents=True, exist_ok=True)
    config_path(root).write_text(
        """project:
  name: demo
checks:
  test:
    - python3 -c "print(1)"
  lint: []
project_scan:
  policy:
"""
        + policy_yaml,
        encoding="utf-8",
    )


def write_workflow_check_policy_config(root: Path, policy_yaml: str) -> None:
    config_path(root).parent.mkdir(parents=True, exist_ok=True)
    config_path(root).write_text(
        """project:
  name: demo
checks:
  test:
    - python3 -c "print(1)"
  lint: []
workflow_check:
  policy:
"""
        + policy_yaml,
        encoding="utf-8",
    )


def test_project_scan_default_omits_policy_fields(tmp_path: Path) -> None:
    payload = project_scan_payload(tmp_path)

    assert "policy_status" not in payload
    assert "policy_findings" not in payload


def test_project_scan_enforce_policy_passes_on_supported_project(
    tmp_path: Path,
) -> None:
    tmp_path.joinpath("tests").mkdir()
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname='demo'\n")
    init = runner.invoke(
        app,
        ["init", "--project-root", str(tmp_path), "--profile", "python"],
    )

    result = runner.invoke(
        app,
        [
            "project-scan",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert init.exit_code == 0
    assert result.exit_code == 0
    assert payload["policy_enforced"] is True
    assert payload["policy_status"] == "passed"
    assert payload["policy_findings"] == []


def test_project_scan_enforce_policy_fails_on_unsupported_project(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        app,
        [
            "project-scan",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["policy_status"] == "failed"
    assert "unsupported_stack" in {
        finding["id"] for finding in payload["policy_findings"]
    }


def test_project_scan_enforce_policy_summary_includes_policy_section(
    tmp_path: Path,
) -> None:
    output = tmp_path / "scan-policy.md"

    result = runner.invoke(
        app,
        [
            "project-scan",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--summary-output",
            str(output),
        ],
    )
    markdown = output.read_text(encoding="utf-8")

    assert result.exit_code == 1
    assert "## Policy" in markdown
    assert "Default project-scan remains report-only" in markdown


def test_project_scan_policy_allowed_profiles_fails(tmp_path: Path) -> None:
    write_package_json(tmp_path, {"lint": "eslint .", "test": "vitest run"})
    write_project_scan_policy_config(
        tmp_path,
        """    allowed_profiles:
      - python
""",
    )

    result = runner.invoke(
        app,
        [
            "project-scan",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert "recommended_profile_not_allowed" in {
        finding["id"] for finding in payload["policy_findings"]
    }


def test_project_scan_policy_fail_on_warning_findings(tmp_path: Path) -> None:
    write_package_json(tmp_path)
    write_project_scan_policy_config(
        tmp_path,
        """    fail_on_warning_findings: true
""",
    )

    result = runner.invoke(
        app,
        [
            "project-scan",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert any(
        finding["rule"] == "fail_on_warning_findings"
        for finding in payload["policy_findings"]
    )


def test_project_scan_policy_fail_on_error_findings(tmp_path: Path) -> None:
    tmp_path.joinpath("package.json").write_text("{not-json", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "project-scan",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert any(
        finding["rule"] == "fail_on_error_findings"
        for finding in payload["policy_findings"]
    )


def workflow_template_payload_for(root: Path, *extra: str) -> dict[str, object]:
    result = runner.invoke(
        app,
        ["workflow-template", "--project-root", str(root), "--json", *extra],
    )
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    return json.loads(result.output)


def test_workflow_template_default_does_not_write_files(tmp_path: Path) -> None:
    result = runner.invoke(app, ["workflow-template", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "VibeBench workflow template" in result.output
    assert not workflow_path(tmp_path).exists()
    assert not (tmp_path / ".github").exists()
    assert not (tmp_path / ".vibebench" / "runs").exists()
    assert not (tmp_path / ".vibebench" / "baselines").exists()


def test_workflow_template_json_stdout_is_pure_json(tmp_path: Path) -> None:
    payload = workflow_template_payload_for(tmp_path)

    assert payload["status"] == "planned"
    assert payload["profile"] == "auto"
    assert payload["resolved_profile"] == "generic"
    assert payload["workflow_written"] is False
    assert payload["output_path"] == str(workflow_path(tmp_path))
    assert "permissions:\n  contents: read" in payload["workflow_yaml"]


@pytest.mark.parametrize(
    ("mode", "command"),
    [
        ("adoption", "python3 -m vibebench ci --adoption"),
        ("adoption-policy", "python3 -m vibebench ci --adoption-policy"),
    ],
)
def test_workflow_template_adoption_modes_json_stdout_is_pure_json(
    tmp_path: Path, mode: str, command: str
) -> None:
    payload = workflow_template_payload_for(tmp_path, "--ci-mode", mode)

    assert payload["ci_mode"] == mode
    assert payload["commands"] == [command]
    assert command in payload["workflow_yaml"]
    assert payload["workflow_yaml"] == payload["template"]
    assert not workflow_path(tmp_path).exists()
    assert not (tmp_path / ".github").exists()


@pytest.mark.parametrize(
    ("mode", "command"),
    [
        ("adoption", "python3 -m vibebench ci --adoption"),
        ("adoption-policy", "python3 -m vibebench ci --adoption-policy"),
    ],
)
def test_workflow_template_adoption_modes_summary_output_includes_command(
    tmp_path: Path, mode: str, command: str
) -> None:
    output = tmp_path / f"workflow-{mode}.md"

    result = runner.invoke(
        app,
        [
            "workflow-template",
            "--project-root",
            str(tmp_path),
            "--ci-mode",
            mode,
            "--summary-output",
            str(output),
        ],
    )
    markdown = output.read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert f"- CI mode: {mode}" in markdown
    assert f"- `{command}`" in markdown
    assert command in markdown
    assert not workflow_path(tmp_path).exists()


def test_workflow_template_json_output_writes_deterministic_json(
    tmp_path: Path,
) -> None:
    output = tmp_path / "workflow" / "template.json"

    result = runner.invoke(
        app,
        [
            "workflow-template",
            "--project-root",
            str(tmp_path),
            "--json-output",
            str(output),
        ],
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert "VibeBench workflow template" in result.output
    assert payload["status"] == "planned"
    assert output.read_text(encoding="utf-8").endswith("\n")


def test_workflow_template_summary_output_writes_markdown_with_yaml(
    tmp_path: Path,
) -> None:
    output = tmp_path / "workflow.md"

    result = runner.invoke(
        app,
        [
            "workflow-template",
            "--project-root",
            str(tmp_path),
            "--summary-output",
            str(output),
        ],
    )
    markdown = output.read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert markdown.startswith("# VibeBench Workflow Template")
    assert "```yaml" in markdown
    assert "name: VibeBench" in markdown
    assert "permissions:" in markdown


def test_workflow_template_dry_run_does_not_create_workflow_dir(
    tmp_path: Path,
) -> None:
    payload = workflow_template_payload_for(tmp_path, "--write", "--dry-run")

    assert payload["write"] is True
    assert payload["dry_run"] is True
    assert payload["would_write"] is True
    assert payload["workflow_written"] is False
    assert not workflow_path(tmp_path).exists()
    assert not (tmp_path / ".github").exists()


def test_workflow_template_write_creates_default_workflow(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["workflow-template", "--project-root", str(tmp_path), "--write"],
    )

    assert result.exit_code == 0
    workflow = workflow_path(tmp_path).read_text(encoding="utf-8")
    assert "name: VibeBench" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "python3 -m vibebench config --check" in workflow


def test_workflow_template_refuses_existing_without_force(tmp_path: Path) -> None:
    workflow_path(tmp_path).parent.mkdir(parents=True)
    workflow_path(tmp_path).write_text("existing: true\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["workflow-template", "--project-root", str(tmp_path), "--write"],
    )

    assert result.exit_code == 1
    assert "Workflow already exists" in result.output
    assert workflow_path(tmp_path).read_text(encoding="utf-8") == "existing: true\n"


def test_workflow_template_force_overwrites_intentionally(tmp_path: Path) -> None:
    workflow_path(tmp_path).parent.mkdir(parents=True)
    workflow_path(tmp_path).write_text("existing: true\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "workflow-template",
            "--project-root",
            str(tmp_path),
            "--write",
            "--force",
        ],
    )

    assert result.exit_code == 0
    workflow = workflow_path(tmp_path).read_text(encoding="utf-8")
    assert "existing: true" not in workflow
    assert "name: VibeBench" in workflow


def test_workflow_template_output_writes_only_with_write(tmp_path: Path) -> None:
    output = tmp_path / "custom" / "vibebench.yml"

    preview = runner.invoke(
        app,
        [
            "workflow-template",
            "--project-root",
            str(tmp_path),
            "--output",
            str(output),
        ],
    )
    assert preview.exit_code == 0
    assert not output.exists()

    written = runner.invoke(
        app,
        [
            "workflow-template",
            "--project-root",
            str(tmp_path),
            "--output",
            str(output),
            "--write",
        ],
    )

    assert written.exit_code == 0
    assert output.exists()


def test_workflow_template_profile_auto_uses_shared_detection(tmp_path: Path) -> None:
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname='demo'\n")
    write_package_json(tmp_path, {"test": "vitest run"})

    payload = workflow_template_payload_for(tmp_path, "--profile", "auto")

    assert payload["resolved_profile"] == "fullstack"
    assert payload["detected_stacks"] == ["python", "node"]
    assert "python:pyproject.toml" in payload["detection_reasons"]
    assert "node:package.json" in payload["detection_reasons"]
    assert "actions/setup-node" in payload["workflow_yaml"]


def test_workflow_template_profiles_produce_expected_metadata(
    tmp_path: Path,
) -> None:
    expected_node = {
        "generic": False,
        "python": False,
        "node": True,
        "fullstack": True,
    }
    for profile, has_node in expected_node.items():
        payload = workflow_template_payload_for(tmp_path, "--profile", profile)
        assert payload["profile"] == profile
        assert payload["resolved_profile"] == profile
        assert ("actions/setup-node" in payload["workflow_yaml"]) is has_node


def test_workflow_template_install_command_is_not_executed(tmp_path: Path) -> None:
    marker = tmp_path / "SHOULD_NOT_EXIST"
    command = "python3 -c \"open('SHOULD_NOT_EXIST','w').write('x')\""

    payload = workflow_template_payload_for(
        tmp_path,
        "--install-command",
        command,
    )

    assert command in payload["workflow_yaml"]
    assert not marker.exists()


def test_workflow_template_ci_modes_generate_expected_commands(tmp_path: Path) -> None:
    basic = workflow_template_payload_for(tmp_path, "--ci-mode", "basic")
    default = workflow_template_payload_for(tmp_path, "--ci-mode", "default")
    adoption = workflow_template_payload_for(tmp_path, "--ci-mode", "adoption")
    adoption_policy = workflow_template_payload_for(
        tmp_path, "--ci-mode", "adoption-policy"
    )
    strict = workflow_template_payload_for(tmp_path, "--ci-mode", "strict")

    assert basic["commands"] == [
        "python3 -m vibebench config --check",
        "python3 -m vibebench ci",
    ]
    assert default["commands"] == basic["commands"]
    assert adoption["commands"] == ["python3 -m vibebench ci --adoption"]
    assert adoption_policy["commands"] == [
        "python3 -m vibebench ci --adoption-policy"
    ]
    assert (
        "python3 -m vibebench ci --project-scan-policy --onboard-policy"
        in strict["commands"]
    )


def test_workflow_template_invalid_profile_and_ci_mode_fail_clearly(
    tmp_path: Path,
) -> None:
    bad_profile = runner.invoke(
        app,
        [
            "workflow-template",
            "--project-root",
            str(tmp_path),
            "--profile",
            "ruby",
        ],
    )
    bad_mode = runner.invoke(
        app,
        [
            "workflow-template",
            "--project-root",
            str(tmp_path),
            "--ci-mode",
            "maximum",
        ],
    )

    assert bad_profile.exit_code == 1
    assert "Unknown workflow profile" in bad_profile.output
    assert bad_mode.exit_code == 1
    assert "Unknown CI mode" in bad_mode.output


def test_workflow_template_excludes_unsafe_github_automation(
    tmp_path: Path,
) -> None:
    payload = workflow_template_payload_for(tmp_path, "--ci-mode", "strict")
    workflow = payload["workflow_yaml"].lower()

    assert "permissions:\n  contents: read" in payload["workflow_yaml"]
    assert "secrets" not in workflow
    assert "github_token" not in workflow
    assert "\ngh " not in workflow
    assert "deploy-pages" not in workflow
    assert "pages: write" not in workflow
    assert "upload-release" not in workflow
    assert "npm publish" not in workflow
    assert "twine upload" not in workflow
    assert "repository settings" not in workflow


def test_workflow_template_creates_no_runs_or_baselines(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["workflow-template", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    assert not (tmp_path / ".vibebench" / "runs").exists()
    assert not (tmp_path / ".vibebench" / "baselines").exists()


def test_onboard_mentions_workflow_template(tmp_path: Path) -> None:
    payload = onboard_payload_for(tmp_path)

    assert "python3 -m vibebench workflow-template" in payload["suggested_commands"]
    assert (
        "python3 -m vibebench workflow-template --write"
        in payload["suggested_commands"]
    )


def write_workflow(root: Path, body: str, name: str = "vibebench.yml") -> Path:
    path = root / ".github" / "workflows" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def minimal_vibebench_workflow() -> str:
    return """name: VibeBench
on:
  pull_request:
jobs:
  vibebench:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - run: python3 -m vibebench ci
"""


def workflow_with_command(command: str) -> str:
    return minimal_vibebench_workflow().replace(
        "python3 -m vibebench ci", command
    )


def workflow_check_payload_for(root: Path, *extra: str) -> dict[str, object]:
    result = runner.invoke(
        app,
        ["workflow-check", "--project-root", str(root), "--json", *extra],
    )
    assert result.output.lstrip().startswith("{")
    assert result.exit_code == 0
    return json.loads(result.output)



def adoption_ready_payload_for(root: Path, *extra: str) -> dict[str, object]:
    result = runner.invoke(
        app,
        ["adoption-ready", "--project-root", str(root), "--json", *extra],
    )
    assert result.output.lstrip().startswith("{")
    assert result.exit_code == 0
    return json.loads(result.output)


def test_adoption_ready_help_works() -> None:
    result = runner.invoke(
        app,
        ["adoption-ready", "--help"],
        env={"COLUMNS": "120"},
    )
    output = strip_ansi(result.output)

    assert result.exit_code == 0
    assert "adoption-ready" in output
    assert "--require-mode" in output
    assert "adoption-policy" in output


def test_adoption_ready_default_requires_adoption_policy(tmp_path: Path) -> None:
    write_workflow(tmp_path, workflow_with_command("python3 -m vibebench ci"))

    result = runner.invoke(
        app,
        ["adoption-ready", "--project-root", str(tmp_path), "--json"],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["required_mode"] == "adoption-policy"
    assert payload["required_ci_modes"] == ["adoption-policy"]
    assert payload["missing_required_ci_modes"] == ["adoption-policy"]
    assert payload["status"] == "failed"


def test_adoption_ready_json_stdout_is_pure_json(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["adoption-ready", "--project-root", str(tmp_path), "--json"],
    )

    payload = json.loads(result.output)
    assert result.output.lstrip().startswith("{")
    assert payload["status"] == "failed"


def test_adoption_ready_json_output_writes_payload_shape(tmp_path: Path) -> None:
    output = tmp_path / "reports" / "adoption-ready.json"

    result = runner.invoke(
        app,
        [
            "adoption-ready",
            "--project-root",
            str(tmp_path),
            "--json",
            "--json-output",
            str(output),
        ],
    )
    stdout_payload = json.loads(result.output)
    file_payload = json.loads(output.read_text(encoding="utf-8"))

    assert result.exit_code == 1
    assert file_payload["status"] == stdout_payload["status"]
    assert file_payload["checks"]
    assert file_payload["required_ci_modes"] == ["adoption-policy"]


def test_adoption_ready_summary_output_writes_markdown(tmp_path: Path) -> None:
    output = tmp_path / "reports" / "adoption-ready.md"

    result = runner.invoke(
        app,
        [
            "adoption-ready",
            "--project-root",
            str(tmp_path),
            "--summary-output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    summary = output.read_text(encoding="utf-8")
    assert summary.startswith("# VibeBench Adoption Readiness")
    assert "Missing required modes: adoption-policy" in summary
    assert "| Check | Status | Message | Advice |" in summary


def test_adoption_ready_missing_adoption_policy_fails(tmp_path: Path) -> None:
    write_workflow(tmp_path, workflow_with_command("python3 -m vibebench ci"))

    result = runner.invoke(
        app,
        ["adoption-ready", "--project-root", str(tmp_path), "--json"],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert "adoption-policy" in payload["missing_required_ci_modes"]


def test_adoption_ready_workflow_template_adoption_policy_passes(
    tmp_path: Path,
) -> None:
    runner.invoke(app, ["init", "--project-root", str(tmp_path)])
    template = workflow_template_payload_for(
        tmp_path,
        "--ci-mode",
        "adoption-policy",
    )
    write_workflow(tmp_path, str(template["workflow_yaml"]))

    payload = adoption_ready_payload_for(tmp_path)

    assert payload["status"] == "passed"
    assert payload["detected_ci_modes"] == ["adoption-policy"]
    assert payload["missing_required_ci_modes"] == []


def test_adoption_ready_require_mode_adoption_passes(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--project-root", str(tmp_path)])
    template = workflow_template_payload_for(tmp_path, "--ci-mode", "adoption")
    write_workflow(tmp_path, str(template["workflow_yaml"]))

    payload = adoption_ready_payload_for(tmp_path, "--require-mode", "adoption")

    assert payload["status"] == "passed"
    assert payload["required_ci_modes"] == ["adoption"]
    assert payload["detected_ci_modes"] == ["adoption"]


def test_adoption_ready_require_mode_dedupes_deterministically(
    tmp_path: Path,
) -> None:
    runner.invoke(app, ["init", "--project-root", str(tmp_path)])
    write_workflow(
        tmp_path,
        workflow_with_command("python3 -m vibebench ci --adoption-policy")
        + "      - run: python3 -m vibebench ci --adoption\n",
    )

    payload = adoption_ready_payload_for(
        tmp_path,
        "--require-mode",
        "adoption-policy",
        "--require-mode",
        "adoption",
        "--require-mode",
        "adoption-policy",
    )

    assert payload["required_ci_modes"] == ["adoption", "adoption-policy"]
    assert payload["missing_required_ci_modes"] == []


def test_adoption_ready_invalid_mode_fails_fast(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "adoption-ready",
            "--project-root",
            str(tmp_path),
            "--require-mode",
            "preview",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert "--require-mode must be one of" in payload["message"]


def test_adoption_ready_strict_reports_strict_mode(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["adoption-ready", "--project-root", str(tmp_path), "--strict", "--json"],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["strict"] is True
    assert payload["status"] == "failed"


def test_adoption_ready_default_creates_no_workflows_or_runs(
    tmp_path: Path,
) -> None:
    result = runner.invoke(app, ["adoption-ready", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert not (tmp_path / ".github" / "workflows").exists()
    assert not (tmp_path / ".vibebench" / "runs").exists()


def test_workflow_check_missing_default_does_not_create_workflow_dir(
    tmp_path: Path,
) -> None:
    payload = workflow_check_payload_for(tmp_path)

    assert payload["status"] == "passed"
    assert payload["summary"]["warning"] >= 1
    assert payload["workflow_path"] is None
    assert not (tmp_path / ".github").exists()


def test_workflow_check_valid_minimal_vibebench_workflow_passes(
    tmp_path: Path,
) -> None:
    workflow = write_workflow(tmp_path, minimal_vibebench_workflow())

    payload = workflow_check_payload_for(tmp_path)

    assert payload["status"] == "passed"
    assert payload["workflow_path"] == str(workflow)
    assert payload["usable_for_vibebench_ci"] is True
    assert payload["summary"]["failed"] == 0


@pytest.mark.parametrize(
    ("command", "expected_modes"),
    [
        ("python3 -m vibebench ci", ["default"]),
        ("python -m vibebench ci --json", ["default"]),
        ("python3 -m vibebench ci --adoption", ["adoption"]),
        ("python -m vibebench ci --adoption --json", ["adoption"]),
        ("python3 -m vibebench ci --adoption-policy", ["adoption-policy"]),
        ("python -m vibebench ci --adoption-policy --json", ["adoption-policy"]),
        ("uv run python -m vibebench ci", ["default"]),
        ("uv run python3 -m vibebench ci --adoption", ["adoption"]),
        (
            "uv run python -m vibebench ci --adoption-policy --json",
            ["adoption-policy"],
        ),
    ],
)
def test_workflow_check_detects_ci_modes(
    tmp_path: Path, command: str, expected_modes: list[str]
) -> None:
    write_workflow(tmp_path, workflow_with_command(command))

    payload = workflow_check_payload_for(tmp_path)

    assert payload["detected_ci_modes"] == expected_modes


def test_workflow_check_detects_modes_from_multiline_run_block(
    tmp_path: Path,
) -> None:
    write_workflow(
        tmp_path,
        """name: VibeBench
on:
  pull_request:
jobs:
  vibebench:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout
      - run: |
          python3 -m vibebench config --check
          python3 -m vibebench ci --adoption
""",
    )

    payload = workflow_check_payload_for(tmp_path)

    assert payload["detected_ci_modes"] == ["adoption"]


def test_workflow_check_dedupes_detected_modes_in_stable_order(
    tmp_path: Path,
) -> None:
    write_workflow(
        tmp_path,
        minimal_vibebench_workflow()
        + "      - run: python3 -m vibebench ci --adoption-policy\n"
        + "      - run: python3 -m vibebench ci --adoption\n"
        + "      - run: python3 -m vibebench ci --adoption\n",
    )

    payload = workflow_check_payload_for(tmp_path)

    assert payload["detected_ci_modes"] == [
        "default",
        "adoption",
        "adoption-policy",
    ]


def test_workflow_check_all_aggregates_detected_modes_deterministically(
    tmp_path: Path,
) -> None:
    write_workflow(
        tmp_path, workflow_with_command("python3 -m vibebench ci --adoption-policy")
    )
    write_workflow(
        tmp_path, workflow_with_command("python3 -m vibebench ci"), name="ci.yml"
    )

    payload = workflow_check_payload_for(tmp_path, "--all")

    assert payload["detected_ci_modes"] == ["default", "adoption-policy"]


@pytest.mark.parametrize(
    ("mode", "expected_modes"),
    [
        ("default", ["default"]),
        ("adoption", ["adoption"]),
        ("adoption-policy", ["adoption-policy"]),
    ],
)
def test_workflow_check_detects_workflow_template_modes(
    tmp_path: Path, mode: str, expected_modes: list[str]
) -> None:
    generated = runner.invoke(
        app,
        [
            "workflow-template",
            "--project-root",
            str(tmp_path),
            "--ci-mode",
            mode,
            "--json",
        ],
    )
    template_payload = json.loads(generated.output)
    write_workflow(tmp_path, str(template_payload["workflow_yaml"]))

    payload = workflow_check_payload_for(tmp_path)

    assert generated.exit_code == 0
    assert payload["detected_ci_modes"] == expected_modes


@pytest.mark.parametrize(
    ("command", "required_mode"),
    [
        ("python3 -m vibebench ci", "default"),
        ("python3 -m vibebench ci --adoption", "adoption"),
        ("python3 -m vibebench ci --adoption-policy", "adoption-policy"),
    ],
)
def test_workflow_check_require_ci_mode_passes_for_detected_mode(
    tmp_path: Path,
    command: str,
    required_mode: str,
) -> None:
    write_workflow(tmp_path, workflow_with_command(command))

    payload = workflow_check_payload_for(
        tmp_path,
        "--require-ci-mode",
        required_mode,
    )

    required_check = next(
        check for check in payload["checks"] if check["id"] == "required_ci_modes"
    )
    assert payload["required_ci_modes"] == [required_mode]
    assert payload["missing_required_ci_modes"] == []
    assert required_check["status"] == "passed"


def test_workflow_check_require_ci_mode_missing_fails_clearly(tmp_path: Path) -> None:
    write_workflow(tmp_path, workflow_with_command("python3 -m vibebench ci"))

    result = runner.invoke(
        app,
        [
            "workflow-check",
            "--project-root",
            str(tmp_path),
            "--require-ci-mode",
            "adoption",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    required_check = next(
        check for check in payload["checks"] if check["id"] == "required_ci_modes"
    )
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert payload["required_ci_modes"] == ["adoption"]
    assert payload["missing_required_ci_modes"] == ["adoption"]
    assert required_check["status"] == "failed"
    assert "Missing: adoption." in required_check["message"]


def test_workflow_check_require_ci_mode_dedupes_in_stable_order(
    tmp_path: Path,
) -> None:
    write_workflow(
        tmp_path,
        workflow_with_command("python3 -m vibebench ci --adoption-policy")
        + "      - run: python3 -m vibebench ci --adoption\n",
    )

    payload = workflow_check_payload_for(
        tmp_path,
        "--require-ci-mode",
        "adoption-policy",
        "--require-ci-mode",
        "adoption",
        "--require-ci-mode",
        "adoption-policy",
    )

    assert payload["required_ci_modes"] == ["adoption", "adoption-policy"]
    assert payload["missing_required_ci_modes"] == []


def test_workflow_check_require_ci_mode_invalid_value_fails_clearly(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        app,
        [
            "workflow-check",
            "--project-root",
            str(tmp_path),
            "--require-ci-mode",
            "preview",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert payload["message"] == (
        "--require-ci-mode must be one of: default, adoption, adoption-policy. "
        "Received 'preview'."
    )


def test_workflow_check_reports_missing_vibebench_invocation(
    tmp_path: Path,
) -> None:
    write_workflow(
        tmp_path,
        minimal_vibebench_workflow().replace(
            "python3 -m vibebench ci", "python3 -m pytest -q"
        ),
    )

    payload = workflow_check_payload_for(tmp_path)

    assert payload["status"] == "passed"
    assert "vibebench_ci_invocation" in {
        finding["id"] for finding in payload["findings"]
    }


def test_workflow_check_strict_fails_when_vibebench_invocation_missing(
    tmp_path: Path,
) -> None:
    write_workflow(
        tmp_path,
        minimal_vibebench_workflow().replace(
            "python3 -m vibebench ci", "python3 -m pytest -q"
        ),
    )

    result = runner.invoke(
        app,
        ["workflow-check", "--project-root", str(tmp_path), "--strict", "--json"],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert "vibebench_ci_invocation" in {
        finding["id"] for finding in payload["findings"]
    }


def test_workflow_check_risky_commands_warn_and_strict_fails(tmp_path: Path) -> None:
    body = (
        minimal_vibebench_workflow()
        + "      - run: gh release create v1\n      - run: npm publish\n"
    )
    workflow = write_workflow(tmp_path, body)

    payload = workflow_check_payload_for(tmp_path, "--path", str(workflow))
    strict = runner.invoke(
        app,
        [
            "workflow-check",
            "--project-root",
            str(tmp_path),
            "--path",
            str(workflow),
            "--strict",
            "--json",
        ],
    )
    strict_payload = json.loads(strict.output)

    assert payload["status"] == "passed"
    assert {"gh_release", "npm_publish"} <= {
        finding["id"] for finding in payload["findings"]
    }
    assert strict.exit_code == 1
    assert strict_payload["status"] == "failed"


def test_workflow_check_path_checks_specific_file(tmp_path: Path) -> None:
    other = write_workflow(tmp_path, minimal_vibebench_workflow(), name="other.yml")

    payload = workflow_check_payload_for(tmp_path, "--path", str(other))

    assert payload["workflow_path"] == str(other)
    assert payload["status"] == "passed"


def test_workflow_check_json_output_and_summary_output(tmp_path: Path) -> None:
    write_workflow(tmp_path, minimal_vibebench_workflow())
    json_output = tmp_path / "check" / "workflow-check.json"
    summary_output = tmp_path / "check" / "workflow-check.md"

    result = runner.invoke(
        app,
        [
            "workflow-check",
            "--project-root",
            str(tmp_path),
            "--json",
            "--require-ci-mode",
            "default",
            "--json-output",
            str(json_output),
            "--summary-output",
            str(summary_output),
        ],
    )
    payload = json.loads(result.output)
    written = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = summary_output.read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert payload == written
    assert markdown.startswith("# VibeBench Workflow Check")
    assert "- Detected CI modes: default" in markdown
    assert "- Required CI modes: default (missing: none)" in markdown


def test_workflow_check_does_not_modify_existing_workflow(tmp_path: Path) -> None:
    workflow = write_workflow(tmp_path, minimal_vibebench_workflow())
    before = workflow.read_text(encoding="utf-8")

    result = runner.invoke(app, ["workflow-check", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert workflow.read_text(encoding="utf-8") == before


def test_workflow_check_empty_workflow_reports_clearly(tmp_path: Path) -> None:
    write_workflow(tmp_path, "")

    payload = workflow_check_payload_for(tmp_path)

    assert "workflow_not_empty" in {finding["id"] for finding in payload["findings"]}


def test_workflow_check_existing_template_output_passes(tmp_path: Path) -> None:
    generated = runner.invoke(
        app,
        ["workflow-template", "--project-root", str(tmp_path), "--write"],
    )
    checked = runner.invoke(
        app,
        ["workflow-check", "--project-root", str(tmp_path), "--strict", "--json"],
    )
    payload = json.loads(checked.output)

    assert generated.exit_code == 0
    assert checked.exit_code == 0
    assert payload["usable_for_vibebench_ci"] is True


def test_workflow_check_default_omits_policy_fields(tmp_path: Path) -> None:
    write_workflow(tmp_path, minimal_vibebench_workflow())

    payload = workflow_check_payload_for(tmp_path)

    assert "policy_status" not in payload
    assert "policy_findings" not in payload
    assert "required_ci_modes" not in payload
    assert "missing_required_ci_modes" not in payload


def test_workflow_check_enforce_policy_passes_with_config_and_ci_ready(
    tmp_path: Path,
) -> None:
    runner.invoke(app, ["init", "--project-root", str(tmp_path), "--profile", "python"])
    write_workflow(tmp_path, minimal_vibebench_workflow())

    payload = workflow_check_payload_for(tmp_path, "--enforce-policy")

    assert payload["status"] == "passed"
    assert payload["policy_evaluated"] is True
    assert payload["policy_status"] == "passed"


def test_workflow_check_enforce_policy_fails_when_config_is_missing(
    tmp_path: Path,
) -> None:
    write_workflow(tmp_path, minimal_vibebench_workflow())

    result = runner.invoke(
        app,
        [
            "workflow-check",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert result.output.lstrip().startswith("{")
    assert payload["status"] == "failed"
    assert payload["policy_status"] == "failed"
    assert {finding["rule"] for finding in payload["policy_findings"]} == {
        "require_config",
    }


def test_workflow_check_enforce_policy_required_ci_modes_fail_when_missing(
    tmp_path: Path,
) -> None:
    write_workflow_check_policy_config(
        tmp_path,
        """    fail_on_blockers: false
    fail_on_errors: false
    fail_on_warnings: false
    require_config: true
    require_ci_ready: false
    required_ci_modes:
      - adoption-policy
    allowed_workflow_names: []
    allowed_action_prefixes: []
""",
    )
    write_workflow(tmp_path, minimal_vibebench_workflow())

    result = runner.invoke(
        app,
        [
            "workflow-check",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["policy_status"] == "failed"
    assert payload["effective_policy"]["required_ci_modes"] == ["adoption-policy"]
    assert any(
        finding["rule"] == "required_ci_modes"
        for finding in payload["policy_findings"]
    )


def test_workflow_check_enforce_policy_can_fail_on_warning_findings(
    tmp_path: Path,
) -> None:
    write_workflow_check_policy_config(
        tmp_path,
        """    fail_on_blockers: false
    fail_on_errors: false
    fail_on_warnings: true
    require_config: true
    require_ci_ready: false
    allowed_workflow_names: []
    allowed_action_prefixes: []
""",
    )
    write_workflow(tmp_path, minimal_vibebench_workflow())

    result = runner.invoke(
        app,
        [
            "workflow-check",
            "--project-root",
            str(tmp_path),
            "--enforce-policy",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 1
    assert payload["policy_status"] == "failed"
    assert any(
        finding["rule"] == "fail_on_warnings"
        for finding in payload["policy_findings"]
    )


def test_workflow_check_allowed_action_prefixes_can_suppress_unpinned_warnings(
    tmp_path: Path,
) -> None:
    write_workflow_check_policy_config(
        tmp_path,
        """    fail_on_blockers: false
    fail_on_errors: false
    fail_on_warnings: true
    require_config: true
    require_ci_ready: false
    allowed_workflow_names: []
    allowed_action_prefixes:
      - actions/
""",
    )
    write_workflow(tmp_path, minimal_vibebench_workflow())

    payload = workflow_check_payload_for(tmp_path, "--enforce-policy")

    assert payload["status"] == "passed"
    assert payload["policy_status"] == "passed"


def test_config_command_without_file_prints_defaults(tmp_path: Path) -> None:
    result = runner.invoke(app, ["config", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "built-in defaults" in result.output
    assert "project" in result.output
    assert "checks" in result.output
    assert "gate" in result.output
    assert "risk" in result.output


def test_config_command_with_valid_config(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    result = runner.invoke(app, ["config", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "vibebench-project" in result.output
    assert "pytest -q" in result.output
    assert "max_patch_lines" in result.output


def test_config_command_example_outputs_starter_yaml(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["config", "--project-root", str(tmp_path), "--example"]
    )

    assert result.exit_code == 0
    assert "project:" in result.output
    assert "checks:" in result.output
    assert "compare:" in result.output
    assert "fail_on_regression" in result.output


def test_config_command_write_example_writes_yaml_file(tmp_path: Path) -> None:
    output = tmp_path / "config.example.yaml"

    result = runner.invoke(
        app,
        [
            "config",
            "--project-root",
            str(tmp_path),
            "--write-example",
            str(output),
        ],
    )

    written = output.read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert f"Config example written: {output}" in result.output
    assert "compare:" in written
    assert "fail_on_regression: false" in written
    assert written.endswith("\n")


def test_config_command_write_example_missing_parent_fails_clearly(
    tmp_path: Path,
) -> None:
    output = tmp_path / "missing" / "config.example.yaml"

    result = runner.invoke(
        app,
        [
            "config",
            "--project-root",
            str(tmp_path),
            "--write-example",
            str(output),
        ],
    )

    assert result.exit_code == 1
    assert "parent does not exist" in result.output
    assert not output.exists()


def test_config_command_init_creates_starter_config(tmp_path: Path) -> None:
    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    generated = config_path(tmp_path).read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert f"Config written: {config_path(tmp_path)}" in result.output
    assert "compare:" in generated
    assert "fail_on_regression" in generated
    assert generated.endswith("\n")


def test_config_command_init_refuses_existing_config(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("existing: true\n", encoding="utf-8")

    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    assert result.exit_code == 1
    assert "Config already exists" in result.output
    assert "--force" in result.output
    assert config_path(tmp_path).read_text(encoding="utf-8") == "existing: true\n"


def test_config_command_init_force_overwrites_existing_config(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("existing: true\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--init", "--force"],
    )

    generated = config_path(tmp_path).read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert f"Config overwritten: {config_path(tmp_path)}" in result.output
    assert "existing: true" not in generated
    assert "compare:" in generated
    assert "fail_on_regression: false" in generated


def test_config_command_init_dry_run_plans_without_writing(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "config",
            "--project-root",
            str(tmp_path),
            "--init",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert not config_path(tmp_path).exists()
    assert not config_path(tmp_path).parent.exists()
    assert str(config_path(tmp_path)) in result.output
    assert "Would write: yes" in result.output
    assert "Force: no" in result.output


def test_config_command_init_dry_run_json_before_and_after_init(
    tmp_path: Path,
) -> None:
    before = runner.invoke(
        app,
        [
            "config",
            "--project-root",
            str(tmp_path),
            "--init",
            "--dry-run",
            "--json",
        ],
    )
    before_payload = json.loads(before.output)

    assert before.exit_code == 0
    assert sorted(before_payload) == [
        "config_path",
        "dry_run",
        "exists",
        "force",
        "project_root",
        "status",
        "would_write",
    ]
    assert before_payload == {
        "status": "planned",
        "project_root": str(tmp_path),
        "config_path": str(config_path(tmp_path)),
        "exists": False,
        "would_write": True,
        "force": False,
        "dry_run": True,
    }
    assert not config_path(tmp_path).exists()
    assert not config_path(tmp_path).parent.exists()

    init_result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--init"],
    )
    after = runner.invoke(
        app,
        [
            "config",
            "--project-root",
            str(tmp_path),
            "--init",
            "--dry-run",
            "--json",
        ],
    )
    after_payload = json.loads(after.output)

    assert init_result.exit_code == 0
    assert after.exit_code == 0
    assert after_payload["status"] == "blocked"
    assert after_payload["project_root"] == str(tmp_path)
    assert after_payload["config_path"] == str(config_path(tmp_path))
    assert after_payload["exists"] is True
    assert after_payload["would_write"] is False
    assert after_payload["force"] is False
    assert after_payload["dry_run"] is True


def test_config_command_init_dry_run_force_preserves_existing_config(
    tmp_path: Path,
) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("existing: true\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "config",
            "--project-root",
            str(tmp_path),
            "--init",
            "--dry-run",
            "--force",
            "--json",
        ],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["exists"] is True
    assert payload["would_write"] is True
    assert payload["force"] is True
    assert payload["dry_run"] is True
    assert config_path(tmp_path).read_text(encoding="utf-8") == "existing: true\n"


def test_config_command_path_outputs_expected_config_path(tmp_path: Path) -> None:
    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--path"])

    assert result.exit_code == 0
    assert ".vibebench/config.yaml" in result.output.replace("\\", "/")
    assert result.output.strip() == str(config_path(tmp_path))


def test_config_command_path_json_before_and_after_init(tmp_path: Path) -> None:
    before = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--path", "--json"],
    )
    before_payload = json.loads(before.output)

    assert before.exit_code == 0
    assert before_payload == {
        "project_root": str(tmp_path),
        "config_path": str(config_path(tmp_path)),
        "exists": False,
    }

    init_result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--init"],
    )
    after = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--path", "--json"],
    )
    after_payload = json.loads(after.output)

    assert init_result.exit_code == 0
    assert after.exit_code == 0
    assert after_payload["project_root"] == str(tmp_path)
    assert after_payload["config_path"] == str(config_path(tmp_path))
    assert after_payload["exists"] is True


def test_config_command_path_respects_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "example"
    result = runner.invoke(
        app,
        ["config", "--project-root", str(project_root), "--path", "--json"],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["project_root"] == str(project_root)
    assert payload["config_path"] == str(config_path(project_root))
    assert payload["exists"] is False


def test_config_command_json_is_valid(tmp_path: Path) -> None:
    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert sorted(payload) == [
        "checks",
        "compare",
        "gate",
        "metrics_diff",
        "onboard",
        "preflight",
        "project",
        "project_scan",
        "regression",
        "risk",
        "workflow_check",
    ]
    assert payload["compare"]["fail_on_regression"] is False
    assert payload["project"]["name"] == "vibebench-project"
    assert payload["checks"]["test"] == ["pytest -q"]
    assert payload["gate"]["min_score"] == 80
    assert payload["risk"]["max_patch_lines"] == 500
    assert payload["onboard"]["policy"]["fail_on_blockers"] is True
    assert payload["regression"]["fail_on_missing_metrics"] is True
    assert payload["regression"]["enabled"] is False
    assert payload["onboard"]["policy"]["require_config"] is True
    assert payload["workflow_check"]["policy"]["fail_on_blockers"] is True


def test_config_command_validate_succeeds_for_valid_config(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    result = runner.invoke(
        app, ["config", "--project-root", str(tmp_path), "--validate"]
    )

    assert result.exit_code == 0
    assert "VibeBench config is valid" in result.output


def test_config_command_invalid_config_fails_clearly(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("project:\n  name: ''\n", encoding="utf-8")

    result = runner.invoke(app, ["config", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "invalid" in result.output
    assert "project.name" in result.output


def test_config_command_show_source_includes_sources(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    result = runner.invoke(
        app, ["config", "--project-root", str(tmp_path), "--show-source"]
    )

    assert result.exit_code == 0
    assert "Source" in result.output
    assert "config file" in result.output


def test_config_command_does_not_break_existing_check_and_gate(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])
    config = config_path(tmp_path).read_text(encoding="utf-8")
    config = config.replace("pytest -q", f"{sys.executable} -c \"print('test ok')\"")
    config = config.replace("ruff check .", f"{sys.executable} -c \"print('lint ok')\"")
    config_path(tmp_path).write_text(config, encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True)

    check = runner.invoke(app, ["check", "--project-root", str(tmp_path)])
    gate = runner.invoke(app, ["gate", "--project-root", str(tmp_path)])

    assert check.exit_code == 0
    assert gate.exit_code == 0


def test_config_show_human_output(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--show"])

    assert result.exit_code == 0
    assert str(config_path(tmp_path)) in result.output.replace("\n", "")
    assert "vibebench-project" in result.output
    assert "pytest -q" in result.output
    assert "min_score" in result.output
    assert "max_patch_lines" in result.output


def test_config_show_json_output(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--show", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert sorted(payload) == [
        "commands",
        "config_path",
        "gate",
        "metrics_diff",
        "onboard",
        "preflight",
        "project",
        "project_scan",
        "regression",
        "risk",
        "workflow_check",
    ]
    assert payload["config_path"] == str(config_path(tmp_path))
    assert payload["project"]["name"] == "vibebench-project"
    assert payload["commands"]["test"] == ["pytest -q"]
    assert payload["gate"]["min_score"] == 80
    assert payload["risk"]["max_patch_lines"] == 500


def test_config_show_missing_config_fails_clearly(tmp_path: Path) -> None:
    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--show"])

    assert result.exit_code == 1
    assert "No VibeBench config found" in result.output


def test_config_show_json_missing_config_keeps_stdout_clean(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--show", "--json"],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No VibeBench config found" in result.stderr


def test_config_show_invalid_config_fails_clearly(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("project:\n  name: ''\n", encoding="utf-8")

    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--show"])

    assert result.exit_code == 1
    assert "invalid" in result.output
    assert "project.name" in result.output


def test_config_validate_still_works_with_show_option_added(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--validate"],
    )

    assert result.exit_code == 0
    assert "VibeBench config is valid" in result.output


def test_config_check_human_output(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--check"])

    assert result.exit_code == 0
    assert "VibeBench config check" in result.output
    assert "overall" in result.output.lower()
    assert "config_file_exists" in result.output
    assert "command_strings" in result.output


def test_config_check_json_output(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--check", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert sorted(payload) == ["checks", "config_path", "overall_status"]
    assert payload["config_path"] == str(config_path(tmp_path))
    assert payload["overall_status"] == "passed"
    assert {check["name"] for check in payload["checks"]} >= {
        "config_file_exists",
        "config_validates",
        "project_name",
        "command_groups",
        "command_strings",
        "gate_policy",
        "risk_policy",
        "regression_policy",
        "onboard_policy",
        "preflight_policy",
    }
    assert all(
        sorted(check) == ["message", "name", "status"] for check in payload["checks"]
    )


def test_config_check_missing_config_fails_clearly(tmp_path: Path) -> None:
    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--check"])

    assert result.exit_code == 1
    assert "No VibeBench config found" in result.output


def test_config_check_json_missing_config_keeps_stdout_clean(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--check", "--json"],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No VibeBench config found" in result.stderr


def test_config_check_invalid_config_fails_clearly(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("project:\n  name: ''\n", encoding="utf-8")

    result = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--check"])

    assert result.exit_code == 1
    assert "invalid" in result.output
    assert "project.name" in result.output


def test_config_check_detects_empty_command_string(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text(
        """
project:
  name: demo
checks:
  test:
    - ""
  lint:
    - ruff check .
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--check", "--json"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["overall_status"] == "failed"
    command_check = next(
        check for check in payload["checks"] if check["name"] == "command_strings"
    )
    assert command_check["status"] == "failed"
    assert "Empty command string" in command_check["message"]


def test_config_check_does_not_break_validate_or_show(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    validate = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--validate"],
    )
    show = runner.invoke(app, ["config", "--project-root", str(tmp_path), "--show"])
    show_json = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--show", "--json"],
    )

    assert validate.exit_code == 0
    assert "VibeBench config is valid" in validate.output
    assert show.exit_code == 0
    assert "vibebench-project" in show.output
    assert show_json.exit_code == 0
    assert json.loads(show_json.output)["project"]["name"] == "vibebench-project"


def test_config_check_advice_human_output_for_empty_command(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text(
        """
project:
  name: demo
checks:
  test:
    - ""
  lint:
    - ruff check .
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--check", "--advice"],
    )

    assert result.exit_code == 1
    assert "Advice" in result.output
    assert "Replace empty command entries" in result.output


def test_config_check_json_advice_output(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text(
        """
project:
  name: demo
checks:
  test:
    - ""
  lint:
    - ruff check .
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "config",
            "--project-root",
            str(tmp_path),
            "--check",
            "--json",
            "--advice",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["advice"] is True
    command_check = next(
        check for check in payload["checks"] if check["name"] == "command_strings"
    )
    assert command_check["status"] == "failed"
    assert "advice" in command_check
    assert "pytest -q" in command_check["advice"]


def test_config_check_json_without_advice_has_no_advice_fields(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text(
        """
project:
  name: demo
checks:
  test:
    - ""
  lint:
    - ruff check .
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--check", "--json"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert "advice" not in payload
    assert all("advice" not in check for check in payload["checks"])


def test_config_check_missing_config_advice(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--check", "--advice"],
    )

    assert result.exit_code == 1
    assert "No VibeBench config found" in result.output
    assert "python -m vibebench init" in result.output


def test_config_check_write_json(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])
    output = tmp_path / "config-check.json"

    result = runner.invoke(
        app,
        [
            "config",
            "--project-root",
            str(tmp_path),
            "--check",
            "--write-json",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "passed"
    assert payload["config_path"] == str(config_path(tmp_path))


def test_config_check_write_summary(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])
    output = tmp_path / "config-check.md"

    result = runner.invoke(
        app,
        [
            "config",
            "--project-root",
            str(tmp_path),
            "--check",
            "--write-summary",
            str(output),
        ],
    )

    assert result.exit_code == 0
    markdown = output.read_text(encoding="utf-8")
    assert "# VibeBench Config Check" in markdown
    assert "Overall status" in markdown


def test_config_check_json_write_json_keeps_stdout_pure(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])
    output = tmp_path / "config-check.json"

    result = runner.invoke(
        app,
        [
            "config",
            "--project-root",
            str(tmp_path),
            "--check",
            "--json",
            "--write-json",
            str(output),
        ],
    )

    assert result.exit_code == 0
    stdout_payload = json.loads(result.output)
    file_payload = json.loads(output.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload


def test_config_check_advice_write_summary_includes_advice(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text(
        """
project:
  name: demo
checks:
  test:
    - ""
  lint:
    - ruff check .
""".lstrip(),
        encoding="utf-8",
    )
    output = tmp_path / "config-check.md"

    result = runner.invoke(
        app,
        [
            "config",
            "--project-root",
            str(tmp_path),
            "--check",
            "--advice",
            "--write-summary",
            str(output),
        ],
    )

    assert result.exit_code == 1
    markdown = output.read_text(encoding="utf-8")
    assert "## Advice" in markdown
    assert "Replace empty command entries" in markdown


def write_release_checklist_project(
    root: Path,
    *,
    version: str = "0.3.0",
    notes_version: str | None = "v0.3.0",
) -> None:
    root.joinpath("pyproject.toml").write_text(
        f'[project]\nname = "vibebench-arena"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    if notes_version is not None:
        root.joinpath(f"RELEASE_NOTES_{notes_version}.md").write_text(
            "# Release notes\n",
            encoding="utf-8",
        )


def stub_release_checklist_dependencies(
    monkeypatch,
    *,
    local_tag: bool = True,
    remote_tag: bool = True,
    remote_error: bool = False,
) -> None:
    monkeypatch.setattr(
        "vibebench.cli.run_package_check",
        lambda root: SimpleNamespace(ready=True),
    )
    monkeypatch.setattr(
        "vibebench.cli.run_release_check",
        lambda root: SimpleNamespace(ready=True),
    )
    monkeypatch.setattr(
        "vibebench.cli.run_doctor",
        lambda root, strict, advice: SimpleNamespace(overall_status="passed"),
    )

    def fake_git(root: Path, args: list[str]) -> SimpleNamespace:
        if args == ["status", "--porcelain"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[:2] == ["tag", "--list"]:
            tag = args[2]
            return SimpleNamespace(
                returncode=0,
                stdout=f"{tag}\n" if local_tag else "",
                stderr="",
            )
        if args[:2] == ["ls-remote", "origin"]:
            if remote_error:
                return SimpleNamespace(returncode=128, stdout="", stderr="offline")
            tag = args[2].removeprefix("refs/tags/")
            return SimpleNamespace(
                returncode=0,
                stdout=f"abc123\trefs/tags/{tag}\n" if remote_tag else "",
                stderr="",
            )
        return SimpleNamespace(returncode=1, stdout="", stderr="unexpected git args")

    monkeypatch.setattr("vibebench.cli.release_checklist_git", fake_git)


def test_release_checklist_human_output(tmp_path: Path, monkeypatch) -> None:
    write_release_checklist_project(tmp_path)
    stub_release_checklist_dependencies(monkeypatch)

    result = runner.invoke(app, ["release-checklist", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "VibeBench release checklist" in result.output
    assert "working_tree_clean" in result.output
    assert "GitHub Release page" in result.output


def test_release_checklist_json_output_is_clean(tmp_path: Path, monkeypatch) -> None:
    write_release_checklist_project(tmp_path)
    stub_release_checklist_dependencies(monkeypatch)

    result = runner.invoke(
        app,
        ["release-checklist", "--project-root", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["overall_status"] == "warning"
    assert payload["target_version"] == "v0.3.0"
    assert payload["package_version"] == "0.3.0"
    assert {check["name"] for check in payload["checks"]} >= {
        "working_tree_clean",
        "package_metadata_version",
        "release_notes_file",
        "local_tag_exists",
        "remote_tag_exists",
        "package_check",
        "release_check",
        "doctor_strict",
        "github_release_page",
    }


def test_release_checklist_write_json_writes_valid_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_release_checklist_project(tmp_path)
    stub_release_checklist_dependencies(monkeypatch)
    output_path = tmp_path / "release-checklist.json"

    result = runner.invoke(
        app,
        [
            "release-checklist",
            "--project-root",
            str(tmp_path),
            "--write-json",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "warning"
    assert payload["target_version"] == "v0.3.0"
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_release_checklist_write_summary_writes_markdown(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_release_checklist_project(tmp_path)
    stub_release_checklist_dependencies(monkeypatch)
    output_path = tmp_path / "release-checklist.md"

    result = runner.invoke(
        app,
        [
            "release-checklist",
            "--project-root",
            str(tmp_path),
            "--write-summary",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    markdown = output_path.read_text(encoding="utf-8")
    assert "# VibeBench Release Checklist" in markdown
    assert "- Version: `v0.3.0`" in markdown
    assert "- Overall status: `warning`" in markdown
    assert "| Item | Status | Message |" in markdown
    assert "No tag is created" in markdown
    assert "No GitHub Release is created" in markdown
    assert "No package publish or upload is performed" in markdown
    assert "No version bump is performed" in markdown


def test_release_checklist_json_stdout_stays_pure_when_writing_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_release_checklist_project(tmp_path)
    stub_release_checklist_dependencies(monkeypatch)
    output_path = tmp_path / "release-checklist.json"

    result = runner.invoke(
        app,
        [
            "release-checklist",
            "--project-root",
            str(tmp_path),
            "--json",
            "--write-json",
            str(output_path),
        ],
    )

    stdout_payload = json.loads(result.output)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert stdout_payload == file_payload
    assert stdout_payload["target_version"] == "v0.3.0"


def test_release_checklist_version_write_summary_records_requested_version(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_release_checklist_project(tmp_path, version="0.3.0", notes_version="v0.4.0")
    stub_release_checklist_dependencies(monkeypatch)
    output_path = tmp_path / "release-checklist.md"

    result = runner.invoke(
        app,
        [
            "release-checklist",
            "--project-root",
            str(tmp_path),
            "--version",
            "v0.4.0",
            "--write-summary",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    markdown = output_path.read_text(encoding="utf-8")
    assert "- Version: `v0.4.0`" in markdown
    assert "target is v0.4.0" in markdown


def test_release_checklist_missing_output_parent_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_release_checklist_project(tmp_path)
    stub_release_checklist_dependencies(monkeypatch)
    output_path = tmp_path / "missing" / "release-checklist.json"

    result = runner.invoke(
        app,
        [
            "release-checklist",
            "--project-root",
            str(tmp_path),
            "--write-json",
            str(output_path),
        ],
    )

    assert result.exit_code == 1
    assert "output parent does not exist" in result.output


def test_release_checklist_output_directory_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_release_checklist_project(tmp_path)
    stub_release_checklist_dependencies(monkeypatch)

    result = runner.invoke(
        app,
        [
            "release-checklist",
            "--project-root",
            str(tmp_path),
            "--write-summary",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert "output path is a directory" in result.output


def test_release_checklist_infers_target_version(tmp_path: Path, monkeypatch) -> None:
    write_release_checklist_project(tmp_path, version="0.3.0", notes_version="v0.3.0")
    stub_release_checklist_dependencies(monkeypatch)

    result = runner.invoke(
        app,
        ["release-checklist", "--project-root", str(tmp_path), "--json"],
    )
    payload = json.loads(result.stdout)

    assert result.exit_code == 0
    assert payload["target_version"] == "v0.3.0"


def test_release_checklist_explicit_version(tmp_path: Path, monkeypatch) -> None:
    write_release_checklist_project(tmp_path, version="0.3.0", notes_version="v0.4.0")
    stub_release_checklist_dependencies(monkeypatch)

    result = runner.invoke(
        app,
        [
            "release-checklist",
            "--project-root",
            str(tmp_path),
            "--version",
            "v0.4.0",
            "--json",
        ],
    )
    payload = json.loads(result.stdout)
    version_check = next(
        check
        for check in payload["checks"]
        if check["name"] == "package_metadata_version"
    )

    assert result.exit_code == 0
    assert payload["target_version"] == "v0.4.0"
    assert version_check["status"] == "warning"


def test_release_checklist_missing_release_notes_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_release_checklist_project(tmp_path, notes_version=None)
    stub_release_checklist_dependencies(monkeypatch)

    result = runner.invoke(
        app,
        ["release-checklist", "--project-root", str(tmp_path), "--json"],
    )
    payload = json.loads(result.stdout)
    notes_check = next(
        check for check in payload["checks"] if check["name"] == "release_notes_file"
    )

    assert result.exit_code == 1
    assert payload["overall_status"] == "failed"
    assert notes_check["status"] == "failed"
    assert "RELEASE_NOTES_v0.3.0.md" in notes_check["message"]


def test_release_checklist_remote_lookup_failure_is_warning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_release_checklist_project(tmp_path)
    stub_release_checklist_dependencies(monkeypatch, remote_error=True)

    result = runner.invoke(
        app,
        ["release-checklist", "--project-root", str(tmp_path), "--json"],
    )
    payload = json.loads(result.stdout)
    remote_check = next(
        check for check in payload["checks"] if check["name"] == "remote_tag_exists"
    )

    assert result.exit_code == 0
    assert remote_check["status"] == "warning"
    assert "Could not inspect remote tag" in remote_check["message"]


def test_release_checklist_does_not_modify_files(tmp_path: Path, monkeypatch) -> None:
    write_release_checklist_project(tmp_path)
    stub_release_checklist_dependencies(monkeypatch)
    before = {
        path.relative_to(tmp_path): path.read_text(encoding="utf-8")
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    result = runner.invoke(app, ["release-checklist", "--project-root", str(tmp_path)])

    after = {
        path.relative_to(tmp_path): path.read_text(encoding="utf-8")
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert result.exit_code == 0
    assert after == before


def test_config_check_advice_mentions_stable_regression_gate(
    tmp_path: Path,
) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--check", "--advice", "--json"],
    )

    payload = json.loads(result.output)
    regression = next(
        check for check in payload["checks"] if check["name"] == "regression_policy"
    )
    assert result.exit_code == 0
    assert "baseline --set-latest --label stable" in regression["advice"]


def test_config_check_rejects_invalid_regression_policy(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text(
        """project:
  name: demo
checks:
  test:
    - pytest -q
regression:
  max_risk_increase: -1
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--check", "--json"],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "regression.max_risk_increase" in result.stderr


def test_config_check_reports_metrics_diff_policy(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--check", "--advice", "--json"],
    )

    payload = json.loads(result.output)
    policy = next(
        check for check in payload["checks"] if check["name"] == "metrics_diff_policy"
    )
    assert result.exit_code == 0
    assert "Metrics-diff policy is internally consistent" in policy["message"]
    assert "metrics_diff.policy.enabled=true" in policy["advice"]


def test_config_check_reports_onboard_policy(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--check", "--advice", "--json"],
    )

    payload = json.loads(result.output)
    policy = next(
        check for check in payload["checks"] if check["name"] == "onboard_policy"
    )
    assert result.exit_code == 0
    assert "Onboard policy is internally consistent" in policy["message"]
    assert "onboard --enforce-policy" in policy["advice"]




def test_config_check_reports_preflight_policy(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--check", "--json"],
    )
    payload = json.loads(result.output)

    assert result.exit_code == 0
    check = next(
        check for check in payload["checks"] if check["name"] == "preflight_policy"
    )
    assert check["status"] == "passed"
    assert "require_project_scan_ready=true" in check["message"]


def test_config_check_reports_workflow_check_policy(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "--project-root", str(tmp_path), "--init"])

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--check", "--advice", "--json"],
    )

    payload = json.loads(result.output)
    policy = next(
        check for check in payload["checks"] if check["name"] == "workflow_check_policy"
    )
    assert result.exit_code == 0
    assert "Workflow-check policy is internally consistent" in policy["message"]
    assert "required_ci_modes=none" in policy["message"]
    assert "workflow-check --enforce-policy" in policy["advice"]


def test_config_check_rejects_invalid_metrics_diff_policy(tmp_path: Path) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text(
        """project:
  name: demo
checks:
  test:
    - pytest -q
metrics_diff:
  policy:
    custom_rules:
      - metric: latency_ms
        max_increase: -1
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["config", "--project-root", str(tmp_path), "--check", "--json"],
    )

    assert result.exit_code == 1
