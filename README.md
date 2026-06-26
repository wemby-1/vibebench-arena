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

VibeBench v0.1.0 already supports:

- config initialization with `.vibebench/config.yaml`
- configured test and lint commands
- VibeScore and risk level calculation
- Git diff risk analysis for uncommitted changes
- static HTML reports for local review and screenshots

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

## Roadmap

Planned next milestones:

- PR comment generation
- GitHub Action integration
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
