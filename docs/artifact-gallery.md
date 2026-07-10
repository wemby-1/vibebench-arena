# VibeBench Artifact Gallery

VibeBench turns AI-assisted code changes into an evidence packet that a maintainer, teammate, or outside reviewer can inspect. This page explains the main artifact names in plain language.

## Why Artifacts Matter

AI coding is fast, but review still needs evidence. A single `passed` or `failed` result is not enough when humans need to understand what changed, what ran, what can be reproduced, and what is safe to share or release.

VibeBench artifacts make the workflow inspectable before commit, in GitHub Actions, during adoption review, and during release preparation.

## Start With These Files

| Artifact | What it is | Why it matters |
| --- | --- | --- |
| `metrics.json` | Score, risk level, command results, diff size, and finding counts. | Shows the basic run outcome in machine-readable form. |
| `check.log` | Raw command output from configured checks. | Helps reviewers understand failures without rerunning immediately. |
| `report/index.html` | Static local HTML report. | Gives a browseable summary suitable for local review and screenshots. |
| `pr-comment.md` | Pasteable review summary. | Turns a run into a concise PR or issue update. |
| `explain.md` | Human-readable explanation of failures, risk findings, and next steps. | Helps reviewers decide what to inspect next. |
| `manifest.json` | Inventory of generated artifacts and run metadata. | Tells automation and humans what exists and where to find it. |
| `github-step-summary.md` | GitHub Actions-friendly run summary. | Gives CI reviewers a compact status view. |
| `vibebench-bundle.zip` | Portable archive of standard run artifacts. | Makes the evidence packet easy to hand off or download from CI. |

## Bundle And Proof Packet

`vibebench bundle` packages the latest run into `vibebench-bundle.zip`. It is the simplest handoff artifact for a specific local or CI run.

`vibebench proof --output-dir PATH --zip` creates a focused proof packet with files such as `proof.html`, `proof.json`, `proof.md`, `proof-manifest.json`, and `proof.zip`. The proof packet is designed for evidence-first review, not for marketing claims.

`vibebench evidence-room --output-dir PATH --zip` creates the broader review package. It can combine proof files, site preview files, trust notes, a security questionnaire, reviewer scorecards, `share-check.json`, `share-check.md`, top-level HTML, Markdown, JSON, and a zip archive. Start with `index.html`.

For committed browseable examples generated from real commands, start with the [public proof packet](../examples/showcase-artifacts/public-proof/README.md) and the [public proof packet tour](public-proof-packet.md).

## Run Index, Trend, And Compare

VibeBench also produces artifacts that explain movement across runs:

| Artifact | Purpose |
| --- | --- |
| `run-index.json` / `run-index.md` | Summarizes recent valid run directories and marks partial or corrupt older run folders instead of crashing. |
| `trend.json` / `trend.md` | Shows recent score/risk movement across valid runs. |
| `compare.json` / `compare.md` | Compares a candidate run with a previous or selected run. |
| `metrics-check.json` / `metrics-check.md` | Validates that one run has usable score/risk data when the check is enabled. |
| `metrics-diff.json` / `metrics-diff.md` | Explains numeric metric movement between baseline and candidate when enabled. |

`compare` and metrics-diff reporting do not imply benchmark certification. Policy enforcement is opt-in through explicit flags or config.

## Adoption And Workflow Artifacts

Adoption-oriented runs can add:

| Artifact | Purpose |
| --- | --- |
| `project-scan.json` / `project-scan.md` | Read-only project readiness signals, stack detection, config status, and init profile recommendation. |
| `onboard.json` / `onboard.md` | Human adoption plan with blockers, warnings, and next steps. |
| `workflow-template.json` / `workflow-template.md` / `workflow-template.yml` | Preview of a generated workflow; it is an artifact unless `workflow-template --write` is explicitly used. |
| `workflow-check.json` / `workflow-check.md` | Read-only validation of existing workflow shape and detected CI modes. |
| `preflight.json` / `preflight.md` | Setup and adoption summary that can remain report-only or become policy-gated. |
| `adoption-ready` JSON/Markdown output | Compact readiness answer for adoption review, usually printed or written only when output paths are requested. |

These artifacts are most useful during the first week of rollout, when a team is deciding whether to stay report-only or enforce adoption policy.

## Release And Sharing Artifacts

| Artifact | Purpose |
| --- | --- |
| `release-check.json` / `release-check.md` | Local release-readiness evidence. Does not tag, publish, upload, or create a GitHub Release. |
| `release-checklist` output | Read-only checklist for target-version review. |
| `release-audit` bundle | Local audit bundle for package, publish, checklist, release-body, summary, and manifest records when explicitly generated. |
| `share-check.json` / `share-check.md` | Local pre-sharing scan summary for evidence rooms, proof packets, static previews, bundles, directories, or zips. |
| `site-preview` output | Local static preview bundle for docs/site review. It does not enable GitHub Pages automatically. |

`share-check` is a pre-sharing aid, not a security certification, third-party audit, or guarantee. Review artifacts manually before publishing them.

## Fastest Commands

```bash
python3 -m vibebench ci
python3 -m vibebench latest --all-paths
python3 -m vibebench bundle
python3 -m vibebench adoption-ready --json
python3 -m vibebench release-check --json
python3 -m vibebench evidence-room --output-dir /tmp/vibebench-evidence-room --zip
```

## Evidence Packet Story

The artifact model is meant to answer practical questions:

- What changed and how risky did it look?
- What checks actually ran?
- What evidence was generated?
- Is the repository ready for broader adoption?
- Is the workflow using the expected VibeBench CI mode?
- Is release readiness documented in a reproducible way?
- What should a human reviewer inspect next?

That is why VibeBench produces inventories, summaries, readiness files, comparison files, and portable bundles instead of only a pass/fail line.

## For Browseable Examples

- [Demo guide](demo.md)
- [Quickstart](quickstart.md)
- [Showcase artifacts](../examples/showcase-artifacts/README.md)
- [Public proof packet](../examples/showcase-artifacts/public-proof/README.md)
- [Public proof packet tour](public-proof-packet.md)
- [Sample artifact pack](../examples/showcase-artifacts/sample/README.md)
- [Case-study artifacts](../examples/showcase-artifacts/case-study/README.md)
- [Trust Center](trust-center.md)
