# VibeBench Arena Demo

VibeBench Arena is a Codex-first / vibe-coding quality console for local-first AI-assisted software projects. It helps turn AI-generated changes into reproducible checks, artifacts, summaries, release audits, and CI-readable outputs.

For a skim-friendly map of the concrete outputs, see the [artifact gallery](artifact-gallery.md).

For a visitor-facing proof path and safe team rollout, see [evaluate in 5 minutes](evaluate.md) and [adoption](adoption.md).

For an evidence-first walkthrough, see the [case study](case-study.md) and its checked-in [case-study artifacts](../examples/showcase-artifacts/case-study/README.md).

For scope and positioning, see the [comparison](comparison.md) and [FAQ](faq.md).

To browse the output shape without running commands, open the checked-in [sample artifact pack](../examples/showcase-artifacts/sample/README.md). To try the one-command local demo, run `python3 -m vibebench demo` or copy the pack with `python3 -m vibebench demo --copy-to /tmp/vibebench-demo`.

For the broader product thesis and practical workflows, see [positioning](positioning.md), [use cases](use-cases.md), [product strategy](product-strategy.md), [public roadmap](roadmap-public.md), and [commercial potential](commercial-potential.md).

For a visual map of the local-first flow, see the [architecture](architecture.md) doc and [VibeBench flow](assets/vibebench-flow.svg).

## Start Here

1. Run the one-command demo: `python3 -m vibebench demo`.
2. Open the [artifact gallery](artifact-gallery.md) to see the artifact surface.
3. Inspect the checked-in [sample artifacts](../examples/showcase-artifacts/sample/README.md).
4. Read [positioning](positioning.md) and [use cases](use-cases.md) for the Codex-first / vibe-coding quality console thesis.
5. Use the GitHub issue templates for demo feedback or real use cases.

## Why Vibe Coding Needs A Quality Gate

AI coding feels fast, but the hard part is trust. A useful local quality gate should make it easy to answer:

- What changed?
- Did the configured checks pass?
- What artifacts can a reviewer inspect?
- Is the project ready for packaging or release work?
- Can the result be reproduced locally or in CI?

VibeBench does that without turning the local demo into a hosted service or credential-dependent workflow.

## What This Demo Proves

This quickstart demo shows that a fresh clone or current checkout can:

- inspect configuration
- preview the CI-quality pipeline
- run the local quality pipeline
- inspect latest run artifacts
- check release readiness
- generate a local release audit zip

The demo does not publish a package, create a tag, create a GitHub Release, or require GitHub credentials.

## Commands

From the repository root:

```bash
python3 -m vibebench demo
python3 -m vibebench demo --json
python3 -m vibebench demo --copy-to /tmp/vibebench-demo
python3 -m vibebench proof
python3 -m vibebench proof --output-dir /tmp/vibebench-proof --zip
python3 -m vibebench proof --verify /tmp/vibebench-proof/proof.zip
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
- `proof` prints a concise Codex-first / vibe-coding, local-first, evidence-first proof packet summary; run `python3 -m vibebench proof --output-dir PATH` to write `proof.md`, `proof.json`, self-contained `proof.html`, and `proof-manifest.json`, and add `--zip` for `proof.zip`. GitHub Actions uploads the same packet as `vibebench-proof-packet`.
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
- It does not require credentials for this local demo.
- It does not call external services for normal local checks.
- It does not replace human review.

## Keeping Codex Tasks Bounded

VibeBench works best when Codex work is shaped into small, auditable milestones:

- inspect only necessary files
- make each milestone small enough to verify
- run focused checks before full checks
- stop after repeated failures and report the exact command/error
- include changed files, checks, commit hash, push status, and final git status in the final response
