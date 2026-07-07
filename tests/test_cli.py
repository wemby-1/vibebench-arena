import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.config import load_config

runner = CliRunner()

def test_cli_help_works() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Codex-first quality gate" in result.output
    assert "version" in result.output
    assert "init" in result.output


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
        "project",
        "regression",
        "risk",
    ]
    assert payload["compare"]["fail_on_regression"] is False
    assert payload["project"]["name"] == "vibebench-project"
    assert payload["checks"]["test"] == ["pytest -q"]
    assert payload["gate"]["min_score"] == 80
    assert payload["risk"]["max_patch_lines"] == 500
    assert payload["regression"]["fail_on_missing_metrics"] is True
    assert payload["regression"]["enabled"] is False

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
        "project",
        "regression",
        "risk",
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
    }
    assert all(
        sorted(check) == ["message", "name", "status"]
        for check in payload["checks"]
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
        '[project]\n'
        'name = "vibebench-arena"\n'
        f'version = "{version}"\n',
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
