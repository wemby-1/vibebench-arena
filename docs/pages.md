# GitHub Pages-ready site

VibeBench Arena now includes a small static site surface under `docs/`.

## Site files

- `docs/index.html` is the GitHub Pages-ready entry page. It points visitors to the product showcase, evaluation path, proof packet command, adoption guide, and honest limits.
- `docs/showcase.html` is the product showcase page. It explains the Codex-first quality console, evidence stack, proof packet, `proof.html`, and review workflow.

Both pages are static files with inline CSS only. They do not need a build step.

## Site readiness check

Before publishing or editing the static entry, run:

```bash
python3 -m vibebench site-check
python3 -m vibebench site-check --json
python3 -m vibebench site-preview --output-dir /tmp/vibebench-site-preview --zip
python3 -m vibebench site-preview --verify /tmp/vibebench-site-preview/site-preview.zip
```

This checks the Pages entry for required proof/evaluation links and obvious unsafe publishing markers. It is local-only. GitHub Pages is not enabled automatically by this command.

`site-preview` writes the same static preview bundle that CI uploads, including `site-check.json`, `site-preview.md`, and optional `site-preview.zip`. In CI, GitHub Actions runs `python3 -m vibebench site-preview --output-dir .vibebench/site-preview --zip` and uploads `vibebench-site-preview` as a downloadable artifact. This still does not enable GitHub Pages automatically; manual setup remains the step below.

## Proof packet command

The Pages entry points visitors to the same local proof packet command used by CI:

```bash
python3 -m vibebench proof --output-dir .vibebench/proof-packet --zip
```

## Preview locally

Run this from the repository root:

```bash
python3 -m http.server 8000 --directory docs
```

Then open these local files or preview them through the local server:

- `docs/index.html`
- `docs/showcase.html`

## Manual GitHub Pages setup

This milestone does not enable GitHub Pages automatically. To enable it manually:

1. Go to repository Settings.
2. Open Pages.
3. Under Build and deployment, choose Source: Deploy from a branch.
4. Choose Branch: `main`.
5. Choose Folder: `/docs`.
6. Save the settings.

After setup, the Pages site entry should be `docs/index.html`, and the product showcase should be `docs/showcase.html`.
