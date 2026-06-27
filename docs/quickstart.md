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

## Generated Files

Generated run artifacts are local outputs and should not be committed:

```text
.vibebench/runs/<timestamp>/
```
