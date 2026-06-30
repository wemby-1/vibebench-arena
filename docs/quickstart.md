# Quickstart

VibeBench Arena is a local quality gate for Codex-first and AI-assisted coding projects.

## Install From Source

```bash
git clone git@github.com:wemby-1/vibebench-arena.git
cd vibebench-arena
python -m pip install -e ".[dev]"
```

## Initialize VibeBench

```bash
python -m vibebench init
```

This creates local config and a GitHub Actions workflow:

```text
.vibebench/config.yaml
.github/workflows/vibebench.yml
```

By default, existing files are skipped. Use `--force` to overwrite generated files, `--no-workflow` to create only config, or `--workflow-only` to create only the workflow.

## Inspect Effective Config

```bash
python -m vibebench config
python -m vibebench config --json
python -m vibebench config --validate
python -m vibebench config --show-source
```

`vibebench config` shows the effective project, checks, gate, and risk settings. It uses `.vibebench/config.yaml` when present and falls back to built-in defaults when no config file exists.

## Diagnose Project Readiness

```bash
python -m vibebench doctor
```

`vibebench doctor` checks Python, Git, `.vibebench/config.yaml`, configured command executables, and whether `.vibebench/runs/` is writable. It does not run your configured checks.

## Show Run History

```bash
python -m vibebench history
```

By default this shows the 10 newest runs with `metrics.json`. You can change the limit or inspect another runs directory:

```bash
python -m vibebench history --limit 5
python -m vibebench history --runs-dir .vibebench/runs
```

## Save A Baseline Run

```bash
python -m vibebench baseline
python -m vibebench baseline --set latest
python -m vibebench baseline --set <run-id>
python -m vibebench compare --baseline
```

The baseline command stores metadata in `.vibebench/baseline.json` and validates that the referenced run and `metrics.json` still exist.

## Clean Old Local Runs

```bash
python -m vibebench clean
python -m vibebench clean --keep 5
python -m vibebench clean --keep 5 --yes
```

`vibebench clean` is dry-run by default. It preserves the newest runs, only considers direct run directories containing `metrics.json`, and deletes nothing unless `--yes` is provided.

## Run Checks

```bash
python -m vibebench check
```

The default config runs:

```bash
pytest -q
ruff check .
```

`vibebench check` writes:

```text
.vibebench/runs/<timestamp>/metrics.json
.vibebench/runs/<timestamp>/check.log
```

## Configure Risk Rules

`vibebench check` uses the `risk` section in `.vibebench/config.yaml` when present. CLI behavior falls back to built-in defaults when this section is absent.

```yaml
risk:
  max_changed_files: 20
  max_patch_lines: 500
  forbidden_paths:
    - .env
    - .env.*
    - secrets/
  secret_like_paths:
    - "*secret*"
    - "*token*"
  lockfiles:
    - package-lock.json
    - pnpm-lock.yaml
    - yarn.lock
    - poetry.lock
    - uv.lock
    - Pipfile.lock
    - requirements.lock
  test_path_patterns:
    - tests/
    - test_*.py
    - "*_test.py"
```

See [risk-rules.md](risk-rules.md) for the full policy reference.

## Enforce A Quality Gate

```bash
python -m vibebench gate
python -m vibebench gate --write-gate-summary
python -m vibebench gate --min-score 90 --max-risk low
python -m vibebench gate --baseline --write-gate-summary
```

`vibebench gate` evaluates an existing run, exits nonzero on failure, and can write `.vibebench/runs/<timestamp>/gate-summary.md`. By default, it reads thresholds from `.vibebench/config.yaml` when a `gate` section is present; CLI flags override config values for one run.

## Run The Full CI Pipeline

```bash
python -m vibebench ci
```

`vibebench ci` runs check, gate, report, PR comment, explain, export, badge, status block, bundle, GitHub annotations, and GitHub summary. Check and gate decide the final exit code, but artifact steps are still attempted on failure so CI logs and artifacts remain useful.

Useful options:

```bash
python -m vibebench ci --min-score 90 --max-risk low
python -m vibebench ci --skip-report --skip-pr-comment
python -m vibebench ci --skip-export
python -m vibebench ci --skip-badge
python -m vibebench ci --skip-status-block
python -m vibebench ci --skip-annotate
python -m vibebench ci --bundle-include-report-assets
python -m vibebench ci --run-dir .vibebench/runs/<run-id>
```

## Generate A Static HTML Report

```bash
python -m vibebench report
```

This writes:

