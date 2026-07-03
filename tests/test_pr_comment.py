import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.pr_comment import (
    DEFAULT_COMMENT_MARKER,
    GitHubApiError,
    GitHubComment,
    ensure_comment_marker,
    generate_pr_comment,
    post_pr_comment,
    pr_comment_post_json,
)
from vibebench.report import ReportError, find_latest_run

runner = CliRunner()


def sample_metrics(
    project_name: str = "demo-project",
    findings: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": project_name,
        "created_at": "2026-06-26T12:00:00Z",
        "overall_status": "passed",
        "score": 92,
        "risk_level": "low",
        "command_results": [
            {
                "group": "test",
                "command": "pytest -q",
                "exit_code": 0,
                "stdout": "ok",
                "stderr": "",
                "duration_seconds": 1.25,
                "status": "passed",
            }
        ],
        "diff_analysis": {
            "git_available": True,
            "changed_files": ["src/app.py"],
            "deleted_files": [],
            "added_files": [],
            "modified_files": ["src/app.py"],
            "renamed_files": [],
            "test_files_changed": ["tests/test_app.py"],
            "tests_deleted": ["tests/test_old.py"],
            "forbidden_paths_touched": [".env.local"],
            "secret_like_files_touched": ["config/token.txt"],
            "lockfiles_changed": ["package-lock.json"],
            "total_added_lines": 10,
            "total_deleted_lines": 2,
            "total_patch_lines": 12,
            "changed_file_count": 1,
            "warnings": [],
            "file_changes": [],
        },
        "risk_findings": findings
        if findings is not None
        else [
            {
                "severity": "warning",
                "code": "lockfiles_changed",
                "message": "Lockfiles changed.",
                "paths": ["package-lock.json"],
            }
        ],
        "summary": {
            "total_commands": 1,
            "passed_commands": 1,
            "failed_commands": 0,
            "total_findings": 1,
            "critical_findings": 0,
            "high_findings": 0,
            "warning_findings": 1,
            "info_findings": 0,
        },
        "run_dir": "",
        "metrics_path": "",
        "log_path": "",
    }


