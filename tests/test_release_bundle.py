import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from vibebench import release_bundle as release_bundle_module
from vibebench.cli import app
from vibebench.release_bundle import (
    ARCHIVE_PAYLOAD_FILES,
    RELEASE_BUNDLE_ARCHIVE,
    RELEASE_CHECKSUMS,
    RELEASE_PROVENANCE_JSON,
    RELEASE_WORKFLOW_VERIFICATION_JSON,
    build_release_candidate_bundle,
    release_bundle_json_payload,
    verify_checksums,
)
from vibebench.release_check import (
    ReleaseCandidateResult,
    candidate_pass,
)

ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


def fast_candidate(project_root: Path) -> ReleaseCandidateResult:
    return ReleaseCandidateResult(
        project_root=project_root,
        target_version="0.4.0",
        released=False,
        checks=[
            candidate_pass("package.version_consistency", "Package", "0.4.0"),
            candidate_pass("action.metadata", "Action", "metadata ok"),
            candidate_pass("public.proof_packet", "Proof", "proof ok"),
            candidate_pass("docs.required", "Docs", "docs ok"),
            candidate_pass("release.released_false", "Released", "released=false"),
        ],
        artifacts={
            "json": "release-candidate.json",
            "markdown": "release-candidate.md",
        },
    )


def patch_fast_candidate(monkeypatch) -> None:
    monkeypatch.setattr(
        release_bundle_module,
        "run_release_candidate_check",
        fast_candidate,
    )


def build_bundle(tmp_path: Path, monkeypatch) -> tuple[Path, object]:
    patch_fast_candidate(monkeypatch)
    output_dir = tmp_path / "candidate"
    result = build_release_candidate_bundle(ROOT, output_dir=output_dir)
    return output_dir, result


def test_release_bundle_help_exposes_options() -> None:
    result = runner.invoke(app, ["release-bundle", "--help"])

    assert result.exit_code == 0
    for option in [
        "--candidate",
        "--output-dir",
        "--archive-output",
        "--json",
        "--json-output",
        "--check",
    ]:
        assert option in result.output


def test_release_bundle_requires_candidate() -> None:
    result = runner.invoke(app, ["release-bundle", "--json"])

    payload = json.loads(result.stdout)
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert payload["candidate"] is False


def test_release_bundle_cli_json_and_json_output_are_pure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_fast_candidate(monkeypatch)
    output_dir = tmp_path / "candidate"
    json_output = tmp_path / "bundle-result.json"

    result = runner.invoke(
        app,
        [
            "release-bundle",
            "--candidate",
            "--output-dir",
            str(output_dir),
            "--json",
            "--json-output",
            str(json_output),
        ],
    )

    stdout_payload = json.loads(result.stdout)
    file_payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert stdout_payload == file_payload
    assert stdout_payload["status"] == "passed"
    assert stdout_payload["candidate"] is True
    assert stdout_payload["target_version"] == "0.4.0"
    assert stdout_payload["released"] is False
    assert stdout_payload["checksums_valid"] is True
    assert "VibeBench Release Candidate Bundle" not in result.stdout


def test_release_bundle_human_mode_writes_required_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir, result = build_bundle(tmp_path, monkeypatch)

    assert result.status == "passed"
    assert output_dir.joinpath("release-candidate.json").is_file()
    assert output_dir.joinpath("release-candidate.md").is_file()
    assert output_dir.joinpath(RELEASE_WORKFLOW_VERIFICATION_JSON).is_file()
    assert output_dir.joinpath(RELEASE_PROVENANCE_JSON).is_file()
    assert output_dir.joinpath(RELEASE_CHECKSUMS).is_file()
    assert output_dir.joinpath(RELEASE_BUNDLE_ARCHIVE).is_file()