```text
.vibebench/runs/<timestamp>/report/index.html
```

## Generate A PR Comment

```bash
python -m vibebench pr-comment
```

This writes:

```text
.vibebench/runs/<timestamp>/pr-comment.md
```

The Markdown is designed to paste into a pull request, issue, or review thread.


## Explain A Run

```bash
python -m vibebench explain
```

This writes:

```text
.vibebench/runs/<timestamp>/explain.md
```

The explanation describes command failures, Git diff risk signals, known risk findings, and suggested next actions. Use `--run-dir` for a specific run, `--output` for a custom path, or `--no-write` to print only.

## Bundle Run Artifacts

```bash
python -m vibebench bundle
```

This writes:

```text
.vibebench/runs/<timestamp>/vibebench-bundle.zip
```

Use `--run-dir` to bundle a specific run, `--output` for a custom zip path, `--include-report-assets` to include the full `report/` directory recursively, and `--strict` to fail if any standard artifact is missing.

## Export A Run

```bash
python -m vibebench export
python -m vibebench export --pretty
python -m vibebench export --format markdown
```

The JSON export is stable machine-readable output for dashboards, badges, external tools, and CI aggregation. Use `--output` to write a file. The one-shot CI command writes `.vibebench/runs/<timestamp>/export.json` by default.

## Generate A Badge Artifact

```bash
python -m vibebench badge
python -m vibebench badge --format markdown
python -m vibebench badge --format url
python -m vibebench badge --format markdown --label "VibeScore"
```

This writes a Shields.io-compatible endpoint JSON file to `.vibebench/runs/<timestamp>/badge.json` by default. Markdown output writes `badge.md` for README copy/paste, and URL output writes `badge-url.txt`. Use `--label` to customize the visible label and `--output` to write a custom path for the selected format. `vibebench ci` generates `badge.json` and `badge.md` by default.

## Generate A README Status Block

```bash
python -m vibebench status-block
python -m vibebench status-block --title "Project Quality"
python -m vibebench status-block --no-include-artifacts
python -m vibebench status-block --output README-status.md
python -m vibebench status-block --readme README.md --write-readme
python -m vibebench status-block --readme README.md --check-readme
```

This writes `.vibebench/runs/<timestamp>/status-block.md`, a copy-pasteable README section with the current status, VibeScore, risk level, diff size, findings, optional badge, and generated artifacts. To keep a README block stable, add `<!-- VIBEBENCH_STATUS_START -->` and `<!-- VIBEBENCH_STATUS_END -->` marker lines, then use `--write-readme` to replace only the marked content. Use `--check-readme` in read-only validation when you want to detect a stale committed status block without modifying files.

## Emit GitHub Actions Annotations

```bash
python -m vibebench annotate
python -m vibebench annotate --no-github-actions
```

Annotations surface command failures and risk findings in GitHub Actions logs. They are reporting-only and exit 0 when annotations are emitted; use `vibebench gate` for pass/fail decisions.

## Generate A GitHub Actions Summary

```bash
python -m vibebench gh-summary
```

In GitHub Actions, this appends to `GITHUB_STEP_SUMMARY`. Locally, it writes:

```text
.vibebench/runs/<timestamp>/github-step-summary.md
```

## Compare Runs

```bash
python -m vibebench compare
```

This compares the latest run with the previous run and writes:

```text
.vibebench/runs/<latest-timestamp>/compare.md
```

You can also compare explicit run directories:

```bash
python -m vibebench compare --base-run .vibebench/runs/<base> --current-run .vibebench/runs/<current>
```

## Try The Risk Demo

From the VibeBench repository:

```bash
python examples/risk-demo/create_risky_repo.py
cd /tmp/vibebench-risk-demo
python -m vibebench check
python -m vibebench report
python -m vibebench pr-comment
python -m vibebench explain
python -m vibebench bundle
```

The risk demo intentionally creates critical findings, so `vibebench check` is expected to exit non-zero.


## CI Artifacts

VibeBench Arena dogfoods itself in this repository's CI. The workflow runs `vibebench ci`, which enforces the policy in `.vibebench/config.yaml`, generates `explain.md`, writes `export.json`, `badge.json`, `badge.md`, and `status-block.md`, bundles run artifacts, emits GitHub annotations, writes the GitHub Actions job summary, and uploads `.vibebench/runs` as artifacts for review.

## Generated Files

Generated run artifacts are local outputs and should not be committed:

```text
.vibebench/runs/<timestamp>/
```
