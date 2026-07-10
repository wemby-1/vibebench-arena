# Investor Brief

VibeBench Arena is a local-first quality gate for Codex-first and AI-assisted software work. This brief is for investors, judges, technical advisors, and community evaluators who need to understand the product opportunity without invented traction or unsupported claims.

## Product Update: GitHub Adoption Kit

VibeBench now includes a reusable composite GitHub Action and generated workflow snippets for external repositories. This lowers integration friction while preserving the same local-first evidence model. This is a product capability, not evidence of customers, revenue, funding, or market traction.

The v0.4.0 candidate adds a machine-verifiable release-candidate gate, Action contract, Marketplace readiness guide, draft release notes, and release checklist. It reports `released=false`; it does not create a tag, GitHub Release, package publication, or Marketplace publication.

## Executive Summary

AI coding agents can produce software changes quickly, but review, adoption, and release decisions still need evidence. VibeBench Arena addresses that gap by turning AI-assisted repository work into inspectable local and CI artifacts: checks, risk signals, workflow readiness, adoption reports, release-readiness evidence, manifests, bundles, and trust-center material.

The current project is an open-source CLI and documentation package, not a claimed commercial product with revenue, customers, or pilots. Its value is best evaluated through the working commands, generated artifacts, test suite, and reviewer-facing demo flow.

For a no-install artifact review, browse the live GitHub Pages launch site, committed [public proof packet](../examples/showcase-artifacts/public-proof/README.md), [public demo portal](../examples/showcase-artifacts/public-demo/README.md), and the [public proof packet tour](public-proof-packet.md). The launch site presents audience paths, evidence-derived proof cards, searchable artifact filtering, copyable local commands, privacy posture, and non-claims. They are demonstration evidence, not traction, certification, revenue, funding, or a production-safety guarantee.

## The Problem

AI-generated and vibe-coded projects can look polished before they are easy to trust. A reviewer may see an impressive demo, a large diff, or a confident assistant transcript, but still lack answers to practical questions:

- What checks actually ran?
- Which files changed, and what risk signals were detected?
- Is the workflow ready for CI adoption?
- Are release-readiness assumptions explicit?
- Can the evidence be inspected after the command finishes?
- What does the project intentionally not claim?

Without a clear evidence layer, AI-assisted speed can create review debt.

## Why This Is Becoming More Important

AI-assisted development is moving from occasional autocomplete to agent-driven repository changes. That shift increases the need for tools that make generated work reviewable, reproducible, and bounded by explicit claims.

As teams adopt Codex, Cursor, Claude Code, GitHub Copilot, and similar tools, the bottleneck moves from generating code to evaluating whether the result is ready for review, adoption, or release work. VibeBench focuses on that evaluation layer.

## Target Users And Possible Buyers

Current users and buyers are hypotheses, not claimed traction:

- Individual AI-assisted builders who want a local quality gate before sharing work.
- Open-source maintainers who need clearer evidence around AI-assisted contributions.
- Engineering teams adopting agentic coding workflows.
- Developer-tooling teams that need internal review artifacts and policy signals.
- Technical due-diligence reviewers evaluating repository discipline.
- AI-native service teams that need repeatable proof packets for client handoff.

Potential buyers, if commercialized, could include engineering leaders, platform teams, developer-experience teams, security/release governance teams, and AI-native software agencies. These are hypotheses to validate.

## Initial Wedge

The initial wedge is a local-first "show me the evidence" workflow for AI-assisted repositories:

```bash
python3 -m vibebench adoption-ready --json
python3 -m vibebench ci --dry-run --json
python3 -m vibebench ci --adoption-policy --workflow-check-require-ci-mode adoption-policy --json
python3 -m vibebench bundle
python3 -m vibebench doctor --strict
python3 -m vibebench public-demo --proof-packet examples/showcase-artifacts/public-proof --output-dir /tmp/vibebench-demo
```

This gives a first-time reviewer a concrete path through readiness, workflow coverage, CI planning, artifacts, and trust boundaries.

