import json
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.proof import proof_html

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
VERIFY_KEYS = {
    "status",
    "verified",
    "target",
    "target_type",
    "checks",
    "files",
    "errors",
}
PACKET_FILES = {"proof.md", "proof.json", "proof.html", "proof-manifest.json"}


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


def make_packet(tmp_path: Path, *extra_args: str) -> tuple[Path, object]:
    output_dir = tmp_path / "packet"
    result = runner.invoke(
        app,
        [
            "proof",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            *extra_args,
        ],
    )
    return output_dir, result


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
    assert "python3 -m vibebench ci --dry-run --json" in payload["recommended_commands"]
    assert "docs/evaluate.md" in payload["recommended_docs"]
    assert (
        "examples/showcase-artifacts/sample/manifest.json"
        in payload["recommended_artifacts"]
    )


def test_proof_output_dir_writes_markdown_json_html_and_manifest(
    tmp_path: Path,
) -> None:
    output_dir, result = make_packet(tmp_path)

    assert result.exit_code == 0
    summary = output_dir / "proof.md"
    data = output_dir / "proof.json"
    html_report = output_dir / "proof.html"
    manifest = output_dir / "proof-manifest.json"
    assert summary.is_file()
    assert data.is_file()
    assert html_report.is_file()
    assert manifest.is_file()
    markdown = summary.read_text(encoding="utf-8")
    assert markdown.startswith("# VibeBench Proof Packet")
    assert "docs/adoption.md" in markdown
    payload = json.loads(data.read_text(encoding="utf-8"))
    assert set(payload) == REQUIRED_KEYS


def test_written_proof_json_matches_json_payload_shape(tmp_path: Path) -> None:
    output_dir, write_result = make_packet(tmp_path)
    json_result = runner.invoke(
        app,
        ["proof", "--project-root", str(tmp_path), "--json"],
    )

    assert write_result.exit_code == 0
    assert json_result.exit_code == 0
    written = json.loads(output_dir.joinpath("proof.json").read_text(encoding="utf-8"))
    stdout_payload = json.loads(json_result.output)
    assert written == stdout_payload


def test_proof_output_dir_zip_writes_archive(tmp_path: Path) -> None:
    output_dir, result = make_packet(tmp_path, "--zip")

    assert result.exit_code == 0
    assert output_dir.joinpath("proof.zip").is_file()


def test_proof_zip_output_writes_explicit_archive_path(tmp_path: Path) -> None:
    output_dir = tmp_path / "packet"
    archive_path = tmp_path / "shareable-proof.zip"

    result = runner.invoke(
        app,
        [
            "proof",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--zip-output",
            str(archive_path),
        ],
    )

    assert result.exit_code == 0
    assert output_dir.joinpath("proof.md").is_file()
    assert archive_path.is_file()


def test_proof_archive_contains_expected_relative_file_names(tmp_path: Path) -> None:
    output_dir, result = make_packet(tmp_path, "--zip")

    assert result.exit_code == 0
    with zipfile.ZipFile(output_dir / "proof.zip") as archive:
        names = set(archive.namelist())
    assert PACKET_FILES <= names
    assert all(not Path(name).is_absolute() for name in names)
    assert all(".." not in Path(name).parts for name in names)


