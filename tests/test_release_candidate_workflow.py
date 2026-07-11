import json
import subprocess
from pathlib import Path

import yaml
from typer.testing import CliRunner

from vibebench.cli import app

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release-candidate.yml"
ACTION_SMOKE = ROOT / ".github" / "workflows" / "action-smoke.yml"
PAGES = ROOT / ".github" / "workflows" / "pages.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"
ARTIFACT_NAME = "vibebench-v0.4.0-release-candidate"

runner = CliRunner()


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def workflow_payload() -> dict:
    return yaml.safe_load(workflow_text())


def test_release_candidate_workflow_exists() -> None:
    assert WORKFLOW.is_file()


def test_release_candidate_workflow_triggers() -> None:
    text = workflow_text()

    assert "pull_request:" in text
    assert "workflow_dispatch:" in text
    assert "push:" in text
    assert 'branches: ["main"]' in text


def test_release_candidate_workflow_permissions_are_read_only() -> None:
    payload = workflow_payload()

    assert payload["permissions"] == {"contents": "read"}
    text = workflow_text()
    for forbidden in [
        "contents: write",
        "packages: write",
        "id-token: write",
        "deployments: write",
    ]:
        assert forbidden not in text


def test_release_candidate_workflow_has_concurrency() -> None:
    payload = workflow_payload()

    assert payload["concurrency"]["cancel-in-progress"] is True
    assert "github.ref" in payload["concurrency"]["group"]


def test_release_candidate_workflow_has_no_publication_commands() -> None:
    text = workflow_text().lower()
    forbidden = [
        " gh ",
        "gh release",
        "git tag",
        "git push --tags",
        "twine upload",
        "hatch publish",
        "poetry publish",
        "pypi",
        "softprops/action-gh-release",
        "ncipollo/release-action",
        "actions/create-release",
        "marketplace/actions/publish",
    ]

    for item in forbidden:
        assert item not in text


def test_release_candidate_workflow_runs_candidate_command_and_outputs() -> None:
    text = workflow_text()

    assert "python3 -m vibebench release-check" in text
    assert "python3 -m vibebench release-bundle" in text
    assert "--candidate" in text
    assert "--json" in text
    assert "--write-json" in text
    assert "--write-summary" in text
    assert "--output-dir \"$CANDIDATE_OUTPUT_DIR\"" in text
    assert "--check" in text
    assert "release-candidate.json" in text
    assert "release-candidate.md" in text
    assert "release-provenance.json" in text
    assert "release-checksums.sha256" in text
    assert "release-candidate-bundle.zip" in text
    assert "tee \"$CANDIDATE_STDOUT_JSON\"" in text


def test_release_candidate_workflow_verifies_bundle_before_upload() -> None:
    text = workflow_text()

    assert "Generate release candidate evidence bundle" in text
    assert "Verify release candidate evidence bundle" in text
    assert "python3 -m vibebench release-bundle" in text
    assert "sha256sum -c release-checksums.sha256" in text
    assert text.index("Verify release candidate evidence bundle") < text.index(
        "Upload release candidate evidence"
    )


def test_release_candidate_workflow_validates_json_schema() -> None:
    text = workflow_text()

    assert 'payload.get("candidate") is not True' in text
    assert 'payload.get("target_version") != "0.4.0"' in text
    assert 'payload.get("released") is not False' in text
    assert 'payload.get("status") != "passed"' in text
    assert 'check.get("status") != "passed"' in text
    assert "json.loads" in text


def test_release_candidate_workflow_runs_public_evidence_checks() -> None:
    text = workflow_text()

    assert "python3 scripts/build_public_proof_packet.py --check" in text
    assert "python3 scripts/build_public_demo.py --check" in text
    assert "python3 scripts/build_pages_site.py --check" in text


