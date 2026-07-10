# Demo Script

This document provides two practical demo flows for VibeBench Arena. Use the five-minute script for first-time reviewers and the fifteen-minute script for technical due diligence.

The demos show inspectable evidence. They do not claim guaranteed security, correctness, compliance, funding, or production readiness.

When a live run is not convenient, use the committed [public proof packet](../examples/showcase-artifacts/public-proof/README.md) and [artifact tour](public-proof-packet.md) as the browsable reference evidence.

## Before You Present

Run from a clean repository checkout:

```bash
git status --short --branch
python3 -m vibebench --help
```

Presenter note: tell the audience that VibeBench is local-first and evidence-first. It runs from the checkout and writes artifacts that reviewers can inspect.

## A. Five-Minute Demo

Audience: investor, judge, recruiter, first-time reviewer, or open-source visitor.

Goal: show the product shape without deep setup.

### 1. Adoption Readiness

```bash
python3 -m vibebench adoption-ready --json
```

Point out:

- `status`
- detected workflow CI modes
- required workflow CI modes
- passed/failed check counts

Narrative: "Before asking anyone to trust the repository, VibeBench reports whether the expected adoption workflow is visible."

Common failure interpretation: a failure usually means configuration or workflow readiness needs review, not that the project is hopeless.

### 2. CI Plan Without Running It

```bash
python3 -m vibebench ci --dry-run --json
```

Point out:

- ordered pipeline steps
- planned artifact generation
- no run directory because this is a dry run

Narrative: "This shows the quality pipeline before it mutates local run artifacts. It is useful for due diligence because the reviewer can see what would run."

### 3. Existing Evidence Or Fast Full Run

Preferred live command when time allows:

```bash
python3 -m vibebench ci --adoption-policy --workflow-check-require-ci-mode adoption-policy --json
```

If that is too slow for the room:

```bash
python3 -m vibebench latest --all-paths
python3 -m vibebench artifacts --json
```

Point out:

- `metrics.json`
- `manifest.json`
- `github-step-summary.md`
- adoption artifacts such as `workflow-check.json` and `preflight.json` when generated
- `release-check.json` when present

Narrative: "The important product idea is not the terminal output. It is the evidence packet left behind for a reviewer."

Fallback: open the [public proof packet index](../examples/showcase-artifacts/public-proof/proof-packet-index.md) to show the same artifact categories from a reproducible reference project.

### 4. Bundle The Evidence

```bash
python3 -m vibebench bundle
python3 -m vibebench latest --artifact bundle --path-only
```

Point out: `vibebench-bundle.zip` is a portable review packet.

Narrative: "This is how evidence moves from one machine or CI job to a reviewer."

### 5. Strict Doctor

```bash
python3 -m vibebench doctor --strict
```

Point out:

- config status
- workflow status
- latest run
- manifest, bundle, and report checks

Closing message: "VibeBench does not ask reviewers to trust vibes. It makes checks, readiness signals, artifacts, and non-claims visible."

What not to claim:

- Do not present it as a security guarantee.
- Do not present it as a correctness proof.
- Do not claim it replaces human review.
- Do not claim it proves commercial traction.

## B. Fifteen-Minute Technical Demo

Audience: engineering leader, technical investor, security reviewer, or open-source maintainer.

Goal: walk from setup assumptions to artifacts, bundles, and trust boundaries.

### 1. Setup And Config

```bash
python3 -m vibebench config --check --json
python3 -m vibebench init --profile auto --dry-run --json
```

Presenter notes:

- `config --check --json` shows whether the active config is valid.
- `init --profile auto --dry-run --json` previews config creation without writing.

Expected output: JSON describing config status and planned init behavior.

Failure interpretation: invalid config is a fixable setup issue and should be resolved before policy enforcement.

### 2. Workflow And Adoption Readiness

```bash
python3 -m vibebench workflow-check --json
python3 -m vibebench workflow-check --require-ci-mode adoption-policy --json
python3 -m vibebench preflight --json
python3 -m vibebench adoption-ready --json
```

Presenter notes:

- `workflow-check` inspects workflow files read-only.
- required mode checks make workflow assumptions explicit.
- `preflight` collects safe setup/adoption signals.
- `adoption-ready` gives the compact readiness answer.

Failure interpretation: missing required modes or preflight warnings should be discussed before moving from report-only to policy-gated CI.

### 3. CI Dry-Run

```bash
python3 -m vibebench ci --dry-run --json
```

Presenter notes:

- This is the reproducible plan.
- It explains what the full CI command would attempt.
- It does not create a run directory.

### 4. Full Evidence Generation

```bash
python3 -m vibebench ci --adoption-policy --workflow-check-require-ci-mode adoption-policy --json
```

Presenter notes:

- This can take longer because it runs configured checks and artifact generation.
- Watch for status, run directory, failed steps, and artifact paths.

Fallback if it takes too long:

```bash
python3 -m vibebench latest --all-paths
python3 -m vibebench artifacts --json
```

Explain that the fallback inspects the latest existing run rather than creating a fresh one.

### 5. Artifacts And Manifest

```bash
python3 -m vibebench latest --all-paths
python3 -m vibebench artifacts --json
python3 -m vibebench manifest --check
```

Point out:

- `metrics.json`
- `manifest.json`
- `report/index.html`
- `github-step-summary.md`
- `workflow-check.json`
- `preflight.json`
- `release-check.json`
- `compare.json`
- `trend.json`

Presenter note: the manifest is the table of contents for the evidence packet.

### 6. Bundle And Evidence Room

```bash
python3 -m vibebench bundle
python3 -m vibebench evidence-room --output-dir /tmp/vibebench-evidence-room --zip
python3 -m vibebench evidence-room --verify /tmp/vibebench-evidence-room
python3 -m vibebench share-check /tmp/vibebench-evidence-room
```

Presenter notes:

- `bundle` is the compact run packet.
- `evidence-room` is the browseable review package.
- `share-check` is a local pre-sharing aid.

Failure interpretation: verification or share-check failures mean the package needs inspection before sharing.

### 7. Strict Doctor And Release Readiness

```bash
python3 -m vibebench release-check --json
python3 -m vibebench doctor --strict
```

Presenter notes:

- `release-check` records local release-readiness evidence.
- `doctor --strict` checks environment and artifact health.
- Neither command creates tags, publishes packages, uploads files, calls GitHub, or creates a release.

### 8. Known Limitations And Trust Boundaries

Say clearly:

- Tests demonstrate expected behavior for covered cases; they do not prove absence of defects.
- Artifact generation improves inspectability; it does not establish formal correctness.
- Workflow checks inspect configured evidence; they cannot guarantee external service behavior.
- VibeBench is not a third-party audit, compliance certification, or replacement for human review.

Recommended closing: "The product is useful because it makes readiness assumptions explicit and traceable to artifacts. The next evaluation question is whether these artifacts match your review workflow."

## Supporting Links

- [Showcase](showcase.md)
- [Investor brief](investor-brief.md)
- [Technical due diligence](technical-due-diligence.md)
- [Proof matrix](proof-matrix.md)
- [Artifact gallery](artifact-gallery.md)
- [Trust Center](trust-center.md)