def write_run(
    project_root: Path,
    name: str,
    metrics: dict[str, object] | None = None,
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = metrics or sample_metrics()
    payload["run_dir"] = str(run_dir)
    payload["metrics_path"] = str(run_dir / "metrics.json")
    payload["log_path"] = str(run_dir / "check.log")
    (run_dir / "metrics.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    return run_dir


def test_pr_comment_generation_creates_markdown(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260626_120000")

    comment_path = generate_pr_comment(tmp_path, run_dir)

    assert comment_path == run_dir / "pr-comment.md"
    assert comment_path.exists()


def test_missing_runs_helpful_failure(tmp_path: Path) -> None:
    with pytest.raises(ReportError, match="Run 'vibebench check' first"):
        find_latest_run(tmp_path)

    result = runner.invoke(app, ["pr-comment", "--project-root", str(tmp_path)])
    assert result.exit_code == 1
    assert "No VibeBench runs found. Run 'vibebench check' first." in result.output


def test_generated_markdown_contains_expected_sections(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260626_120000")

    comment_path = generate_pr_comment(tmp_path, run_dir)
    markdown = comment_path.read_text(encoding="utf-8")

    assert "## VibeBench Check" in markdown
    assert "demo-project" in markdown
    assert "92" in markdown
    assert "🟢 low" in markdown
    assert "`pytest -q`" in markdown
    assert "Changed files" in markdown
    assert "Lockfiles changed" in markdown
    assert "Looks safe to review and ship" in markdown
    assert "Codex writes code. VibeBench verifies it." in markdown


def test_risk_findings_are_rendered(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path, "20260626_120000")

    comment_path = generate_pr_comment(tmp_path, run_dir)
    markdown = comment_path.read_text(encoding="utf-8")

    assert "**warning** `lockfiles_changed`" in markdown
    assert "`package-lock.json`" in markdown


def test_long_finding_list_is_capped(tmp_path: Path) -> None:
    findings = [
        {
            "severity": "warning",
            "code": f"finding_{index}",
            "message": f"Finding {index}",
            "paths": [f"path-{index}.txt"],
        }
        for index in range(12)
    ]
    run_dir = write_run(tmp_path, "20260626_120000", sample_metrics(findings=findings))

    comment_path = generate_pr_comment(tmp_path, run_dir)
    markdown = comment_path.read_text(encoding="utf-8")

    assert "finding_9" in markdown
    assert "finding_10" not in markdown
    assert "...and 2 more findings." in markdown


def test_run_dir_option_works(tmp_path: Path) -> None:
    first = write_run(tmp_path, "20260626_120000", sample_metrics("first-project"))
    second = write_run(tmp_path, "20260626_130000", sample_metrics("second-project"))

    result = runner.invoke(
        app,
        [
            "pr-comment",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(first),
        ],
    )

    assert result.exit_code == 0
    assert first.joinpath("pr-comment.md").exists()
    assert not second.joinpath("pr-comment.md").exists()
    assert "PR comment generated." in result.output


def test_failed_run_recommendation_says_do_not_ship(tmp_path: Path) -> None:
    metrics = sample_metrics()
    metrics["overall_status"] = "failed"
    metrics["score"] = 80
    run_dir = write_run(tmp_path, "20260626_120000", metrics)

    comment_path = generate_pr_comment(tmp_path, run_dir)
    markdown = comment_path.read_text(encoding="utf-8")

    assert "Do not ship until failures are resolved." in markdown


class FakeGitHubClient:
    def __init__(self, comments: list[GitHubComment] | None = None) -> None:
        self.comments = comments or []
        self.created_body: str | None = None
        self.updated_body: str | None = None
        self.list_called = False
        self.create_called = False
        self.update_called = False

    def list_comments(self, repo: str, pr_number: int) -> list[GitHubComment]:
        self.list_called = True
        return self.comments

    def create_comment(self, repo: str, pr_number: int, body: str) -> GitHubComment:
        self.create_called = True
        self.created_body = body
        return GitHubComment(123, body, "https://github.test/comment/123")

    def update_comment(self, repo: str, comment_id: int, body: str) -> GitHubComment:
        self.update_called = True
        self.updated_body = body
        return GitHubComment(comment_id, body, f"https://github.test/comment/{comment_id}")


class FailingGitHubClient:
    def list_comments(self, repo: str, pr_number: int) -> list[GitHubComment]:
        raise GitHubApiError("boom")

    def create_comment(self, repo: str, pr_number: int, body: str) -> GitHubComment:
        raise AssertionError("create should not be called")

    def update_comment(self, repo: str, comment_id: int, body: str) -> GitHubComment:
        raise AssertionError("update should not be called")


def write_comment_file(root: Path, body: str = "hello") -> Path:
    run_dir = write_run(root, "20260626_120000")
    path = run_dir / "pr-comment.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_marker_is_inserted_when_body_lacks_marker() -> None:
    body = ensure_comment_marker("hello", DEFAULT_COMMENT_MARKER)

    assert body.startswith(DEFAULT_COMMENT_MARKER)
    assert "hello" in body


def test_marker_is_not_duplicated_when_body_already_has_marker() -> None:
    body = f"{DEFAULT_COMMENT_MARKER}\n\nhello"

    assert ensure_comment_marker(body, DEFAULT_COMMENT_MARKER) == body


def test_post_dry_run_does_not_call_network(tmp_path: Path) -> None:
    comment = write_comment_file(tmp_path)
    client = FakeGitHubClient()

    result = post_pr_comment(
        tmp_path,
        body_file=comment,
        repo="owner/repo",
        pr_number=7,
        dry_run=True,
        client=client,
    )

    assert result.status == "would-post"
    assert result.action == "would-post"
    assert client.list_called is False
    assert client.create_called is False
    assert client.update_called is False


def test_post_uses_explicit_repo_and_pr_number(tmp_path: Path) -> None:
    comment = write_comment_file(tmp_path)
    client = FakeGitHubClient()

    result = post_pr_comment(
        tmp_path,
        body_file=comment,
        repo="owner/repo",
        pr_number=42,
        env={"GITHUB_TOKEN": "secret"},
        client=client,
    )

    assert result.status == "created"
    assert result.repo == "owner/repo"
    assert result.pr_number == 42
    assert client.create_called is True


def test_post_infers_repo_from_environment(tmp_path: Path) -> None:
    comment = write_comment_file(tmp_path)
    client = FakeGitHubClient()

    result = post_pr_comment(
        tmp_path,
        body_file=comment,
        pr_number=42,
        env={"GITHUB_REPOSITORY": "env/repo", "GITHUB_TOKEN": "secret"},
        client=client,
    )

    assert result.status == "created"
    assert result.repo == "env/repo"


def test_post_infers_pr_number_from_github_event(tmp_path: Path) -> None:
    comment = write_comment_file(tmp_path)
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 55}}), encoding="utf-8")
    client = FakeGitHubClient()

    result = post_pr_comment(
        tmp_path,
        body_file=comment,
        repo="owner/repo",
        env={"GITHUB_EVENT_PATH": str(event), "GITHUB_TOKEN": "secret"},
        client=client,
    )

    assert result.status == "created"
    assert result.pr_number == 55


