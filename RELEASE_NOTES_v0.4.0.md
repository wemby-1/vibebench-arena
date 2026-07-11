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
- Hosted `VibeBench release candidate` workflow that validates the candidate gate on push, pull request, and manual dispatch with read-only repository permissions.
- Deterministic release-candidate evidence bundle with provenance, checksums, and a reproducible ZIP archive.

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

The release-candidate bundle command produces a portable evidence directory and archive:

```bash
python3 -m vibebench release-bundle --candidate
python3 -m vibebench release-bundle --candidate --check
python3 -m vibebench release-bundle --candidate --json
```

The bundle contains `release-candidate.json`, `release-candidate.md`, `workflow-verification.json`, `release-provenance.json`, `release-checksums.sha256`, selected reviewer docs, package/action metadata files, and `release-candidate-bundle.zip`. `release-provenance.json` records schema version, project and package version, `candidate=true`, `released=false`, source commit when available, source tree clean/dirty state, package/action metadata consistency, workflow paths, included files, deterministic-build policy, archive format, and checksum algorithm. It does not include wall-clock generation timestamps, hostnames, usernames, absolute local paths, runner paths, secrets, or environment tokens.

`release-checksums.sha256` uses SHA256 over sorted POSIX relative payload paths. It intentionally excludes `release-checksums.sha256` and `release-candidate-bundle.zip` to avoid recursive self-checksums. The ZIP archive contains only the allowlisted candidate payload files, uses sorted relative paths, a normalized `1980-01-01T00:00:00Z` ZIP timestamp, and normalized `0644` file permissions.

The hosted candidate workflow uploads the stable artifact `vibebench-v0.4.0-release-candidate`, containing the full bundle evidence. `workflow-verification.json` is local structural verification and does not claim remote hosted-run status.

## Security and Privacy Boundaries

- Core commands run from the local checkout.
- The candidate gate does not call the GitHub API.
- The candidate gate does not create a tag, GitHub Release, package upload, or Marketplace listing.
- The hosted candidate workflow uses `contents: read` and does not request package, release, deployment, or OIDC publishing permissions.
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
python3 -m vibebench release-bundle --candidate --check
python3 scripts/build_public_proof_packet.py --check
python3 scripts/build_public_demo.py --check
python3 scripts/build_pages_site.py --check
python3 -m pytest -q
```

## Post-candidate Release Steps

1. Confirm the real hosted Action smoke run passed `minimal`, `strict`, and `proof`.
2. Confirm the hosted `VibeBench release candidate` workflow passed and inspect its uploaded candidate artifact.
3. Rerun the full local verification chain from a clean checkout.
4. Create the annotated `v0.4.0` tag only after approval.
5. Draft and publish the GitHub Release only after approval.
6. Publish a package only if separately approved.
7. Decide whether to draft or publish the GitHub Marketplace listing after a stable ref exists.
