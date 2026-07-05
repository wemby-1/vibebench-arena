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
2. Run `python3 -m vibebench demo`.
3. Inspect the sample artifacts.
4. Run `python3 -m vibebench ci --dry-run --json`.
5. Read the [comparison](comparison.md) and [FAQ](faq.md).

## First day

- Use the issue and PR templates for real workflow feedback.
- Define team review expectations for AI-generated changes.
- Decide which artifacts matter for your workflow.
- Compare one AI-generated change against a human review.

## First week

- Run VibeBench on small changes.
- Collect review packets.
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
