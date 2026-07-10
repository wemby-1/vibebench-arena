import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

from typer.testing import CliRunner

from vibebench.cli import app

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "examples" / "showcase-artifacts" / "public-proof"
REFERENCE_DEMO = ROOT / "examples" / "showcase-artifacts" / "public-demo"
BUILDER = ROOT / "scripts" / "build_public_demo.py"
runner = CliRunner()


class LinkParser(HTMLParser):
    """Collect links and asset references from generated HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.remote_assets: list[str] = []
        self.script_sources: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = dict(attrs)
        for key in ("href", "src"):
            value = values.get(key)
            if not value:
                continue
            if value.startswith(("http://", "https://")):
                self.remote_assets.append(value)
            if tag == "script" and key == "src":
                self.script_sources.append(value)
            if key == "href":
                self.links.append(value)


def test_cli_help_exposes_public_demo_options() -> None:
    result = runner.invoke(app, ["public-demo", "--help"])

    assert result.exit_code == 0
    assert "--run-dir" in result.output
    assert "--proof-packet" in result.output
    assert "--output-dir" in result.output
    assert "--check" in result.output
    assert "--json-output" in result.output
    assert "--summary-output" in result.output


def test_public_demo_builds_from_committed_proof_packet(tmp_path: Path) -> None:
    output = tmp_path / "demo"

    result = runner.invoke(
        app,
        [
            "public-demo",
            "--proof-packet",
            str(PACKET),
            "--output-dir",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (output / "index.html").is_file()
    assert (output / "demo.json").is_file()
    assert (output / "README.md").is_file()
    payload = json.loads((output / "demo.json").read_text(encoding="utf-8"))
    assert payload["source_type"] == "proof-packet"
    assert payload["project"] == "vibebench-reference-project"
    assert payload["score"] == 100


def test_public_demo_builds_from_normal_run_directory(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path / "run")
    output = tmp_path / "demo"

    result = runner.invoke(
        app,
        ["public-demo", "--run-dir", str(run_dir), "--output-dir", str(output)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads((output / "demo.json").read_text(encoding="utf-8"))
    assert payload["source_type"] == "run"
    assert payload["project"] == "Demo <Project>"
    assert "unavailable optional evidence" in (output / "index.html").read_text(
        encoding="utf-8"
    )


def test_run_dir_and_proof_packet_conflict(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path / "run")
    result = runner.invoke(
        app,
        [
            "public-demo",
            "--run-dir",
            str(run_dir),
            "--proof-packet",
            str(PACKET),
            "--output-dir",
            str(tmp_path / "demo"),
        ],
    )

    assert result.exit_code == 1
    assert "mutually exclusive" in result.output
    assert not (tmp_path / "demo").exists()


def test_missing_input_fails_cleanly_with_json(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "public-demo",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(tmp_path / "demo"),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert result.output.lstrip().startswith("{")
    assert payload["status"] == "failed"
    assert not (tmp_path / "demo").exists()


def test_invalid_input_fails_cleanly(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid"
    invalid.mkdir()
    (invalid / "metrics.json").write_text("{not json", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "public-demo",
            "--run-dir",
            str(invalid),
            "--output-dir",
            str(tmp_path / "demo"),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert "not valid JSON" in payload["message"]
    assert not (tmp_path / "demo").exists()


def test_output_directory_cannot_be_inside_source(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path / "run")
    output = run_dir / "public-demo"

    result = runner.invoke(
        app,
        ["public-demo", "--run-dir", str(run_dir), "--output-dir", str(output)],
    )

    assert result.exit_code == 1
    assert "must not be inside" in result.output
    assert not output.exists()


def test_json_stdout_and_json_output_are_valid_json(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    json_output = tmp_path / "result.json"

    result = runner.invoke(
        app,
        [
            "public-demo",
            "--proof-packet",
            str(PACKET),
            "--output-dir",
            str(output),
            "--json",
            "--json-output",
            str(json_output),
        ],
    )

    stdout_payload = json.loads(result.output)
    file_payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert stdout_payload["status"] == "passed"
    assert file_payload["status"] == "passed"


def test_summary_output_writes_markdown(tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    result = runner.invoke(
        app,
        [
            "public-demo",
            "--proof-packet",
            str(PACKET),
            "--output-dir",
            str(tmp_path / "demo"),
            "--summary-output",
            str(summary),
        ],
    )

    text = summary.read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert text.startswith("# VibeBench Public Demo")
    assert "vibebench-reference-project" in text
    assert "python3 scripts/build_public_proof_packet.py --check" in text


def test_index_contains_expected_public_sections(tmp_path: Path) -> None:
    output = build_demo(tmp_path)
    html = (output / "index.html").read_text(encoding="utf-8")

    for expected in [
        "Reviewer Summary",
        "Evidence Overview",
        "Artifact Explorer",
        "Five-Minute Review Path",
        "Audience Views",
        "Reproduction",
        "Non-Claims and Trust Boundaries",
        "What this evidence proves",
        "What this does not prove",
    ]:
        assert expected in html


def test_demo_json_is_public_safe_and_has_file_listing(tmp_path: Path) -> None:
    output = build_demo(tmp_path)
    payload = json.loads((output / "demo.json").read_text(encoding="utf-8"))

    assert payload["files"]
    assert payload["output_dir"] == "."
    assert_no_public_leaks(output)


def test_generated_links_are_relative_internal_and_resolve(tmp_path: Path) -> None:
    output = build_demo(tmp_path)

    for html_file in output.rglob("*.html"):
        parser = LinkParser()
        parser.feed(html_file.read_text(encoding="utf-8"))
        assert not parser.remote_assets
        assert not parser.script_sources
        for link in parser.links:
            if link.startswith("#"):
                continue
            assert not link.startswith(("/", "http://", "https://"))
            target = (html_file.parent / link.split("#", 1)[0]).resolve()
            assert target.exists(), f"{html_file}: {link}"


def test_no_external_http_asset_dependency_exists(tmp_path: Path) -> None:
    output = build_demo(tmp_path)
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in output.rglob("*")
        if path.is_file()
    )

    assert "http://" not in text
    assert "https://" not in text
    assert "<script" not in (output / "index.html").read_text(encoding="utf-8").lower()


def test_symlink_and_path_traversal_are_safely_omitted(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path / "run")
    outside = tmp_path / "outside.html"
    outside.write_text("/home/example/secret", encoding="utf-8")
    report_dir = run_dir / "report"
    report_dir.mkdir()
    (report_dir / "index.html").symlink_to(outside)
    (run_dir / "artifact-inventory.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "name": "escape",
                        "path": "../outside.html",
                        "available": True,
                        "size_bytes": 10,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / "demo"
    result = runner.invoke(
        app,
        ["public-demo", "--run-dir", str(run_dir), "--output-dir", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert not (output / "artifacts" / "report" / "index.html").exists()
    payload = json.loads((output / "demo.json").read_text(encoding="utf-8"))
    assert all(".." not in item["path"] for item in payload["artifacts"])


def test_optional_missing_artifacts_do_not_fail(tmp_path: Path) -> None:
    proof = tmp_path / "proof"
    shutil.copytree(PACKET, proof)
    (proof / "release-check.json").unlink()
    output = tmp_path / "demo"

    result = runner.invoke(
        app,
        ["public-demo", "--proof-packet", str(proof), "--output-dir", str(output)],
    )

    payload = json.loads((output / "demo.json").read_text(encoding="utf-8"))
    assert result.exit_code == 0, result.output
    assert any(
        item["id"] == "release_check" and item["available"] is False
        for item in payload["evidence"]
    )


def test_artifact_order_and_repeated_generation_are_deterministic(
    tmp_path: Path,
) -> None:
    first = build_demo(tmp_path / "one")
    second = build_demo(tmp_path / "two")

    first_payload = json.loads((first / "demo.json").read_text(encoding="utf-8"))
    artifacts = first_payload["artifacts"]
    ordering = [(not item["available"], item["path"]) for item in artifacts]
    assert ordering == sorted(ordering)
    assert snapshot_hashes(first) == snapshot_hashes(second)


def test_check_succeeds_and_detects_changed_added_missing_files(
    tmp_path: Path,
) -> None:
    output = build_demo(tmp_path)

    ok = runner.invoke(
        app,
        [
            "public-demo",
            "--proof-packet",
            str(PACKET),
            "--output-dir",
            str(output),
            "--check",
            "--json",
        ],
    )
    assert ok.exit_code == 0, ok.output

    (output / "index.html").write_text("changed", encoding="utf-8")
    (output / "extra.txt").write_text("extra", encoding="utf-8")
    (output / "README.md").unlink()
    changed = runner.invoke(
        app,
        [
            "public-demo",
            "--proof-packet",
            str(PACKET),
            "--output-dir",
            str(output),
            "--check",
            "--json",
        ],
    )
    payload = json.loads(changed.output)
    assert changed.exit_code == 1
    assert "changed: index.html" in payload["differences"]
    assert "added: extra.txt" in payload["differences"]
    assert "missing: README.md" in payload["differences"]


def test_check_is_read_only_and_source_proof_packet_remains_unchanged(
    tmp_path: Path,
) -> None:
    output = build_demo(tmp_path)
    before_output = snapshot_hashes(output)
    before_packet = snapshot_hashes(PACKET)

    result = runner.invoke(
        app,
        [
            "public-demo",
            "--proof-packet",
            str(PACKET),
            "--output-dir",
            str(output),
            "--check",
        ],
    )

    assert result.exit_code == 0, result.output
    assert snapshot_hashes(output) == before_output
    assert snapshot_hashes(PACKET) == before_packet


def test_host_github_step_summary_and_root_outputs_are_not_modified(
    tmp_path: Path,
) -> None:
    host_summary = tmp_path / "github-step-summary.md"
    host_summary.write_text("host summary\n", encoding="utf-8")
    root_runs_before = snapshot_optional_tree(ROOT / ".vibebench" / "runs")
    root_baselines_before = snapshot_optional_tree(ROOT / ".vibebench" / "baselines")
    env = os.environ.copy()
    env.update(
        {
            "GITHUB_ACTIONS": "true",
            "GITHUB_STEP_SUMMARY": str(host_summary),
            "GITHUB_OUTPUT": str(tmp_path / "github-output"),
            "GITHUB_ENV": str(tmp_path / "github-env"),
            "GITHUB_PATH": str(tmp_path / "github-path"),
            "GITHUB_WORKSPACE": str(ROOT),
            "GITHUB_EVENT_PATH": str(tmp_path / "event.json"),
        }
    )

    completed = subprocess.run(
        [sys.executable, str(BUILDER), "--check"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert host_summary.read_text(encoding="utf-8") == "host summary\n"
    assert snapshot_optional_tree(ROOT / ".vibebench" / "runs") == root_runs_before
    assert (
        snapshot_optional_tree(ROOT / ".vibebench" / "baselines")
        == root_baselines_before
    )


def test_committed_reference_portal_matches_builder_check() -> None:
    completed = subprocess.run(
        [sys.executable, str(BUILDER), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert (REFERENCE_DEMO / "index.html").is_file()
    assert (REFERENCE_DEMO / "demo.json").is_file()
    assert (REFERENCE_DEMO / "README.md").is_file()


def test_html_escapes_project_name_from_run(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path / "run", project="<script>alert(1)</script>")
    output = tmp_path / "demo"

    result = runner.invoke(
        app,
        ["public-demo", "--run-dir", str(run_dir), "--output-dir", str(output)],
    )

    html = (output / "index.html").read_text(encoding="utf-8")
    assert result.exit_code == 0, result.output
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert" not in html


def build_demo(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    output = tmp_path / "demo"
    result = runner.invoke(
        app,
        ["public-demo", "--proof-packet", str(PACKET), "--output-dir", str(output)],
    )
    assert result.exit_code == 0, result.output
    return output


def write_run(path: Path, *, project: str = "Demo <Project>") -> Path:
    path.mkdir(parents=True)
    payload = {
        "schema_version": "1.0",
        "project_name": project,
        "created_at": "2026-07-10T00:00:00Z",
        "overall_status": "passed",
        "score": 95,
        "risk_level": "low",
        "summary": {
            "total_commands": 1,
            "passed_commands": 1,
            "failed_commands": 0,
            "total_findings": 0,
        },
        "command_results": [
            {
                "group": "test",
                "command": "python3 -m pytest -q",
                "status": "passed",
                "exit_code": 0,
            }
        ],
        "risk_findings": [],
        "diff_analysis": {"changed_file_count": 0},
    }
    (path / "metrics.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def snapshot_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def snapshot_optional_tree(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def assert_no_public_leaks(output: Path) -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in output.rglob("*")
        if path.is_file()
    )
    forbidden = [
        r"/home/",
        r"/data/code/",
        r"/tmp/(?!vibebench-demo\b)",
        r"ghp_[A-Za-z0-9_]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"authorization\s*[:=]",
        r"api[_-]?key\s*[:=]",
        r"password\s*[:=]",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    ]
    for pattern in forbidden:
        assert not re.search(pattern, text, flags=re.IGNORECASE), pattern
