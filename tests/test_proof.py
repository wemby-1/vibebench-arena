import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

runner = CliRunner()
REQUIRED_KEYS = {
    "status",
    "project",
    "summary",
    "positioning",
    "local_first",
    "evidence_first",
    "recommended_commands",
    "recommended_docs",
    "recommended_artifacts",
    "honest_limits",
    "next_steps",
}


def proof_texts(payload: dict[str, object], *extra: str) -> str:
    return "\n".join([json.dumps(payload, sort_keys=True), *extra]).lower()


def banned_phrases() -> list[str]:
    return [
        "guaranteed " + "stars",
        "guaranteed " + "funding",
        "millions of " + "users",
        "enterprise " + "customers",
        "market " + "leader",
        "best in the " + "world",
        "融" + "资成功",
        "保" + "证融资",
        "保证高 " + "star",
        "tok" + "en",
        "api " + "key",
        "pass" + "word",
        "sec" + "ret",
    ]


def test_proof_human_output_includes_key_positioning_terms(tmp_path: Path) -> None:
    result = runner.invoke(app, ["proof", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    output = result.output
    assert "VibeBench Proof Packet" in output
    assert "Codex-first" in output
    assert "vibe-coding" in output
    assert "local-first" in output
    assert "evidence-first" in output
    assert "python3 -m vibebench demo" in output
    assert not tmp_path.joinpath("proof.md").exists()
    assert not tmp_path.joinpath("proof.json").exists()


def test_proof_json_output_is_valid_pure_json(tmp_path: Path) -> None:
    result = runner.invoke(app, ["proof", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload) == REQUIRED_KEYS
    assert payload["status"] == "ready"
    assert payload["project"]["name"] == "VibeBench Arena"
    assert "VibeBench Proof Packet" not in result.output


def test_proof_json_payload_has_required_stable_keys(tmp_path: Path) -> None:
    result = runner.invoke(app, ["proof", "--project-root", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert REQUIRED_KEYS <= set(payload)
    assert payload["local_first"]["enabled"] is True
    assert payload["evidence_first"]["enabled"] is True
    assert "python3 -m vibebench ci --dry-run --json" in payload[
        "recommended_commands"
    ]
    assert "docs/evaluate.md" in payload["recommended_docs"]
    assert "examples/showcase-artifacts/sample/manifest.json" in payload[
        "recommended_artifacts"
    ]


def test_proof_output_dir_writes_markdown_and_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "packet"

    result = runner.invoke(
        app,
        ["proof", "--project-root", str(tmp_path), "--output-dir", str(output_dir)],
    )

    assert result.exit_code == 0
    summary = output_dir / "proof.md"
    data = output_dir / "proof.json"
    assert summary.is_file()
    assert data.is_file()
    markdown = summary.read_text(encoding="utf-8")
    assert markdown.startswith("# VibeBench Proof Packet")
    assert "docs/adoption.md" in markdown
    payload = json.loads(data.read_text(encoding="utf-8"))
    assert set(payload) == REQUIRED_KEYS


def test_written_proof_json_matches_json_payload_shape(tmp_path: Path) -> None:
    output_dir = tmp_path / "packet"
    write_result = runner.invoke(
        app,
        ["proof", "--project-root", str(tmp_path), "--output-dir", str(output_dir)],
    )
    json_result = runner.invoke(
        app,
        ["proof", "--project-root", str(tmp_path), "--json"],
    )

    assert write_result.exit_code == 0
    assert json_result.exit_code == 0
    written = json.loads(output_dir.joinpath("proof.json").read_text(encoding="utf-8"))
    stdout_payload = json.loads(json_result.output)
    assert written == stdout_payload


def test_proof_output_dir_json_keeps_stdout_pure_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "packet"

    result = runner.invoke(
        app,
        [
            "proof",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ready"
    assert output_dir.joinpath("proof.md").is_file()
    assert output_dir.joinpath("proof.json").is_file()
    assert "Proof Markdown" not in result.output


def test_proof_output_dir_file_fails_clearly(tmp_path: Path) -> None:
    output_file = tmp_path / "packet-file"
    output_file.write_text("already here\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["proof", "--project-root", str(tmp_path), "--output-dir", str(output_file)],
    )

    assert result.exit_code == 1
    assert "exists as a file" in result.output


def test_proof_json_output_path_missing_parent_fails_clearly(tmp_path: Path) -> None:
    missing_parent_output = tmp_path / "missing" / "proof.json"

    result = runner.invoke(
        app,
        [
            "proof",
            "--project-root",
            str(tmp_path),
            "--json-output",
            str(missing_parent_output),
        ],
    )

    assert result.exit_code == 1
    assert "parent directory does not exist" in result.output


def test_proof_generated_outputs_avoid_banned_hype_and_safety_phrases(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "packet"
    result = runner.invoke(
        app,
        [
            "proof",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    combined = proof_texts(
        payload,
        output_dir.joinpath("proof.md").read_text(encoding="utf-8"),
        output_dir.joinpath("proof.json").read_text(encoding="utf-8"),
    )
    for phrase in banned_phrases():
        assert phrase not in combined
