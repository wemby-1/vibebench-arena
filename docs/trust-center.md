# VibeBench Arena Trust Center

This Trust Center is project-maintained documentation, not a third-party audit or compliance certification. It explains the current security, privacy, reproducibility, local-first, and evidence artifact posture for external reviewers, maintainers, adopters, and due-diligence readers. Open the [Security Questionnaire](security-questionnaire.md) for adopter-facing Q&A about local-first behavior, artifact sharing, CI uploads, static HTML safety, JSON purity, and non-claims.

## Local-first operation

VibeBench Arena is designed to run from a repository checkout. The core evaluation path uses local commands and local files so reviewers can inspect what is generated before trusting it.

## No required cloud service for local evaluation

Local evaluation does not require a hosted VibeBench service. GitHub Actions can upload artifacts when CI runs in a repository, but the core proof, site preview, evidence-room package, scorecard, and verification commands work locally.

## What artifacts are generated

- Evidence-room package: a self-opening review bundle with `index.html`, evidence summaries, trust notes, reviewer scorecard files, proof packet, static site preview, JSON, Markdown, and zip output.
- Proof packet: local proof files including `proof.html`, `proof.json`, `proof.md`, `proof-manifest.json`, and optional `proof.zip`.
- Static site preview: a local bundle for the public docs entry and setup guide.
- Reviewer scorecard: neutral HTML, Markdown, and JSON checklists with `not_reviewed` placeholders.
- Security Questionnaire: adopter-facing Q&A for local-first behavior, artifact boundaries, CI uploads, sharing review, JSON stdout, static HTML safety, and non-claims. It is project-maintained documentation, not a third-party certification or audit.

## Evidence-room package

The evidence room is the broadest local evaluation package. It combines reviewer-facing HTML, Markdown, JSON, nested proof packet files, nested static site preview files, and verification commands. Start with `index.html`.

## Proof packet

The proof packet is focused on proof evidence. It is intended to give reviewers a self-contained HTML report, structured JSON, readable Markdown, a manifest, and optional archive output.

## Static site preview

The static site preview packages the public docs entry and related files so reviewers can inspect the GitHub Pages-ready surface without enabling GitHub Pages automatically.

## Reviewer scorecard

The reviewer scorecard is a neutral checklist. It does not assert an external review outcome. Reviewers can use it to track reproducibility, artifact completeness, JSON output purity, static HTML safety, local-first behavior, and remaining notes.

## JSON output purity

JSON commands are expected to write pure JSON to stdout when the `--json` option is used. This makes the output scriptable and parseable without scraping human tables.

## Static HTML safety rules

Generated static HTML artifacts are expected to avoid JavaScript, remote URLs, external assets, images, absolute local paths, fake traction claims, fake trust claims, and unsupported commercial claims.

## Path/privacy hygiene

Generated shareable artifacts should prefer relative paths or placeholders. Reviewers should inspect artifacts before sharing them outside a local environment.

Evidence rooms include `share-check.json` and `share-check.md`; reviewers should open `index.html` first, then inspect `share-check.md` if they want the local pre-sharing scan summary. Before sharing an evidence room, proof packet, static preview, or zip externally, run `python3 -m vibebench share-check PATH`; use `python3 -m vibebench share-check PATH --json` for machine-readable output. The scanner is a local pre-sharing aid, not a security certification, not a third-party audit, and not a guarantee.

For run quality regression checks, use `python3 -m vibebench regression-check` or opt CI in with `python3 -m vibebench ci --regression-check`. Automatic previous-run inference is convenient for local experiments; guarded pinned baselines are better for stable gates. Generate a clean run with `python3 -m vibebench ci --json`, dry-run `python3 -m vibebench baseline --promote-latest --label stable --dry-run --json`, promote with `python3 -m vibebench baseline --promote-latest --label stable`, then configure `regression.enabled: true`, `baseline_label: stable`, and `require_baseline: true` so future `python3 -m vibebench ci --json` runs the gate by default. CI does not auto-promote baselines. Promoted baselines carry a compact metrics snapshot; use `python3 -m vibebench baseline --verify --label stable`, `python3 -m vibebench baseline --export --label stable --output baseline.json`, `python3 -m vibebench baseline --verify --input baseline.json`, and `python3 -m vibebench baseline --import baseline.json --label stable` for portable gates on another machine or cleaned workspace. Add `--require-portable` for snapshot-based portability or `--require-live-metrics` when the original run must still be present. Regression-check is a local quality gate, not a benchmark certification, and depends on the metrics available in run artifacts.

## GitHub Actions artifact behavior

GitHub Actions can upload downloadable proof packet, static site preview, and evidence-room artifacts. This does not publish a package, create a release, enable GitHub Pages, or change repository settings.

## Security and privacy boundaries

VibeBench records local evidence and CI-readable artifacts. It is not a credential leak scanner, a sandbox, a hosted security product, or a replacement for human security review. Treat generated artifacts as review materials and inspect them before sharing.

## What the project does not claim

- No third-party audit.
- No compliance certification.
- No fake security certification.
- No invented customer or adoption claims.
- No promise of funding or business outcomes.
- No guarantee that generated code is correct or safe.
- No automatic publishing, deployment, release, or repository settings change.

## Recommended reviewer verification commands

```bash
python3 -m vibebench evidence-room --output-dir /tmp/vibebench-evidence-room --zip
python3 -m vibebench evidence-room --verify /tmp/vibebench-evidence-room
python3 -m vibebench proof --verify /tmp/vibebench-evidence-room/proof-packet
python3 -m vibebench site-preview --verify /tmp/vibebench-evidence-room/site-preview
python3 -m vibebench site-check
python3 -m vibebench share-check PATH
python3 -m vibebench share-check PATH --json
python3 -m vibebench regression-check
python3 -m vibebench ci --regression-check
python3 -m vibebench baseline --set-latest --label stable
python3 -m vibebench ci --regression-check --baseline-label stable --json
python3 -m vibebench ci --dry-run --json
python3 -m vibebench release-check
python3 -m vibebench doctor --strict
```

## Responsible disclosure / security policy

For vulnerability reporting expectations, see the repository [Security Policy](../SECURITY.md).
