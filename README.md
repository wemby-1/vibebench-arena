# VibeBench Arena

**A Codex-first quality gate for vibe coding projects: run local checks, generate reviewable evidence, and show whether an AI-assisted repo is ready for adoption or release work.**

> Codex writes code. VibeBench verifies what happened.

[![CI](https://github.com/wemby-1/vibebench-arena/actions/workflows/ci.yml/badge.svg)](https://github.com/wemby-1/vibebench-arena/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)

![VibeBench report preview](docs/assets/report-preview.svg)

<!-- VIBEBENCH_STATUS_START -->
## VibeBench Status

- Overall status: passed
- VibeScore: 100
- Risk level: low
- Changed files: 0
- Patch lines: 0
- Risk findings: 0

<!-- VIBEBENCH_STATUS_END -->

VibeBench Arena is a local-first quality gate for AI coding workflows. In practice, that means it sits between "the agent changed the code" and "a human is ready to trust, merge, share, or release it" and leaves concrete evidence behind.

![VibeBench flow](docs/assets/vibebench-flow.svg)

## 30-Second Read

VibeBench is not another chatbot or benchmark leaderboard. It is an evidence-first CLI for AI-assisted engineering: run local checks, capture score/risk/diff signals, generate proof packets and review artifacts, and verify whether the repository is ready for adoption, workflow CI, or release-readiness review.

## Quickstart In 3 Steps

```bash
python3 -m pip install -e ".[dev]"
python3 -m vibebench ci
python3 -m vibebench latest --all-paths
```

1. Install and run VibeBench locally from the repo checkout.
2. Run a local CI-style gate that produces a timestamped run directory.
3. Inspect the latest artifacts before you share them or wire them into GitHub Actions.

If you want a shorter preview before a full run, start with `python3 -m vibebench ci --dry-run --json`.

## One-Step GitHub Action Preview

External repositories can try VibeBench with the repository-root composite action:

```yaml
- uses: wemby-1/vibebench-arena@main
  with:
    preset: minimal
```

`@main` is a preview/development reference, not a stable action release. Production consumers should pin a future stable tag or a reviewed commit SHA. The action installs VibeBench from the action checkout, evaluates the caller repository, writes GitHub Step Summary output, exposes machine-readable outputs such as `status`, `score`, `risk`, `run-dir`, `manifest-path`, and `bundle-path`, and can optionally upload only intended VibeBench evidence.

Generate reviewable workflows with:

```bash
python3 -m vibebench github-action --preset minimal
python3 -m vibebench github-action --preset strict --upload-artifacts
python3 -m vibebench github-action --preset proof --json
```

See [GitHub Actions](docs/github-actions.md) and the [action consumer fixture](examples/action-consumer/README.md).

## Showcase Demo

## Live Demo

The deterministic public launch site is published with GitHub Pages at:

```text
https://wemby-1.github.io/vibebench-arena/
```

It is a static product website built from committed, reproducible VibeBench evidence. It includes a 30-second product frame, audience paths for developers/reviewers/investors/community evaluators, evidence-derived proof cards, a searchable artifact explorer, copyable local commands, and trust boundaries. It is not an independent hosted scanning service, and it does not claim security certification, compliance certification, users, funding, revenue, or product-market fit.

Evaluating quickly? Start with the [showcase page](docs/showcase.md), the [showcase demo kit](examples/showcase-artifacts/README.md), the [public proof packet](examples/showcase-artifacts/public-proof/README.md), and the [public demo portal](examples/showcase-artifacts/public-demo/README.md). They give reviewers a 5-minute path through readiness, workflow coverage, CI planning, evidence packets, and trust boundaries without turning this README into a command dump.

To generate the standalone portal yourself:

```bash
python3 -m vibebench public-demo \
  --proof-packet examples/showcase-artifacts/public-proof \
  --output-dir /tmp/vibebench-demo
```

Then open `/tmp/vibebench-demo/index.html` directly in a browser. The portal is self-contained and does not require a server or network access.

To verify the Pages build locally:

```bash
python3 scripts/build_public_demo.py --check
python3 scripts/build_pages_site.py --output-dir /tmp/vibebench-pages-site
python3 scripts/build_pages_site.py --check
```

The generated site uses local CSS/JS/SVG assets, project-Pages-safe relative links, `robots.txt`, `sitemap.xml`, `404.html`, `site.webmanifest`, and `.nojekyll`. It has no analytics, cookies, trackers, remote fonts, CDNs, or remote runtime dependencies; JavaScript only improves filtering, copying, and mobile navigation.

For diligence review, use the [investor brief](docs/investor-brief.md), [technical due diligence](docs/technical-due-diligence.md), [proof matrix](docs/proof-matrix.md), [public proof packet tour](docs/public-proof-packet.md), [demo script](docs/demo-script.md), and [Trust Center](docs/trust-center.md).

## Why This Exists

AI coding makes it easy to produce code quickly. It does not automatically make the result easy to review.

Ordinary repo visitors, maintainers, adopters, and technical evaluators usually need more than "tests passed." They need to see what changed, what checks ran, what evidence was generated, whether the workflow is reproducible, and whether the project looks ready for broader adoption or release work.

VibeBench is built for that gap. It does not replace human review, and it does not claim to guarantee quality.

## What You Get

- Local CI-style runs with lint, tests, gates, summaries, and bundleable artifacts.
- Adoption and workflow readiness checks that show whether the repo is set up the way VibeBench expects.
- Release-readiness checks that stay local unless you explicitly choose to publish elsewhere.
- Machine-readable JSON plus reviewer-friendly Markdown and HTML artifacts.
- GitHub Actions summaries and downloadable evidence without requiring GitHub API posting.

## Who This Is For

- Solo builders using Codex, Cursor, Claude Code, or similar agent-driven workflows.
- Teams adopting AI coding agents and trying to add credible quality signals without heavy process.
- Reviewers, technical evaluators, or investors who need evidence instead of vibes.
- Open-source maintainers who want reproducible quality signals for AI-assisted contributions.

## Demo Funnel

Run this from the repository root:

```bash
python3 -m vibebench ci
python3 -m vibebench adoption-ready --json
python3 -m vibebench bundle
python3 -m vibebench doctor --strict
```

- `python3 -m vibebench ci` proves the project can run its local quality gate and write a full run directory.
- `python3 -m vibebench adoption-ready --json` proves the repo can report adoption-readiness signals in a machine-readable way.
- `python3 -m vibebench bundle` proves the latest run can be packaged into a shareable evidence archive.
- `python3 -m vibebench doctor --strict` proves the local environment and expected artifacts are present for stricter CI/release-style checks.

For a plan-only preview, use `python3 -m vibebench ci --dry-run --json`. For release readiness, add `python3 -m vibebench release-check --json`.

## Evidence Packet

The core artifact story is an evidence packet, not just a pass/fail line. A normal run or proof workflow can produce:

- `metrics.json`: score, risk, and core run metrics.
- `manifest.json`: inventory of what the run produced and where it lives.
- `vibebench-bundle.zip`: a portable zip of the latest run artifacts.
- `github-step-summary.md`: the GitHub Actions-friendly summary for the run.
- `proof.html`, `proof.json`, `proof.md`, and `proof.zip`: a focused proof packet when `vibebench proof` is used.
- `preflight.json` / `preflight.md`: report-only adoption setup signals when preflight is enabled.
- `workflow-check.json` / `workflow-check.md`: report-only workflow readiness evidence when workflow checks are enabled.
- `release-check.json` / `release-check.md`: local release-readiness evidence.
- `evidence-room/` outputs when available: a self-contained review package with `index.html`, trust notes, questionnaire files, scorecards, and share-check artifacts.
- `public-demo` output: a deterministic standalone portal with `index.html`, `demo.json`, and `README.md` for sharing a run or proof packet without teaching the full CLI first.

These files are meant to answer practical questions: what ran, what changed, what evidence exists, and what a reviewer should inspect next.

For a checked-in, reproducible example, browse the [public proof packet](examples/showcase-artifacts/public-proof/README.md), the [public demo portal](examples/showcase-artifacts/public-demo/README.md), and the [artifact tour](docs/public-proof-packet.md).

## Why It Is Different From Ordinary CI

Ordinary CI mostly answers one question: did the checks pass?

VibeBench also tries to answer:

- What changed?
- What evidence was generated?
- Is the project ready for adoption?
- Is the workflow using the expected VibeBench CI mode?
- Are release and adoption signals reproducible from the repo checkout?

That is why the project leans so heavily on manifests, summaries, readiness checks, bundles, and review artifacts instead of only returning a status badge.

## Readiness Model

VibeBench has a layered readiness story:

- `preflight` is the safest read-only entry point for setup signals.
- `workflow-check` reports whether the repo is using the expected VibeBench CI mode.
- `adoption-ready` combines workflow, doctor, and release-readiness signals for a compact adoption answer.
- `release-check` records local release-readiness evidence without tagging, publishing, or creating a GitHub Release.
- `doctor --strict` verifies that the environment and expected artifacts are healthy enough for stricter gating.

See [quickstart](docs/quickstart.md), [adoption](docs/adoption.md), and the [Trust Center](docs/trust-center.md) for the practical flow.

## v0.4.0 Release Candidate

Milestone 160 prepares v0.4.0 as a release candidate, not as a completed release. The package version is aligned to `0.4.0`, while the candidate gate reports `released=false` and performs no tag creation, GitHub Release creation, package publication, or Marketplace publication.

```bash
python3 -m vibebench release-check --candidate
python3 -m vibebench release-check --candidate --json
python3 -m vibebench release-check --candidate --write-json release-candidate.json --write-summary release-candidate.md
python3 -m vibebench release-bundle --candidate
python3 -m vibebench release-bundle --candidate --check
```

Reviewer navigation:

- [GitHub Action contract](docs/github-action.md)
- [Marketplace readiness](docs/marketplace-readiness.md)
- [v0.4.0 release candidate notes](RELEASE_NOTES_v0.4.0.md)
- [v0.4.0 release checklist](docs/release-checklist-v0.4.0.md)

`release-bundle --candidate` writes a deterministic, portable evidence directory at `.vibebench/release-candidates/v0.4.0/` by default. It includes `release-candidate.json`, `release-candidate.md`, `workflow-verification.json`, `release-provenance.json`, `release-checksums.sha256`, selected reviewer docs, package/action metadata files, and `release-candidate-bundle.zip`. Checksums cover payload files and intentionally exclude `release-checksums.sha256` and the archive itself; the ZIP uses sorted relative paths, normalized timestamps, and normalized file permissions for byte-for-byte rebuilds from the same source state.

The hosted `VibeBench release candidate` workflow validates the same candidate gate on GitHub, generates and checks the deterministic bundle, verifies checksums, and uploads `vibebench-v0.4.0-release-candidate`. `workflow-verification.json` is local structural evidence; remote GitHub Actions status must still be checked separately after push. Both `VibeBench release candidate` and `Action smoke` with `minimal`, `strict`, and `proof` should be green before continuing release work. Passing the candidate gate is readiness evidence, not a claim of adoption, funding, customers, stars, revenue, benchmark dominance, or security certification.

## Evaluate From GitHub

- [Showcase](docs/showcase.md): the reviewer-friendly product demo narrative.
- [Showcase demo kit](examples/showcase-artifacts/README.md): copy-paste commands and artifact interpretation.
- [Public proof packet](examples/showcase-artifacts/public-proof/README.md): committed artifacts regenerated from a deterministic reference project.
- [Public proof packet tour](docs/public-proof-packet.md): reading order, provenance, normalization, and staleness checks.
- [Investor brief](docs/investor-brief.md): product value, market hypotheses, maturity, risks, and non-claims.
- [Technical due diligence](docs/technical-due-diligence.md): architecture, evidence lifecycle, tests, risks, and evaluator checklist.
- [Proof matrix](docs/proof-matrix.md): claim-to-command-to-artifact mapping.
- [Demo script](docs/demo-script.md): five-minute and fifteen-minute presenter flows.
- [Quickstart](docs/quickstart.md): the shortest path from clone to usable local evidence.
- [Adoption guide](docs/adoption.md): how teams roll this out safely.
- [Artifact gallery](docs/artifact-gallery.md): what the outputs mean to a non-core maintainer.
- [Trust Center](docs/trust-center.md): project-maintained boundaries around local-first behavior, artifacts, and claims.
- [Demo guide](docs/demo.md): a compact command sequence for showing the workflow live.
- [Evaluate in 5 minutes](docs/evaluate.md): the fastest credibility check for new visitors.
- [Positioning](docs/positioning.md): the product and category framing.
- [Use cases](docs/use-cases.md): who this helps and why.
- [Case study](docs/case-study.md): how an AI-assisted change becomes reviewable evidence.

## More Commands

```bash
python3 -m vibebench ci --dry-run --json
python3 -m vibebench preflight --json
python3 -m vibebench workflow-check
python3 -m vibebench release-check --json
python3 -m vibebench evidence-room --output-dir /tmp/vibebench-evidence-room --zip
python3 -m vibebench public-demo --proof-packet examples/showcase-artifacts/public-proof --output-dir /tmp/vibebench-demo
python3 -m vibebench latest --artifact evidence-room-index-html --path-only
```

- `ci --dry-run --json` previews the quality pipeline without running it.
- `preflight --json` reports setup and adoption signals without creating a run.
- `workflow-check` inspects an existing GitHub Actions workflow read-only.
- `release-check --json` records local release-readiness status.
- `evidence-room --zip` creates a self-contained review package for external inspection.
- `public-demo` creates a deterministic standalone portal that can be opened from `index.html` without a server.
- `latest --artifact ... --path-only` helps scripts or reviewers jump to the exact artifact they need.

## Project Boundaries

- No claim that VibeBench guarantees quality.
- No claim that it replaces human review.
- No hidden publish, tag, release, or GitHub API side effects in the normal local flow.
- No requirement for a hosted service to evaluate the core workflow.

For broader roadmap and thesis docs, see [product strategy](docs/product-strategy.md), [public roadmap](docs/roadmap-public.md), and [commercial potential](docs/commercial-potential.md).
