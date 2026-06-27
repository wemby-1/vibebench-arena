# Changelog

All notable changes to VibeBench Arena will be documented in this file.

The format is inspired by Keep a Changelog, and this project aims to follow semantic versioning once releases begin.

## [Unreleased]

### Added

- `vibebench history` for inspecting recent local run metrics and generated artifacts.
- `vibebench doctor` for local readiness diagnostics before running checks.
- `vibebench compare` for comparing the latest run against a previous run and writing `compare.md`.
- Upgraded active GitHub Actions to Node 24-compatible action majors.
- Active GitHub Actions CI now dogfoods VibeBench and uploads `.vibebench/runs` artifacts.
- `vibebench gh-summary` for GitHub Actions step summaries without GitHub API posting.
- Example GitHub Actions workflow and setup documentation.
- Release-readiness documentation for contributors, security reporting, risk rules, and quickstart usage.
- GitHub issue and pull request templates for focused open-source collaboration.

## [0.1.0] - 2026-06-27

### Added

- Clean Python 3.11+ CLI scaffold with Typer, Rich, Pydantic, and PyYAML.
- `vibebench init` for creating `.vibebench/config.yaml`.
- `vibebench check` for running configured local test and lint commands.
- VibeScore, risk level, and structured `metrics.json` output.
- Git diff risk analysis for forbidden paths, secret-like files, deleted tests, changed tests, lockfiles, large patches, and broad file changes.
- Static HTML report generation with `vibebench report`.
- PR-ready Markdown summary generation with `vibebench pr-comment`.
- Risk demo pack that creates a temporary repository with intentionally dangerous uncommitted changes.
- README visual preview assets for clean and risky VibeBench runs.

### Notes

- v0.1.0 is local-first and Codex-first: Codex writes code, VibeBench verifies it.
- This release does not include GitHub API posting, hosted dashboards, or multi-agent arena workflows.
