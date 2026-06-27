# VibeBench Arena v0.1.0

**Codex-first quality gate for vibe coding projects.**

> Codex writes code. VibeBench verifies it.

VibeBench Arena v0.1.0 is the first local-first release for checking whether AI-generated code is ready to review and ship. It focuses on a small, practical CLI rather than a hosted benchmark platform.

## Highlights

- Local quality gate for Codex-first and AI-assisted coding workflows.
- Runs configured test and lint commands from `.vibebench/config.yaml`.
- Calculates VibeScore, risk level, and overall pass/fail status.
- Analyzes the current Git working-tree diff for risky changes.
- Generates static HTML reports and PR-ready Markdown summaries.
- Includes a reproducible risk demo that shows VibeBench catching dangerous changes.

## What Is Included

- `vibebench init` for creating project config.
- `vibebench check` for running configured commands and risk analysis.
- `vibebench report` for static HTML reports.
- `vibebench pr-comment` for Markdown summaries that can be pasted into pull requests or review threads.
- Release-readiness docs: quickstart, risk rules, contributing guide, security policy, changelog, issue templates, and PR template.

## Quick Start

```bash
python -m pip install -e ".[dev]"
python -m vibebench init
python -m vibebench check
python -m vibebench report
python -m vibebench pr-comment
```

Generated run artifacts are written under:

```text
.vibebench/runs/<timestamp>/
```

## Commands

- `vibebench init`: create `.vibebench/config.yaml`.
- `vibebench check`: run configured checks, calculate score, analyze Git diff risk, and write metrics/log files.
- `vibebench report`: generate `.vibebench/runs/<timestamp>/report/index.html`.
- `vibebench pr-comment`: generate `.vibebench/runs/<timestamp>/pr-comment.md`.

## Risk Checks

VibeBench v0.1.0 analyzes uncommitted changes against `HEAD` and flags:

- forbidden paths such as `.env`, `.env.*`, and `secrets/`
- secret-like paths containing keywords such as `secret`, `token`, `api_key`, or `password`
- deleted test files
- changed test files
- changed lockfiles
- large patches
- too many changed files

## Demo

Try the risk demo from the repository root:

```bash
python examples/risk-demo/create_risky_repo.py
cd /tmp/vibebench-risk-demo
python -m vibebench check
python -m vibebench report
python -m vibebench pr-comment
```

The demo intentionally creates critical findings, so `vibebench check` is expected to fail. It is designed to show VibeBench catching suspicious AI-generated changes before shipping.

## Known Limitations

- No cloud dependency and no hosted service.
- No GitHub API posting yet.
- No automatic GitHub Release or PR comment publishing yet.
- Not a full multi-agent arena yet.
- Secret-like detection is path-based in v0.1.0; it does not scan file contents.
- Risk analysis focuses on the local uncommitted working-tree diff against `HEAD`.

## What Is Next

Planned future work includes:

- GitHub Action integration.
- Optional automated PR comment posting.
- More configurable risk rules.
- Replay timeline for AI-generated changes.
- Multi-agent arena workflows after the local quality gate is mature.