def test_non_pr_event_skips_cleanly(tmp_path: Path) -> None:
    comment = write_comment_file(tmp_path)

    result = post_pr_comment(
        tmp_path,
        body_file=comment,
        repo="owner/repo",
        env={"GITHUB_TOKEN": "secret"},
    )

    assert result.status == "skipped"
    assert result.action == "skip"
    assert "No pull request context" in result.message


def test_missing_token_in_real_post_mode(tmp_path: Path) -> None:
    comment = write_comment_file(tmp_path)

    with pytest.raises(ReportError, match="Missing GitHub token"):
        post_pr_comment(
            tmp_path,
            body_file=comment,
            repo="owner/repo",
            pr_number=7,
            env={},
        )


def test_existing_marker_comment_is_updated(tmp_path: Path) -> None:
    comment = write_comment_file(tmp_path, "new body")
    client = FakeGitHubClient(
        [GitHubComment(10, f"old\n{DEFAULT_COMMENT_MARKER}", "old-url")]
    )

    result = post_pr_comment(
        tmp_path,
        body_file=comment,
        repo="owner/repo",
        pr_number=7,
        env={"GITHUB_TOKEN": "secret"},
        client=client,
    )

    assert result.status == "updated"
    assert result.comment_id == 10
    assert client.update_called is True
    assert client.create_called is False
    assert client.updated_body is not None
    assert DEFAULT_COMMENT_MARKER in client.updated_body


def test_no_marker_comment_is_created(tmp_path: Path) -> None:
    comment = write_comment_file(tmp_path, "new body")
    client = FakeGitHubClient([GitHubComment(10, "ordinary comment")])

    result = post_pr_comment(
        tmp_path,
        body_file=comment,
        repo="owner/repo",
        pr_number=7,
        env={"GITHUB_TOKEN": "secret"},
        client=client,
    )

    assert result.status == "created"
    assert result.comment_id == 123
    assert client.create_called is True
    assert client.update_called is False
    assert client.created_body is not None
    assert DEFAULT_COMMENT_MARKER in client.created_body


def test_post_json_payload_shape(tmp_path: Path) -> None:
    comment = write_comment_file(tmp_path)

    result = post_pr_comment(
        tmp_path,
        body_file=comment,
        repo="owner/repo",
        pr_number=7,
        dry_run=True,
    )
    payload = pr_comment_post_json(result)

    assert payload["status"] == "would-post"
    assert payload["repo"] == "owner/repo"
    assert payload["pr_number"] == 7
    assert payload["comment_id"] is None
    assert payload["dry_run"] is True
    assert payload["body_file"] == str(comment)
    assert payload["marker"] == DEFAULT_COMMENT_MARKER


def test_no_fail_on_error_returns_failed_result(tmp_path: Path) -> None:
    comment = write_comment_file(tmp_path)

    result = post_pr_comment(
        tmp_path,
        body_file=comment,
        repo="owner/repo",
        pr_number=7,
        env={"GITHUB_TOKEN": "secret"},
        client=FailingGitHubClient(),
        fail_on_error=False,
    )

    assert result.status == "failed"
    assert result.action == "failed"
    assert "boom" in result.message


def test_cli_dry_run_json_stdout_is_pure_json(tmp_path: Path) -> None:
    comment = write_comment_file(tmp_path)

    result = runner.invoke(
        app,
        [
            "pr-comment",
            "--project-root",
            str(tmp_path),
            "--post",
            "--dry-run",
            "--json",
            "--body-file",
            str(comment),
            "--repo",
            "owner/repo",
            "--pr-number",
            "7",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "would-post"
    assert payload["repo"] == "owner/repo"
    assert payload["pr_number"] == 7
