# VibeBench Arena

**Codex-first quality gate for vibe coding projects.**

> Codex writes code. VibeBench verifies it.

[![CI](https://github.com/wemby-1/vibebench-arena/actions/workflows/ci.yml/badge.svg)](https://github.com/wemby-1/vibebench-arena/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)

![VibeBench report preview](docs/assets/report-preview.svg)

VibeBench Arena is a local verification tool for Codex-first and AI-assisted
coding workflows. It helps developers check whether AI-generated code is safe to
review, commit, and ship.

The project is intentionally small today. v0.1.0 focuses on a clean CLI, local
checks, Git diff risk analysis, VibeScore, and a static HTML report.

## Why VibeBench?

AI coding agents can produce useful changes quickly, but speed creates review
pressure. VibeBench adds a local quality gate between generated code and shipping
decisions.

It is designed to be:

- local-first and easy to run inside an existing repository
- readable for developers who are new to Python tooling
- useful in Codex-first workflows without replacing human review
- incremental, with focused milestones instead of a large benchmark platform

## What It Checks Today

Current VibeBench supports:

- config initialization with `.vibebench/config.yaml`
- configured test and lint commands
- VibeScore and risk level calculation
- Git diff risk analysis for uncommitted changes
- static HTML reports for local review and screenshots
- PR-ready Markdown summaries for pasteable code review comments
- GitHub Actions step summaries without GitHub API posting

Git diff risk analysis flags:

- deleted test files
- touched `.env`, `.env.*`, or `secrets/` paths
- secret-like paths containing words such as `token`, `api_key`, or `password`
- changed lockfiles such as `package-lock.json`, `poetry.lock`, or `uv.lock`
- large patches over the configured threshold
- changes touching more than 20 files

## Quick Start

```bash
python -m pip install -e ".[dev]"
python -m vibebench init
python -m vibebench check
python -m vibebench report
python -m vibebench pr-comment
python -m vibebench gh-summary
```

The default config looks like this:

```yaml
project:
  name: vibebench-project

checks:
  test:
    - pytest -q
  lint:
    - ruff check .

risk_rules:
  forbidden_paths:
    - .env
    - .env.*
    - secrets/
  warn_if_tests_deleted: true
  warn_if_lockfiles_changed: true
  large_patch_lines: 500
```

## Example Workflow

```bash
# Create project config once
python -m vibebench init

# Run local quality gate before committing
python -m vibebench check

# Generate a static local report
python -m vibebench report

# Generate a Markdown summary for a PR or review thread
python -m vibebench pr-comment

# Write a GitHub Actions step summary or local summary file
python -m vibebench gh-summary
```

`vibebench check` writes:

```text
.vibebench/runs/<timestamp>/metrics.json
.vibebench/runs/<timestamp>/check.log
```

`vibebench report` writes:

```text
.vibebench/runs/<timestamp>/report/index.html
```

`vibebench pr-comment` writes:

```text
.vibebench/runs/<timestamp>/pr-comment.md
```

## What The HTML Report Shows

The static report is a dependency-light HTML file suitable for local review,
screenshots, and README demos. It includes:

- project name and run timestamp
- overall status, VibeScore, and risk level
- command results for test and lint checks
- risk findings from Git diff analysis
- changed files and patch line summary
- a short recommendation for review or shipping

Generated reports under `.vibebench/runs/` are local artifacts and should not be
committed. The image at `docs/assets/report-preview.svg` is a static README
preview asset.

## PR Comment Summary

`vibebench pr-comment` generates a concise Markdown summary that can be pasted
into a GitHub Pull Request, issue, or code review. It includes:

- overall status, VibeScore, risk level, project name, and timestamp
- command results for configured checks
- Git diff risk summary counts
- up to 10 risk findings with affected paths
- the same recommendation used by the HTML report

Automatic GitHub PR posting is planned later; the current command is local and
does not call the GitHub API.

## GitHub Actions

`vibebench gh-summary` writes a concise Markdown summary to the GitHub Actions step summary when `GITHUB_STEP_SUMMARY` is set. It does not post PR comments through the GitHub API yet.

This repository dogfoods VibeBench in its own CI: after direct Ruff and pytest checks, CI runs `vibebench check`, generates report/comment/summary artifacts, and uploads `.vibebench/runs`. See [docs/examples/github-actions/vibebench.yml](docs/examples/github-actions/vibebench.yml) for a copyable workflow and [docs/github-actions.md](docs/github-actions.md) for details.

## Try The Risk Demo

A clean 100/100 run is useful, but VibeBench is meant to catch risky generated changes before they ship. The risk demo creates a temporary repository with a clean baseline commit, then intentionally leaves suspicious uncommitted changes for VibeBench to analyze.

```bash
python examples/risk-demo/create_risky_repo.py
cd /tmp/vibebench-risk-demo
python -m vibebench check
python -m vibebench report
python -m vibebench pr-comment
```

The demo intentionally touches `.env.local` and `secrets/`, deletes a test file, changes a lockfile, and creates a large patch. `vibebench check` is expected to fail because critical findings are present.

![VibeBench risk demo preview](docs/assets/risk-demo-preview.svg)

See [examples/risk-demo/README.md](examples/risk-demo/README.md) for details.

## Documentation

- [Quickstart](docs/quickstart.md)
- [Risk rules](docs/risk-rules.md)
- [GitHub Actions](docs/github-actions.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Changelog](CHANGELOG.md)

## Roadmap

Planned next milestones:

- automatic GitHub PR comment posting
- richer GitHub Action integration
- multi-agent arena workflows
- replay timeline for AI-generated changes

Not in v0.1.0:

- hosted benchmark leaderboards
- browser app or dashboard server
- multi-agent tournament system

## Built With A Codex-First Workflow

VibeBench Arena is built around a simple principle:

> Codex writes code. VibeBench verifies it.

That means small milestones, clear tests, readable implementation, and local
checks that fit naturally into AI-assisted development. VibeBench does not
replace human review; it gives reviewers a better starting point.
