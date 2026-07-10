# VibeBench Arena Trust Center

This Trust Center is project-maintained documentation, not a third-party audit or certification. It explains the current local-first, artifact, reproducibility, and sharing posture for reviewers, adopters, maintainers, and due-diligence readers.

## Local-first Operation

VibeBench Arena is designed to run from a repository checkout. The core evaluation path uses local commands and local files so teams can inspect outputs before trusting or sharing them.

Local evaluation does not require a hosted VibeBench service. GitHub Actions can upload artifacts when CI runs in a repository, but the core checks, proof packet, bundle, evidence room, readiness reports, and verification commands work locally.

## What Is Checked

Depending on command and config, VibeBench can check or report:

- configured test and lint commands
- quality gate thresholds from `.vibebench/config.yaml`
- Git diff risk signals such as deleted tests, sensitive paths, credential-like paths, lockfile movement, broad file changes, and large patches
- config validity and consistency
- package metadata and import/script readiness
- artifact manifest consistency
- workflow CI mode readiness for generated VibeBench workflow shapes
- adoption setup signals through project-scan, onboard, preflight, workflow-check, and adoption-ready
- release-readiness evidence through release-check
- shareability signals through share-check

These checks are evidence inputs. They do not guarantee correctness, safety, compliance, funding, traction, or business outcomes.

## Evidence-Backed Outputs

The project is designed to leave an evidence packet behind, not just a status line. Common outputs include:

- `metrics.json`: score, risk, command results, and run metrics.
- `check.log`: raw configured-check output.
- `manifest.json`: the run inventory.
- `report/index.html`: static local report.
- `github-step-summary.md`: GitHub Actions-friendly summary.
- `vibebench-bundle.zip`: portable archive of the run artifacts.
- `preflight.json` / `preflight.md`: adoption setup signals when enabled.
- `workflow-check.json` / `workflow-check.md`: workflow readiness evidence when enabled.
- `release-check.json` / `release-check.md`: local release-readiness evidence.
- `evidence-room/`: a self-contained reviewer package when generated.
- `public-demo/`: a deterministic standalone portal with `index.html`, `demo.json`, `README.md`, and curated safe links when generated from a run or proof packet.

JSON commands are expected to write parseable JSON to stdout when `--json` is used, which makes the output usable by scripts without scraping human tables.

## Evidence-room Package

The evidence-room package is the broadest external review package. It can include `index.html`, trust notes, questionnaire files, reviewer scorecards, proof packet files, static site preview files, share-check artifacts, and a zip archive for handoff.

Start with `index.html` when it is present. Open `share-check.md` before sharing the package externally.

## Proof packet

The proof packet is focused on proof evidence. It is intended to give reviewers a self-contained HTML report, structured JSON, readable Markdown, a manifest, and optional archive output.

## Public demo portal

The public demo portal converts a VibeBench run or proof packet into a self-contained `index.html` review surface. It copies only explicitly allowlisted artifacts, omits unsafe symlinks or escaping paths, labels unavailable optional evidence, and runs the same conservative sharing scan before writing the final portal.

It summarizes supplied evidence only. It does not independently prove security, replace human code review, certify compliance, or prove customers, funding, commercial traction, adoption, or product-market fit.

The separately published GitHub Pages demo is built from the committed public
demo with `scripts/build_pages_site.py`. Public GitHub-facing docs can point to
that hosted page, but this Trust Center stays offline-safe because it is copied
into evidence-room packages. The Pages build adds the static deployment wrapper
and `.nojekyll`, but it does not run hosted checks, collect analytics, load
remote runtime assets, or create evidence beyond the committed reproducible
artifacts.

## Static site preview

The static site preview packages the public docs entry and related files so reviewers can inspect the GitHub Pages-ready surface without enabling GitHub Pages automatically.

## Reviewer scorecard

The reviewer scorecard is a neutral checklist. It does not assert an external review outcome. Reviewers can use it to track reproducibility, artifact completeness, JSON output purity, static HTML safety, local-first behavior, and remaining notes.

## JSON output purity

JSON output purity means commands using `--json` should write JSON to stdout without extra prose, banners, progress tables, or Markdown.

## How The Readiness Checks Fit Together

The readiness model is layered:

- `preflight` is the safest read-only setup check.
- `workflow-check` reports whether the repository workflow is using the expected VibeBench CI mode.
- `adoption-ready` combines workflow, doctor, and release signals into a compact adoption answer.
- `release-check` records local release-readiness evidence without publishing, tagging, or creating a GitHub Release.
- `doctor --strict` verifies environment and artifact health for stricter CI/release-style confidence.

Adoption readiness is not one hidden calculation. It is a set of reproducible checks with visible outputs.

## Why It Is Safe To Run And Audit

- Core commands run from the local repository checkout.
- Read-only commands such as `preflight`, `project-scan`, `onboard`, `workflow-check`, `adoption-ready`, `release-check`, and `doctor` do not publish packages or create GitHub Releases.
- `workflow-template` previews a workflow by default and writes only when `--write` is explicitly passed.
- `init` writes `.vibebench/config.yaml` only and does not install dependencies or create workflow files.
- Normal local evaluation does not require GitHub API access or a hosted VibeBench service.
- Generated artifacts are plain files that reviewers can inspect, diff, bundle, verify, or delete.
- CI artifact uploads, when configured by a repository workflow, are visible GitHub Actions behavior rather than hidden local side effects.

## Security and privacy Boundaries

Before sharing an evidence room, public demo, bundle, proof packet, static preview, directory, or zip externally, run:

```bash
python3 -m vibebench share-check PATH
python3 -m vibebench share-check PATH --json
```

This is a local pre-sharing aid, not a security certification or guarantee. Artifacts should still be reviewed by a human before they are published outside the local environment.

Generated static HTML artifacts are expected to avoid JavaScript, remote URLs, external assets, absolute local paths, fake trust claims, and unsupported commercial claims. That expectation is part of the project's artifact posture, not an external audit result.

## Due Diligence Navigation

For structured evaluation, pair this Trust Center with:

- [Technical due diligence](technical-due-diligence.md)
- [Proof matrix](proof-matrix.md)
- [Investor brief](investor-brief.md)
- [Demo script](demo-script.md)

## What The Project Does Not Claim

- No third-party security certification.
- No compliance certification.
- No third-party audit.
- No invented customer, traction, funding, or adoption claims.
- No guarantee that generated code is correct or safe.
- No replacement for human review or security review.
- No hidden package publish, upload, tag creation, release creation, deployment, or repository settings changes in the normal local flow.

## Recommended Verification Commands

```bash
python3 -m vibebench ci --dry-run --json
python3 -m vibebench ci
python3 -m vibebench adoption-ready --json
python3 -m vibebench release-check --json
python3 -m vibebench doctor --strict
python3 -m vibebench bundle
python3 -m vibebench evidence-room --output-dir review-output/evidence-room --zip
python3 -m vibebench evidence-room --verify review-output/evidence-room
python3 -m vibebench proof --verify review-output/evidence-room/proof-packet
python3 -m vibebench site-preview --verify review-output/evidence-room/site-preview
python3 scripts/build_public_demo.py --check
python3 scripts/build_pages_site.py --output-dir review-output/pages-site
python3 scripts/build_pages_site.py --check
python3 -m vibebench site-check
```

## Responsible disclosure

For vulnerability reporting expectations, see the repository [Security Policy](../SECURITY.md).

For the practical rollout flow, see [adoption](adoption.md). For a shorter start path, see [quickstart](quickstart.md). For adopter-facing Q&A, open the [Security Questionnaire](security-questionnaire.md).
