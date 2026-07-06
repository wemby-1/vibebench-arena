# VibeBench Arena Reviewer Guide

VibeBench Arena is a Codex-first / vibe-coding quality console. It turns AI-assisted code changes into local checks, proof packets, static site previews, evidence rooms, and CI artifacts that an external reviewer can inspect.

Use this guide if you are a developer, maintainer, AI coding team, evaluator, or due-diligence reader who wants a fast, factual view of what the project does.

## Review in 3 minutes

1. Open the [review hub](review-hub.html) for the skim path.
2. Run the demo:

   ```bash
   python3 -m vibebench demo
   ```

3. Generate a proof packet:

   ```bash
   python3 -m vibebench proof --output-dir PATH/vibebench-proof --zip
   ```

4. Generate a combined evidence room:

   ```bash
   python3 -m vibebench evidence-room --output-dir PATH/vibebench-evidence-room --zip
   ```

5. Open `PATH/vibebench-evidence-room/index.html` as the downloaded package start page, then use `review-scorecard.html` or `review-scorecard.md` as the neutral checklist.
6. Preview the local CI plan:

   ```bash
   python3 -m vibebench ci --dry-run --json
   ```

Choose any writable temporary or project-local directory for `PATH`.

## CI artifacts to download

- `vibebench-proof-packet`: the proof packet with `proof.html`, `proof.json`, `proof.md`, manifest data, and a zip archive.
- `vibebench-site-preview`: a static preview of the public docs entry, product page, setup guide, and site-check JSON.
- `vibebench-evidence-room`: the combined review package with `index.html`, `review-scorecard.html`, `review-scorecard.md`, top-level HTML, Markdown, JSON, zip archive, nested proof packet, and nested site preview.

## What the artifacts prove

- The demo proves the local command surface is available and points to checked-in example artifacts.
- The proof packet proves that VibeBench can package reviewable evidence into human-readable and machine-readable files.
- The site preview proves the public docs entry can be checked and bundled without enabling GitHub Pages automatically.
- The evidence room proves the proof packet and static site preview can be combined into one verifiable local package.
- The CI plan proves the ordered quality pipeline can be inspected before running it.

## Verify generated evidence

Use the verifier for the package you received:

```bash
python3 -m vibebench proof --verify PATH
python3 -m vibebench site-preview --verify PATH
python3 -m vibebench evidence-room --verify PATH
```

For an evidence room, start with `index.html`, then open `review-scorecard.html` for the neutral checklist, `evidence-room.html` for the human overview, and `evidence-room.json` for the machine-readable summary. The scorecard is a reviewer aid, not a third-party endorsement. The nested `proof-packet/` directory shows the proof report, and `site-preview/` shows the static public docs bundle.

## What this does not claim

- No fake traction.
- No fundraising promises.
- No invented customers.
- No benchmark dominance claim.
- No promise that every AI-generated change is correct.
- No automatic GitHub Pages enablement.

VibeBench is local-first and evidence-first. It helps reviewers decide what to inspect next; it does not replace human judgment.
