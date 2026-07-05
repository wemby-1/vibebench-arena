# GitHub Pages-ready site

VibeBench Arena now includes a small static site surface under `docs/`.

## Site files

- `docs/index.html` is the GitHub Pages-ready entry page. It points visitors to the product showcase, evaluation path, proof packet command, adoption guide, and honest limits.
- `docs/showcase.html` is the product showcase page. It explains the Codex-first quality console, evidence stack, proof packet, `proof.html`, and review workflow.

Both pages are static files with inline CSS only. They do not need a build step.

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