def test_proof_manifest_contains_sha256_and_size_for_expected_files(
    tmp_path: Path,
) -> None:
    output_dir, result = make_packet(tmp_path)

    assert result.exit_code == 0
    manifest = json.loads(
        output_dir.joinpath("proof-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "ready"
    assert manifest["project"]["name"] == "VibeBench Arena"
    files = {item["name"]: item for item in manifest["files"]}
    assert set(files) == {"proof.md", "proof.json", "proof.html"}
    for item in files.values():
        assert item["size_bytes"] > 0
        assert len(item["sha256"]) == 64


def test_proof_verify_directory_passes(tmp_path: Path) -> None:
    output_dir, write_result = make_packet(tmp_path)

    result = runner.invoke(app, ["proof", "--verify", str(output_dir)])

    assert write_result.exit_code == 0
    assert result.exit_code == 0
    assert "verification passed" in result.output.lower()


def test_proof_verify_zip_passes(tmp_path: Path) -> None:
    output_dir, write_result = make_packet(tmp_path, "--zip")

    result = runner.invoke(app, ["proof", "--verify", str(output_dir / "proof.zip")])

    assert write_result.exit_code == 0
    assert result.exit_code == 0
    assert "verification passed" in result.output.lower()


def test_proof_verify_json_is_pure_valid_json(tmp_path: Path) -> None:
    output_dir, write_result = make_packet(tmp_path, "--zip")

    result = runner.invoke(
        app,
        ["proof", "--verify", str(output_dir / "proof.zip"), "--json"],
    )

    assert write_result.exit_code == 0
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload) == VERIFY_KEYS
    assert payload["verified"] is True
    assert payload["target_type"] == "zip"
    assert "verification passed" not in result.output.lower()


def test_proof_verify_fails_when_required_file_is_missing(tmp_path: Path) -> None:
    output_dir, write_result = make_packet(tmp_path)
    output_dir.joinpath("proof.json").unlink()

    result = runner.invoke(app, ["proof", "--verify", str(output_dir)])

    assert write_result.exit_code == 0
    assert result.exit_code == 1
    assert "missing required" in result.output.lower()


def test_proof_verify_fails_when_file_is_modified(tmp_path: Path) -> None:
    output_dir, write_result = make_packet(tmp_path)
    output_dir.joinpath("proof.md").write_text("changed\n", encoding="utf-8")

    result = runner.invoke(app, ["proof", "--verify", str(output_dir)])

    assert write_result.exit_code == 0
    assert result.exit_code == 1
    assert "mismatch" in result.output.lower()


def test_proof_output_dir_zip_json_keeps_stdout_pure_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "packet"

    result = runner.invoke(
        app,
        [
            "proof",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--zip",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ready"
    assert output_dir.joinpath("proof.md").is_file()
    assert output_dir.joinpath("proof.json").is_file()
    assert output_dir.joinpath("proof.html").is_file()
    assert output_dir.joinpath("proof-manifest.json").is_file()
    assert output_dir.joinpath("proof.zip").is_file()
    assert "Proof archive" not in result.output


def test_proof_html_output_writes_non_empty_html_file(tmp_path: Path) -> None:
    html_path = tmp_path / "proof-report.html"

    result = runner.invoke(
        app,
        [
            "proof",
            "--project-root",
            str(tmp_path),
            "--html-output",
            str(html_path),
        ],
    )

    assert result.exit_code == 0
    html = html_path.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert "VibeBench Proof Packet" in html


def test_proof_html_contains_title_and_core_sections(tmp_path: Path) -> None:
    output_dir, result = make_packet(tmp_path)

    assert result.exit_code == 0
    html = output_dir.joinpath("proof.html").read_text(encoding="utf-8")
    assert "<title>VibeBench Proof Packet</title>" in html
    assert "Codex-first / vibe-coding quality evidence" in html
    assert "Summary" in html
    assert "CI dry-run / plan evidence" in html
    assert "Release readiness evidence" in html
    assert "Doctor / strict readiness evidence" in html
    assert "Artifact or proof packet outputs" in html
    assert "Verification / checksum status" in html


def test_proof_html_has_no_remote_or_absolute_local_references(tmp_path: Path) -> None:
    output_dir, result = make_packet(tmp_path)

    assert result.exit_code == 0
    html = output_dir.joinpath("proof.html").read_text(encoding="utf-8")
    assert "http://" not in html
    assert "https://" not in html
    assert "/tmp/" not in html
    assert "/home/" not in html
    assert "/data/code/" not in html


def test_proof_json_with_html_output_keeps_stdout_pure_json(tmp_path: Path) -> None:
    html_path = tmp_path / "proof.html"

    result = runner.invoke(
        app,
        [
            "proof",
            "--project-root",
            str(tmp_path),
            "--json",
            "--html-output",
            str(html_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ready"
    assert html_path.is_file()
    assert "Proof HTML" not in result.output


def test_proof_verify_fails_when_required_html_is_missing(tmp_path: Path) -> None:
    output_dir, write_result = make_packet(tmp_path)
    output_dir.joinpath("proof.html").unlink()

    result = runner.invoke(app, ["proof", "--verify", str(output_dir)])

    assert write_result.exit_code == 0
    assert result.exit_code == 1
    assert "proof.html" in result.output
    assert "missing required" in result.output.lower()


def test_proof_html_escapes_dynamic_payload_content() -> None:
    payload = {
        "status": "ready<script>",
        "project": {"name": "Name <unsafe>"},
        "summary": "ignored",
        "positioning": {"description": "Codex <first> & safe"},
        "local_first": {"description": "Local <only>"},
        "evidence_first": {"description": "Evidence & review"},
        "recommended_commands": ["python3 -m example --name '<x>'"],
        "recommended_docs": ["docs/<guide>.md"],
        "recommended_artifacts": ["artifact<script>.json"],
        "honest_limits": ["No <claims>"],
        "next_steps": ["Review & share"],
    }

    html = proof_html(payload)

    assert "ready&lt;script&gt;" in html
    assert "Name &lt;unsafe&gt;" in html
    assert "&#x27;&lt;x&gt;&#x27;" in html
    assert "No &lt;claims&gt;" in html
    assert "ready<script>" not in html
    assert "Name <unsafe>" not in html


def test_proof_verify_fails_when_html_is_modified(tmp_path: Path) -> None:
    output_dir, write_result = make_packet(tmp_path)
    output_dir.joinpath("proof.html").write_text("changed\n", encoding="utf-8")

    result = runner.invoke(app, ["proof", "--verify", str(output_dir)])

    assert write_result.exit_code == 0
    assert result.exit_code == 1
    assert "proof.html" in result.output
    assert "mismatch" in result.output.lower()


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
    output_dir, result = make_packet(tmp_path, "--zip", "--json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    combined = proof_texts(
        payload,
        output_dir.joinpath("proof.md").read_text(encoding="utf-8"),
        output_dir.joinpath("proof.json").read_text(encoding="utf-8"),
        output_dir.joinpath("proof-manifest.json").read_text(encoding="utf-8"),
        output_dir.joinpath("proof.html").read_text(encoding="utf-8"),
    )
    for phrase in banned_phrases():
        assert phrase not in combined
