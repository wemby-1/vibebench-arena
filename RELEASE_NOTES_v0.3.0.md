# VibeBench Arena v0.3.0

GitHub-native review workflows, richer artifacts, and safer release readiness for local-first AI-assisted coding.

## Release Status

v0.3.0 is the current stable release. Package metadata, the annotated v0.3.0 tag, GitHub Release, and release-readiness checks are aligned.

## Highlights

- GitHub PR comment posting can publish or update generated VibeBench summaries without creating duplicate comments.
- GitHub Actions integration now covers PR comment posting, annotations, summaries, artifacts, and the full VibeBench CI flow.
- Package readiness checks validate local packaging shape without publishing to PyPI.
- Run index, compare, package-check, config-check, release-check, and bundle artifacts make CI output easier to inspect and download.
- Compare regression blocking is opt-in from the CLI or config, so teams can choose when regressions should fail CI.
- Config initialization is easier to inspect before writing files, including path inspection, examples, and dry-run output.

## New Commands And Command Improvements

- `python -m vibebench pr-comment --post` posts or updates PR comments from generated Markdown.
- `python -m vibebench package-check` checks package metadata, imports, console script configuration, README/license references, and key docs.
- `python -m vibebench run-index` summarizes valid, partial, and damaged run directories.
- `python -m vibebench compare --fail-on-regression` can fail on a regressed compare verdict when explicitly requested.
- `python -m vibebench ci --fail-on-regression` applies the same regression guard inside the CI pipeline.
- `python3 -m vibebench config --example` prints a starter config.
- `python3 -m vibebench config --write-example PATH` writes a starter config copy.
- `python3 -m vibebench config --init` initializes `.vibebench/config.yaml` safely.
- `python3 -m vibebench config --path` prints the expected config path.
- `python3 -m vibebench config --init --dry-run` previews config initialization without creating or modifying files.
- `--json` support on these inspection and readiness commands keeps automation output machine-readable.

## GitHub Actions And PR Comments

v0.3.0 is focused on making VibeBench useful inside normal GitHub review loops. The generated workflow can run VibeBench CI, upload `vibebench-run-artifacts`, emit annotations and summaries, and post/update a PR comment using the standard GitHub Actions token. Local generation and copy-paste review workflows remain supported.

## Artifact And Release Readiness

v0.3.0 strengthens the artifact loop:

- `package-check.json` and `package-check.md` capture package readiness.
- `run-index.json` and `run-index.md` make run history inspectable even when some run directories are incomplete.
- `compare.json` and `compare.md` summarize latest-vs-previous run movement.
- `release-check` and strict `doctor` checks provide read-only pre-release confidence.
- `vibebench ci` continues to generate config-check, package-check, report, comment, explain, export, badge, status block, trend, run-index, compare, manifest, release-check, bundle, and summary artifacts.

## Configuration UX

Config workflows are safer and more transparent:

- `config --init` creates a starter `.vibebench/config.yaml` and refuses to overwrite by default.
- `config --init --force` overwrites only when explicitly requested.
- `config --init --dry-run` reports the project root, config path, whether the config exists, whether a real run would write, and whether `--force` is active.
- `config --init --dry-run --json` prints pure JSON for automation.
- `config --path --json`, `config --show --json`, and `config --check --json` remain valid machine-readable inspection paths.
- `compare.fail_on_regression` can persist an opt-in regression policy in `.vibebench/config.yaml`.

## Compatibility And Safety Notes

- v0.3.0 remains local-first and Codex-first.
- Existing v0.2.0 workflows should continue to work.
- Compare regression failure remains opt-in; reporting-only compare behavior is still the default.
- `release-check` and strict `doctor` are read-only readiness checks.
- Package-check does not publish to PyPI and does not require network access.
- PR comment posting is intended for GitHub Actions token based workflows and should not require extra secrets.

## Verification Checklist

For future release maintenance, verify:

- `python3 -m ruff check .`
- `python3 -m pytest -q`
- `python3 -m vibebench release-check`
- `python3 -m vibebench doctor --strict`
- `python3 -m vibebench ci`
- GitHub Actions is green on `main`.
- Downloaded `vibebench-run-artifacts` include expected release, package, run-index, compare, manifest, bundle, and summary artifacts.

## Upgrade Notes From v0.2.0

- Existing `.vibebench/config.yaml` files should remain compatible.
- Teams that want CI to fail on compare regressions can use `python -m vibebench ci --fail-on-regression` or set `compare.fail_on_regression: true`.
- Teams that only want compare reporting can keep the default behavior or use `--no-fail-on-regression` to override a configured guard for one run.
- Use `python3 -m vibebench config --init --dry-run` before initializing config in an existing repository.
- Use `python -m vibebench package-check` before release work to catch local packaging/documentation readiness issues.

## Known Limitations

- v0.3.0 is not a hosted dashboard release.
- v0.3.0 does not publish the project to PyPI.
- v0.3.0 does not add a multi-agent arena tournament system.
- PR comment posting depends on GitHub Actions context and permissions when run in CI.
- VibeBench remains a quality gate and artifact generator; it does not replace human review.

## Suggested Release Steps

1. Run `python3 -m vibebench release-check`.
2. Run `python3 -m vibebench doctor --strict`.
3. Confirm GitHub Actions is green on `main`.
4. Review this release note and `CHANGELOG.md`.
5. Update the GitHub Release page body manually if this file changes after publication.
