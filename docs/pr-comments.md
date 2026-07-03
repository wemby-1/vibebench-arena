# GitHub PR Comment Integration Design

VibeBench already generates `pr-comment.md` for local review. Today, users must inspect that file, copy it into a pull request manually, or download it from CI artifacts. v0.3.0 should make that review loop more GitHub-native by allowing GitHub Actions to post or update a VibeBench PR comment automatically.

This document defines the intended behavior before implementation. It is a design contract for the future GitHub API work; it does not mean VibeBench posts PR comments yet.

## Goals

- Let GitHub Actions post or update the generated VibeBench PR comment.
- Preserve the existing local `python -m vibebench pr-comment` artifact generation behavior.
- Avoid duplicate VibeBench comments across repeated CI runs.
- Support dry-run behavior for safe workflow testing.
- Use the standard GitHub Actions token for normal same-repository pull requests.
- Keep the implementation testable without live network calls.

## Non-Goals

- No hosted dashboard.
- No custom bot service.
- No requirement for user-created GitHub secrets for normal same-repo PRs.
- No automatic posting on untrusted events where GitHub permissions are unsafe or unavailable.
- No replacement for the existing pasteable Markdown workflow.

## Proposed CLI Interface

The future implementation should extend the existing `pr-comment` command instead of adding an unrelated top-level command.

Recommended command shapes:

```bash
python -m vibebench pr-comment --post
python -m vibebench pr-comment --post --dry-run
python -m vibebench pr-comment --post --body-file .vibebench/runs/<run-id>/pr-comment.md
python -m vibebench pr-comment --post --repo OWNER/REPO --pr-number 123
```

Proposed options:

- `--post`: post or update the PR comment through the GitHub API.
- `--dry-run`: resolve inputs and print what would happen without calling the network.
- `--body-file PATH`: use an explicit Markdown body instead of the latest generated `pr-comment.md`.
- `--repo OWNER/REPO`: explicit GitHub repository, useful outside GitHub Actions.
- `--pr-number N`: explicit pull request number, useful outside GitHub Actions.
- `--comment-marker TEXT`: stable hidden marker used to find an existing VibeBench comment. Default: `<!-- vibebench-pr-comment -->`.
- `--token-env NAME`: environment variable that contains the GitHub token. Default: `GITHUB_TOKEN`.
- `--fail-on-error / --no-fail-on-error`: control whether posting failures fail the command. Default should be conservative for CI; implementation should document the chosen default clearly.
- `--json`: future machine-readable output mode.

The command should continue to support local artifact generation without `--post` exactly as it does today.

## GitHub Actions Behavior

On `pull_request` events, the implementation should infer repo and PR number from GitHub Actions context when explicit CLI values are not provided.

Expected defaults:

- Repository from `GITHUB_REPOSITORY`, such as `OWNER/REPO`.
- Pull request number from `GITHUB_EVENT_PATH` event payload.
- Token from `GITHUB_TOKEN` unless `--token-env` points elsewhere.

Required workflow permissions:

```yaml
permissions:
  contents: read
  pull-requests: write
```

Recommended workflow shape:

```yaml
- name: Run VibeBench
  run: python -m vibebench ci

- name: Post VibeBench PR comment
  if: github.event_name == 'pull_request'
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: python -m vibebench pr-comment --post
```

For non-PR events, the command should skip clearly instead of crashing when no PR number can be inferred.

Dry-run should be safe in any workflow:

```yaml
- name: Preview VibeBench PR comment posting
  run: python -m vibebench pr-comment --post --dry-run
```

## Duplicate Comment Prevention

The implementation should use a stable hidden marker in the comment body:

```html
<!-- vibebench-pr-comment -->
```

Posting behavior:

1. Build the final comment body by prepending or preserving the marker.
2. List existing PR comments visible to the token.
3. Search for an existing comment containing the marker.
4. Update that comment when found.
5. Create a new comment only when no marker exists.
6. Never create repeated comments on every CI run.

If multiple matching comments are found, the safest behavior is to update the newest matching comment and report a warning, or fail clearly in strict mode. The implementation should choose one deterministic behavior and test it.

## Safety And Security Rules

- Never print GitHub tokens.
- Do not include token values in JSON output, debug logs, tracebacks, or error messages.
- Use `GITHUB_TOKEN` by default for normal same-repository pull requests.
- Document that fork pull requests may have restricted token permissions.
- Skip clearly when required context is unavailable, such as non-PR events without `--pr-number`.
- Keep `--dry-run` available and fully testable without network calls.
- Do not post on untrusted events unless GitHub permissions and event semantics make it safe.
- Do not make PR comment posting the quality gate authority; `check`, `gate`, and `ci` remain responsible for pass/fail decisions.

## Output Behavior

Human output should clearly report one of these statuses:

- `skipped`: posting was not attempted, usually because the event is not a PR or required context is missing.
- `would-post`: dry-run would create a new comment.
- `would-update`: dry-run would update an existing marker comment.
- `created`: a new comment was created.
- `updated`: an existing marker comment was updated.
- `failed`: posting failed.

Future JSON output should be pure JSON and include stable fields such as:

```json
{
  "status": "created",
  "action": "create",
  "repo": "OWNER/REPO",
  "pr_number": 123,
  "comment_id": 456,
  "comment_url": "https://github.com/OWNER/REPO/pull/123#issuecomment-456",
  "dry_run": false,
  "message": "Created VibeBench PR comment."
}
```

For skipped output, `comment_id` and `comment_url` should be `null`.

## Error Behavior

Expected error cases:

- Missing token when posting is required.
- Missing repo or PR number outside inferable GitHub Actions context.
- Missing or unreadable body file.
- GitHub API permission failure.
- GitHub API rate limiting or transient network failure.

The implementation should keep errors beginner-readable and avoid dumping raw API responses when they contain unnecessary noise. It should expose enough status for CI logs to be useful.

## Test Strategy

No tests should make live GitHub API calls.

Future implementation tests should cover:

- Marker insertion and marker preservation.
- Existing comment detection by marker.
- Create vs update decision logic.
- Duplicate marker handling.
- JSON output purity.
- Dry-run does not call the network.
- Missing token behavior.
- Missing repo or PR number behavior.
- Non-PR GitHub event skip behavior.
- Explicit `--body-file`, `--repo`, and `--pr-number` behavior.
- `--token-env` reads the selected environment variable without printing it.
- GitHub API client mocked for list/create/update calls.
- Failure handling for API errors and permission errors.

## Implementation Notes For M60

M60 should prefer a small internal GitHub client abstraction so command logic can be tested without network access. The first implementation should stay focused on issue comments for pull requests and should not add review comments, checks API integration, or a dashboard.

The minimum useful implementation is:

1. Resolve comment body.
2. Resolve GitHub context.
3. In dry-run mode, report the intended action without network calls.
4. In post mode, list comments, find marker, update or create, and print a concise result.
5. Add mocked tests for all decision paths.
