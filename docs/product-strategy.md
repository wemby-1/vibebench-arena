# VibeBench Arena Product Strategy

## Problem

AI coding is becoming easier, but engineering trust is becoming harder. Developers can ask Codex, Cursor, and other AI agents to produce useful changes quickly, yet teams still need evidence before they merge, ship, or release those changes.

Generated code needs more than a chat transcript. It needs local checks, diff review, risk review, artifact-backed summaries, release readiness, and reproducible audit trails that humans can inspect.

For a concrete artifact-driven walkthrough, see the [case study](case-study.md).

## Product Thesis

VibeBench Arena is a Codex-first / vibe-coding quality console. It turns AI coding from a black-box chat process into a local, inspectable, auditable engineering workflow.

The product thesis is simple: AI agents can accelerate code creation, but engineering teams still need a quality console that records what changed, what ran, what risks appeared, and which artifacts support the next decision.

## Visual Architecture

For the product architecture and diagrams, see [architecture](architecture.md), [VibeBench flow](assets/vibebench-flow.svg), and the [artifact evidence stack](assets/artifact-evidence-stack.svg).

## What It Is

VibeBench Arena is currently:

- a local-first CLI for AI-assisted software projects
- quality checks and CI-style dry-run planning
- Git diff and risk review for generated changes
- run artifacts, reports, summaries, manifests, comparisons, and bundles
- release and publish readiness checks that stay local
- demo and showcase artifacts that make the evidence surface inspectable from GitHub

## What It Is Not

VibeBench Arena is not:

- a chatbot
- a hosted benchmark leaderboard
- a prompt collection
- a generic CI replacement
- a fake coding-agent evaluation platform
- a substitute for human review

It complements existing agents, test suites, and CI systems by making AI-assisted engineering evidence easier to inspect.

## Why Now

Developers are increasingly using Codex, Cursor, and other AI agents as normal parts of software creation. The bottleneck is moving from "the agent produced a patch" to "a person or team can trust the patch enough to review, merge, or release it."

That creates demand for tools that are local-first, GitHub-native, reproducible, and honest about what they prove. VibeBench focuses on the trust layer around AI coding rather than on replacing the coding agent itself.

## Moat And Differentiation

VibeBench can become differentiated through:

- Local-first execution: core workflows run from the checkout without a hosted account.
- Artifact-driven review: every run can leave Markdown, JSON, reports, manifests, bundles, and release audit records.
- GitHub-native output: summaries, annotations, badges, and PR-ready Markdown fit existing review habits.
- Codex-first ergonomics: the project is designed around agent-written changes and human verification.
- Audit-friendly workflows: release and publish readiness checks create local records without hidden publish side effects.
- Demoable evidence: the one-command demo and artifact gallery let visitors inspect the product shape quickly.
- Reproducibility: commands and artifacts can be rerun locally or in CI.

## User Personas

- Solo AI coding builders who want a quick local quality gate before commit.
- Open-source maintainers reviewing AI-generated pull requests.
- Engineering teams adopting AI coding who need repeatable review evidence.
- Researchers studying AI-assisted development workflows and the artifacts those workflows produce.

## Honest Limitations

VibeBench Arena is early-stage. It is not a SaaS product yet, and it should be evaluated by its current local CLI, docs, demos, and artifacts.

The project does not claim fake adoption, fake revenue, fake customers, fake investors, or promised outcomes. It does not replace human review. It is a practical foundation for making Codex-first / vibe-coding engineering more inspectable, auditable, and reproducible.

## How To Evaluate It

Start with:

1. Run `python3 -m vibebench demo`.
2. Open the [artifact gallery](artifact-gallery.md).
3. Inspect the [sample artifact pack](../examples/showcase-artifacts/sample/README.md).
4. Read the [public roadmap](roadmap-public.md) and [commercial potential](commercial-potential.md).
5. Share real workflow feedback through the GitHub issue templates.
