# GitHub Pages-ready site

VibeBench Arena now includes a small static site surface under `docs/`.

## Site files

- `docs/index.html` is the GitHub Pages-ready entry page. It points visitors to the product showcase, evaluation path, proof packet command, adoption guide, and honest limits.
- `docs/showcase.html` is the product showcase page. It explains the Codex-first quality console, evidence stack, proof packet, `proof.html`, and review workflow.
- `docs/review-hub.html` is the 3-minute public review entry for proof packet, site preview, evidence room, and CI artifact inspection.
- `docs/reviewer-guide.md` is the compact Markdown guide for external reviewers and evaluators.
- `docs/trust-center.html` and `docs/trust-center.md` describe project-maintained local-first, privacy, reproducibility, and artifact-safety boundaries. They are not third-party certification materials.
- `docs/security-questionnaire.html` and `docs/security-questionnaire.md` provide adopter-facing Q&A about local-first behavior, artifact sharing, CI uploads, static HTML safety, JSON purity, and non-claims. They are project-maintained documentation, not third-party certification or audit materials.

Both pages are static files with inline CSS only. They do not need a build step.

## Site readiness check

Before publishing or editing the static entry, run:

```bash
python3 -m vibebench site-check
python3 -m vibebench site-check --json
python3 -m vibebench site-preview --output-dir /tmp/vibebench-site-preview --zip
python3 -m vibebench site-preview --verify /tmp/vibebench-site-preview/site-preview.zip
python3 -m vibebench share-check PATH
python3 -m vibebench share-check PATH --json
```

This checks the Pages entry for required proof/evaluation links and obvious unsafe publishing markers. It is local-only. GitHub Pages is not enabled automatically by this command.

`site-preview` writes the same static preview bundle that CI uploads, including `site-check.json`, `site-preview.md`, and optional `site-preview.zip`. In CI, GitHub Actions runs `python3 -m vibebench site-preview --output-dir .vibebench/site-preview --zip` and uploads `vibebench-site-preview` as a downloadable artifact. This still does not enable GitHub Pages automatically; manual setup remains the step below.

## Proof packet command

The Pages entry points visitors to the same local proof packet command used by CI:

```bash
python3 -m vibebench proof --output-dir .vibebench/proof-packet --zip
```

## Evidence room package

For a single external-evaluation package that combines the proof packet and static site preview, run:

```bash
python3 -m vibebench evidence-room --output-dir PATH --zip
python3 -m vibebench evidence-room --verify PATH
```

The evidence room is local-first and evidence-first. It contains `index.html`, Trust Center files, Security Questionnaire files, reviewer scorecard files, `share-check.json`, `share-check.md`, top-level HTML, Markdown, JSON, a nested proof packet, and a nested static site preview. Reviewers should open `index.html` first, then inspect `share-check.md` if they want the local pre-sharing scan summary. Normal `python3 -m vibebench ci` writes it into the run directory, `python3 -m vibebench latest --artifact evidence-room-index-html --path-only` locates the newest landing page, and `python3 -m vibebench ci --skip-evidence-room` skips only that combined package. GitHub Actions also uploads it as the downloadable `vibebench-evidence-room` artifact. It does not enable GitHub Pages automatically and does not claim traction, funding, customers, revenue, or adoption. The Security Questionnaire is project-maintained adopter-facing Q&A about local-first behavior, artifact sharing, CI uploads, static HTML safety, JSON purity, and non-claims, not a third-party certification or audit. The scorecard is a reviewer aid, not a third-party endorsement. Share-check is a local aid, not a security certification, third-party audit, or guarantee.

Before sharing an evidence room, proof packet, static preview, or zip externally, run `python3 -m vibebench share-check PATH`; use `python3 -m vibebench share-check PATH --json` for machine-readable output. The scanner is a local aid, not a security certification, third-party audit, or guarantee, and artifacts still need manual review before publishing.

## Preview locally

Run this from the repository root:

```bash
python3 -m http.server 8000 --directory docs
```

Then open these local files or preview them through the local server:

- `docs/index.html`
- `docs/showcase.html`
- `docs/review-hub.html`
- `docs/reviewer-guide.md`
- `docs/trust-center.html`
- `docs/security-questionnaire.html`

## Manual GitHub Pages setup

This milestone does not enable GitHub Pages automatically. To enable it manually:

1. Go to repository Settings.
2. Open Pages.
3. Under Build and deployment, choose Source: Deploy from a branch.
4. Choose Branch: `main`.
5. Choose Folder: `/docs`.
6. Save the settings.

After setup, the Pages site entry should be `docs/index.html`, and the product showcase should be `docs/showcase.html`.
