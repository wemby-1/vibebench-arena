# VibeBench Arena Showcase

VibeBench Arena is a Codex-first quality gate for AI-assisted projects. This showcase is for reviewers, maintainers, community adopters, and technical due-diligence readers who want to understand the product quickly without confusing a CLI transcript for the whole story.

## GitHub Adoption Path

The launch site includes an "Integrate VibeBench" configurator that renders a deterministic GitHub Actions snippet for the reusable composite action. It supports `minimal`, `strict`, and `proof` presets, optional artifact upload, optional config path, and required CI adoption mode. The snippet is visible without JavaScript and is labeled as `@main` preview/development guidance.

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

The live public launch site is published at
[`https://wemby-1.github.io/vibebench-arena/`](https://wemby-1.github.io/vibebench-arena/).
It is built from the committed public demo and public proof packet, so visitors
can inspect the current evidence without cloning the repository. It presents a
30-second product frame, audience-specific routes, evidence-derived proof cards,
a searchable/filterable artifact explorer, copyable local commands, trust
boundaries, and diligence links. It is a static presentation of reproducible
reference evidence, not an independent hosted scanner.

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

For the copy-paste demo script and artifact interpretation, see the [showcase artifacts README](../examples/showcase-artifacts/README.md). For browsable committed evidence generated from a deterministic fixture, inspect the [public proof packet](../examples/showcase-artifacts/public-proof/README.md), the [public demo portal](../examples/showcase-artifacts/public-demo/README.md), and [artifact tour](public-proof-packet.md).

To regenerate the portal:

```bash
python3 -m vibebench public-demo \
  --proof-packet examples/showcase-artifacts/public-proof \
  --output-dir /tmp/vibebench-demo
```

To reproduce the Pages site locally:

```bash
python3 scripts/build_public_demo.py --check
python3 scripts/build_pages_site.py --output-dir /tmp/vibebench-pages-site
python3 scripts/build_pages_site.py --check
```

The Pages build remains deterministic and local-asset-only: no analytics,
cookies, trackers, remote fonts, CDNs, or remote runtime dependencies.

For deeper evaluation, use the [investor brief](investor-brief.md), [technical due diligence](technical-due-diligence.md), [proof matrix](proof-matrix.md), and [demo script](demo-script.md).

## What This Does Not Claim

VibeBench does not guarantee security, correctness, funding, adoption, or code quality. It does not replace human review. It does not publish packages, create tags, create releases, or call the GitHub API in the normal local demo path.

It makes the evidence around AI-assisted work easier to inspect.

## Next Links

- [Showcase demo kit](../examples/showcase-artifacts/README.md)
- [Public proof packet](../examples/showcase-artifacts/public-proof/README.md)
- [Public demo portal](../examples/showcase-artifacts/public-demo/README.md)
- [Public proof packet tour](public-proof-packet.md)
- [Investor brief](investor-brief.md)
- [Technical due diligence](technical-due-diligence.md)
- [Proof matrix](proof-matrix.md)
- [Demo script](demo-script.md)
- [Quickstart](quickstart.md)
- [Adoption guide](adoption.md)
- [Artifact gallery](artifact-gallery.md)
- [Trust Center](trust-center.md)
