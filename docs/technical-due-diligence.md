# Technical Due Diligence

This document is for technical investors, engineering leaders, security reviewers, and open-source maintainers evaluating VibeBench Arena. It describes what the system does, how evidence is produced, and where the current boundaries are.

VibeBench is not formally audited or certified. Tests demonstrate expected behavior; they do not prove absence of defects. Artifact generation improves inspectability; it does not establish formal correctness.

## System Purpose

VibeBench Arena is a local-first quality gate for AI-assisted repositories. It runs configured checks, records risk and readiness signals, generates reviewer-friendly artifacts, and supports adoption and release-readiness review.

The intended use is the layer between "an agent changed the code" and "a human or team is ready to trust, merge, share, or release it."

## High-Level Architecture

At a high level, the system has five layers:

1. Repository inputs: Git state, `.vibebench/config.yaml`, configured check commands, optional workflow files, and existing run artifacts.
2. CLI checks: `check`, `gate`, `config`, `workflow-check`, `preflight`, `adoption-ready`, `release-check`, and `doctor`.
3. CI orchestration: `ci` runs the quality pipeline, optional adoption evidence, optional policy gates, artifact generation, summaries, manifests, and bundles.
4. Evidence artifacts: JSON, Markdown, HTML reports, manifests, bundles, proof packets, evidence rooms, trend/compare output, and GitHub step summaries.
5. Human review: maintainers and evaluators inspect artifacts, decide whether policy should be report-only or enforced, and make merge/release/adoption decisions.

For diagrams, see [architecture](architecture.md) and [artifact gallery](artifact-gallery.md).

## Major CLI And Artifact Layers

- Core quality: `check`, `gate`, `ci`, `report`, `pr-comment`, `explain`.
- Readiness: `project-scan`, `onboard`, `preflight`, `workflow-check`, `adoption-ready`, `doctor`, `release-check`.
- Artifact discovery: `latest`, `artifacts`, `manifest`, `run-index`, `trend`, `compare`.
- Handoff packages: `bundle`, `proof`, `site-preview`, `evidence-room`, `share-check`.
- Release support: `package-check`, `publish-check`, `release-checklist`, `release-body`, `release-audit`.

The [proof matrix](proof-matrix.md) maps major claims to commands and artifacts.

## Read-Only Checks Versus Policy-Enforced Checks

VibeBench separates reporting from enforcement.

Read-only or report-only commands include:

```bash
python3 -m vibebench preflight --json
python3 -m vibebench workflow-check --json
python3 -m vibebench adoption-ready --json
python3 -m vibebench release-check --json
python3 -m vibebench doctor --strict
python3 -m vibebench ci --adoption
```

Policy-enforced paths include:

```bash
python3 -m vibebench preflight --enforce-policy
python3 -m vibebench workflow-check --enforce-policy
python3 -m vibebench ci --preflight-policy
python3 -m vibebench ci --workflow-check-policy
python3 -m vibebench ci --adoption-policy
```

This allows evaluators to collect evidence before deciding whether a signal should fail CI.

## CI Integration Model

`python3 -m vibebench ci` is the main orchestration command. It can run checks, gate evaluation, config/package checks, reports, PR comments, explanations, exports, badges, status blocks, trend/run-index/compare outputs, evidence-room generation, manifest checks, release-check artifacts, annotations, bundles, and GitHub summaries.

Useful CI planning command:

```bash
python3 -m vibebench ci --dry-run --json
```

Workflow readiness is checked with:

```bash
python3 -m vibebench workflow-check --json
python3 -m vibebench workflow-check --require-ci-mode adoption-policy --json
```

Workflow checks analyze repository workflow files and configured evidence. They cannot guarantee the behavior of external services, future workflow edits, or secrets managed outside the repository.

## Evidence And Artifact Lifecycle

A normal run writes local artifacts under:

```text
.vibebench/runs/<timestamp>/
```

Common artifacts include `metrics.json`, `check.log`, `report/index.html`, `pr-comment.md`, `explain.md`, `manifest.json`, `github-step-summary.md`, `release-check.json`, `release-check.md`, `compare.json`, `compare.md`, and `vibebench-bundle.zip`. `public-demo` can convert a run or curated proof packet into a deterministic standalone portal with `index.html`, `demo.json`, `README.md`, and only allowlisted copied artifacts.

Generated run artifacts are local outputs. They should not be committed unless a specific sample artifact is intentionally curated.

The intentionally curated exceptions are the [public proof packet](../examples/showcase-artifacts/public-proof/README.md) and [public demo portal](../examples/showcase-artifacts/public-demo/README.md), regenerated from the deterministic [reference project](../examples/reference-project/). The [artifact tour](public-proof-packet.md) explains provenance, normalization, and `--check` freshness verification.

## Reproducibility Model

Reproducibility comes from:

- local execution from the repository checkout
- explicit `.vibebench/config.yaml`
- JSON output modes for automation
- CI dry-run plans before execution
- manifests that inventory outputs
- bundle and evidence-room packages for handoff
- public-demo portals for no-server evidence review
- strict doctor and release-check commands for environment/artifact readiness

This model supports repeatable review. It does not make the underlying project deterministic if configured commands, dependencies, or external services are nondeterministic.

## Manifest And Bundle Model

