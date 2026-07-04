# Changelog

All notable changes to VibeBench Arena will be documented in this file.

The format is inspired by Keep a Changelog, and this project aims to follow semantic versioning once releases begin.

## [Unreleased]

### Added

- Package metadata prepared for v0.3.0 without creating a tag or GitHub release.
- v0.3.0 release candidate notes in [RELEASE_NOTES_v0.3.0.md](RELEASE_NOTES_v0.3.0.md), covering GitHub-native review workflows, artifacts, config UX, readiness checks, and release steps.
- Config init dry-run mode with `python3 -m vibebench config --init --dry-run`, JSON output, and force-aware write planning.
- v0.3.0 roadmap planning in [ROADMAP.md](ROADMAP.md), covering GitHub-native PR review workflows, packaging readiness, init/template polish, artifact UX, policy presets, non-goals, and release criteria.
- GitHub PR comment posting via `python -m vibebench pr-comment --post`, with dry-run mode, JSON output, marker-based update behavior, tested create/update decisions, and pull-request-only GitHub Actions wiring.
- Local package/install readiness checks with `python -m vibebench package-check`, `--json`, `--advice`, persisted `package-check.json` / `package-check.md` artifacts, CI generation, and release-check integration.
- Run index artifacts with `python -m vibebench run-index`, `run-index.json`, `run-index.md`, CI generation, artifact discovery, manifest/bundle/GitHub summary integration, and `--skip-run-index`.
- Opt-in compare regression guard with `vibebench compare --fail-on-regression`, `vibebench ci --fail-on-regression`, and CI policy via `.vibebench/config.yaml` (`compare.fail_on_regression`); default compare remains reporting-only, `insufficient-data` does not fail, and `--skip-compare` overrides the CI guard.

## [0.2.0] - 2026-07-03

### Added

- Release notes in [RELEASE_NOTES_v0.2.0.md](RELEASE_NOTES_v0.2.0.md).
- `vibebench ci` as the one-shot check, gate, artifact, annotation, bundle, and GitHub summary pipeline.
- Machine-readable CI output with `vibebench ci --json` and `--json-output`.
- CI dry-run / plan mode with `vibebench ci --dry-run`, `vibebench ci --plan`, `ci-plan.json`, and `ci-plan.md`.
- CI pipeline contract tests covering import safety, canonical step order, skip flags, dry-run JSON, and release-check integration.
- `vibebench release-check` for read-only pre-release readiness checks across config, strict doctor, latest run, manifest, artifacts, CI plan, and `git diff --check`.
- Release-check artifacts with `release-check.json` and `release-check.md`, including generation from `vibebench ci`.
- Config path inspection with `config --path`, safe config initialization with `config --init`, starter config examples with `config --example` / `config --write-example`, consistency diagnostics with `config --show`, `config --check`, `config --check --advice`, and persisted `config-check.json` / `config-check.md` artifacts.
- Strict doctor checks, JSON output, and actionable advice with `vibebench doctor --strict`, `--json`, and `--advice`.
- Run manifest generation and consistency checks with `vibebench manifest` and `vibebench manifest --check`.
- Run discovery and artifact inspection commands including `latest`, `latest --all-paths`, `artifacts`, `history`, `trend`, `compare`, and `baseline`.
- Machine-readable and shareable run artifacts including `export.json`, `badge.json`, `badge.md`, `badge-url.txt`, `status-block.md`, `trend.md`, `trend.json`, and `vibebench-bundle.zip`.
- GitHub Actions annotations and step summaries without GitHub API posting.
- Active GitHub Actions dogfooding of VibeBench, including quality gate enforcement, downloadable `vibebench-run-artifacts`, and Node 24-compatible official actions.
- `vibebench init` bootstrapping for `.vibebench/config.yaml` and `.github/workflows/vibebench.yml`, with safe overwrite controls.
- Configurable `gate` and `risk` policy sections in `.vibebench/config.yaml`.
- `vibebench clean` for safe dry-run cleanup of old local run directories.
- Release-readiness documentation, GitHub Actions documentation, quickstart updates, contributor/security docs, and issue/PR templates.

### Notes

- v0.2.0 remains local-first and Codex-first: Codex writes code, VibeBench verifies it.
- PyPI publishing, default workflow PR comment posting, hosted dashboards, and multi-agent arena workflows remain out of scope for v0.2.0.

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
