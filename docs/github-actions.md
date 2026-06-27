# GitHub Actions

VibeBench can run inside GitHub Actions without using the GitHub API or requiring a GitHub token. The `gh-summary` command writes a Markdown summary to the GitHub Actions step summary when `GITHUB_STEP_SUMMARY` is available.

## Copy The Example Workflow

Copy the example workflow into your repository:

```bash
mkdir -p .github/workflows
cp .github/workflows/vibebench.yml.example .github/workflows/vibebench.yml
```

The example lives at:

```text
.github/workflows/vibebench.yml.example
```

## What The Workflow Does

The example workflow:

- checks out your repository
- sets up Python 3.11
- installs VibeBench from the GitHub tag until PyPI support exists
- initializes `.vibebench/config.yaml` if it is missing
- runs `vibebench check`
- generates the HTML report
- generates the PR-ready Markdown comment
- writes the GitHub Actions step summary
- uploads `.vibebench/runs` as a workflow artifact

## Why `if: always()` Is Used

`vibebench check` should fail the workflow when configured commands fail or critical risks are found. The later report, comment, summary, and artifact upload steps use `if: always()` so reviewers can still inspect VibeBench output after a failed check.

## Artifacts

The workflow uploads:

```text
.vibebench/runs/
```

That directory can include:

- `metrics.json`
- `check.log`
- `report/index.html`
- `pr-comment.md`
- `github-step-summary.md` when not running inside GitHub step summary mode

## Limitations

- VibeBench does not post PR comments through the GitHub API yet.
- Your project test and lint commands must be installable and runnable in CI.
- v0.1.0 is installed from the GitHub tag until PyPI support exists.
- If you use unreleased commands from `main`, update the install line to point at the branch or commit you want to test.
