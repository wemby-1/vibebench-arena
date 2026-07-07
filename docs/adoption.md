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
2. Skim the [review hub](review-hub.html), [Pages site entry](index.html), and [product showcase](showcase.html) for the CLI, CI proof packet, and artifact loop.
3. Run `python3 -m vibebench demo`.
4. Inspect the sample artifacts.
5. For a real project, run `python3 -m vibebench onboard`, `python3 -m vibebench onboard --json`, `python3 -m vibebench init --profile auto`, `python3 -m vibebench config --check`, `python3 -m vibebench workflow-template`, `python3 -m vibebench workflow-template --ci-mode adoption --write`, `python3 -m vibebench ci --dry-run`, and then `python3 -m vibebench ci`. Project-scan describes readiness signals; `project-scan --enforce-policy` and `ci --project-scan-policy` gate those signals with `project_scan.policy`. Onboard produces a human adoption plan; `onboard --enforce-policy` and `ci --onboard-policy` gate whether that plan is acceptable with `onboard.policy`, reusing `onboard.json` and `onboard.md`. The default scan, onboard, `ci --project-scan`, and `ci --onboard` paths remain report-only. Init writes config, can select generic, python, node, or fullstack, and does not install dependencies, overwrite config without `--force`, or create runs/baselines. `workflow-template` is preview-only unless `--write` is passed and refuses to overwrite existing workflow files without `--force`.
6. Run `python3 -m vibebench metrics-check` to verify that the latest `metrics.json` has usable score/risk data before promotion or regression comparison. Use `--run-dir PATH` for a specific run and `--strict` when optional-field warnings should fail. Use `python3 -m vibebench ci --metrics-check --metrics-diff --json` to make the same check auditable as `metrics-check.json`, `metrics-check.md`, `metrics-diff.json`, and `metrics-diff.md` artifacts.
7. Run `python3 -m vibebench regression-check` before sharing or releasing once two runs exist. Automatic baseline inference is fine for local experiments; stable adoption gates should generate a candidate with `python3 -m vibebench ci --json`, dry-run `python3 -m vibebench baseline --promote-latest --label stable --dry-run --json`, promote with `python3 -m vibebench baseline --promote-latest --label stable`, and verify with `python3 -m vibebench baseline --show --label stable --json`. Use `--require-baseline`, `--require-regression-baseline`, or config `require_baseline: true` when missing baseline data should fail. CI does not auto-promote baselines. Verify/export/import the promoted snapshot with `python3 -m vibebench baseline --verify --label stable`, `python3 -m vibebench baseline --export --label stable --output baseline.json`, `python3 -m vibebench baseline --verify --input baseline.json`, and `python3 -m vibebench baseline --import baseline.json --label stable` for new machines or cleaned workspaces; add `--require-portable` for portable gates or `--require-live-metrics` when the original run must still exist. This is a local regression gate, not a benchmark certification.
8. Generate a shareable evidence room with `python3 -m vibebench evidence-room --output-dir PATH --zip` or a normal `python3 -m vibebench ci`; open it from `index.html`, inspect `share-check.md` if you want the local pre-sharing scan summary, read `trust-center.html` for project-maintained local-first/privacy/reproducibility boundaries, open `security-questionnaire.html` for adopter-facing Q&A about local-first behavior, artifact sharing, CI uploads, static HTML safety, JSON purity, and non-claims, and use `review-scorecard.html` as the neutral checklist. It combines the proof packet, static site preview, `share-check.json`, `share-check.md`, top-level HTML, Markdown, JSON, and a zip archive for external evaluation. Local CI writes `evidence-room/`, and GitHub Actions uploads `vibebench-evidence-room`.
9. Verify the room with `python3 -m vibebench evidence-room --verify PATH`.
10. Before sharing externally, run `python3 -m vibebench share-check PATH`; use `python3 -m vibebench share-check PATH --json` for automation. It is a local pre-sharing aid, not a security certification, third-party audit, or guarantee, and teams should still manually review artifacts before publishing.
11. Generate a shareable proof packet with `python3 -m vibebench proof --output-dir .vibebench/proof-packet --zip`; inspect the self-contained evidence-first `proof.html` before sharing, or use the GitHub Actions proof packet summary card and download `vibebench-proof-packet` after CI runs.
12. Run `python3 -m vibebench site-preview --output-dir /tmp/vibebench-site-preview --zip` and `python3 -m vibebench site-preview --verify /tmp/vibebench-site-preview/site-preview.zip` before publishing or editing the static Pages entry; CI reuses the same command for `vibebench-site-preview` without enabling GitHub Pages automatically.
12. Read the [comparison](comparison.md) and [FAQ](faq.md).

## First day

- Use the issue and PR templates for real workflow feedback.
- Define team review expectations for AI-generated changes.
- Decide which artifacts matter for your workflow.
- Compare one AI-generated change against a human review.

## First week

- Run VibeBench on small changes.
- Locate the newest local CI evidence-room landing page with `python3 -m vibebench latest --artifact evidence-room-index-html --path-only`; use `python3 -m vibebench ci --skip-evidence-room` only when you do not need the combined review package.
- Collect review packets and proof packet outputs, including the GitHub Actions `vibebench-proof-packet` artifact and summary card when available; inspect the self-contained HTML report, then verify a proof packet before sharing it.
- Share the [reviewer guide](reviewer-guide.md) with maintainers or evaluators who need the 3-minute artifact path.
- Open the [Trust Center](trust-center.html) and [Security Questionnaire](security-questionnaire.html) when reviewers need project-maintained safety, privacy, reproducibility, local-first behavior, artifact sharing, CI upload, static HTML safety, JSON purity, and non-claim boundaries; they are not third-party certification or audit materials.
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

Metrics-check validates one run, metrics-diff explains numeric changes between two runs, metrics-diff policy enforces acceptable drift thresholds when explicitly enabled with `metrics-diff --enforce-policy` or `ci --metrics-diff-policy`, and regression-check remains the high-level score/risk gate against the selected baseline. Default CI is unchanged; `ci --metrics-diff` stays report-only. Use `latest --artifact metrics-diff-json --path-only` or `latest --artifact metrics-diff-md --path-only` to locate CI diff artifacts, including policy fields/sections when policy was evaluated.