## Product Value

VibeBench helps reviewers trace a repository from "an AI-assisted change happened" to "these checks ran, these artifacts exist, these readiness assumptions were evaluated, and these claims are not being made."

The value is practical:

- fewer vague quality claims
- more repeatable local and CI review paths
- structured JSON for automation
- Markdown and HTML for human review
- bundles and evidence rooms for handoff
- explicit separation between report-only evidence and policy-gated checks

## Differentiated Evidence Model

VibeBench is differentiated by combining several evidence surfaces in one local-first flow:

- CI dry-run planning before execution
- configured command execution and gate results
- Git diff risk signals
- workflow-check and required CI mode reporting
- preflight and adoption-ready readiness checks
- release-check and strict doctor diagnostics
- manifests, artifact inventories, bundles, trends, comparisons, and evidence rooms
- Trust Center and proof matrix docs that explain boundaries

This does not prove formal correctness. It makes the review evidence easier to inspect.

## Business-Model Hypotheses

Possible business models, all unvalidated hypotheses:

- Paid team dashboards for artifact history, policy status, and organization-level trends.
- Hosted evidence-room review for teams that want shareable proof packets with access control.
- Enterprise policy packs for AI-assisted engineering governance.
- Due-diligence and audit-support workflows for AI-native software agencies.
- Support, training, and integration services for teams adopting Codex-first workflows.

No revenue, customers, pilots, or partnerships are claimed.

## Go-To-Market Hypotheses

Possible go-to-market paths, all hypotheses:

- Open-source adoption through GitHub visitors who can run the showcase demo in minutes.
- Content-led education around AI-assisted review, adoption readiness, and proof packets.
- Developer-tooling community channels focused on Codex-first workflows.
- Team pilots that start report-only and move to policy-gated checks after trust is established.
- Technical due-diligence use cases where the repository itself demonstrates discipline.

## Defensibility Hypotheses

Potential defensibility could come from:

- a growing corpus of artifact contracts and review workflows
- local-first trust with CI-readable outputs
- opinionated Codex-first ergonomics
- accumulated policy presets and workflow-mode checks
- familiarity among maintainers and reviewers who use the same evidence vocabulary
- integrations around manifests, bundles, evidence rooms, and team review history

These are hypotheses, not established moats.

## Current Product Maturity

The project currently has:

- a working Python CLI
- CI dry-run planning and full CI orchestration
- workflow checks and required CI mode reporting
- preflight, adoption-ready, doctor, and release-check commands
- manifests, bundles, artifact inventories, trend/compare outputs, proof packets, and evidence rooms
- a Trust Center, artifact gallery, showcase demo kit, and technical docs
- a large automated test suite run as part of repository verification

It should still be evaluated as an open-source, local-first CLI project. It is not presented as a mature hosted enterprise platform.

## Key Risks And Open Questions

- Whether teams feel enough pain around AI-assisted review to adopt a dedicated evidence layer.
- Which artifacts reviewers actually use after the first demo.
- How policy presets should differ across small projects, open-source repos, and larger teams.
- Whether local-first adoption converts into hosted or team-level product demand.
- How to keep artifact output useful without overwhelming reviewers.
- How to integrate with existing CI, code review, and security review workflows without duplicating them.
- What evidence buyers require before treating VibeBench as part of a governed engineering process.

## Explicit Non-Claims

VibeBench does not claim:

- revenue, customers, pilots, partnerships, funding, or growth
- third-party audit or compliance certification
- guaranteed security, correctness, adoption, or code quality
- replacement of human review or independent security assessment
- automatic publishing, deployment, package upload, tag creation, or GitHub Release creation in the normal local flow

## Evaluation Links

- [Showcase](showcase.md)
- [Quickstart](quickstart.md)
- [Adoption guide](adoption.md)
- [Artifact gallery](artifact-gallery.md)
- [Technical due diligence](technical-due-diligence.md)
- [Proof matrix](proof-matrix.md)
- [Demo script](demo-script.md)
- [Trust Center](trust-center.md)
