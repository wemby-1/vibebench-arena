import json
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

runner = CliRunner()


def write_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def make_evidence_room(tmp_path: Path) -> Path:
    output_dir = tmp_path / "room"
    result = runner.invoke(
        app,
        ["evidence-room", "--output-dir", str(output_dir), "--zip"],
    )
    assert result.exit_code == 0
    return output_dir


def run_share_check(path: Path, *args: str):
    return runner.invoke(app, ["share-check", str(path), *args])


def test_share_check_passes_generated_evidence_room_directory(tmp_path: Path) -> None:
    room = make_evidence_room(tmp_path)

    result = run_share_check(room)

    assert result.exit_code == 0
    assert "VibeBench share-check" in result.output
    assert "Status: passed" in result.output


def test_share_check_passes_single_markdown_file(tmp_path: Path) -> None:
    report = tmp_path / "regression-check.md"
    report.write_text(
        "# VibeBench Regression Check\n\n"
        "This is a local quality regression gate, not a benchmark certification.\n",
        encoding="utf-8",
    )

    result = run_share_check(report)

    assert result.exit_code == 0
    assert "Target type: file" in result.output
    assert "Status: passed" in result.output


def test_share_check_passes_generated_evidence_room_zip(tmp_path: Path) -> None:
    room = make_evidence_room(tmp_path)

    result = run_share_check(room / "evidence-room.zip")

    assert result.exit_code == 0
    assert "Target type: zip" in result.output
    assert "Status: passed" in result.output


