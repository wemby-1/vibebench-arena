# GitHub Actions

VibeBench can run inside GitHub Actions without using the GitHub API or requiring a GitHub token. The `annotate` command emits GitHub Actions annotations for command failures and risk findings, and the `gh-summary` command writes a Markdown summary to the GitHub Actions step summary when `GITHUB_STEP_SUMMARY` is available.


## VibeBench Dogfoods Itself

This repository's active CI runs direct `ruff` and `pytest` checks first, then runs VibeBench itself. CI now runs `python -m vibebench ci`, which enforces the policy in `.vibebench/config.yaml`; if check or gate fails, the job fails. The command still attempts to generate the HTML report, PR-ready Markdown comment, human-readable explanation, machine-readable export, badge artifacts, README status block, trend summaries, machine-readable manifest plus consistency check, zip artifact bundle, GitHub annotations, GitHub step summary, and uploads `.vibebench/runs` as artifacts.

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
- runs direct Ruff and pytest checks
- runs `python -m vibebench ci` as the recommended VibeBench CI entrypoint
- uses check and gate as the final VibeBench pass/fail decision
- still attempts report, PR comment, explanation, export, badge, status block, trend summaries, manifest, GitHub annotations, bundle, and GitHub summary artifacts on failure
- uploads `.vibebench/runs` as a workflow artifact

## Add A Quality Gate

Use `vibebench ci` when CI should fail on explicit score, risk, and finding thresholds while still producing debugging artifacts:

```yaml
      - name: Run VibeBench CI pipeline
        run: python -m vibebench ci
```

The command writes `.vibebench/runs/<timestamp>/gate-summary.md` and supports one-run gate overrides such as `--min-score`, `--max-risk`, `--allow-findings`, and `--no-require-status-passed`.

## Why `if: always()` Is Used

`vibebench ci` should fail the workflow when check or gate fails. It internally still attempts report, comment, explanation, export, badge, status block, trend summaries, annotation output, bundle, and summary generation so reviewers can inspect VibeBench output after a failed check or gate. The artifact upload step remains `if: always()`.

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
- `vibebench-bundle.zip`
- `export.json`
- `badge.json`
- `badge.md`
- `status-block.md`
- `trend.md`
- `trend.json`
- `manifest.json`
- `gate-summary.md`
- GitHub Actions annotations in the job log when findings or command failures exist
- `github-step-summary.md` when not running inside GitHub step summary mode

CI should keep generating `status-block.md` as an artifact, but it should not mutate README files. If a project wants read-only README drift detection, add a separate step such as:

```yaml
- name: Check README VibeBench status block
  run: python -m vibebench status-block --readme README.md --check-readme
```

For local updates, run `python -m vibebench status-block --readme README.md --write-readme` after a fresh VibeBench run.

To inspect what CI uploaded, run `python -m vibebench artifacts --json` locally against a downloaded `.vibebench/runs/<run-id>` directory, or use `python -m vibebench artifacts --only-available` for a concise human-readable view.

## Limitations

- VibeBench does not post PR comments through the GitHub API yet.
- Your project test and lint commands must be installable and runnable in CI.
- The generated workflow assumes your project can be installed with `python -m pip install -e ".[dev]"`; adjust that step if your project uses a different install command. Pin the VibeBench install line to a tag or commit when you need reproducible CI.
