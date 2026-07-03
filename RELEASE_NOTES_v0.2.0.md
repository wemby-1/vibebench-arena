# VibeBench Arena v0.2.0

Tagline: Codex-first quality gate for vibe coding projects.

Slogan: Codex writes code. VibeBench verifies it.

These notes are prepared for the v0.2.0 release. This metadata commit does not create a tag, publish a package, or create a GitHub Release.

## Highlights

v0.2.0 is focused on making VibeBench more useful in real local and CI workflows. Since v0.1.0, VibeBench has grown from a local check/report scaffold into a fuller quality-gate toolkit with CI orchestration, machine-readable outputs, release readiness checks, run artifact discovery, and downloadable GitHub Actions artifacts.

## What Changed Since v0.1.0

- One-shot CI pipeline with `python -m vibebench ci`.
- Configurable quality gate policy in `.vibebench/config.yaml`.
- CI JSON output for automation with `vibebench ci --json` and `--json-output`.
- CI dry-run and plan mode with `vibebench ci --dry-run` and `vibebench ci --plan`.
- Persistent CI plan artifacts: `ci-plan.json` and `ci-plan.md`.
- Config inspection and consistency checks, including `config-check.json` and `config-check.md` artifacts.
- Strict doctor checks, JSON output, and actionable advice.
- Manifest generation and manifest consistency checks.
- Run artifact inventory, latest-run lookup, bundle generation, trend summaries, badge artifacts, status blocks, and machine-readable exports.
- Release readiness checks with `vibebench release-check`.
- Release-check artifacts: `release-check.json` and `release-check.md`.
- GitHub Actions annotations, step summaries, and downloadable run artifacts.
- Contract tests that pin CI step order, skip flags, JSON dry-run payloads, and import safety.

## New CI Capabilities

`python -m vibebench ci` is now the recommended CI entrypoint. It runs the configured checks, enforces the quality gate, and then attempts artifact generation so failures are easier to diagnose.

The current pipeline includes:

1. `check`
2. `gate`
3. `config-check`
4. `report`
5. `pr-comment`
6. `explain`
7. `export`
8. `badge`
9. `status-block`
10. `trend`
11. `manifest`
12. `manifest-check`
13. `release-check`
14. `annotate`
15. `bundle`
16. `gh-summary`

GitHub Actions now uploads selected run outputs as a downloadable artifact named `vibebench-run-artifacts`.

Expected uploaded files can include:

- `metrics.json`
- `manifest.json`
- `vibebench-bundle.zip`
- `github-step-summary.md`
- `release-check.json`
- `release-check.md`
- `config-check.json`
- `config-check.md`
- `trend.json`
- `trend.md`
- `report/**`

## Dry-Run And Plan Mode

Use dry-run mode to inspect the CI pipeline without running checks or writing normal run artifacts:

```bash
python -m vibebench ci --dry-run
python -m vibebench ci --dry-run --json
python -m vibebench ci --dry-run --write-plan
```

Dry-run mode is useful when reviewing CI changes, debugging skip flags, or documenting the expected pipeline order.

## Machine-Readable Outputs

v0.2.0 capabilities include JSON outputs for automation and external tooling:

- `python -m vibebench ci --json`
- `python -m vibebench config --check --json`
- `python -m vibebench doctor --json --strict --advice`
- `python -m vibebench release-check --json`
- `python -m vibebench artifacts --json`
- `python -m vibebench trend --json`
- `python -m vibebench latest --json`

Several commands can also persist JSON artifacts for CI download or dashboard ingestion.

## Release Check

`python -m vibebench release-check` provides a read-only pre-release readiness check. It combines existing VibeBench signals instead of inventing a separate release policy.

It checks:

- config consistency
- strict doctor readiness
- latest valid run availability
- manifest consistency
- artifact inventory generation
- CI dry-run plan generation
- `git diff --check`

Artifact output is available with:

```bash
python -m vibebench release-check --write-json /tmp/release-check.json
python -m vibebench release-check --write-summary /tmp/release-check.md
```

In normal `vibebench ci`, these are written into the latest run directory as `release-check.json` and `release-check.md` unless `--skip-release-check` is used.

## Upgrade And Migration

Existing users can keep using:

```bash
python -m vibebench ci
```

New optional commands include:

```bash
python -m vibebench ci --dry-run
python -m vibebench ci --dry-run --write-plan
python -m vibebench release-check
python -m vibebench release-check --json
```

GitHub Actions users can download `vibebench-run-artifacts` from a workflow run's Artifacts section. The artifact contains selected run outputs for review and debugging.

No breaking changes are included in v0.2.0. Existing local commands remain compatible, and the package metadata is updated to 0.2.0 for the release.

## Release Readiness Flow

Before tagging or publishing a future v0.2.0 release, run:

```bash
python -m ruff check .
python -m pytest -q
python -m vibebench ci
python -m vibebench release-check
python -m vibebench doctor --strict
python -m vibebench manifest --check
python -m vibebench artifacts --json
python -m vibebench clean
```

Then confirm:

- working tree is clean
- CI is green on GitHub
- `vibebench-run-artifacts` is uploaded and downloadable
- release notes and changelog match the intended release scope

## Release Checklist

Before creating the v0.2.0 tag or GitHub Release in a separate milestone:

1. Run `python -m vibebench release-check`.
2. Run `python -m vibebench ci`.
3. Confirm GitHub Actions is green on `main`.
4. Confirm `vibebench-run-artifacts` is uploaded and downloadable from the workflow run.
5. Create and push the `v0.2.0` tag only in the dedicated release milestone.

## Known Limitations

- No PyPI publishing is included in this release metadata step.
- No GitHub Release is created automatically.
- VibeBench still does not post PR comments through the GitHub API.
- VibeBench is not yet a hosted dashboard or multi-agent arena platform.

## What Is Next

Potential follow-up work:

- tag v0.2.0 in the separate release milestone when maintainers are ready
- add GitHub API PR comment posting
- improve dashboard/export integrations
- continue hardening release readiness and artifact contracts
