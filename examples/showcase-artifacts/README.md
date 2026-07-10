# Showcase Demo Kit

This folder is the copy-paste demo kit for VibeBench Arena. It is for GitHub visitors, maintainers, community adopters, and technical reviewers who want to see how the project turns an AI-assisted repository into reviewable quality evidence.

For the narrative page, start with [docs/showcase.md](../../docs/showcase.md). For artifact definitions, use the [artifact gallery](../../docs/artifact-gallery.md). For trust boundaries and non-claims, use the [Trust Center](../../docs/trust-center.md).

## Demo Goal

In about five minutes, the demo should show:

- readiness: whether the repository matches the expected adoption workflow
- workflow coverage: whether the expected VibeBench CI mode is visible
- reproducible CI plan: what the pipeline would run before executing it
- evidence packet: where run artifacts and the bundle live
- trust boundary: what the tool checks and what it intentionally does not claim

This is not a security certification, correctness proof, funding claim, or replacement for human review.

## Five-Minute Command Path

Run from the repository root:

```bash
python3 -m vibebench adoption-ready --json
python3 -m vibebench ci --dry-run --json
python3 -m vibebench ci --adoption-policy --workflow-check-require-ci-mode adoption-policy --json
python3 -m vibebench bundle
python3 -m vibebench doctor --strict
```

## What Each Step Demonstrates

| Step | What to look for | Evidence value |
| --- | --- | --- |
| `adoption-ready --json` | `status`, `detected_ci_modes`, `required_ci_modes`, and failed/passed check counts. | Shows adoption readiness as structured, read-only output. |
| `ci --dry-run --json` | Ordered planned steps such as check, gate, report, manifest, release-check, bundle, and summary. | Shows the reproducible CI plan before a run writes artifacts. |
| `ci --adoption-policy --workflow-check-require-ci-mode adoption-policy --json` | A real run with policy-capable adoption checks and required workflow mode evidence. | Shows workflow coverage and adoption policy evidence in the run. |
| `bundle` | The latest `vibebench-bundle.zip` path. | Packages run artifacts into a portable evidence packet. |
| `doctor --strict` | Environment, config, latest run, manifest, bundle, and report checks. | Shows local artifact health without publish or release side effects. |

## Reviewer Walkthrough

After the run, locate artifacts:

```bash
python3 -m vibebench latest --all-paths
python3 -m vibebench artifacts --json
python3 -m vibebench latest --artifact bundle --path-only
```

Start with:

- `metrics.json`: score, risk level, command results, diff size, and finding counts.
- `manifest.json`: inventory of generated artifacts.
- `github-step-summary.md`: concise CI-style human summary.
- `workflow-check.json` / `workflow-check.md`: workflow mode readiness evidence when generated.
- `preflight.json` / `preflight.md`: adoption setup evidence when generated.
- `release-check.json` / `release-check.md`: local release-readiness evidence.
- `vibebench-bundle.zip`: portable packet for handoff.

## Optional Browseable Evidence Room

When a reviewer wants a browseable handoff package:

```bash
python3 -m vibebench evidence-room --output-dir /tmp/vibebench-evidence-room --zip
python3 -m vibebench evidence-room --verify /tmp/vibebench-evidence-room
python3 -m vibebench share-check /tmp/vibebench-evidence-room
```

Open `/tmp/vibebench-evidence-room/index.html` first. Inspect `share-check.md` before sharing the package outside the local environment.

## Demo Notes

- The demo is local-first.
- The commands above do not create tags, create GitHub Releases, publish packages, upload packages, call `gh`, or call the GitHub API.
- Generated `.vibebench/runs/` outputs are local artifacts and should not be committed.
- If `ci --adoption-policy` fails, use the generated artifacts to explain what was checked and which readiness signal failed.

## Checked-In Samples

This directory also contains small checked-in sample packs:

- [sample](sample/README.md): representative output shapes for browsing without running commands.
- [case-study](case-study/README.md): artifacts that pair with the full [case study](../../docs/case-study.md).
