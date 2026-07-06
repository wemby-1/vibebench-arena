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
5. Run `python3 -m vibebench ci --dry-run --json`.
6. Run `python3 -m vibebench evidence-room --output-dir PATH --zip` or `python3 -m vibebench ci` to generate a combined proof packet and static site preview for external evaluation; open the package from `index.html` and use `review-scorecard.html` as the neutral checklist. CI writes `evidence-room/` into the run artifacts and GitHub Actions also uploads `vibebench-evidence-room`.
7. Verify it with `python3 -m vibebench evidence-room --verify PATH`.
8. Run `python3 -m vibebench proof --output-dir .vibebench/proof-packet --zip` to inspect the proof packet directly; in GitHub Actions, CI shows a proof packet summary card and uploads the same evidence-first packet as `vibebench-proof-packet`.
9. Run `python3 -m vibebench site-preview --output-dir /tmp/vibebench-site-preview --zip`, then `python3 -m vibebench site-preview --verify /tmp/vibebench-site-preview/site-preview.zip`; CI reuses the same command and uploads `vibebench-site-preview` without enabling GitHub Pages automatically.
10. Inspect the sample [artifact gallery](artifact-gallery.md).
11. Inspect the [case study](case-study.md).

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
- A VibeBench Evidence Room with `index.html`, reviewer scorecard files, top-level HTML, Markdown, JSON, nested proof packet, nested static site preview, and a verifiable zip archive.
- Local CI evidence-room lookup with `python3 -m vibebench latest --artifact evidence-room-index-html --path-only`; use `python3 -m vibebench ci --skip-evidence-room` when the combined package is not needed.
- A VibeBench Proof Packet with `proof.md`, `proof.json`, a self-contained evidence-first `proof.html`, `proof-manifest.json`, and optional `proof.zip`, either from `python3 -m vibebench proof --output-dir PATH --zip` or the CI `vibebench-proof-packet` artifact and summary card.
- Verification with `python3 -m vibebench proof --verify /tmp/vibebench-proof/proof.zip`.
- Release/readiness checks that stay local unless a user chooses otherwise.
- Docs that map product direction to engineering proof.
- A reviewer-facing [review hub](review-hub.html) and [reviewer guide](reviewer-guide.md) for a 3-minute external evaluation.

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
