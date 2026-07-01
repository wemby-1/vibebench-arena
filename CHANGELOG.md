# Changelog

All notable changes to VibeBench Arena will be documented in this file.

The format is inspired by Keep a Changelog, and this project aims to follow semantic versioning once releases begin.

## [Unreleased]

### Added

- `vibebench config --check` and `vibebench config --check --json` for focused config consistency diagnostics.
- `vibebench config --show` and `vibebench config --show --json` for inspecting the active validated config file.
- `vibebench manifest` for writing machine-readable `manifest.json` run indexes and `vibebench manifest --check` for drift detection against run artifacts.
- `vibebench latest --all-paths` for printing every available artifact path from the newest valid run.
- `vibebench latest` for locating the newest valid run and key artifact paths.
- `vibebench trend` for summarizing recent run quality movement across scores, risks, and findings, with optional `trend.md` and `trend.json` artifact output.
- `vibebench artifacts` for listing known run artifacts, availability, and file sizes.
- `vibebench status-block` for copy-pasteable README status summaries, plus marker-based README update and check modes.
- `vibebench badge` for Shields.io-compatible `badge.json`, `badge.md`, and badge URL run status artifacts.
- `vibebench export` for stable JSON and Markdown run exports for dashboards, external tools, and CI aggregation.
- `vibebench annotate` for emitting GitHub Actions annotations from command failures and risk findings.
- `vibebench ci` for running the complete check, gate, and artifact pipeline in one command, including trend summary, trend JSON, and manifest generation.
- `vibebench bundle` for packaging run artifacts into `vibebench-bundle.zip`.
- `vibebench explain` for human-readable run explanations and `explain.md` artifacts.
- `vibebench config` for inspecting, validating, and exporting the effective configuration.
- `vibebench init` now bootstraps `.vibebench/config.yaml` and a GitHub Actions workflow, with safe overwrite controls.
- Configurable `risk` policy in `.vibebench/config.yaml` for Git diff risk detection.
- `vibebench gate` for explicit local and CI pass/fail quality thresholds.
- Configurable `gate` policy in `.vibebench/config.yaml`, with CLI flags as explicit overrides.
- Active GitHub Actions CI now enforces the VibeBench quality gate from config and writes `gate-summary.md`.
- `vibebench baseline` for saving a project baseline run and comparing against it.
- `vibebench clean` for safe dry-run cleanup of old local run directories.
- `vibebench history` for inspecting recent local run metrics and generated artifacts.
- `vibebench doctor --json`, `vibebench doctor --strict`, and `vibebench doctor --advice` for machine-readable diagnostics, stronger release/CI readiness preflights, and actionable repair suggestions.
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
