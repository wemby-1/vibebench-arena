# Changelog

All notable changes to VibeBench Arena will be documented in this file.

The format is inspired by Keep a Changelog, and this project aims to follow semantic versioning once releases begin.

## [Unreleased]

### Added

- Added a public review hub and reviewer guide for 3-minute external evaluation of proof packet, site preview, evidence room, and CI artifacts.

- Added evidence-room generation to local `vibebench ci`, including `--skip-evidence-room`, artifact discovery/latest aliases, manifest entries, bundle inclusion, and GitHub summary visibility.

- Added CI evidence room generation and upload as the downloadable `vibebench-evidence-room` artifact for external evaluation without enabling GitHub Pages automatically.

- Added `python3 -m vibebench evidence-room` for creating, zipping, JSON-exporting, and verifying a local evidence room that combines the proof packet and static site preview for external evaluation.

- Added `python3 -m vibebench site-preview` for creating, zipping, JSON-exporting, and verifying the reusable static site preview bundle that CI uploads as `vibebench-site-preview`.

- Added CI static site readiness checking and a downloadable `vibebench-site-preview` artifact for reviewing the GitHub Pages-ready docs without enabling Pages automatically.

- Added `python3 -m vibebench site-check` with JSON output to verify the static GitHub Pages entry, required proof/evaluation links, and unsafe publishing markers before manual Pages setup.

- Added a GitHub Pages-ready site entry and manual setup guide for serving the public docs from `docs/`.

- Added a GitHub Pages-ready static product showcase page for the CLI, CI proof packet, artifacts, and honest evaluation path.

- Improved the GitHub Actions proof packet summary card with file details, the local reproduction command, and artifact download guidance.

- Added GitHub Actions proof packet generation and upload as the `vibebench-proof-packet` artifact.

- Added a self-contained local HTML proof report (`proof.html`) to proof packets, manifests, archives, and verification.

- Added proof packet manifests, zip archive output, and local verification for shareable proof packets.

- Added `python3 -m vibebench proof` for generating a local proof packet with visitor-facing Markdown and JSON evidence.

- Added a 5-minute evaluation path and adoption guide for GitHub visitors and teams evaluating Codex-first/vibe-coding quality workflows.

- Added honest comparison and FAQ pages explaining how VibeBench Arena differs from CI, benchmarks, chatbots, and code review assistants.

- Added an evidence-first public case study showing how AI-assisted changes become reviewable VibeBench artifacts.

- Added visual architecture and artifact evidence diagrams for the GitHub landing page.

- Added public product strategy, roadmap, and commercial potential docs that explain the Codex-first / vibe-coding quality console narrative without fake traction or promised outcomes.

- Improved the GitHub landing-page positioning across README and public docs, emphasizing the Codex-first / vibe-coding quality console, one-command demo, artifact gallery, sample artifacts, and local-first evidence trail.

- Added `python3 -m vibebench demo` for a one-command local showcase demo of the checked-in sample artifact pack, including JSON and safe copy modes.
- Added GitHub issue templates, a PR template, and community feedback paths for bugs, features, use cases, and demo feedback.
- Added project positioning and use-case docs for evaluating VibeBench as a Codex-first / vibe-coding quality console.
- Added a small checked-in sample artifact pack for GitHub visitors to browse VibeBench output shapes without running commands.
- Added an artifact gallery and showcase docs for GitHub visitors.
- Added public GitHub-facing quickstart demo and positioning docs for VibeBench Arena.
- `release-audit` bundles `release-body.md` and `release-body.json` in directories, zips, manifests, and verification checks for local-only release handoff/audit records without tags, GitHub Releases, GitHub API calls, uploads, publishes, version bumps, or dependency installs.
- Local-only `python3 -m vibebench release-body` export for copy/paste GitHub Release bodies from `RELEASE_NOTES_vX.Y.Z.md`, with `--check` for stale release-candidate wording and no tag, release, upload, publish, version bump, or dependency install side effects.
- `release-audit` now writes `release-audit-manifest.json` checksums and `release-audit --verify PATH` validates them when present, without tags, GitHub Releases, package uploads/publishes, version bumps, or dependency installs.
- Read-only `python3 -m vibebench release-audit --verify PATH` mode for validating local release audit directories or zip archives without creating tags, GitHub Releases, package uploads/publishes, version bumps, or dependency installs.
- Local-only release-audit archive output with `python3 -m vibebench release-audit --zip` and `python3 -m vibebench release-audit --zip-output PATH`, without creating tags, GitHub Releases, package uploads/publishes, or version bumps.
- Local-only `python -m vibebench release-audit` command for generating package, publish, release checklist, and aggregate audit artifacts without creating tags, releases, package uploads, or version bumps.
- Persistent `release-checklist --write-json` and `release-checklist --write-summary` audit records for local release preparation without creating tags, releases, package uploads, or version bumps.
- Persistent `publish-check --write-json` and `publish-check --write-summary` audit records for local-only package publishing readiness without uploading packages or creating releases.
- Local-only `python -m vibebench publish-check` dry-run for package publishing readiness, covering metadata, release notes, tags, package-check, package-check --build, and release-check without uploading packages or creating releases.
- Opt-in local-only package build readiness check with `python -m vibebench package-check --build`, including JSON build metadata and release-check guidance before PyPI or GitHub Package publishing.
- Low-cost Codex task template in [docs/codex-task-template.md](docs/codex-task-template.md) for bounded, auditable milestone prompts.
- Read-only `vibebench release-checklist` command for target-version release preparation checks without creating tags or GitHub releases.
- Package metadata prepared for v0.3.0 without creating a tag or GitHub release.
- Final v0.3.0 release notes in [RELEASE_NOTES_v0.3.0.md](RELEASE_NOTES_v0.3.0.md), covering GitHub-native review workflows, artifacts, config UX, readiness checks, and release maintenance.
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
- Git diff risk analysis for forbidden paths, credential-like files, deleted tests, changed tests, lockfiles, large patches, and broad file changes.
- Static HTML report generation with `vibebench report`.
- PR-ready Markdown summary generation with `vibebench pr-comment`.
- Risk demo pack that creates a temporary repository with intentionally dangerous uncommitted changes.
- README visual preview assets for clean and risky VibeBench runs.

### Notes

- v0.1.0 is local-first and Codex-first: Codex writes code, VibeBench verifies it.
- This release does not include GitHub API posting, hosted dashboards, or multi-agent arena workflows.
