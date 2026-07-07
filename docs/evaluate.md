# Evaluate VibeBench Arena in 5 minutes

VibeBench Arena is a Codex-first / vibe-coding quality console for turning AI-assisted changes into local-first, evidence-first, audit-friendly review packets.

## Who this is for

- Developers evaluating AI coding workflows.
- Teams adopting Codex, vibe-coding, or related AI-assisted programming habits.
- Maintainers who need auditable AI-generated changes.
- Investors or observers evaluating whether this is a credible engineering product.

## 5-minute path

1. Read the README positioning or open the [review hub](review-hub.html) and [Pages site entry](index.html) to understand the local-first evidence model.
2. Skim the GitHub Pages-ready [product showcase](showcase.html).
3. Run `python3 -m vibebench demo`.
4. Run `python3 -m vibebench demo --json`.
5. For a real project, run `python3 -m vibebench onboard`, `python3 -m vibebench onboard --json`, `python3 -m vibebench init --profile auto`, `python3 -m vibebench config --check`, `python3 -m vibebench ci --dry-run`, and then `python3 -m vibebench ci`. Onboard is read-only and prints the suggested adoption commands; project-scan is read-only and report-only by default; `project-scan --enforce-policy` and `ci --project-scan-policy` enforce `project_scan.policy`, while `ci --project-scan` only writes report artifacts; init writes config, can select generic, python, node, or fullstack, and does not install dependencies, overwrite config without `--force`, or create runs/baselines.
6. Run `python3 -m vibebench metrics-check` to verify the latest run metrics contract, or `python3 -m vibebench metrics-check --run-dir PATH --strict` when a specific run must have complete optional metrics. It checks `metrics.json` shape plus score/risk usability for baseline promotion and regression-check. Add `python3 -m vibebench ci --metrics-check --metrics-diff --json` when that validation should be captured as `metrics-check.json`, `metrics-check.md`, `metrics-diff.json`, and `metrics-diff.md` artifacts discoverable with `latest --artifact metrics-check-json --path-only`.
7. Run `python3 -m vibebench regression-check` to compare candidate score and risk against a baseline run. Automatic previous-run inference is convenient for experiments; for stable gates, generate a candidate with `python3 -m vibebench ci --json`, dry-run `python3 -m vibebench baseline --promote-latest --label stable --dry-run --json`, promote with `python3 -m vibebench baseline --promote-latest --label stable`, verify with `python3 -m vibebench baseline --show --label stable --json`, then use `python3 -m vibebench ci --regression-check --baseline-label stable --json` or config-enabled `ci --json`. `--set-latest` remains direct/manual; CI does not auto-promote baselines. Verify the pinned baseline with `python3 -m vibebench baseline --verify --label stable --require-portable --json`; export the stable snapshot with `python3 -m vibebench baseline --export --label stable --output baseline.json`, verify exported files with `python3 -m vibebench baseline --verify --input baseline.json`, and import it elsewhere with `python3 -m vibebench baseline --import baseline.json --label stable` when the original run directory is unavailable. This is a local regression gate, not a benchmark certification.
8. Run `python3 -m vibebench evidence-room --output-dir PATH --zip` or `python3 -m vibebench ci` to generate a combined proof packet and static site preview for external evaluation; open the package from `index.html`, inspect `share-check.md` if you want the local pre-sharing scan summary, read `trust-center.html` for project-maintained local-first/privacy/reproducibility boundaries, open `security-questionnaire.html` for adopter-facing Q&A about local-first behavior, artifact sharing, CI uploads, static HTML safety, JSON purity, and non-claims, and use `review-scorecard.html` as the neutral checklist. Evidence rooms include `share-check.json` and `share-check.md`. CI writes `evidence-room/` into the run artifacts and GitHub Actions also uploads `vibebench-evidence-room`.
9. Verify it with `python3 -m vibebench evidence-room --verify PATH`.
10. Before sharing externally, run `python3 -m vibebench share-check PATH`; use `python3 -m vibebench share-check PATH --json` for machine-readable output. It is a local pre-sharing aid, not a security certification, third-party audit, or guarantee, and artifacts still need manual review before publishing.
11. Run `python3 -m vibebench proof --output-dir .vibebench/proof-packet --zip` to inspect the proof packet directly; in GitHub Actions, CI shows a proof packet summary card and uploads the same evidence-first packet as `vibebench-proof-packet`.
12. Run `python3 -m vibebench site-preview --output-dir /tmp/vibebench-site-preview --zip`, then `python3 -m vibebench site-preview --verify /tmp/vibebench-site-preview/site-preview.zip`; CI reuses the same command and uploads `vibebench-site-preview` without enabling GitHub Pages automatically.
13. Inspect the sample [artifact gallery](artifact-gallery.md).
13. Inspect the [case study](case-study.md).

## What to look for

- Local-first operation from the repository checkout.
- Evidence artifacts that reviewers can inspect.
- Reproducible commands, not a hosted-only claim.
- GitHub-friendly summaries for maintainers and teams.
- No fake traction claims.
- No external service dependency for the core local proof.

## What counts as a good signal

- Clear command output.
- Machine-readable JSON.
- Artifacts that explain decisions and review context.
- A VibeBench Evidence Room with `index.html`, reviewer scorecard files, `share-check.json`, `share-check.md`, top-level HTML, Markdown, JSON, nested proof packet, nested static site preview, and a verifiable zip archive.
- Local CI evidence-room lookup with `python3 -m vibebench latest --artifact evidence-room-index-html --path-only`; use `python3 -m vibebench ci --skip-evidence-room` when the combined package is not needed.
- A VibeBench Proof Packet with `proof.md`, `proof.json`, a self-contained evidence-first `proof.html`, `proof-manifest.json`, and optional `proof.zip`, either from `python3 -m vibebench proof --output-dir PATH --zip` or the CI `vibebench-proof-packet` artifact and summary card.
- Verification with `python3 -m vibebench proof --verify /tmp/vibebench-proof/proof.zip`.
- Release/readiness checks that stay local unless a user chooses otherwise.
- Docs that map product direction to engineering proof.
- A reviewer-facing [review hub](review-hub.html) and [reviewer guide](reviewer-guide.md) for a 3-minute external evaluation.
- A [Trust Center](trust-center.html) and [Security Questionnaire](security-questionnaire.html) for project-maintained safety, privacy, reproducibility, local-first behavior, artifact sharing, CI uploads, static HTML safety, JSON purity, and non-claims; they are not third-party certification or audit materials.

## What this does not claim

- No promised star growth.
- No promised funding outcome.
- No promised enterprise customer wins.
- No benchmark dominance claim.
- No hidden external telemetry.

## Next steps

- Read the [adoption guide](adoption.md).
- Review the [comparison](comparison.md).
- Open issues using the repository templates.
- Try VibeBench on a small repo before expanding team use.

Metrics-check validates one run, metrics-diff explains numeric changes between two runs, metrics-diff policy enforces acceptable drift thresholds when explicitly enabled with `metrics-diff --enforce-policy` or `ci --metrics-diff-policy`, and regression-check remains the high-level score/risk gate against the selected baseline. Default CI is unchanged; `ci --metrics-diff` stays report-only. Use `latest --artifact metrics-diff-json --path-only` or `latest --artifact metrics-diff-md --path-only` to locate CI diff artifacts, including policy fields/sections when policy was evaluated.
