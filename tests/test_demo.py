import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench import demo as demo_module
from vibebench.cli import app

runner = CliRunner()


def make_sample_pack(root: Path) -> Path:
    sample_dir = root / "examples" / "showcase-artifacts" / "sample"
    sample_dir.mkdir(parents=True)
    files = {
        "README.md": "# Sample\n",
        "ci-summary.md": "# CI Summary\n",
        "ci-plan.json": "{}\n",
        "artifact-inventory.json": "{}\n",
        "compare-summary.md": "# Compare\n",
        "release-audit-summary.md": "# Release Audit\n",
        "manifest.json": "{}\n",
    }
    for name, content in files.items():
        sample_dir.joinpath(name).write_text(content, encoding="utf-8")
    return sample_dir


def test_demo_human_output_mentions_showcase_local_artifacts(tmp_path: Path) -> None:
    make_sample_pack(tmp_path)

    result = runner.invoke(app, ["demo", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    output = result.output.lower()
    assert "showcase" in output
    assert "local" in output
    assert "artifact" in output


def test_demo_json_output_is_pure_json(tmp_path: Path) -> None:
    make_sample_pack(tmp_path)

    result = runner.invoke(app, ["demo", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "available"
    assert payload["available"] is True
    assert payload["demo_name"] == "local showcase demo"


def test_demo_json_includes_expected_artifact_names(tmp_path: Path) -> None:
    make_sample_pack(tmp_path)

    result = runner.invoke(app, ["demo", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    names = {item["name"] for item in payload["artifacts"]}
    assert names == {
        "README.md",
        "ci-summary.md",
        "ci-plan.json",
        "artifact-inventory.json",
        "compare-summary.md",
        "release-audit-summary.md",
        "manifest.json",
    }


def test_demo_copy_to_copies_sample_files(tmp_path: Path) -> None:
    make_sample_pack(tmp_path)
    output_dir = tmp_path / "copied"

    result = runner.invoke(
        app,
        ["demo", "--project-root", str(tmp_path), "--copy-to", str(output_dir)],
    )

    assert result.exit_code == 0
    assert output_dir.joinpath("README.md").read_text(encoding="utf-8") == "# Sample\n"
    assert output_dir.joinpath("ci-plan.json").is_file()
    assert output_dir.joinpath("artifact-inventory.json").is_file()


def test_demo_json_copy_to_remains_pure_json(tmp_path: Path) -> None:
    make_sample_pack(tmp_path)
    output_dir = tmp_path / "copied"

    result = runner.invoke(
        app,
        [
            "demo",
            "--project-root",
            str(tmp_path),
            "--json",
            "--copy-to",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["copied"] is True
    assert payload["output_dir"] == output_dir.as_posix()
    assert "README.md" in payload["copied_files"]


def test_demo_copy_conflict_fails_without_force(tmp_path: Path) -> None:
    make_sample_pack(tmp_path)
    output_dir = tmp_path / "copied"
    output_dir.mkdir()
    output_dir.joinpath("README.md").write_text("conflict\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["demo", "--project-root", str(tmp_path), "--copy-to", str(output_dir)],
    )

    assert result.exit_code == 1
    assert "Conflicting files" in result.output
    assert output_dir.joinpath("README.md").read_text(encoding="utf-8") == "conflict\n"


def test_demo_copy_force_replaces_conflicting_files(tmp_path: Path) -> None:
    make_sample_pack(tmp_path)
    output_dir = tmp_path / "copied"
    output_dir.mkdir()
    output_dir.joinpath("README.md").write_text("conflict\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "demo",
            "--project-root",
            str(tmp_path),
            "--copy-to",
            str(output_dir),
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert output_dir.joinpath("README.md").read_text(encoding="utf-8") == "# Sample\n"


def test_demo_missing_sample_dir_reports_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(demo_module, "SAMPLE_DIR", Path("missing-sample"))

    result = runner.invoke(app, ["demo", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["available"] is False
    assert payload["status"] == "missing"
    assert "missing" in payload["message"].lower()
