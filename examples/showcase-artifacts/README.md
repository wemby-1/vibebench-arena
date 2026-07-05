# Showcase Artifacts

This folder is a lightweight tour of what VibeBench produces. It is for GitHub visitors who want to understand the artifact surface before running a full project workflow.

For the fastest browseable preview, run `python3 -m vibebench demo`, copy the pack with `python3 -m vibebench demo --copy-to /tmp/vibebench-demo`, or open the checked-in [sample artifact pack](sample/README.md).

These showcase artifacts support the project positioning: VibeBench makes AI-assisted coding reviewable and auditable.

## Artifact Tour

VibeBench turns Codex-first / vibe-coding changes into a quality console of local evidence:

- CI plans and run outputs show what would run and what did run.
- Artifact inventory output shows where reports, summaries, manifests, and bundles live.
- Compare output shows movement between runs.
- Package and publish checks show local release readiness without uploading anything.
- Release checklist and release audit outputs support release review.
- Release body export prepares copy/paste release notes without creating a GitHub Release.

## Copy-Paste Commands

Run from the repository root:

```bash
python3 -m vibebench demo
python3 -m vibebench demo --json
python3 -m vibebench demo --copy-to /tmp/vibebench-demo
python3 -m vibebench ci --dry-run --json
python3 -m vibebench artifacts --json
python3 -m vibebench compare --json
python3 -m vibebench package-check --json
python3 -m vibebench publish-check --json
python3 -m vibebench release-checklist --json
python3 -m vibebench release-body --version v0.3.0 --output /tmp/vibebench-release-body-demo.md
python3 -m vibebench release-audit --zip --output-dir /tmp/vibebench-release-audit-demo
```

If `/tmp/vibebench-release-audit-demo` already exists, remove it first or choose another output directory.

## Expected Files

Representative local outputs include:

- `.vibebench/runs/<timestamp>/metrics.json`
- `.vibebench/runs/<timestamp>/report/index.html`
- `.vibebench/runs/<timestamp>/manifest.json`
- `.vibebench/runs/<timestamp>/compare.json`
- `/tmp/vibebench-release-body-demo.md`
- `/tmp/vibebench-release-audit-demo/release-audit.zip`
- `/tmp/vibebench-release-audit-demo/release-audit-manifest.json`

Generated outputs are local and safe to delete. This showcase does not check in generated zip files, binary files, or large JSON blobs.

## Safety Notes

These commands do not publish or upload packages, create tags, create GitHub Releases, call the GitHub API, use `gh`, bump versions, or install dependencies.

For a broader explanation, see the [artifact gallery](../../docs/artifact-gallery.md) and the [quickstart demo](../quickstart-demo/README.md).
