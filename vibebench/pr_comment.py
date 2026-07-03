"""PR-ready Markdown comment generation and GitHub posting for VibeBench runs."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from vibebench.report import (
    ReportError,
    find_latest_run,
    load_metrics,
    recommendation_for,
)

MAX_FINDINGS = 10
DEFAULT_COMMENT_MARKER = "<!-- vibebench-pr-comment -->"
DEFAULT_TOKEN_ENV = "GITHUB_TOKEN"
GITHUB_API_URL = "https://api.github.com"


@dataclass(frozen=True)
class GitHubComment:
    """A small representation of a GitHub issue comment."""

    comment_id: int
    body: str
    html_url: str | None = None


@dataclass(frozen=True)
class PrCommentPostResult:
    """Structured result for PR comment posting."""

    status: str
    action: str
    repo: str | None
    pr_number: int | None
    comment_id: int | None
    comment_url: str | None
    dry_run: bool
    body_file: str | None
    marker: str
    message: str


class GitHubCommentClient(Protocol):
    """Protocol for a tiny GitHub comments client."""

    def list_comments(self, repo: str, pr_number: int) -> list[GitHubComment]:
        """List pull request issue comments."""

    def create_comment(self, repo: str, pr_number: int, body: str) -> GitHubComment:
        """Create a pull request issue comment."""

    def update_comment(self, repo: str, comment_id: int, body: str) -> GitHubComment:
        """Update a pull request issue comment."""


class GitHubApiError(RuntimeError):
    """Raised when the GitHub API request fails."""


class UrlLibGitHubClient:
    """Minimal GitHub REST API client using the standard library."""

    def __init__(self, token: str, api_url: str = GITHUB_API_URL) -> None:
        self.token = token
        self.api_url = api_url.rstrip("/")

    def list_comments(self, repo: str, pr_number: int) -> list[GitHubComment]:
        payload = self._request(
            "GET",
            f"/repos/{repo}/issues/{pr_number}/comments?per_page=100",
        )
        if not isinstance(payload, list):
            raise GitHubApiError("GitHub returned an unexpected comments response.")
        return [
            comment_from_payload(item)
            for item in payload
            if isinstance(item, dict)
        ]

    def create_comment(self, repo: str, pr_number: int, body: str) -> GitHubComment:
        payload = self._request(
            "POST",
            f"/repos/{repo}/issues/{pr_number}/comments",
            {"body": body},
        )
        if not isinstance(payload, dict):
            raise GitHubApiError("GitHub returned an unexpected create response.")
        return comment_from_payload(payload)

    def update_comment(self, repo: str, comment_id: int, body: str) -> GitHubComment:
        payload = self._request(
            "PATCH",
            f"/repos/{repo}/issues/comments/{comment_id}",
            {"body": body},
        )
        if not isinstance(payload, dict):
            raise GitHubApiError("GitHub returned an unexpected update response.")
        return comment_from_payload(payload)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_url}{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "vibebench-arena",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.reason or f"HTTP {exc.code}"
            raise GitHubApiError(f"GitHub API request failed: {detail}") from exc
        except urllib.error.URLError as exc:
            raise GitHubApiError(f"GitHub API request failed: {exc.reason}") from exc
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise GitHubApiError("GitHub returned invalid JSON.") from exc


def generate_pr_comment(project_root: Path, run_dir: Path | None = None) -> Path:
    """Generate pr-comment.md for a run and return its path."""
    selected_run_dir = (run_dir or find_latest_run(project_root)).resolve()
    metrics = load_metrics(selected_run_dir)
    output_path = selected_run_dir / "pr-comment.md"
    output_path.write_text(render_markdown(metrics), encoding="utf-8")
    return output_path


def post_pr_comment(
    project_root: Path,
    *,
    run_dir: Path | None = None,
    body_file: Path | None = None,
    repo: str | None = None,
    pr_number: int | None = None,
    marker: str = DEFAULT_COMMENT_MARKER,
    token_env: str = DEFAULT_TOKEN_ENV,
    dry_run: bool = False,
    fail_on_error: bool = True,
    client: GitHubCommentClient | None = None,
    env: dict[str, str] | None = None,
) -> PrCommentPostResult:
    """Post or update a GitHub pull request comment."""
    selected_env = env if env is not None else os.environ
    selected_repo = repo or selected_env.get("GITHUB_REPOSITORY")
    selected_pr_number = pr_number or infer_pr_number(selected_env)

    selected_body_file = resolve_body_file(project_root, run_dir, body_file)
    if selected_body_file is None:
        return PrCommentPostResult(
            status="skipped",
            action="skip",
            repo=selected_repo,
            pr_number=selected_pr_number,
            comment_id=None,
            comment_url=None,
            dry_run=dry_run,
            body_file=None,
            marker=marker,
            message="No pr-comment.md found. Run 'vibebench pr-comment' first.",
        )

    try:
        raw_body = selected_body_file.read_text(encoding="utf-8")
    except OSError as exc:
        message = f"Unable to read PR comment body file: {selected_body_file}"
        raise ReportError(message) from exc
    body = ensure_comment_marker(raw_body, marker)

    if not selected_repo:
        return PrCommentPostResult(
            status="skipped",
            action="skip",
            repo=None,
            pr_number=selected_pr_number,
            comment_id=None,
            comment_url=None,
            dry_run=dry_run,
            body_file=str(selected_body_file),
            marker=marker,
            message=(
                "No GitHub repository found. Provide --repo OWNER/REPO "
                "or set GITHUB_REPOSITORY."
            ),
        )
    if selected_pr_number is None:
        return PrCommentPostResult(
            status="skipped",
            action="skip",
            repo=selected_repo,
            pr_number=None,
            comment_id=None,
            comment_url=None,
            dry_run=dry_run,
            body_file=str(selected_body_file),
            marker=marker,
            message=(
                "No pull request context found. Provide --pr-number "
                "or run on a pull_request event."
            ),
        )

    if dry_run:
        return PrCommentPostResult(
            status="would-post",
            action="would-post",
            repo=selected_repo,
            pr_number=selected_pr_number,
            comment_id=None,
            comment_url=None,
            dry_run=True,
            body_file=str(selected_body_file),
            marker=marker,
            message="Dry run: would post or update the VibeBench PR comment.",
        )

    token = selected_env.get(token_env)
    if not token:
        message = f"Missing GitHub token. Set {token_env} or use --token-env."
        if fail_on_error:
            raise ReportError(message)
        return PrCommentPostResult(
            status="failed",
            action="failed",
            repo=selected_repo,
            pr_number=selected_pr_number,
            comment_id=None,
            comment_url=None,
            dry_run=False,
            body_file=str(selected_body_file),
            marker=marker,
            message=message,
        )

    selected_client = client or UrlLibGitHubClient(token)
    try:
        comments = selected_client.list_comments(selected_repo, selected_pr_number)
        existing = find_marker_comment(comments, marker)
        if existing is not None:
            updated = selected_client.update_comment(
                selected_repo,
                existing.comment_id,
                body,
            )
            return PrCommentPostResult(
                status="updated",
                action="update",
                repo=selected_repo,
                pr_number=selected_pr_number,
                comment_id=updated.comment_id,
                comment_url=updated.html_url,
                dry_run=False,
                body_file=str(selected_body_file),
                marker=marker,
                message="Updated existing VibeBench PR comment.",
            )
        created = selected_client.create_comment(
            selected_repo,
            selected_pr_number,
            body,
        )
        return PrCommentPostResult(
            status="created",
            action="create",
            repo=selected_repo,
            pr_number=selected_pr_number,
            comment_id=created.comment_id,
            comment_url=created.html_url,
            dry_run=False,
            body_file=str(selected_body_file),
            marker=marker,
            message="Created VibeBench PR comment.",
        )
    except GitHubApiError as exc:
        message = str(exc)
        if fail_on_error:
            raise ReportError(message) from exc
        return PrCommentPostResult(
            status="failed",
            action="failed",
            repo=selected_repo,
            pr_number=selected_pr_number,
            comment_id=None,
            comment_url=None,
            dry_run=False,
            body_file=str(selected_body_file),
            marker=marker,
            message=message,
        )


def resolve_body_file(
    project_root: Path,
    run_dir: Path | None,
    body_file: Path | None,
) -> Path | None:
    """Resolve the PR comment body file."""
    if body_file is not None:
        selected = body_file if body_file.is_absolute() else project_root / body_file
        selected = selected.resolve()
        if not selected.is_file():
            raise ReportError(f"PR comment body file not found: {selected}")
        return selected

    try:
        selected_run_dir = (run_dir or find_latest_run(project_root)).resolve()
    except ReportError:
        return None
    candidate = selected_run_dir / "pr-comment.md"
    return candidate if candidate.is_file() else None


def ensure_comment_marker(body: str, marker: str) -> str:
    """Ensure the hidden VibeBench marker is present exactly once."""
    if marker in body:
        return body
    if body.startswith("\n"):
        return f"{marker}\n{body}"
    return f"{marker}\n\n{body}"


def infer_pr_number(env: dict[str, str]) -> int | None:
    """Infer pull request number from the GitHub event payload."""
    event_path = env.get("GITHUB_EVENT_PATH")
    if not event_path:
        return None
    try:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    pull_request = payload.get("pull_request")
    if isinstance(pull_request, dict):
        value = pull_request.get("number") or payload.get("number")
    else:
        value = payload.get("number")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def find_marker_comment(
    comments: list[GitHubComment], marker: str
) -> GitHubComment | None:
    """Find the newest comment containing the marker."""
    for comment in reversed(comments):
        if marker in comment.body:
            return comment
    return None


def comment_from_payload(payload: dict[str, Any]) -> GitHubComment:
    """Convert a GitHub API payload to a comment object."""
    try:
        comment_id = int(payload.get("id"))
    except (TypeError, ValueError) as exc:
        raise GitHubApiError("GitHub comment payload is missing id.") from exc
    body = payload.get("body")
    html_url = payload.get("html_url")
    return GitHubComment(
        comment_id=comment_id,
        body=body if isinstance(body, str) else "",
        html_url=html_url if isinstance(html_url, str) else None,
    )


def pr_comment_post_json(result: PrCommentPostResult) -> dict[str, object]:
    """Return a stable JSON payload for PR comment posting."""
    return {
        "status": result.status,
        "action": result.action,
        "repo": result.repo,
        "pr_number": result.pr_number,
        "comment_id": result.comment_id,
        "comment_url": result.comment_url,
        "dry_run": result.dry_run,
        "body_file": result.body_file,
        "marker": result.marker,
        "message": result.message,
    }


def render_markdown(metrics: dict[str, Any]) -> str:
    """Render a concise Markdown summary for a pull request comment."""
    project_name = text(metrics.get("project_name", "Unknown project"))
    created_at = text(metrics.get("created_at", "Unknown time"))
    status = text(metrics.get("overall_status", "unknown"))
    score = text(metrics.get("score", 0))
    risk_level = text(metrics.get("risk_level", "unknown"))
    commands = as_list(metrics.get("command_results"))
    diff = as_dict(metrics.get("diff_analysis"))
    findings = as_list(metrics.get("risk_findings"))
    recommendation = recommendation_for(metrics)

    sections = [
        "## VibeBench Check",
        "",
        f"- **Status:** {status_icon(status)} {status}",
        f"- **VibeScore:** {score}",
        f"- **Risk:** {risk_icon(risk_level)} {risk_level}",
        f"- **Project:** {project_name}",
        f"- **Created at:** {created_at}",
        "",
        "### Command Results",
        "",
        command_table(commands),
        "",
        "### Git Diff Risk Summary",
        "",
        diff_summary(diff, findings),
        "",
        "### Risk Findings",
        "",
        findings_section(findings),
        "",
        "### Recommendation",
        "",
        recommendation,
        "",
        "_Generated by VibeBench Arena — Codex writes code. VibeBench verifies it._",
        "",
    ]
    return "\n".join(sections)


def command_table(commands: list[Any]) -> str:
    """Render command results as a Markdown table."""
    rows = [
        "| Group | Command | Status | Exit Code | Duration |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not commands:
        rows.append("| - | - | - | - | - |")
        return "\n".join(rows)

    for command in commands:
        item = as_dict(command)
        rows.append(
            "| "
            f"{cell(item.get('group', ''))} | "
            f"`{inline_code(item.get('command', ''))}` | "
            f"{status_icon(text(item.get('status', 'unknown')))} "
            f"{cell(item.get('status', 'unknown'))} | "
            f"{cell(item.get('exit_code', ''))} | "
            f"{cell(format_duration(item.get('duration_seconds', 0)))} |"
        )
    return "\n".join(rows)


def diff_summary(diff: dict[str, Any], findings: list[Any]) -> str:
    """Render Git diff summary bullets."""
    rows = [
        f"- **Changed files:** {text(diff.get('changed_file_count', 0))}",
        f"- **Added lines:** {text(diff.get('total_added_lines', 0))}",
        f"- **Deleted lines:** {text(diff.get('total_deleted_lines', 0))}",
        f"- **Patch lines:** {text(diff.get('total_patch_lines', 0))}",
        f"- **Tests deleted:** {len(as_list(diff.get('tests_deleted')))}",
        "- **Forbidden paths touched:** "
        f"{len(as_list(diff.get('forbidden_paths_touched')))}",
        "- **Secret-like files touched:** "
        f"{len(as_list(diff.get('secret_like_files_touched')))}",
        f"- **Lockfiles changed:** {len(as_list(diff.get('lockfiles_changed')))}",
        f"- **Risk findings:** {len(findings)}",
    ]
    return "\n".join(rows)


def findings_section(findings: list[Any]) -> str:
    """Render up to ten risk findings."""
    if not findings:
        return "No risk findings detected."

    lines: list[str] = []
    for finding in findings[:MAX_FINDINGS]:
        item = as_dict(finding)
        severity = text(item.get("severity", "info"))
        code = text(item.get("code", "unknown"))
        message = truncate(text(item.get("message", "")), 220)
        paths = as_list(item.get("paths"))
        line = f"- **{severity}** `{inline_code(code)}`: {message}"
        if paths:
            rendered_paths = ", ".join(
                f"`{inline_code(truncate(text(path), 120))}`" for path in paths[:5]
            )
            if len(paths) > 5:
                rendered_paths = f"{rendered_paths}, +{len(paths) - 5} more"
            line = f"{line} ({rendered_paths})"
        lines.append(line)

    remaining = len(findings) - MAX_FINDINGS
    if remaining > 0:
        lines.append(f"...and {remaining} more findings.")
    return "\n".join(lines)


def status_icon(status: str) -> str:
    """Return the icon for a status value."""
    return "✅" if status == "passed" else "❌"


def risk_icon(risk_level: str) -> str:
    """Return the icon for a risk level."""
    return {
        "low": "🟢",
        "medium": "🟡",
        "high": "🟠",
        "critical": "🔴",
    }.get(risk_level, "⚪")


def format_duration(value: object) -> str:
    """Format seconds for display."""
    try:
        return f"{float(value):.3f}s"
    except (TypeError, ValueError):
        return text(value)


def cell(value: object) -> str:
    """Escape Markdown table cell delimiters."""
    return text(value).replace("|", "\\|").replace("\n", " ")


def inline_code(value: object) -> str:
    """Make text safe inside Markdown inline code."""
    return text(value).replace("`", "\\`").replace("|", "\\|").replace("\n", " ")


def truncate(value: str, limit: int) -> str:
    """Keep generated comments concise."""
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


def as_dict(value: object) -> dict[str, Any]:
    """Return value as a dict if possible."""
    return value if isinstance(value, dict) else {}


def as_list(value: object) -> list[Any]:
    """Return value as a list if possible."""
    return value if isinstance(value, list) else []


def text(value: object) -> str:
    """Convert dynamic values to text."""
    if value is None:
        return ""
    return str(value)