def test_share_check_json_stdout_is_pure_json(tmp_path: Path) -> None:
    room = make_evidence_room(tmp_path)

    result = run_share_check(room, "--json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "passed"
    assert payload["target_type"] == "directory"
    assert "VibeBench share-check" not in result.output


def test_share_check_json_output_writes_valid_json(tmp_path: Path) -> None:
    room = make_evidence_room(tmp_path)
    output = tmp_path / "share-check.json"

    result = run_share_check(room, "--json-output", str(output))

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"


def test_share_check_json_and_json_output_match(tmp_path: Path) -> None:
    room = make_evidence_room(tmp_path)
    output = tmp_path / "share-check.json"

    result = run_share_check(room, "--json", "--json-output", str(output))

    assert result.exit_code == 0
    assert json.loads(result.output) == json.loads(output.read_text(encoding="utf-8"))


def test_share_check_markdown_output_writes_report(tmp_path: Path) -> None:
    room = make_evidence_room(tmp_path)
    output = tmp_path / "share-check.md"

    result = run_share_check(room, "--markdown-output", str(output))

    assert result.exit_code == 0
    content = output.read_text(encoding="utf-8")
    assert "# VibeBench Share Check" in content
    assert "local pre-sharing aid" in content
    assert "not a security certification" in content
    assert "not a third-party audit" in content
    assert "not a guarantee" in content


def test_share_check_json_with_markdown_output_keeps_stdout_pure_json(
    tmp_path: Path,
) -> None:
    room = make_evidence_room(tmp_path)
    output = tmp_path / "share-check.md"

    result = run_share_check(room, "--json", "--markdown-output", str(output))

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "passed"
    assert output.is_file()
    assert "Share-check Markdown" not in result.output


def test_share_check_json_output_and_markdown_output_write_files(
    tmp_path: Path,
) -> None:
    room = make_evidence_room(tmp_path)
    json_output = tmp_path / "share-check.json"
    markdown_output = tmp_path / "share-check.md"

    result = run_share_check(
        room,
        "--json-output",
        str(json_output),
        "--markdown-output",
        str(markdown_output),
    )

    assert result.exit_code == 0
    assert json.loads(json_output.read_text(encoding="utf-8"))["status"] == "passed"
    assert "# VibeBench Share Check" in markdown_output.read_text(encoding="utf-8")


def test_share_check_missing_target_fails_clearly(tmp_path: Path) -> None:
    result = run_share_check(tmp_path / "missing")

    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_share_check_flags_unsafe_zip_path(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../escape.html", "<html></html>\n")

    result = run_share_check(archive, "--json")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["findings"][0]["code"] == "unsafe_zip_path"


def test_share_check_flags_script_tag(tmp_path: Path) -> None:
    target = write_file(tmp_path / "pkg" / "index.html", "<script></script>\n")

    result = run_share_check(target.parent, "--json")

    assert result.exit_code == 1
    codes = {item["code"] for item in json.loads(result.output)["findings"]}
    assert "html_script_tag" in codes


def test_share_check_flags_remote_url(tmp_path: Path) -> None:
    target = write_file(
        tmp_path / "pkg" / "index.html",
        '<link rel="stylesheet" href="https://example.com/x.css">\n',
    )

    result = run_share_check(target.parent, "--json")

    assert result.exit_code == 1
    codes = {item["code"] for item in json.loads(result.output)["findings"]}
    assert "remote_url" in codes
    assert "html_remote_stylesheet" in codes


def test_share_check_allow_remote_urls_downgrades_remote_url(
    tmp_path: Path,
) -> None:
    target = write_file(tmp_path / "pkg" / "notes.md", "See https://example.com/x\n")

    result = run_share_check(target.parent, "--allow-remote-urls", "--json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "passed"
    assert payload["findings"][0]["code"] == "remote_url"
    assert payload["findings"][0]["severity"] == "warning"


def test_share_check_strict_fails_on_remote_url_warning(tmp_path: Path) -> None:
    target = write_file(tmp_path / "pkg" / "notes.md", "See https://example.com/x\n")

    result = run_share_check(
        target.parent,
        "--allow-remote-urls",
        "--strict",
        "--json",
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "failed"
    assert payload["summary"]["warning_count"] == 1


def test_share_check_flags_personal_absolute_paths(tmp_path: Path) -> None:
    target = write_file(
        tmp_path / "pkg" / "notes.md",
        "/home/yangdongjiang/project\n/data/code/yangdongjiang/project\n",
    )

    result = run_share_check(target.parent, "--json")

    assert result.exit_code == 1
    codes = {item["code"] for item in json.loads(result.output)["findings"]}
    assert "absolute_home_path" in codes
    assert "absolute_data_code_path" in codes


def test_share_check_allows_documented_tmp_vibebench_command(
    tmp_path: Path,
) -> None:
    target = write_file(
        tmp_path / "pkg" / "notes.md",
        "python3 -m vibebench evidence-room --output-dir "
        "/tmp/vibebench-evidence-room --zip\n",
    )

    result = run_share_check(target.parent, "--json")

    assert result.exit_code == 0
    assert json.loads(result.output)["findings"] == []


def test_share_check_flags_non_example_tmp_path(tmp_path: Path) -> None:
    target = write_file(tmp_path / "pkg" / "notes.md", "cache: /tmp/random-file\n")

    result = run_share_check(target.parent, "--json")

    assert result.exit_code == 1
    codes = {item["code"] for item in json.loads(result.output)["findings"]}
    assert "absolute_tmp_path" in codes


def test_share_check_flags_github_token_like_string(tmp_path: Path) -> None:
    token = "ghp_" + ("A" * 36)
    target = write_file(tmp_path / "pkg" / "notes.txt", token + "\n")

    result = run_share_check(target.parent, "--json")

    assert result.exit_code == 1
    assert json.loads(result.output)["findings"][0]["code"] == "github_token"


def test_share_check_flags_openai_key_like_string(tmp_path: Path) -> None:
    key = "sk-" + ("a" * 40)
    target = write_file(tmp_path / "pkg" / "notes.txt", key + "\n")

    result = run_share_check(target.parent, "--json")

    assert result.exit_code == 1
    assert json.loads(result.output)["findings"][0]["code"] == "openai_api_key"


def test_share_check_flags_aws_key_like_string(tmp_path: Path) -> None:
    target = write_file(tmp_path / "pkg" / "notes.txt", "AKIAABCDEFGHIJKLMNOP\n")

    result = run_share_check(target.parent, "--json")

    assert result.exit_code == 1
    assert json.loads(result.output)["findings"][0]["code"] == "aws_access_key"


def test_share_check_flags_private_key_block(tmp_path: Path) -> None:
    target = write_file(
        tmp_path / "pkg" / "notes.txt",
        "-----BEGIN PRIVATE KEY-----\n",
    )

    result = run_share_check(target.parent, "--json")

    assert result.exit_code == 1
    assert json.loads(result.output)["findings"][0]["code"] == "private_key_block"


def test_share_check_flags_secret_assignment(tmp_path: Path) -> None:
    target = write_file(
        tmp_path / "pkg" / "notes.txt",
        "OPENAI_API_KEY=sk-example-value\n",
    )

    result = run_share_check(target.parent, "--json")

    assert result.exit_code == 1
    codes = {item["code"] for item in json.loads(result.output)["findings"]}
    assert "secret_assignment" in codes


def test_share_check_allows_generic_secret_documentation(tmp_path: Path) -> None:
    target = write_file(
        tmp_path / "pkg" / "notes.md",
        "Does local evaluation require secrets or tokens? No tokens are needed.\n",
    )

    result = run_share_check(target.parent, "--json")

    assert result.exit_code == 0
    assert json.loads(result.output)["findings"] == []


def test_share_check_flags_fake_positive_claim(tmp_path: Path) -> None:
    target = write_file(tmp_path / "pkg" / "notes.md", "SOC 2 certified\n")

    result = run_share_check(target.parent, "--json")

    assert result.exit_code == 1
    assert json.loads(result.output)["findings"][0]["code"] == "fake_trust_claim"


def test_share_check_allows_honest_non_claim_language(tmp_path: Path) -> None:
    target = write_file(
        tmp_path / "pkg" / "notes.md",
        "\n".join(
            [
                "not claiming SOC 2 certification",
                "not claiming ISO 27001 certification",
                "not a third-party audit",
                "not independently audited",
                "no fake traction claims",
            ]
        )
        + "\n",
    )

    result = run_share_check(target.parent, "--json")

    assert result.exit_code == 0
    assert json.loads(result.output)["findings"] == []


def test_share_check_command_is_registered_in_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "share-check" in result.output
