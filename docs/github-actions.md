# GitHub Actions

VibeBench can run inside GitHub Actions without using the GitHub API or requiring a GitHub token. The `gh-summary` command writes a Markdown summary to the GitHub Actions step summary when `GITHUB_STEP_SUMMARY` is available.


## VibeBench Dogfoods Itself

This repository's active CI runs direct `ruff` and `pytest` checks first, then runs VibeBench itself. CI now enforces `vibebench gate --write-gate-summary` using the policy in `.vibebench/config.yaml`; if the gate fails, the job fails. CI still generates the HTML report, PR-ready Markdown comment, human-readable explanation, GitHub step summary, and uploads `.vibebench/runs` as artifacts.

## Generate The Workflow

Generate the default VibeBench workflow with:

```bash
python -m vibebench init
```

This creates `.github/workflows/vibebench.yml` unless it already exists. Use `python -m vibebench init --workflow-only` to create only the workflow, or `--force` to overwrite generated files. The template also lives at:

```text
docs/examples/github-actions/vibebench.yml
```

## What The Workflow Does

The example workflow:

- checks out your repository
- sets up Python 3.11
- installs the project with `python -m pip install -e ".[dev]"` and installs VibeBench from GitHub until PyPI support exists
- runs `python -m vibebench check`
- enforces `python -m vibebench gate --write-gate-summary` with explicit score, risk, and finding thresholds from config
- generates the HTML report
- generates the PR-ready Markdown comment
- generates a human-readable run explanation
- writes the GitHub Actions step summary
- uploads `.vibebench/runs` as a workflow artifact

## Add A Quality Gate

Use `vibebench gate` when CI should fail on explicit score, risk, and finding thresholds. Put the policy in `.vibebench/config.yaml`, then run the gate after `vibebench check` and before the always-on artifact generation steps:

```yaml
      - name: Enforce VibeBench gate
        run: python -m vibebench gate --write-gate-summary
```

`--write-gate-summary` writes `.vibebench/runs/<timestamp>/gate-summary.md`, which can be uploaded with the rest of the run artifacts. CLI threshold flags still work as explicit one-run overrides.

## Why `if: always()` Is Used

`vibebench check` should fail the workflow when configured commands fail or critical risks are found. `vibebench gate` should also fail the workflow when explicit quality thresholds are not met, so it should not use `if: always()`. The later report, comment, explanation, summary, and artifact upload steps use `if: always()` so reviewers can still inspect VibeBench output after a failed check or gate.

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
- `explain.md`
- `gate-summary.md`
- `github-step-summary.md` when not running inside GitHub step summary mode

## Limitations

- VibeBench does not post PR comments through the GitHub API yet.
- Your project test and lint commands must be installable and runnable in CI.
- The generated workflow assumes your project can be installed with `python -m pip install -e ".[dev]"`; adjust that step if your project uses a different install command. Pin the VibeBench install line to a tag or commit when you need reproducible CI.
