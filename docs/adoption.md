# Adopt VibeBench Arena safely

VibeBench Arena helps individuals and small teams make AI-assisted coding work reviewable. Treat it as a local-first quality console, not as an autonomous deploy bot.

## Adoption principles

- Start local.
- Inspect before trusting.
- Keep AI-generated work reviewable.
- Make every run leave evidence.
- Avoid replacing human judgment.

## First 30 minutes

1. Clone the project.
2. Skim the [Pages site entry](index.html) and [product showcase](showcase.html) for the CLI, CI proof packet, and artifact loop.
3. Run `python3 -m vibebench demo`.
4. Inspect the sample artifacts.
5. Run `python3 -m vibebench ci --dry-run --json`.
6. Generate a shareable evidence room with `python3 -m vibebench evidence-room --output-dir /tmp/vibebench-evidence-room --zip`; it combines the proof packet, static site preview, top-level HTML, Markdown, JSON, and a zip archive for external evaluation.
7. Verify the room with `python3 -m vibebench evidence-room --verify /tmp/vibebench-evidence-room/evidence-room.zip`.
8. Generate a shareable proof packet with `python3 -m vibebench proof --output-dir .vibebench/proof-packet --zip`; inspect the self-contained evidence-first `proof.html` before sharing, or use the GitHub Actions proof packet summary card and download `vibebench-proof-packet` after CI runs.
9. Run `python3 -m vibebench site-preview --output-dir /tmp/vibebench-site-preview --zip` and `python3 -m vibebench site-preview --verify /tmp/vibebench-site-preview/site-preview.zip` before publishing or editing the static Pages entry; CI reuses the same command for `vibebench-site-preview` without enabling GitHub Pages automatically.
10. Read the [comparison](comparison.md) and [FAQ](faq.md).

## First day

- Use the issue and PR templates for real workflow feedback.
- Define team review expectations for AI-generated changes.
- Decide which artifacts matter for your workflow.
- Compare one AI-generated change against a human review.

## First week

- Run VibeBench on small changes.
- Collect review packets and proof packet outputs, including the GitHub Actions `vibebench-proof-packet` artifact and summary card when available; inspect the self-contained HTML report, then verify a proof packet before sharing it.
- Compare outcomes across runs.
- Identify missing checks or unclear artifacts.
- Decide whether to integrate VibeBench into the team workflow.

## Adoption checklist

- Local commands pass.
- Artifacts are understandable.
- Reviewers know where to look.
- No credentials are committed.
- No publishing or release action is automated by default.
- The team understands this is a quality console, not an autonomous deploy bot.

## Suggested pilot

- One repo.
- One maintainer.
- One AI coding workflow.
- One week.
- Inspect artifacts before expanding.

## Non-goals and safety

- Not a replacement for CI.
- Not a replacement for code review.
- Not a fake leaderboard.
- Not an auto-publishing tool.
