# GitHub Marketplace Readiness

This guide is an operational checklist for preparing the VibeBench reusable Action for GitHub Marketplace review. M160 does not perform Marketplace publication.

## Draft a Release Banner

GitHub may show a "Draft a release" banner for repository actions that look publishable. The banner means GitHub sees Action metadata and a possible release path. It does not mean the Action has been published, reviewed, or listed in Marketplace.

## Prerequisites

- `action.yml` has a stable name, description, author, valid branding icon and color, documented inputs, and documented outputs.
- A stable release tag exists, such as `v0.4.0`.
- The real GitHub Action smoke workflow has passed `minimal`, `strict`, and `proof` after the candidate push.
- The hosted `VibeBench release candidate` workflow has passed and uploaded `vibebench-v0.4.0-release-candidate`.
- `python3 -m vibebench release-check --candidate` passes and reports `released=false`.
- `python3 -m vibebench release-bundle --candidate --check` passes for the deterministic candidate evidence bundle.
- Release notes exist and describe the Action contract honestly.
- Support and security links resolve: [Security Policy](../SECURITY.md), [Contributing](../CONTRIBUTING.md), and [GitHub Action guide](github-action.md).

## Stable Ref Guidance

- Development preview: `wemby-1/vibebench-arena@main`.
- Post-release stable tag: `wemby-1/vibebench-arena@v0.4.0`.
- Optional major alias: `wemby-1/vibebench-arena@v0`, only if maintainers intentionally maintain it.
- Strongest immutability: a full commit SHA.

Do not describe `@main` as the stable consumer contract.

## Security Review

Review the boundary between `GITHUB_WORKSPACE` and `GITHUB_ACTION_PATH`, artifact upload allowlists, parsed `python-command`, path traversal protections, and permissions. Normal Action examples should use:

```yaml
permissions:
  contents: read
```

Optional artifact upload does not require broad repository write permissions.

## Release Notes Requirement

Marketplace publication should reference release notes that state what changed, what evidence exists, and what is not claimed. For v0.4.0 candidate work, use [release notes](../RELEASE_NOTES_v0.4.0.md) as the draft source.

## Consumer Smoke Verification

Before a Marketplace decision, verify a separate consumer run for:

- `minimal`
- `strict`
- `proof`

Remote GitHub Actions status must be reviewed separately after push. Local structural checks are necessary, but they are not a substitute for the hosted smoke result.

The release-candidate workflow uploads only the narrow candidate evidence directory with `release-candidate.json`, `release-candidate.md`, `workflow-verification.json`, `release-provenance.json`, `release-checksums.sha256`, selected reviewer/package/action metadata files, and `release-candidate-bundle.zip`. The bundle is integrity-verifiable local candidate evidence; it does not publish a release, package, or Marketplace listing.

## Rollback Process

1. Stop promoting the affected stable ref.
2. Move or remove a major alias only under the repository's tag policy.
3. Publish corrective release notes if a public release already exists.
4. Keep the candidate gate and smoke workflow as the evidence trail.

## M160 Non-publication State

M160 leaves `released=false`. It creates no tag, no GitHub Release, no package publication, and no Marketplace publication.
