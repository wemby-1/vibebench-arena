# Quickstart

VibeBench Arena is a local quality gate for Codex-first and AI-assisted coding projects.

## Install From Source

```bash
git clone git@github.com:wemby-1/vibebench-arena.git
cd vibebench-arena
python -m pip install -e ".[dev]"
```

## Initialize Config

```bash
python -m vibebench init
```

This creates:

```text
.vibebench/config.yaml
```

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
```

The risk demo intentionally creates critical findings, so `vibebench check` is expected to exit non-zero.


## CI Artifacts

VibeBench Arena dogfoods itself in this repository's CI. The workflow runs `vibebench check`, enforces `vibebench gate --write-gate-summary` using the policy in `.vibebench/config.yaml`, writes the GitHub Actions job summary with `vibebench gh-summary`, and uploads `.vibebench/runs` as artifacts for review.

## Generated Files

Generated run artifacts are local outputs and should not be committed:

```text
.vibebench/runs/<timestamp>/
```
