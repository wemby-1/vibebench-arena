# VibeBench Arena Showcase

VibeBench Arena is a Codex-first quality gate for AI-assisted projects. This showcase is for reviewers, maintainers, community adopters, and technical due-diligence readers who want to understand the product quickly without confusing a CLI transcript for the whole story.

## The Problem

Vibe-coded and AI-generated projects can look impressive in a demo. They may have polished UI, a large diff, or a confident assistant transcript. What they often lack is verifiable quality evidence:

- What checks actually ran?
- What changed, and how risky was the diff?
- Is there a reproducible CI plan?
- Is the project ready for an adoption workflow?
- What artifacts can a reviewer inspect later?
- What is not being claimed?

That gap matters because AI-assisted speed can make review harder. A project can appear active and polished while still leaving maintainers, users, teams, or investors without enough evidence to judge readiness.

## The Solution

VibeBench Arena turns AI-assisted work into evidence-first CI, adoption, and readiness outputs. It sits after the coding agent changes the repository and before humans decide whether to trust, merge, share, or release the work.

It does not replace tests, CI, or human review. It packages the signals around them: checks, score/risk data, workflow readiness, adoption evidence, release-readiness notes, manifests, summaries, bundles, and trust boundaries.

## What A Reviewer Sees

After a normal demo path, a reviewer can inspect:

- `adoption-ready --json`: a compact read-only readiness answer for the expected adoption workflow.
- `ci --dry-run --json`: the reproducible CI plan before checks are executed.
- `ci --adoption-policy --workflow-check-require-ci-mode adoption-policy --json`: a policy-gated adoption run that records check results and readiness artifacts.
- `metrics.json`: score, risk level, command results, diff size, and finding counts.
- `manifest.json`: what artifacts were generated and where they live.
- `github-step-summary.md`: a CI-friendly summary of the run.
- `vibebench-bundle.zip`: a portable evidence packet for handoff.
- `doctor --strict`: environment and artifact health checks for stricter review.
- Trust Center and artifact-gallery docs that explain boundaries and non-claims.

The point is not to claim perfection. The point is to make quality evidence easier to inspect.

## Why It Matters

For maintainers, VibeBench provides a repeatable way to ask what happened during an AI-assisted change and where the review evidence lives.

For open-source users, it gives a visible path from "this repository looks active" to "these are the checks, artifacts, and boundaries I can inspect."

For engineering teams, it supports adoption workflows that start report-only and can later become policy-gated when the team agrees on expectations.

For investors and technical due diligence, it creates a practical evidence packet: what was checked, what passed, what artifacts exist, and what the project intentionally does not claim.

## Five-Minute Demo Path

Run from the repository root:

```bash
python3 -m vibebench adoption-ready --json
python3 -m vibebench ci --dry-run --json
python3 -m vibebench ci --adoption-policy --workflow-check-require-ci-mode adoption-policy --json
python3 -m vibebench bundle
python3 -m vibebench doctor --strict
```

What this shows:

- Readiness: `adoption-ready --json` reports whether the repo matches the expected adoption workflow.
- Reproducible CI plan: `ci --dry-run --json` shows the ordered pipeline without writing run artifacts.
- Workflow coverage: the adoption-policy CI command requires the expected `adoption-policy` workflow mode and records policy-gated evidence.
- Evidence packet: `bundle` packages the latest run for review or handoff.
- Trust boundary: `doctor --strict` checks local environment and artifact health without publishing, tagging, uploading, or calling GitHub.

For the copy-paste demo script and artifact interpretation, see the [showcase artifacts README](../examples/showcase-artifacts/README.md).

For deeper evaluation, use the [investor brief](investor-brief.md), [technical due diligence](technical-due-diligence.md), [proof matrix](proof-matrix.md), and [demo script](demo-script.md).

## What This Does Not Claim

VibeBench does not guarantee security, correctness, funding, adoption, or code quality. It does not replace human review. It does not publish packages, create tags, create releases, or call the GitHub API in the normal local demo path.

It makes the evidence around AI-assisted work easier to inspect.

## Next Links

- [Showcase demo kit](../examples/showcase-artifacts/README.md)
- [Investor brief](investor-brief.md)
- [Technical due diligence](technical-due-diligence.md)
- [Proof matrix](proof-matrix.md)
- [Demo script](demo-script.md)
- [Quickstart](quickstart.md)
- [Adoption guide](adoption.md)
- [Artifact gallery](artifact-gallery.md)
- [Trust Center](trust-center.md)
