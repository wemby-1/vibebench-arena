# VibeBench Arena v0.4.0 Release Candidate Notes

These are draft release notes for the v0.4.0 release candidate. This repository is prepared with package version `0.4.0`, but this candidate is not a completed release.

Candidate state:

- `released=false`
- no tag was created
- no GitHub Release was created
- no package publication occurred
- no Marketplace publication occurred
- remote GitHub Actions status must be reviewed separately after push

## Product Positioning

VibeBench Arena is a local-first evidence gate for AI-assisted software work. It turns repository checks, risk signals, adoption readiness, release readiness, public proof packets, and reviewer-facing artifacts into files that maintainers and external technical reviewers can inspect.

Passing the candidate gate is evidence of readiness. It is not a promise of adoption, funding, stars, customers, revenue, product-market fit, benchmark dominance, security certification, or a guarantee that generated code is correct or safe.

## Major Capabilities Since v0.3.0

- Reusable repository-root composite GitHub Action with `minimal`, `strict`, and `proof` presets.
- Isolated Action runner boundary between `GITHUB_WORKSPACE` and `GITHUB_ACTION_PATH`.
- Action smoke workflow covering all three presets against a separate consumer fixture.
- Deterministic public proof packet and public demo portal.
- GitHub Pages launch-site builder and local check path.
- Local-first evidence room, share-check, Trust Center, and security questionnaire flow.
- Adoption/workflow/release readiness checks with machine-readable JSON and Markdown artifacts.
- Candidate release gate for v0.4.0 that joins package, Action, public evidence, documentation, and non-publication state.

## Reusable GitHub Action

The Action contract is documented in [docs/github-action.md](docs/github-action.md). Recommended references are separated by state:

- Development preview: `wemby-1/vibebench-arena@main`
- Post-release stable example: `wemby-1/vibebench-arena@v0.4.0`
- Optional major alias after maintainer approval: `wemby-1/vibebench-arena@v0`
- Strongest immutability: a full commit SHA

The v0.4.0 tag does not exist as part of M160 candidate preparation.

## Public Proof, Demo, and Pages

The committed public proof packet and public demo are deterministic review surfaces. The Pages builder can render a static launch site from those committed artifacts. These public surfaces summarize evidence; they do not create hosted scanning, analytics, certification, or publication outcomes.

## Evidence and Artifact Model

The release-candidate gate can produce:

- `release-candidate.json`
- `release-candidate.md`

Both are deterministic. JSON stdout for `--json` is pure JSON.

## Security and Privacy Boundaries

- Core commands run from the local checkout.
- The candidate gate does not call the GitHub API.
- The candidate gate does not create a tag, GitHub Release, package upload, or Marketplace listing.
- Public static surfaces are checked for deterministic builders and offline-safe Trust Center boundaries.
- Action paths are checked for caller workspace and action source separation.

## Installation and Upgrade Notes

For local development from a checkout:

```bash
python3 -m pip install -e ".[dev]"
python3 -m vibebench release-check --candidate
```

For Action consumers, keep using `@main` only as a development preview until a stable tag exists.

## Breaking Changes

None known for the CLI paths covered by existing tests. Normal `release-check` behavior remains backward compatible.

## Known Limitations

- Remote GitHub Action smoke status cannot be verified locally without GitHub-side access and must be reviewed separately.
- The candidate gate is structural and artifact-based; it does not prove future GitHub Release, Marketplace, or package-registry behavior.
- VibeBench remains a local-first evidence tool, not a hosted dashboard or certification authority.

## Verification Summary

The intended verification chain includes:

```bash
python3 -m vibebench release-check --candidate
python3 -m vibebench release-check --candidate --json
python3 scripts/build_public_proof_packet.py --check
python3 scripts/build_public_demo.py --check
python3 scripts/build_pages_site.py --check
python3 -m pytest -q
```

## Post-candidate Release Steps

1. Confirm the real hosted Action smoke run passed `minimal`, `strict`, and `proof`.
2. Rerun the full local verification chain from a clean checkout.
3. Create the annotated `v0.4.0` tag only after approval.
4. Draft and publish the GitHub Release only after approval.
5. Publish a package only if separately approved.
6. Decide whether to draft or publish the GitHub Marketplace listing after a stable ref exists.
