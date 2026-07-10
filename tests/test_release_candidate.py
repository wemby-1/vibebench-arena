import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from vibebench import cli as cli_module
from vibebench import release_check as release_check_module
from vibebench.cli import app
from vibebench.release_check import (
    ReleaseCandidateCheck,
    ReleaseCandidateResult,
    candidate_documentation_checks,
    candidate_fail,
    candidate_package_checks,
    candidate_pass,
    check_action_metadata,
    check_action_smoke,
    check_builder_current,
    check_docs_placeholders,
    check_local_tag_absent,
    check_stable_ref_claims,
    release_candidate_json_payload,
    release_candidate_markdown,
    run_release_candidate_check,
    write_release_candidate_json,
    write_release_candidate_summary,
)

ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


def fast_public_checks(project_root: Path) -> list[ReleaseCandidateCheck]:
    return [
        candidate_pass(
            "public.proof_packet",
            "Public proof packet",
            "stubbed public proof packet check passed",
            path="examples/showcase-artifacts/public-proof",
        ),
        candidate_pass(
            "public.demo",
            "Public demo portal",
            "stubbed public demo check passed",
            path="examples/showcase-artifacts/public-demo",
        ),
        candidate_pass(
            "public.pages_site",
            "GitHub Pages launch site",
            "stubbed Pages check passed",
            path="scripts/build_pages_site.py",
        ),
    ]


def test_candidate_result_for_repository_passes_with_fast_public_checks(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        release_check_module,
        "candidate_public_evidence_checks",
        fast_public_checks,
    )

    result = run_release_candidate_check(ROOT)
    payload = release_candidate_json_payload(result)

    assert result.status == "passed"
    assert payload["candidate"] is True
    assert payload["target_version"] == "0.4.0"
    assert payload["released"] is False
    assert payload["summary"]["failed"] == 0


def test_candidate_json_schema_and_ordering_are_deterministic(monkeypatch) -> None:
    monkeypatch.setattr(
        release_check_module,
        "candidate_public_evidence_checks",
        fast_public_checks,
    )

    payload = release_candidate_json_payload(run_release_candidate_check(ROOT))
    ids = [check["id"] for check in payload["checks"]]

    assert set(payload) == {
        "schema_version",
        "status",
        "candidate",
        "target_version",
        "released",
        "checks",
        "summary",
        "artifacts",
    }
    assert ids == sorted(ids)
    assert payload == release_candidate_json_payload(run_release_candidate_check(ROOT))


