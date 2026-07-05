# Case Study Showcase Artifacts

This folder is a static illustrative case study for GitHub visitors. It is not a real production customer dataset, and it does not contain private repository data.

The goal is to show how VibeBench Arena can turn an AI-assisted change into reviewable evidence that a human can inspect before trusting or merging it.

## Narrative

Request: "Use an AI coding agent to add a small feature."

Concern: "The code may pass visually but still needs review evidence."

VibeBench output: local checks, CI plan, artifact inventory, comparison summary, and release audit summary.

Reviewer decision: merge, request changes, or reject.

## Files

- [ai-change-request.md](ai-change-request.md) records the synthetic request and review concern.
- [evidence-summary.md](evidence-summary.md) summarizes the illustrative VibeBench artifacts.
- [reviewer-decision.md](reviewer-decision.md) shows the reviewer decision options.
- [review-packet.json](review-packet.json) provides a small machine-readable review packet.

For the full case study, see [docs/case-study.md](../../../docs/case-study.md). For the broader artifact tour, see [docs/artifact-gallery.md](../../../docs/artifact-gallery.md).
