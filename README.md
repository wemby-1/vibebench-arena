# VibeBench Arena

Codex-first quality gate for vibe coding projects.

> Codex writes code. VibeBench verifies it.

VibeBench Arena is a local quality gate for teams using Codex-first or
AI-assisted development workflows. AI coding agents can produce changes quickly,
but developers still need a clear, local way to check whether generated code is
reasonable to ship.

This repository is intentionally starting small. The v0.1.0 milestone provides
a clean Python CLI scaffold, typed configuration, and test coverage for the
foundation. It does not try to be a benchmark platform yet.

## Why This Exists

Vibe coding can be fast and useful, but speed creates review pressure. VibeBench
Arena exists to help developers put lightweight verification between generated
code and shipping decisions.

The project aims to be:

- local-first and easy to run in a normal repository
- readable for developers who are new to Python tooling
- practical for Codex-first workflows
- incremental, with each milestone adding one focused capability

## Quickstart

```bash
python -m pip install -e ".[dev]"
python -m vibebench --help
python -m vibebench init
```

The `init` command creates:

```text
.vibebench/config.yaml
```

Default configuration:

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

## Current v0.1.0 Scope

This first milestone includes:

- Python 3.11+ package scaffold
- Typer-based CLI
- Rich terminal output
- Pydantic config models
- YAML config loading with beginner-friendly errors
- pytest tests
- ruff lint configuration
- GitHub Actions CI

Available commands:

```bash
vibebench --help
vibebench version
vibebench init
```

## Built with a Codex-First Workflow

VibeBench Arena is designed around the idea that Codex writes code and
VibeBench verifies it. That means the project values small milestones, clear
tests, readable implementation, and local checks that fit naturally into an
AI-assisted development loop.

The goal is not to replace human review. The goal is to give developers a
better first pass before review begins.

## Roadmap

Planned next steps:

- run configured test and lint commands
- add basic git working-tree and patch awareness
- flag risky file changes such as secrets and deleted tests
- produce a simple terminal verification summary
- add machine-readable output for CI integrations
- explore richer reports after the local CLI is useful

Not in v0.1.0:

- git diff analysis
- HTML reports
- benchmark leaderboards
- multi-agent arena workflows