`manifest` writes or checks a machine-readable index for a run:

```bash
python3 -m vibebench manifest
python3 -m vibebench manifest --check
```

`bundle` packages standard run artifacts:

```bash
python3 -m vibebench bundle
python3 -m vibebench bundle --strict
```

The manifest helps evaluators see what exists. The bundle helps reviewers move the evidence packet across machines or CI artifact systems.

## Testing Strategy

The repository test suite exercises CLI behavior, artifact generation, JSON output, readiness checks, share/evidence-room behavior, release readiness, and many command contracts.

Current verification for this milestone includes:

```bash
python3 -m ruff check .
python3 -m pytest -q
python3 -m vibebench adoption-ready --json
python3 -m vibebench workflow-check --json
python3 -m vibebench ci --dry-run --json
python3 -m vibebench release-check --json
python3 -m vibebench doctor --strict
```

Passing tests demonstrate expected behavior for covered cases. They do not prove that defects, security issues, or integration failures are absent.

## Configuration And Policy Model

VibeBench reads `.vibebench/config.yaml` when present and falls back to defaults when appropriate. Configuration can define project metadata, checks, gate thresholds, risk rules, workflow-check policy, preflight policy, onboarding policy, project-scan policy, metrics policy, regression policy, and compare behavior.

Useful commands:

```bash
python3 -m vibebench config --check
python3 -m vibebench config --check --json
python3 -m vibebench init --profile auto --dry-run --json
```

Policy settings should be reviewed before enforcing them in CI.

## Trust Boundaries

VibeBench is local-first and artifact-first. The normal local workflow does not require a hosted service, GitHub API access, package publishing, tag creation, or GitHub Release creation.

Trust boundaries are documented in the [Trust Center](trust-center.md). Shareable outputs should be checked with:

```bash
python3 -m vibebench share-check PATH
python3 -m vibebench share-check PATH --json
```

`share-check` is a local pre-sharing aid, not a security certification.

## Security And Privacy Considerations

- Generated artifacts may contain repository-specific paths, command output, or file names.
- Reviewers should inspect bundles, proof packets, evidence rooms, and zips before external sharing.
- Static HTML artifacts are intended to be inspectable local files.
- Workflow checks can flag risky workflow shapes, but they do not validate external account settings or third-party service behavior.
- VibeBench does not replace secret scanning, SAST, dependency scanning, threat modeling, or independent security review.

## Known Limitations

- The tool is only as meaningful as the configured checks and policies.
- Local run artifacts can become stale if the repository changes after generation.
- Workflow checks inspect files and known patterns; they cannot guarantee CI provider behavior.
- Release-readiness checks are local evidence, not a release approval.
- JSON artifacts are useful for automation, but downstream consumers still need schema and failure handling.
- Evidence rooms and bundles improve handoff, but reviewers must still inspect them.

## Failure Modes

- Config is missing, invalid, or not aligned with the project.
- Configured commands are unavailable or fail.
- Workflow mode expectations do not match the repository workflow.
- Adoption policy fails because required setup evidence is missing.
- Manifest checks fail because artifacts were removed or changed.
- Bundle strict mode fails because expected artifacts are missing.
- Share-check flags unsafe markers before external sharing.
- Strict doctor fails because no recent valid run or required artifact exists.

Failures should be treated as review signals. They do not necessarily mean the project is unusable.

## Operational Risks

- Teams may over-trust a score without reading underlying artifacts.
- Generated outputs may be shared before manual review.
- Policy gates may be enabled before the team agrees on thresholds.
- Long-running configured tests can slow demos or CI.
- Artifact volume can overwhelm reviewers if the review path is not curated.
- Future integrations could introduce hosted-service trust assumptions that do not exist in the local CLI.

## Areas Requiring Future Validation

- Which artifact views are most useful to maintainers and evaluators.
- Which policy presets work across project sizes and languages.
- How teams want to compare runs over time.
- Whether hosted artifact review is valuable enough to justify a service.
- How VibeBench fits beside existing security, compliance, release, and observability tools.
- Which adoption signals predict sustained use.

## Suggested Evaluator Checklist

- Run `python3 -m vibebench ci --dry-run --json` and inspect planned steps.
- Run `python3 -m vibebench adoption-ready --json` and confirm required workflow modes.
- Run `python3 -m vibebench workflow-check --json` and inspect workflow findings.
- Run or inspect a recent `python3 -m vibebench ci` run.
- Open `metrics.json`, `manifest.json`, `github-step-summary.md`, and `report/index.html`.
- Run `python3 -m vibebench bundle` and confirm `vibebench-bundle.zip` exists.
- Run `python3 -m vibebench release-check --json`.
- Run `python3 -m vibebench doctor --strict`.
- Read the [proof matrix](proof-matrix.md), [artifact gallery](artifact-gallery.md), and [Trust Center](trust-center.md).
- Confirm the project makes no unsupported claims about security, correctness, compliance, customers, or revenue.

## Supporting Documents

- [Showcase](showcase.md)
- [Investor brief](investor-brief.md)
- [Proof matrix](proof-matrix.md)
- [Demo script](demo-script.md)
- [Quickstart](quickstart.md)
- [Adoption guide](adoption.md)
- [Artifact gallery](artifact-gallery.md)
- [Trust Center](trust-center.md)