def test_candidate_cli_json_stdout_is_pure_json(monkeypatch) -> None:
    monkeypatch.setattr(
        release_check_module,
        "candidate_public_evidence_checks",
        fast_public_checks,
    )

    result = runner.invoke(app, ["release-check", "--candidate", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["candidate"] is True
    assert "VibeBench Release Candidate" not in result.stdout


def test_candidate_cli_writes_json_and_markdown_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        release_check_module,
        "candidate_public_evidence_checks",
        fast_public_checks,
    )
    json_path = tmp_path / "nested" / "release-candidate.json"
    markdown_path = tmp_path / "nested" / "release-candidate.md"

    result = runner.invoke(
        app,
        [
            "release-check",
            "--candidate",
            "--json",
            "--write-json",
            str(json_path),
            "--write-summary",
            str(markdown_path),
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["released"] is False
    file_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert file_payload["target_version"] == "0.4.0"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# VibeBench v0.4.0 Release Candidate" in markdown
    assert "no release/tag/package publication occurred" in markdown


def test_candidate_writer_creates_selected_parent_directories(tmp_path: Path) -> None:
    result = ReleaseCandidateResult(
        project_root=tmp_path,
        target_version="0.4.0",
        released=False,
        checks=[candidate_pass("release.released_false", "Released", "released=false")],
        artifacts={"json": "release-candidate.json"},
    )
    json_path = tmp_path / "missing" / "release-candidate.json"
    markdown_path = tmp_path / "missing" / "release-candidate.md"

    write_release_candidate_json(result, json_path)
    write_release_candidate_summary(result, markdown_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["released"] is False
    assert "released=false" in markdown_path.read_text(encoding="utf-8")


def test_candidate_cli_failure_returns_nonzero(monkeypatch, tmp_path: Path) -> None:
    failing = ReleaseCandidateResult(
        project_root=tmp_path,
        target_version="0.4.0",
        released=False,
        checks=[candidate_fail("docs.required", "Required docs", "missing docs")],
        artifacts={},
    )
    monkeypatch.setattr(
        cli_module,
        "run_release_candidate_check",
        lambda project_root: failing,
    )

    result = runner.invoke(app, ["release-check", "--candidate", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["status"] == "failed"


def test_legacy_release_check_json_shape_remains_compatible(tmp_path: Path) -> None:
    from tests.test_release_check import create_ready_project

    create_ready_project(tmp_path)

    result = runner.invoke(
        app,
        ["release-check", "--project-root", str(tmp_path), "--json"],
    )

    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert set(payload) == {
        "status",
        "project_root",
        "latest_run_dir",
        "latest_run_id",
        "checks",
    }
    assert "candidate" not in payload


def test_package_version_mismatch_fails(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "vibebench").mkdir()
    (tmp_path / "vibebench" / "__init__.py").write_text(
        '__version__ = "0.4.0"\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "vibebench-arena"
version = "0.3.0"

[project.scripts]
vibebench = "vibebench.cli:main"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        release_check_module,
        "run_package_check",
        lambda project_root: type(
            "PackageResult",
            (),
            {"ready": True, "checks": []},
        )(),
    )

    checks = candidate_package_checks(tmp_path, "0.4.0")
    version_check = next(
        check for check in checks if check.id == "package.version_consistency"
    )

    assert version_check.status == "failed"
    assert "0.4.0" in version_check.message


def test_missing_required_candidate_document_fails(tmp_path: Path) -> None:
    checks = candidate_documentation_checks(tmp_path, "0.4.0")
    required = next(check for check in checks if check.id == "docs.required")

    assert required.status == "failed"
    assert "docs/github-action.md" in required.message


def test_placeholder_candidate_documentation_fails(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "README.md").write_text("TODO\n", encoding="utf-8")

    check = check_docs_placeholders(tmp_path)

    assert check.status == "failed"
    assert "README.md" in check.message


def test_false_publication_wording_fails(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "README.md").write_text(
        "@main is a stable production release\n",
        encoding="utf-8",
    )
    (docs / "github-action.md").write_text("", encoding="utf-8")
    (docs / "marketplace-readiness.md").write_text(
        "The package has been published.\n",
        encoding="utf-8",
    )
    (tmp_path / "RELEASE_NOTES_v0.4.0.md").write_text("", encoding="utf-8")

    check = check_stable_ref_claims(tmp_path, "0.4.0")

    assert check.status == "failed"
    assert "@main" in check.message or "package" in check.message


def test_missing_action_metadata_fails() -> None:
    check = check_action_metadata({"name": "", "description": ""})

    assert check.status == "failed"
    assert "branding" in check.message


def test_action_smoke_topology_failure_detected(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "action-smoke.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        """
jobs:
  action-smoke:
    strategy:
      matrix:
        preset: [minimal, strict]
    continue-on-error: true
""",
        encoding="utf-8",
    )

    check = check_action_smoke(tmp_path)

    assert check.status == "failed"
    assert "minimal, strict, proof" in check.message
    assert "continue-on-error" in check.message


def test_local_v040_tag_detection_uses_isolated_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "tag", "v0.4.0"], cwd=tmp_path, check=True)

    check = check_local_tag_absent(tmp_path, "0.4.0")

    assert check.status == "failed"
    assert "v0.4.0" in check.message


def test_builder_failure_reports_stale_public_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    script = tmp_path / "scripts" / "build_public_demo.py"
    script.parent.mkdir()
    script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout="", stderr="stale demo\n")

    monkeypatch.setattr(release_check_module.subprocess, "run", fake_run)

    check = check_builder_current(
        tmp_path,
        "public.demo",
        "Public demo portal",
        ["python3", "scripts/build_public_demo.py", "--check"],
        "examples/showcase-artifacts/public-demo",
    )

    assert check.status == "failed"
    assert "stale demo" in check.message


def test_candidate_markdown_is_deterministic(tmp_path: Path) -> None:
    result = ReleaseCandidateResult(
        project_root=tmp_path,
        target_version="0.4.0",
        released=False,
        checks=[candidate_pass("release.released_false", "Released", "released=false")],
        artifacts={"json": "release-candidate.json"},
    )

    assert release_candidate_markdown(result) == release_candidate_markdown(result)
    assert "Released: `false`" in release_candidate_markdown(result)
