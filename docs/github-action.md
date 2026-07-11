# VibeBench GitHub Action

This document is the reusable Action contract for the repository-root composite action in `action.yml`. The Action is prepared for v0.4.0 release-candidate review, but v0.4.0 is not released yet and the Action has not been published to GitHub Marketplace.

## Presets

| Preset | Purpose | Default upload behavior |
| --- | --- | --- |
| `minimal` | First-adoption check with the smallest evidence footprint. | `false` |
| `strict` | Policy-oriented adoption check with stricter workflow readiness. | `true` in generated snippets |
| `proof` | Strict check plus proof-oriented bundle and manifest evidence. | `true` in generated snippets |

The real Action smoke workflow must pass all three presets: `minimal`, `strict`, and `proof`. Remote GitHub Actions status must be reviewed separately after pushing the candidate.

The separate `VibeBench release candidate` workflow validates package, reusable Action, public evidence, docs, non-publication state, and the deterministic candidate evidence bundle. It does not replace `Action smoke`; both workflows should be green before release work continues. The bundle's `workflow-verification.json` is local structural evidence, not a claim that hosted workflow runs passed.

## Input Contract

| Input | Default | Contract |
| --- | --- | --- |
| `preset` | `minimal` | One of `minimal`, `strict`, or `proof`. |
| `config` | empty | Optional config file path inside `GITHUB_WORKSPACE`. |
| `working-directory` | `.` | Directory inside `GITHUB_WORKSPACE` to evaluate. |
| `fail-on` | `quality` | Comma-separated policy: `quality`, `regression`, `quality,regression`, or `none`. |
| `required-mode` | empty | Optional required VibeBench CI mode, such as `adoption-policy`. |
| `upload-artifacts` | `false` | Whether to upload the allowlisted evidence paths. |
| `artifact-name` | `vibebench-evidence` | Name for optional uploaded evidence. |
| `retention-days` | `14` | Artifact retention days, bounded by GitHub runner limits. |
| `python-command` | `python3` | Python command parsed without a shell. |

Paths supplied by the caller must resolve inside `GITHUB_WORKSPACE`. The Action installs VibeBench from `GITHUB_ACTION_PATH`, which is the checked-out Action source, not the caller repository.

## Output Contract

| Output | Meaning |
| --- | --- |
| `status` | VibeBench result status, or `infrastructure-failed`. |
| `score` | VibeScore when `metrics.json` is available. |
| `risk` | Risk level when `metrics.json` is available. |
| `run-id` | Created run directory name. |
| `run-dir` | Workspace-relative run directory path. |
| `summary-path` | GitHub Step Summary or generated summary path. |
| `manifest-path` | Workspace-relative `manifest.json` path. |
| `bundle-path` | Workspace-relative bundle path. |
| `proof-path` | Proof artifact path when generated. |
| `artifact-count` | Count of intended evidence files eligible for upload. |

## Exit-code Semantics

- `0`: selected preset completed and policy did not fail.
- `1`: VibeBench quality or regression policy failed.
- `2`: Action input validation or infrastructure failed.

## Artifact Behavior

The Action uploads artifacts only when `upload-artifacts: true`. Upload paths are collected from the generated VibeBench evidence allowlist, not from arbitrary repository files. Optional artifact upload requires `actions: read` for normal execution and GitHub's artifact service; no repository write permission is required for the Action itself.

## Required Permissions

Normal use:

```yaml
permissions:
  contents: read
```

Optional PR commenting or repository-specific workflows may need additional permissions outside this Action contract. Do not grant broader permissions just to run the reusable Action.

## Static-site Applicability

Static-site checks and proof/demo evidence are local files. The Action can generate evidence that is later uploaded as CI artifacts, but it does not enable GitHub Pages, deploy a site, create a release, publish a package, or publish a Marketplace listing.

## Examples

Development preview, useful before the v0.4.0 release exists:

```yaml
- uses: wemby-1/vibebench-arena@main
  with:
    preset: minimal
```

Post-release stable example, valid only after the maintainer creates the tag:

```yaml
- uses: wemby-1/vibebench-arena@v0.4.0
  with:
    preset: strict
    upload-artifacts: true
```

Major alias example, valid only if maintainers intentionally move `v0` after release:

```yaml
- uses: wemby-1/vibebench-arena@v0
  with:
    preset: proof
```

Strongest immutability:

```yaml
- uses: wemby-1/vibebench-arena@FULL_COMMIT_SHA
  with:
    preset: proof
```

## Security and Trust Boundary

- `@main` is a development preview reference, not a stable production release.
- Pin to a full commit SHA when immutability matters most.
- Pin to `v0.4.0` or `v0` only after the corresponding tag exists.
- Caller paths stay inside `GITHUB_WORKSPACE`.
- Action source comes from `GITHUB_ACTION_PATH`.
- The Action does not call the GitHub API, publish packages, create tags, create GitHub Releases, or publish to Marketplace.
- The release-candidate evidence bundle is candidate evidence only; it preserves `released=false` and does not publish anything.

## Unsupported and Non-claims

The Action does not prove semantic correctness, replace code review, certify security or compliance, guarantee benchmark dominance, prove adoption, or claim customers, funding, stars, revenue, or product-market fit.
