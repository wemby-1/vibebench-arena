import json
import shutil
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.evidence_room import REQUIRED_FILES

runner = CliRunner()


def copy_docs_site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    shutil.copytree(Path("docs"), site)
    return site


def make_room(tmp_path: Path, *extra_args: str) -> tuple[Path, object]:
    output_dir = tmp_path / "room"
    result = runner.invoke(
        app,
        [
            "evidence-room",
            "--output-dir",
            str(output_dir),
            *extra_args,
        ],
    )
    return output_dir, result


def test_evidence_room_human_command_does_not_crash() -> None:
    result = runner.invoke(app, ["evidence-room"])

    assert result.exit_code == 0
    assert "VibeBench evidence room" in result.output
    assert "Status: ready" in result.output


def test_evidence_room_json_stdout_is_pure_json() -> None:
    result = runner.invoke(app, ["evidence-room", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ready"
    assert "VibeBench evidence room" not in result.output


def test_evidence_room_json_output_writes_valid_json(tmp_path: Path) -> None:
    output = tmp_path / "evidence-room.json"

    result = runner.invoke(app, ["evidence-room", "--json-output", str(output)])

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "ready"


def test_evidence_room_json_and_json_output_match(tmp_path: Path) -> None:
    output = tmp_path / "evidence-room.json"

    result = runner.invoke(
        app,
        ["evidence-room", "--json", "--json-output", str(output)],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == json.loads(output.read_text(encoding="utf-8"))


def test_evidence_room_output_dir_writes_required_top_level_files(
    tmp_path: Path,
) -> None:
    output_dir, result = make_room(tmp_path)

    assert result.exit_code == 0
    assert output_dir.joinpath("evidence-room.html").is_file()
    assert output_dir.joinpath("evidence-room.md").is_file()
    assert output_dir.joinpath("evidence-room.json").is_file()


def test_evidence_room_output_dir_creates_proof_packet_files(tmp_path: Path) -> None:
    output_dir, result = make_room(tmp_path)

    assert result.exit_code == 0
    assert output_dir.joinpath("proof-packet", "proof.html").is_file()
    assert output_dir.joinpath("proof-packet", "proof.json").is_file()
    assert output_dir.joinpath("proof-packet", "proof.md").is_file()
    assert output_dir.joinpath("proof-packet", "proof-manifest.json").is_file()
    assert output_dir.joinpath("proof-packet", "proof.zip").is_file()


def test_evidence_room_output_dir_creates_site_preview_files(tmp_path: Path) -> None:
    output_dir, result = make_room(tmp_path)

    assert result.exit_code == 0
    assert output_dir.joinpath("site-preview", "index.html").is_file()
    assert output_dir.joinpath("site-preview", "showcase.html").is_file()
    assert output_dir.joinpath("site-preview", "site-check.json").is_file()
    assert output_dir.joinpath("site-preview", "site-preview.md").is_file()
    assert output_dir.joinpath("site-preview", "site-preview.zip").is_file()


def test_evidence_room_zip_creates_archive_with_safe_names(tmp_path: Path) -> None:
    output_dir, result = make_room(tmp_path, "--zip")

    assert result.exit_code == 0
    archive_path = output_dir / "evidence-room.zip"
    assert archive_path.is_file()
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    assert set(REQUIRED_FILES) <= names
    assert all(not Path(name).is_absolute() for name in names)
    assert all(".." not in Path(name).parts for name in names)
    assert all(".vibebench/runs" not in name for name in names)


def test_evidence_room_zip_output_writes_explicit_archive(tmp_path: Path) -> None:
    output_dir = tmp_path / "room"
    archive_path = tmp_path / "room.zip"

    result = runner.invoke(
        app,
        [
            "evidence-room",
            "--output-dir",
            str(output_dir),
            "--zip-output",
            str(archive_path),
        ],
    )

    assert result.exit_code == 0
    assert archive_path.is_file()
    assert not output_dir.joinpath("evidence-room.zip").exists()


def test_evidence_room_verify_directory_passes(tmp_path: Path) -> None:
    output_dir, write_result = make_room(tmp_path, "--zip")

    result = runner.invoke(app, ["evidence-room", "--verify", str(output_dir)])

    assert write_result.exit_code == 0
    assert result.exit_code == 0
    assert "verification passed" in result.output.lower()


def test_evidence_room_verify_zip_passes(tmp_path: Path) -> None:
    output_dir, write_result = make_room(tmp_path, "--zip")

    result = runner.invoke(
        app,
        ["evidence-room", "--verify", str(output_dir / "evidence-room.zip")],
    )

    assert write_result.exit_code == 0
    assert result.exit_code == 0
    assert "verification passed" in result.output.lower()


def test_evidence_room_verify_json_is_pure_json(tmp_path: Path) -> None:
    output_dir, _ = make_room(tmp_path, "--zip")

    result = runner.invoke(
        app,
        ["evidence-room", "--verify", str(output_dir), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["verified"] is True
    assert "Evidence room verification passed" not in result.output


def test_evidence_room_verify_fails_for_missing_top_level_file(
    tmp_path: Path,
) -> None:
    output_dir, _ = make_room(tmp_path, "--zip")
    output_dir.joinpath("evidence-room.html").unlink()

    result = runner.invoke(app, ["evidence-room", "--verify", str(output_dir)])

    assert result.exit_code == 1
    assert "evidence-room.html" in result.output


def test_evidence_room_verify_fails_for_missing_nested_proof_file(
    tmp_path: Path,
) -> None:
    output_dir, _ = make_room(tmp_path, "--zip")
    output_dir.joinpath("proof-packet", "proof.html").unlink()

    result = runner.invoke(app, ["evidence-room", "--verify", str(output_dir)])

    assert result.exit_code == 1
    assert "proof-packet/proof.html" in result.output


def test_evidence_room_verify_fails_for_missing_nested_site_preview_file(
    tmp_path: Path,
) -> None:
    output_dir, _ = make_room(tmp_path, "--zip")
    output_dir.joinpath("site-preview", "index.html").unlink()

    result = runner.invoke(app, ["evidence-room", "--verify", str(output_dir)])

    assert result.exit_code == 1
    assert "site-preview/index.html" in result.output


def test_evidence_room_verify_fails_for_invalid_json(tmp_path: Path) -> None:
    output_dir, _ = make_room(tmp_path, "--zip")
    output_dir.joinpath("evidence-room.json").write_text("{", encoding="utf-8")

    result = runner.invoke(app, ["evidence-room", "--verify", str(output_dir)])

    assert result.exit_code == 1
    assert "valid_json:evidence-room.json" in result.output


def test_evidence_room_verify_fails_for_script_tag(tmp_path: Path) -> None:
    output_dir, _ = make_room(tmp_path, "--zip")
    html = output_dir / "evidence-room.html"
    html.write_text(
        html.read_text(encoding="utf-8") + "\n<script></script>",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["evidence-room", "--verify", str(output_dir)])

    assert result.exit_code == 1
    assert "<script" in result.output


def test_evidence_room_verify_fails_for_remote_url(tmp_path: Path) -> None:
    output_dir, _ = make_room(tmp_path, "--zip")
    html = output_dir / "evidence-room.html"
    html.write_text(
        html.read_text(encoding="utf-8") + "\nhttps://example.test",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["evidence-room", "--verify", str(output_dir)])

    assert result.exit_code == 1
    assert "https://" in result.output


def test_evidence_room_verify_fails_for_absolute_local_path(
    tmp_path: Path,
) -> None:
    output_dir, _ = make_room(tmp_path, "--zip")
    markdown = output_dir / "evidence-room.md"
    markdown.write_text(
        markdown.read_text(encoding="utf-8") + "\n/data/code/example",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["evidence-room", "--verify", str(output_dir)])

    assert result.exit_code == 1
    assert "/data/code/" in result.output


def test_evidence_room_custom_root_works(tmp_path: Path) -> None:
    site = copy_docs_site(tmp_path)
    output_dir = tmp_path / "room"

    result = runner.invoke(
        app,
        [
            "evidence-room",
            "--root",
            str(site),
            "--output-dir",
            str(output_dir),
            "--zip",
        ],
    )

    assert result.exit_code == 0
    assert output_dir.joinpath("site-preview", "index.html").read_text(
        encoding="utf-8"
    ) == site.joinpath("index.html").read_text(encoding="utf-8")


def test_evidence_room_does_not_copy_vibebench_runs(tmp_path: Path) -> None:
    site = copy_docs_site(tmp_path)
    site.joinpath(".vibebench", "runs", "demo").mkdir(parents=True)
    site.joinpath(".vibebench", "runs", "demo", "metrics.json").write_text(
        "{}",
        encoding="utf-8",
    )
    output_dir = tmp_path / "room"

    result = runner.invoke(
        app,
        [
            "evidence-room",
            "--root",
            str(site),
            "--output-dir",
            str(output_dir),
            "--zip",
        ],
    )

    assert result.exit_code == 0
    assert not output_dir.joinpath(".vibebench").exists()
    with zipfile.ZipFile(output_dir / "evidence-room.zip") as archive:
        assert all(".vibebench/runs" not in name for name in archive.namelist())
