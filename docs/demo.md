# VibeBench Arena Demo

VibeBench Arena is a Codex-first / vibe-coding quality console for local-first AI-assisted software projects. It helps turn AI-generated changes into reproducible checks, artifacts, summaries, release audits, and CI-readable outputs.

## Why Vibe Coding Needs A Quality Gate

AI coding feels fast, but the hard part is trust. A useful local quality gate should make it easy to answer:

- What changed?
- Did the configured checks pass?
- What artifacts can a reviewer inspect?
- Is the project ready for packaging or release work?
- Can the result be reproduced locally or in CI?

VibeBench does that without turning the local demo into a hosted service or secret-dependent workflow.

## What This Demo Proves

This quickstart demo shows that a fresh clone or current checkout can:

- inspect configuration
- preview the CI-quality pipeline
- run the local quality pipeline
- inspect latest run artifacts
- check release readiness
- generate a local release audit zip

The demo does not publish a package, create a tag, create a GitHub Release, or require a GitHub token.

## Commands

From the repository root:

```bash
python3 -m vibebench config --path
python3 -m vibebench config --show --json
python3 -m vibebench ci --dry-run
python3 -m vibebench ci
python3 -m vibebench latest --all-paths
python3 -m vibebench artifacts --json
python3 -m vibebench release-check
python3 -m vibebench release-audit --zip --output-dir /tmp/vibebench-release-audit-demo
```

If `/tmp/vibebench-release-audit-demo` already exists, remove it first or choose a different output directory.

## What To Expect

- `config --path` prints the expected `.vibebench/config.yaml` path.
- `config --show --json` prints machine-readable project and policy configuration.
- `ci --dry-run` prints the planned check, gate, artifact, manifest, release-check, bundle, and summary steps.
- `ci` runs the local pipeline and writes a timestamped run directory.
- `latest --all-paths` lists the newest run and artifact paths.
- `artifacts --json` prints machine-readable artifact availability.
- `release-check` prints a read-only release readiness table.
- `release-audit --zip` writes a local audit directory and `release-audit.zip`.

## Where Artifacts Are Written

Normal run artifacts are written under:

```text
.vibebench/runs/<timestamp>/
```

Common files include `metrics.json`, `report/index.html`, `pr-comment.md`, `explain.md`, `manifest.json`, `release-check.json`, `release-check.md`, and `vibebench-bundle.zip`.

The release audit demo writes to:

```text
/tmp/vibebench-release-audit-demo/
```

That folder includes package-check, publish-check, release-checklist, release-body, release-audit, checksum manifest, and zip archive outputs.

## Inspect The Latest Run

Use:

```bash
python3 -m vibebench latest --all-paths
python3 -m vibebench artifacts --json
```

These commands make the newest local outputs visible without opening a dashboard or calling an external service.

## Inspect Release Readiness

Use:

```bash
python3 -m vibebench release-check
```

This is read-only. It checks local readiness signals and does not tag, publish, upload, or create a GitHub Release.

## Generate A Release Audit Zip

Use:

```bash
python3 -m vibebench release-audit --zip --output-dir /tmp/vibebench-release-audit-demo
```

The zip is a local handoff record for release review. It can be inspected or verified later, but it does not publish anything.

## What VibeBench Intentionally Does Not Do

- It does not automatically publish packages.
- It does not automatically create GitHub Releases.
- It does not require secrets or API tokens for this local demo.
- It does not call external services for normal local checks.
- It does not replace human review.

## Keeping Codex Tasks Bounded

VibeBench works best when Codex work is shaped into small, auditable milestones:

- inspect only necessary files
- make each milestone small enough to verify
- run focused checks before full checks
- stop after repeated failures and report the exact command/error
- include changed files, checks, commit hash, push status, and final git status in the final response
