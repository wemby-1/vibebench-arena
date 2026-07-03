# VibeBench Arena Roadmap

VibeBench Arena is a Codex-first quality gate for vibe coding projects.

> Codex writes code. VibeBench verifies it.

## Current Status After v0.2.0

v0.2.0 established VibeBench as a local and CI verification tool with a complete artifact loop:

- `vibebench ci` as the one-shot CI pipeline.
- Configurable `gate` and `risk` policies in `.vibebench/config.yaml`.
- Machine-readable outputs for CI, config checks, doctor, release checks, artifacts, trend, latest run lookup, and exports.
- Dry-run / plan mode with persistent `ci-plan.json` and `ci-plan.md` artifacts.
- Release readiness checks and release-check artifacts.
- Manifest generation and manifest consistency checks.
- GitHub Actions annotations, step summaries, and downloadable `vibebench-run-artifacts`.
- Contract tests that pin CI pipeline order, skip flags, dry-run JSON, and import safety.

The project is still intentionally local-first. It can now post/update PR comments from GitHub Actions, but it does not publish to PyPI, provide a hosted dashboard, or implement multi-agent arena workflows.

## v0.3.0 Theme

**From local/CI verification to collaborative GitHub-native review workflows.**

v0.3.0 should make VibeBench easier to use in real code review loops while preserving the small, inspectable, local-first design that made v0.2.0 reliable.

## Priority Areas

### A. GitHub PR Comment Integration

Goal: make `pr-comment.md` useful directly inside GitHub pull requests. The design contract lives in [docs/pr-comments.md](docs/pr-comments.md).

Planned direction:

- Post or update PR comments from the generated `pr-comment.md` content.
- Avoid duplicate VibeBench comments by using a stable marker or bot-owned comment update strategy.
- Provide a dry-run mode that prints what would be posted or updated.
- Work inside GitHub Actions using the standard GitHub token.
- Avoid requiring secrets beyond what GitHub Actions already provides.
- Keep local generation and copy-paste workflows unchanged.

### B. Packaging And Installation Readiness

Goal: make installation guidance more reliable without rushing package distribution.

Planned direction:

- Validate `pyproject.toml` metadata and packaging shape with `python -m vibebench package-check`.
- Persist `package-check.json` and `package-check.md` in CI/release artifact flows.
- Document editable installs clearly for contributors.
- Consider a `pipx`-friendly install workflow.
- Keep source installs and local development paths first-class.
- Do not publish to PyPI unless a later milestone explicitly scopes and verifies it.

### C. Project Initialization Templates

Goal: make first-run setup clearer for new repositories.

Planned direction:

- Improve `vibebench init` output and generated templates where needed.
- Make the generated config easier to understand on first read.
- Provide a minimal example project that demonstrates setup, check, gate, report, CI, and artifact download.
- Clarify when to use editable install, GitHub install, or future packaged install paths.

### D. Artifact UX And Dashboard Direction

Goal: make generated artifacts easier to inspect, share, and reason about.

Planned direction:

- Polish `report/index.html` for review screenshots and local browsing.
- Make `vibebench-bundle.zip` contents easier to inspect after download.
- Keep the GitHub Actions artifact download path obvious in docs.
- Explore a future dashboard direction without committing to a hosted service in v0.3.0.

### E. Policy Presets

Goal: make quality policy easier to adopt without breaking existing config.

Planned direction:

- Add starter/default/strict policy profile guidance.
- Preserve compatibility with existing `.vibebench/config.yaml` files.
- Document when to use each profile.
- Keep explicit config values visible and understandable.

## Proposed Milestone Sequence

- **M59: GitHub PR comment design**
  Define the comment marker strategy, permissions model, dry-run output, and failure behavior in [docs/pr-comments.md](docs/pr-comments.md) before implementing API calls.

- **M60: GitHub PR comment implementation**
  Add the command and tests for posting/updating PR comments from `pr-comment.md`, with dry-run support and no duplicate comments.

- **M61: GitHub PR comment workflow wiring**
  Wire marker-based PR comment posting into GitHub Actions safely.

- **M63: Packaging/install readiness**
  Validate package metadata, document install paths, and make contributor/user installation guidance sharper without publishing to PyPI.

- **M62: Init/template polish**
  Improve `vibebench init`, generated workflow/config guidance, and a minimal example project for first-run clarity.

- **M63: Artifact/report UX polish**
  Improve report and bundle usability, artifact navigation, and screenshot/readme readiness.

- **M64: v0.3.0 release candidate docs**
  Prepare release notes, changelog updates, readiness checklist, and final verification for v0.3.0.

This sequence can change if implementation work reveals a better dependency order. The guiding rule is to keep each milestone small enough to review and test cleanly.

## Non-Goals For v0.3.0

- No hosted benchmark dashboard.
- No multi-agent arena tournament system.
- No PyPI publishing unless a later milestone explicitly scopes it.
- No broad rewrite of the existing config schema.
- No replacement for human review.
- No requirement for secrets beyond standard GitHub Actions token behavior for GitHub-native features.

## Release Criteria For v0.3.0

v0.3.0 should be considered ready when:

- Existing v0.2.0 workflows remain compatible.
- GitHub Actions CI stays green.
- `python -m vibebench release-check` passes.
- `python -m vibebench ci` passes locally and in CI.
- GitHub Actions artifacts remain downloadable as `vibebench-run-artifacts`.
- New PR comment behavior has dry-run support and focused tests.
- PR comment integration avoids duplicate comments.
- Documentation explains setup, permissions, install paths, and artifact review clearly.
- The release notes and changelog describe the v0.3.0 scope without overstating the product.
