# FAQ

For a quick proof path and safe rollout checklist, start with [evaluate in 5 minutes](evaluate.md) and [adoption](adoption.md).

## Is VibeBench Arena a benchmark?

No. VibeBench Arena is not a benchmark leaderboard. It is a local-first quality console for reviewing AI-assisted code changes in a real repository.

Benchmarks evaluate agents or models on task suites. VibeBench helps developers inspect their own changes with checks, artifacts, risk signals, comparison outputs, and release readiness evidence.

## Is it a chatbot or RAG app?

No. VibeBench is not a chatbot interface and not a RAG application.

It runs from the repository checkout and produces reviewable engineering artifacts. The point is to inspect what changed and what evidence exists, not to continue a conversation.

## Does it replace tests?

No. Tests and linters remain essential.

VibeBench works around them: it runs configured checks, records their results, adds diff risk signals, and packages the output into artifacts that reviewers can inspect.

## Does it guarantee AI-generated code is correct?

No. VibeBench does not guarantee that AI-generated code is correct.

It can show which checks ran, what risks were detected, which artifacts exist, and whether local release readiness checks passed. Humans still need to review the implementation, intent, edge cases, security posture, and product fit.

## Why local-first?

AI coding work often touches private source code, unreleased product ideas, and release decisions. A local-first workflow lets developers inspect evidence from the checkout without requiring a hosted account for the core flow.

Local-first also keeps evaluation simple for GitHub visitors: clone the repo, run the demo or dry-run CI plan, and inspect the artifacts.

## What does "Codex-first" mean here?

"Codex-first" means the workflow assumes an AI coding agent may be the first author of a change. VibeBench is designed for the moment after the agent edits files and before a human trusts, merges, or releases the result.

It does not depend on Codex only. The same review pattern can apply to changes produced with Cursor, Claude Code, GitHub Copilot, or a human developer.

## What does "vibe-coding quality console" mean?

It means VibeBench adds a quality and evidence layer around fast AI-assisted coding. Instead of treating "the agent said it works" as enough, VibeBench creates a console of checks, risk scoring, summaries, artifacts, comparisons, and readiness records.

The goal is to make fast changes inspectable, auditable, and reproducible.

## Who is it for?

VibeBench is for solo developers, open-source maintainers, AI coding teams, release owners, and technical evaluators who want more evidence around AI-assisted changes.

It is especially useful when a patch looks plausible but still needs disciplined review.

## What artifacts does it produce?

Representative outputs include CI plans, run summaries, risk findings, HTML reports, PR-ready Markdown, explain summaries, JSON exports, artifact inventories, manifests, badges, comparison outputs, release-check records, and release audit bundles.

See the [artifact gallery](artifact-gallery.md) for the current artifact surface.

## How should a reviewer use the output?

A reviewer should treat VibeBench output as decision support.

Use it to see what ran, what changed, which risks appeared, where the artifacts live, and what release readiness signals exist. Then review the code and decide whether to merge, request changes, or reject the patch.

## How is it useful before a pull request?

Before a pull request, VibeBench helps a developer slow down and inspect the change locally. A developer can run the demo, preview the CI plan, run the quality pipeline, check risk findings, and prepare a cleaner review packet before asking others to review.

## How is it useful for maintainers?

Maintainers can use VibeBench artifacts to ask for concrete evidence on AI-generated contributions. Instead of only reading a contributor's claim, they can inspect check results, summaries, risk findings, and reproducible commands.

## How is it useful for AI coding teams?

AI coding teams can use VibeBench as a shared review habit. It gives fast-moving teams a repeatable way to capture evidence around agent-written changes, compare runs, and keep release readiness checks visible.

## What are the current limitations?

VibeBench is early and local-first. It does not replace human review, does not prove semantic correctness, and depends on the project's configured checks and risk rules.

It is not a hosted team dashboard today. It should be evaluated by the CLI, docs, demo, artifact gallery, case study, and checked-in sample artifacts that exist in this repository.

## How can someone evaluate it quickly?

Start here:

1. Run `python3 -m vibebench demo`.
2. Run `python3 -m vibebench demo --json`.
3. Run `python3 -m vibebench ci --dry-run --json`.
4. Open the [case study](case-study.md), [comparison](comparison.md), and [artifact gallery](artifact-gallery.md).
5. Inspect the checked-in [sample artifact pack](../examples/showcase-artifacts/sample/README.md).

## What is the long-term product direction?

The long-term direction is a broader AI coding quality console: stronger policy presets, better artifact review, team workflows, hosted views for teams that want them, deeper CI/GitHub integration, and release governance.

Those are product directions, not claims of current traction. The current project focuses on local checks, evidence artifacts, honest docs, and GitHub-readable workflows.

## Related

- [Evaluate in 5 minutes](evaluate.md)
- [Adoption guide](adoption.md)
- [Comparison](comparison.md)
- [Case study](case-study.md)
- [Product strategy](product-strategy.md)
- [Commercial potential](commercial-potential.md)