def test_release_bundle_candidate_json_fields_and_provenance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir, _ = build_bundle(tmp_path, monkeypatch)

    candidate = json.loads(
        output_dir.joinpath("release-candidate.json").read_text(encoding="utf-8")
    )
    provenance = json.loads(
        output_dir.joinpath(RELEASE_PROVENANCE_JSON).read_text(encoding="utf-8")
    )
    assert candidate["candidate"] is True
    assert candidate["target_version"] == "0.4.0"
    assert candidate["released"] is False
    assert candidate["status"] == "passed"
    assert provenance["package_version"] == "0.4.0"
    assert provenance["init_version"] == "0.4.0"
    assert provenance["package_metadata"]["consistent"] is True
    assert provenance["action_metadata"]["consistent"] is True
    assert provenance["released"] is False


def test_release_bundle_checksums_and_zip_are_safe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir, result = build_bundle(tmp_path, monkeypatch)
    archive_path = output_dir / RELEASE_BUNDLE_ARCHIVE

    assert result.archive_sha256
    assert len(result.archive_sha256) == 64
    assert verify_checksums(output_dir) is True
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        assert names == [
            path.as_posix()
            for path in sorted(ARCHIVE_PAYLOAD_FILES, key=lambda item: item.as_posix())
        ]
        assert len(names) == len(set(names))
        assert all(not name.startswith("/") for name in names)
        assert all(".." not in Path(name).parts for name in names)
        assert all(".vibebench/runs" not in name for name in names)
        assert all("__pycache__" not in name for name in names)


def test_release_bundle_artifacts_are_portable_and_do_not_leak_local_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir, _ = build_bundle(tmp_path, monkeypatch)

    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in output_dir.rglob("*")
        if path.is_file() and path.suffix != ".zip"
    )
    forbidden = [
        str(tmp_path),
        "/tmp/",
        "/home/",
        "/data/code/",
        "GITHUB_TOKEN",
        "github_pat_",
        "-----BEGIN",
    ]
    for marker in forbidden:
        assert marker not in combined


def test_release_bundle_build_is_deterministic_across_temp_roots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_fast_candidate(monkeypatch)
    first = tmp_path / "one"
    second = tmp_path / "two"

    first_result = build_release_candidate_bundle(ROOT, output_dir=first)
    second_result = build_release_candidate_bundle(ROOT, output_dir=second)

    for relative in first_result.files:
        assert first.joinpath(relative).read_bytes() == second.joinpath(
            relative
        ).read_bytes()
    assert first_result.archive_sha256 == second_result.archive_sha256


def test_release_bundle_check_mode_passes_and_is_read_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir, _ = build_bundle(tmp_path, monkeypatch)
    before = {
        path.relative_to(output_dir).as_posix(): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file()
    }

    result = build_release_candidate_bundle(ROOT, output_dir=output_dir, check=True)
    after = {
        path.relative_to(output_dir).as_posix(): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file()
    }

    assert result.status == "passed"
    assert result.checked is True
    assert before == after


