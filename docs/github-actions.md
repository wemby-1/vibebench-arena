# GitHub Actions

VibeBench can run inside GitHub Actions without using the GitHub API or requiring a GitHub token. The `gh-summary` command writes a Markdown summary to the GitHub Actions step summary when `GITHUB_STEP_SUMMARY` is available.


## VibeBench Dogfoods Itself

This repository's active CI runs direct `ruff` and `pytest` checks first, then runs VibeBench itself. CI now enforces `vibebench gate --min-score 80 --max-risk medium --allow-findings 0 --write-gate-summary`; if the gate fails, the job fails. CI still generates the HTML report, PR-ready Markdown comment, GitHub step summary, and uploads `.vibebench/runs` as artifacts.

## Copy The Example Workflow

Copy the example workflow into your repository:

```bash
mkdir -p .github/workflows
cp docs/examples/github-actions/vibebench.yml .github/workflows/vibebench.yml
```

The example lives at:

```text
docs/examples/github-actions/vibebench.yml
```

## What The Workflow Does

The example workflow:

- checks out your repository
- sets up Python 3.11
- installs VibeBench from the GitHub tag until PyPI support exists
- initializes `.vibebench/config.yaml` if it is missing
- runs `vibebench check`
- enforces `vibebench gate` with explicit score, risk, and finding thresholds
- generates the HTML report
- generates the PR-ready Markdown comment
- writes the GitHub Actions step summary
- uploads `.vibebench/runs` as a workflow artifact

## Add A Quality Gate

Use `vibebench gate` when CI should fail on explicit score, risk, and finding thresholds. Put it after `vibebench check` and before the always-on artifact generation steps:

```yaml
      - name: Enforce VibeBench gate
        run: python -m vibebench gate --min-score 80 --max-risk medium --allow-findings 0 --write-gate-summary
```

`--write-gate-summary` writes `.vibebench/runs/<timestamp>/gate-summary.md`, which can be uploaded with the rest of the run artifacts.

## Why `if: always()` Is Used

`vibebench check` should fail the workflow when configured commands fail or critical risks are found. `vibebench gate` should also fail the workflow when explicit quality thresholds are not met, so it should not use `if: always()`. The later report, comment, summary, and artifact upload steps use `if: always()` so reviewers can still inspect VibeBench output after a failed check or gate.

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
- `gate-summary.md`
- `github-step-summary.md` when not running inside GitHub step summary mode

## Limitations

- VibeBench does not post PR comments through the GitHub API yet.
- Your project test and lint commands must be installable and runnable in CI.
- v0.1.0 is installed from the GitHub tag until PyPI support exists.
- If you use unreleased commands from `main`, update the install line to point at the branch or commit you want to test.