def test_release_candidate_workflow_uploads_only_candidate_directory() -> None:
    payload = workflow_payload()
    upload_steps = [
        step
        for step in payload["jobs"]["validate"]["steps"]
        if step.get("uses") == "actions/upload-artifact@v7"
    ]

    assert len(upload_steps) == 1
    with_payload = upload_steps[0]["with"]
    assert with_payload["name"] == ARTIFACT_NAME
    assert with_payload["path"] == "${{ runner.temp }}/vibebench-release-candidate"
    assert ".git" not in workflow_text()
    assert ".vibebench/runs" not in workflow_text()
    assert "_site" not in with_payload["path"]
    for expected in [
        "release-candidate.json",
        "release-candidate.md",
        "workflow-verification.json",
        "release-provenance.json",
        "release-checksums.sha256",
        "release-candidate-bundle.zip",
    ]:
        assert expected in workflow_text()


def test_release_candidate_workflow_has_no_authoritative_continue_on_error() -> None:
    assert "continue-on-error" not in workflow_text()


def test_release_candidate_summary_preserves_non_publication_state() -> None:
    text = workflow_text()

    assert "Released: `false`" in text
    assert "Archive SHA256:" in text
    assert "Payload file count:" in text
    assert "candidate evidence only" in text
    assert "does not create a tag" in text
    assert "create a GitHub Release" in text
    assert "upload a package" in text
    assert "publish to GitHub Marketplace" in text
    assert "has been published" not in text


def test_ci_workflow_remains_byte_for_byte_unchanged() -> None:
    baseline = subprocess.run(
        ["git", "show", "HEAD:.github/workflows/ci.yml"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout

    assert CI.read_text(encoding="utf-8") == baseline


def test_existing_workflow_contracts_remain_valid() -> None:
    action_smoke = yaml.safe_load(ACTION_SMOKE.read_text(encoding="utf-8"))
    action_text = ACTION_SMOKE.read_text(encoding="utf-8")
    pages = yaml.safe_load(PAGES.read_text(encoding="utf-8"))

    assert action_smoke["jobs"]["action-smoke"]["strategy"]["matrix"]["preset"] == [
        "minimal",
        "strict",
        "proof",
    ]
    assert "continue-on-error" not in action_text
    assert pages["permissions"]["contents"] == "read"
    assert pages["permissions"]["pages"] == "write"
    assert pages["permissions"]["id-token"] == "write"


def test_release_candidate_cli_modes_remain_compatible(tmp_path: Path) -> None:
    json_path = tmp_path / "candidate" / "release-candidate.json"
    summary_path = tmp_path / "candidate" / "release-candidate.md"

    human = runner.invoke(app, ["release-check", "--candidate"])
    as_json = runner.invoke(app, ["release-check", "--candidate", "--json"])
    written = runner.invoke(
        app,
        [
            "release-check",
            "--candidate",
            "--json",
            "--write-json",
            str(json_path),
            "--write-summary",
            str(summary_path),
        ],
    )

    assert human.exit_code == 0
    assert "VibeBench Release Candidate" in human.stdout
    assert as_json.exit_code == 0
    payload = json.loads(as_json.stdout)
    assert payload["candidate"] is True
    assert payload["target_version"] == "0.4.0"
    assert payload["released"] is False
    assert payload["status"] == "passed"
    assert written.exit_code == 0
    assert json.loads(written.stdout)["status"] == "passed"
    assert json.loads(json_path.read_text(encoding="utf-8"))["released"] is False
    assert "Released: `false`" in summary_path.read_text(encoding="utf-8")


def test_legacy_release_check_modes_remain_compatible() -> None:
    human = runner.invoke(app, ["release-check"])
    as_json = runner.invoke(app, ["release-check", "--json"])

    assert human.exit_code == 0
    assert "Release readiness:" in human.stdout
    assert as_json.exit_code == 0
    payload = json.loads(as_json.stdout)
    assert "candidate" not in payload
    assert set(payload) == {
        "status",
        "project_root",
        "latest_run_dir",
        "latest_run_id",
        "checks",
    }