def test_release_bundle_check_mode_detects_tampering(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir, _ = build_bundle(tmp_path, monkeypatch)
    output_dir.joinpath("release-candidate.md").write_text(
        "tampered\n",
        encoding="utf-8",
    )

    result = build_release_candidate_bundle(ROOT, output_dir=output_dir, check=True)

    payload = release_bundle_json_payload(result)
    assert result.status == "failed"
    assert payload["checked"] is True
    assert any(check.status == "failed" for check in result.checks)


def test_release_bundle_check_mode_detects_bad_checksum(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir, _ = build_bundle(tmp_path, monkeypatch)
    output_dir.joinpath(RELEASE_CHECKSUMS).write_text("bad\n", encoding="utf-8")

    result = build_release_candidate_bundle(ROOT, output_dir=output_dir, check=True)

    assert result.status == "failed"
    assert result.checksums_valid is False


def test_release_bundle_check_mode_detects_unexpected_archive_member(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir, _ = build_bundle(tmp_path, monkeypatch)
    archive_path = output_dir / RELEASE_BUNDLE_ARCHIVE
    with zipfile.ZipFile(archive_path, "a") as archive:
        archive.writestr("../evil.txt", "nope")

    result = build_release_candidate_bundle(ROOT, output_dir=output_dir, check=True)

    assert result.status == "failed"
    assert any(check.name == "archive.members" for check in result.checks)


def test_release_bundle_check_mode_detects_malformed_json_and_version_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir, _ = build_bundle(tmp_path, monkeypatch)
    output_dir.joinpath("release-candidate.json").write_text("{bad", encoding="utf-8")

    malformed = build_release_candidate_bundle(ROOT, output_dir=output_dir, check=True)

    assert malformed.status == "failed"
    build_release_candidate_bundle(ROOT, output_dir=output_dir)
    payload = json.loads(
        output_dir.joinpath("release-candidate.json").read_text(encoding="utf-8")
    )
    payload["target_version"] = "0.3.0"
    output_dir.joinpath("release-candidate.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    mismatch = build_release_candidate_bundle(ROOT, output_dir=output_dir, check=True)

    assert mismatch.status == "failed"
    assert any(check.name == "candidate.target_version" for check in mismatch.checks)


def test_release_bundle_output_overrides(tmp_path: Path, monkeypatch) -> None:
    patch_fast_candidate(monkeypatch)
    output_dir = tmp_path / "candidate"
    archive = tmp_path / "archives" / "candidate.zip"
    archive.parent.mkdir()

    result = build_release_candidate_bundle(
        ROOT,
        output_dir=output_dir,
        archive_output=archive,
    )

    assert result.status == "passed"
    assert result.archive_path == archive.resolve()
    assert archive.is_file()
    assert not output_dir.joinpath(RELEASE_BUNDLE_ARCHIVE).exists()


def test_release_bundle_environment_isolation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_fast_candidate(monkeypatch)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path / "runner"))

    result = runner.invoke(
        app,
        [
            "release-bundle",
            "--candidate",
            "--output-dir",
            str(tmp_path / "candidate"),
            "--json",
        ],
    )

    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert not summary.exists()


def test_release_bundle_check_fails_for_missing_output_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_fast_candidate(monkeypatch)

    result = build_release_candidate_bundle(
        ROOT,
        output_dir=tmp_path / "missing",
        check=True,
    )

    assert result.status == "failed"
    assert any(check.name == "output_dir" for check in result.checks)


def test_release_bundle_legacy_release_check_modes_remain_compatible() -> None:
    human = runner.invoke(app, ["release-check"])
    as_json = runner.invoke(app, ["release-check", "--json"])
    candidate = runner.invoke(app, ["release-check", "--candidate", "--json"])

    assert human.exit_code == 0
    assert as_json.exit_code == 0
    assert "candidate" not in json.loads(as_json.stdout)
    payload = json.loads(candidate.stdout)
    assert candidate.exit_code == 0
    assert payload["candidate"] is True
    assert payload["target_version"] == "0.4.0"
    assert payload["released"] is False
    assert payload["status"] == "passed"


def test_release_bundle_does_not_require_local_runs_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_fast_candidate(monkeypatch)
    workspace = tmp_path / "shallow"
    shutil.copytree(
        ROOT,
        workspace,
        ignore=shutil.ignore_patterns(
            ".git",
            ".vibebench/runs",
            ".vibebench/release-candidates",
            ".pytest_cache",
            "__pycache__",
        ),
    )

    result = build_release_candidate_bundle(
        workspace,
        output_dir=tmp_path / "candidate",
    )

    assert result.status == "passed"
    assert result.archive_sha256


def test_release_bundle_shallow_no_tags_checkout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_fast_candidate(monkeypatch)
    clone = tmp_path / "clone"
    subprocess.run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "clone",
            "--depth",
            "1",
            "--no-tags",
            f"file://{ROOT}",
            str(clone),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = build_release_candidate_bundle(
        clone,
        output_dir=tmp_path / "candidate",
    )
    tags = subprocess.run(
        ["git", "tag", "--list", "v0.4.0"],
        cwd=clone,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert result.status == "passed"
    assert result.archive_sha256
    assert tags == ""
