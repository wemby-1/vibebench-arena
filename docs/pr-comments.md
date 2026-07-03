# GitHub PR Comment Integration

VibeBench generates `pr-comment.md` for local review and can post or update that Markdown summary on a GitHub pull request. The generated GitHub Actions workflow includes a pull-request-only posting step, while local users can run `python -m vibebench pr-comment --post` directly when they want to post from another environment.

The posting implementation is intentionally small and boring. It uses the GitHub REST API, a stable hidden marker, and no live network calls in tests.

## Goals

- Preserve the existing local `python -m vibebench pr-comment` artifact generation behavior.
- Let GitHub Actions post or update the generated VibeBench PR comment when explicitly requested.
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
- No posting on push events or non-PR events.

## CLI Interface

The existing `pr-comment` command still writes the Markdown artifact:

```bash
python -m vibebench pr-comment
```

Posting mode extends the same command:

```bash
python -m vibebench pr-comment --post
python -m vibebench pr-comment --post --dry-run
python -m vibebench pr-comment --post --dry-run --json
python -m vibebench pr-comment --post --body-file .vibebench/runs/<run-id>/pr-comment.md
python -m vibebench pr-comment --post --repo OWNER/REPO --pr-number 123
```

Options:

- `--post`: post or update the PR comment through the GitHub API.
- `--dry-run`: resolve inputs and print what would happen without calling the network.
- `--body-file PATH`: use an explicit Markdown body instead of the latest generated `pr-comment.md`.
- `--repo OWNER/REPO`: explicit GitHub repository, useful outside GitHub Actions.
- `--pr-number N`: explicit pull request number, useful outside GitHub Actions.
- `--comment-marker TEXT`: stable hidden marker used to find an existing VibeBench comment. Default: `<!-- vibebench-pr-comment -->`.
- `--token-env NAME`: environment variable that contains the GitHub token. Default: `GITHUB_TOKEN`.
- `--fail-on-error / --no-fail-on-error`: control whether posting failures fail the command. The default is `--fail-on-error`.
- `--json`: print a pure JSON posting result.

## GitHub Actions Behavior

On `pull_request` events, VibeBench can infer repo and PR number from GitHub Actions context when explicit CLI values are not provided.

Defaults:

- Repository from `GITHUB_REPOSITORY`, such as `OWNER/REPO`.
- Pull request number from `GITHUB_EVENT_PATH` event payload.
- Token from `GITHUB_TOKEN` unless `--token-env` points elsewhere.

Required workflow permissions:

```yaml
permissions:
  contents: read
  pull-requests: write
```

Workflow shape:

```yaml
- name: Run VibeBench
  run: python -m vibebench ci

- name: Post VibeBench PR comment
  if: github.event_name == 'pull_request'
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: python -m vibebench pr-comment --post --no-fail-on-error
```

For non-PR events, the workflow step is skipped by `if: github.event_name == 'pull_request'`. If the command is run manually without PR context, it skips clearly instead of crashing. The workflow uses `--no-fail-on-error` so permission-limited fork PRs do not fail the core VibeBench check/gate verdict.

Dry-run is safe in any workflow:

```yaml
- name: Preview VibeBench PR comment posting
  run: python -m vibebench pr-comment --post --no-fail-on-error --dry-run
```

## Duplicate Comment Prevention

VibeBench uses a stable hidden marker in the comment body:

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

If multiple matching comments exist, VibeBench updates the newest matching comment deterministically.

## Safety And Security Rules

- Never print GitHub tokens.
- Do not include token values in JSON output, debug logs, tracebacks, or error messages.
- Use `GITHUB_TOKEN` by default for normal same-repository pull requests.
- Fork pull requests may have restricted token permissions.
- Skip clearly when required context is unavailable, such as non-PR events without `--pr-number`.
- Keep `--dry-run` available and fully testable without network calls.
- Do not post on untrusted events unless GitHub permissions and event semantics make it safe.
- Do not make PR comment posting the quality gate authority; `check`, `gate`, and `ci` remain responsible for pass/fail decisions.

## Output Behavior

Human output reports one of these statuses:

- `skipped`: posting was not attempted, usually because the event is not a PR or required context is missing.
- `would-post`: dry-run would post or update the VibeBench PR comment.
- `created`: a new comment was created.
- `updated`: an existing marker comment was updated.
- `failed`: posting failed.

JSON output is pure JSON and includes stable fields:

```json
{
  "status": "created",
  "action": "create",
  "repo": "OWNER/REPO",
  "pr_number": 123,
  "comment_id": 456,
  "comment_url": "https://github.com/OWNER/REPO/pull/123#issuecomment-456",
  "dry_run": false,
  "body_file": ".vibebench/runs/<run-id>/pr-comment.md",
  "marker": "<!-- vibebench-pr-comment -->",
  "message": "Created VibeBench PR comment."
}
```

For skipped output, `comment_id` and `comment_url` are `null`.

## Error Behavior

Expected error cases:

- Missing token when posting is required.
- Missing repo or PR number outside inferable GitHub Actions context.
- Missing or unreadable body file.
- GitHub API permission failure.
- GitHub API rate limiting or transient network failure.

Use `--no-fail-on-error` when a workflow should report a failed posting result without failing the job.

## Test Strategy

No tests make live GitHub API calls.

Coverage includes:

- Marker insertion and marker preservation.
- Existing comment detection by marker.
- Create vs update decision logic.
- JSON output purity.
- Dry-run does not call the network.
- Missing token behavior.
- Missing repo or PR number behavior.
- Non-PR GitHub event skip behavior.
- Explicit `--body-file`, `--repo`, and `--pr-number` behavior.
- GitHub API client fakes for list/create/update calls.
- Failure handling for API errors and permission errors.
