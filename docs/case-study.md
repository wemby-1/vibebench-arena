# Case Study: From Vibe-Coded Change to Reviewable Evidence

This case study shows a realistic local-first workflow for turning an AI-assisted code change into a review packet that humans can inspect before trusting, merging, or releasing the change.

It is a public, artifact-driven example. It is not a production customer story, not a claim of adoption, and not proof that automation can replace engineering judgment.

## Problem

AI coding agents can make useful changes quickly. A developer can ask an agent to add a feature, update a workflow, or revise documentation, and the result may look plausible in the editor.

The review problem starts after that moment:

- The change may pass a quick visual scan but still affect risky files.
- The agent's explanation may omit checks that did not run.
- The patch may be larger or broader than expected.
- Reviewers may need reproducible evidence rather than a chat transcript.
- Release owners may need local readiness signals before packaging or publishing work.

VibeBench Arena focuses on that review gap. It sits after the coding agent and before the human decision.

## Scenario

A developer asks an AI coding agent:

> Add a small feature and update the related docs.

The agent edits the repository. The code and docs look reasonable, but the team does not want to merge based only on the agent's answer.

The reviewer wants to know:

- What changed?
- Which checks ran locally?
- Did the risk score change?
- Which artifacts can be inspected?
- Is the project ready for release preparation?
- What still needs human review?

## Workflow

The workflow stays local-first:

1. The developer reviews the AI-generated diff in Git.
2. VibeBench runs configured checks and CI-style dry-run planning.
3. VibeBench scores risk from the current diff, including suspicious paths, deleted tests, lockfile movement, broad patches, and patch size.
4. VibeBench generates Markdown, JSON, HTML, manifest, comparison, and bundle artifacts.
5. VibeBench checks release readiness with local-only commands.
6. The developer shares the resulting review packet with a human reviewer.
7. The reviewer decides whether to merge, request changes, or reject the change.

The important point is not that VibeBench declares the patch correct. The important point is that it creates inspectable evidence around the patch.

## Evidence Produced

A VibeBench review packet can include:

- CI plan output showing what would run in the quality pipeline.
- Local check results showing whether configured lint and test commands passed.
- Risk scoring and findings based on the Git diff.
- Artifact inventory listing the reports, summaries, manifests, and bundles that exist.
- Comparison summary showing movement from a previous run when comparison data is available.
- Release-check output showing local readiness signals.
- GitHub-friendly Markdown that can be pasted into a review.
- Machine-readable JSON for scripts or dashboards.

The checked-in illustrative packet for this case study lives in [examples/showcase-artifacts/case-study](../examples/showcase-artifacts/case-study/README.md).

## What A Reviewer Can Decide

The reviewer can use the packet to make a bounded engineering decision:

- Merge when the diff is scoped, checks pass, risk findings are understood, and the reviewer agrees with the implementation.
- Request changes when the artifact trail shows missing checks, unclear risk, incomplete docs, or implementation concerns.
- Reject when the change is too broad, risky, poorly justified, or not aligned with the requested work.

VibeBench does not make that decision automatically. It makes the decision easier to discuss.

## Why This Is Different From A Chatbot Answer

A chatbot answer is usually a narrative. It may explain what the agent intended, but it is not the same thing as local engineering evidence.

VibeBench produces artifacts that can be inspected outside the conversation:

- commands and check results
- risk findings tied to the diff
- generated reports and summaries
- artifact manifests and inventories
- release readiness records
- repeatable local commands

That means a reviewer can evaluate the repository state, not only the agent's confidence.

## Why This Matters For AI Coding Teams

AI coding teams need speed, but they also need accountability. When agents make code changes quickly, teams need a shared way to ask what happened and what evidence supports the next step.

VibeBench helps by making the review packet concrete:

- Maintainers can inspect AI-assisted pull requests with more context.
- Solo developers can slow down before committing a plausible patch.
- Teams can compare runs and archive evidence for later review.
- Release owners can check readiness without publishing, uploading, tagging, or creating a GitHub Release.

The value is practical: make the work reviewable before it becomes trusted.

## Limitations And Honest Boundaries

This case study is intentionally modest:

- It is a static illustrative case study, not a real production customer dataset.
- It does not prove that a patch is correct.
- It does not replace code review, product review, security review, or release ownership.
- It depends on the quality of the repository's configured checks.
- It can highlight risk signals, but humans still need to interpret them.
- It does not claim adoption, revenue, category dominance, investment outcomes, or benchmark superiority.

VibeBench is useful when its artifacts help humans make better decisions. It should be judged by the checks it runs, the records it leaves, and the clarity of the workflow.

## Try It Locally

From the repository root:

```bash
python3 -m vibebench demo
python3 -m vibebench demo --json
python3 -m vibebench ci --dry-run --json
python3 -m vibebench release-check
```

Then inspect:

- [Demo guide](demo.md)
- [Artifact gallery](artifact-gallery.md)
- [Architecture](architecture.md)
- [Static case-study artifacts](../examples/showcase-artifacts/case-study/README.md)

For a copyable evidence pack, run:

```bash
python3 -m vibebench demo --copy-to /tmp/vibebench-demo
```
