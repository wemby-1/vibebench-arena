# v0.4.0 Release Checklist

This checklist tracks the v0.4.0 release candidate. M160 prepares the candidate and leaves Release and Post-release items incomplete.

Candidate state:

- `released=false`
- no tag was created
- no GitHub Release was created
- no package publication occurred
- no Marketplace publication occurred
- remote GitHub Actions status must be reviewed separately after push

Passing this checklist is readiness evidence, not a claim of adoption, funding, stars, customers, revenue, benchmark dominance, security certification, or a guarantee that generated code is correct or safe.

## Pre-release

- [ ] Run `python3 -m vibebench release-check --candidate`.
- [ ] Run `python3 -m vibebench release-check --candidate --json`.
- [ ] Generate `release-candidate.json` with `--write-json`.
- [ ] Generate `release-candidate.md` with `--write-summary`.
- [ ] Generate `python3 -m vibebench release-bundle --candidate`.
- [ ] Verify the bundle with `python3 -m vibebench release-bundle --candidate --check`.
- [ ] Verify `release-checksums.sha256` against the bundle payload files.
- [ ] Confirm `release-candidate-bundle.zip` contains only allowlisted relative paths.
- [ ] Run full tests with `python3 -m pytest -q`.
- [ ] Confirm the hosted Action smoke matrix passed `minimal`, `strict`, and `proof`.
- [ ] Verify Pages deployment status after push.
- [ ] Run public demo/proof checks.
- [ ] Run package build/check if package publication is being considered.
- [ ] Confirm version alignment across `pyproject.toml` and `vibebench/__init__.py`.
- [ ] Run docs/link checks.
- [ ] Run secret/leak scans and unsupported-claim scans.
- [ ] Confirm repository status is clean.
- [ ] Confirm hosted `VibeBench release candidate` is green after push.
- [ ] Download and inspect `vibebench-v0.4.0-release-candidate`.
- [ ] Confirm hosted `Action smoke` is green for `minimal`, `strict`, and `proof`.

## Release

- [ ] Final version decision approved.
- [ ] Annotated `v0.4.0` tag created.
- [ ] GitHub Release drafted and published.
- [ ] Release notes attached or copied.
- [ ] Package publishing completed only if intentionally approved.
- [ ] Major alias tag policy decided.
- [ ] Marketplace draft/publication decision made.

M160 leaves every Release item incomplete.

M161 adds the hosted pre-release candidate gate only. It still leaves every Release item incomplete and keeps `released=false`.

M162 adds a deterministic candidate evidence bundle only. It keeps `released=false`,
does not create a tag, does not create a GitHub Release, does not publish a
package, and does not publish to GitHub Marketplace.

## Post-release

- [ ] Install from a clean environment.
- [ ] Consume the Action from a separate repository.
- [ ] Verify stable ref behavior.
- [ ] Verify Pages link.
- [ ] Verify downloadable artifacts.
- [ ] Confirm rollback procedure.
- [ ] Monitor issues.

M160 leaves every Post-release item incomplete.
