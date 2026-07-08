# Quickstart

VibeBench Arena is a local quality gate for Codex-first and AI-assisted coding projects.

## Install From Source

```bash
git clone git@github.com:wemby-1/vibebench-arena.git
cd vibebench-arena
python -m pip install -e ".[dev]"
python -m vibebench --help
python -m vibebench package-check
```

## Initialize VibeBench

```bash
python3 -m vibebench preflight
python3 -m vibebench preflight --json
python3 -m vibebench preflight --enforce-policy
python3 -m vibebench project-scan
python3 -m vibebench onboard
python3 -m vibebench onboard --json
python3 -m vibebench onboard --enforce-policy
python3 -m vibebench project-scan --json
python3 -m vibebench project-scan --enforce-policy
python3 -m vibebench init --profile auto
python3 -m vibebench config --check
python3 -m vibebench workflow-template
python3 -m vibebench workflow-template --write
python3 -m vibebench workflow-check
python3 -m vibebench ci --dry-run
python3 -m vibebench ci --preflight
python3 -m vibebench ci --preflight-policy
python3 -m vibebench ci --adoption
python3 -m vibebench ci --adoption-policy
python3 -m vibebench ci --onboard
python3 -m vibebench ci --onboard-policy
python3 -m vibebench ci --project-scan
python3 -m vibebench ci --project-scan-policy
python3 -m vibebench ci
```

`preflight` is the first safe read-only command and is report-only by default: it reuses project-scan, onboard, workflow-template preview, and workflow-check without creating config, runs, baselines, dependencies, or workflow files. `preflight --enforce-policy` evaluates `preflight.policy` as an explicit gate. `project-scan` is read-only inspection: it describes readiness signals, detects stacks, recommends an init profile, inspects config status, and never creates config, runs, baselines, dependencies, or workflow files. `project-scan --enforce-policy` evaluates `project_scan.policy`; `ci --project-scan` writes report-only `project-scan.json` and `project-scan.md`, while `ci --project-scan-policy` writes the same artifacts and enforces the policy. `onboard` is a read-only human adoption plan. `onboard --enforce-policy` evaluates whether that plan is acceptable under `onboard.policy`; `ci --onboard` writes report-only `onboard.json` and `onboard.md`, while `ci --onboard-policy` writes the same artifacts and fails CI only when the onboarding policy fails. `ci --preflight` writes report-only `preflight.json` and `preflight.md` run artifacts. `ci --preflight-policy` writes the same artifact names and fails CI when `preflight.policy` fails; `--skip-preflight` suppresses both modes. `ci --adoption` creates the full report-only adoption evidence pack with existing artifact names. `ci --adoption-policy` turns project-scan, onboard, workflow-check, and preflight into gates while keeping workflow-template preview/report-only; matching `--skip-*` flags suppress individual preset checks. `workflow-check` is also report-only by default; `workflow-check --enforce-policy` evaluates `workflow_check.policy`, `ci --workflow-check` writes report-only `workflow-check.json` and `workflow-check.md`, and `ci --workflow-check-policy` reuses those artifacts as an explicit gate. `--skip-workflow-check` suppresses both workflow-check modes. Default CI is unchanged unless one of those flags is passed.

```yaml
project_scan:
  policy:
    enabled: false
    require_config_valid: true
    require_supported_stack: true
    allowed_profiles: [generic, python, node, fullstack]
    fail_on_error_findings: true
    fail_on_warning_findings: false
    require_recommended_profile: false

onboard:
  policy:
    enabled: true
    fail_on_blockers: true
    fail_on_errors: true
    fail_on_warnings: false
    require_config: true
    require_ci_ready: false
```

`init --profile auto` creates `.vibebench/config.yaml` only. It can select `generic`, `python`, `node`, or `fullstack` from project markers, reusing existing `package.json` lint/test scripts when present. Init never installs dependencies, never overwrites config unless `--force` is provided, and does not create `.vibebench/runs`, `.vibebench/baselines`, workflows, or repository settings. `workflow-template` previews a conservative GitHub Actions workflow by default; `--ci-mode adoption` creates a report-only adoption CI template, `--ci-mode adoption-policy` creates a policy-gated adoption CI template, and `workflow-template --write` creates `.github/workflows/vibebench.yml` only after review. `workflow-check` validates an existing workflow read-only, reports detected CI modes (`default`, `adoption`, and `adoption-policy`), and warns about missing VibeBench CI shape or risky release/publish/deploy commands; `workflow-check --enforce-policy` turns those signals into a gate with `workflow_check.policy`. `ci --workflow-check` records report-only `workflow-check.json` and `workflow-check.md` evidence, while `ci --workflow-check-policy` reuses the same artifacts and fails only when workflow policy fails. `ci --workflow-template` creates `workflow-template.json`, `workflow-template.md`, and `workflow-template.yml` artifacts in the run directory only. These paths do not call GitHub, add credentials, enable Pages, publish packages, create releases, or modify workflows except explicit template `--write`.

## Inspect Effective Config

```bash
python -m vibebench config
python -m vibebench config --json
python -m vibebench config --validate
python -m vibebench config --check
python -m vibebench config --check --advice
python -m vibebench config --show-source
python3 -m vibebench init --profile auto --dry-run --json
python3 -m vibebench init --profile python
python3 -m vibebench init --profile generic
python3 -m vibebench init --profile node
python3 -m vibebench init --profile fullstack
python3 -m vibebench config --example
python3 -m vibebench config --write-example .vibebench/config.example.yaml
python3 -m vibebench config --path
python3 -m vibebench config --path --json
```

`vibebench config` shows the effective project, checks, gate, and risk settings. It uses `.vibebench/config.yaml` when present and falls back to built-in defaults when no config file exists. Use `python3 -m vibebench init --profile auto --dry-run --json` to preview stack-aware initialization, `python3 -m vibebench init --profile auto` to write config, and `--force` only when overwriting is intentional. Use `python3 -m vibebench config --example`, `python3 -m vibebench config --write-example .vibebench/config.example.yaml`, or `python3 -m vibebench config --path --json` for lower-level config inspection.

## Diagnose Project Readiness

```bash
python3 -m vibebench project-scan
python3 -m vibebench project-scan --summary-output /tmp/vibebench-scan.md
python -m vibebench doctor
python -m vibebench package-check
python -m vibebench package-check --json
python -m vibebench release-check
python -m vibebench release-checklist
```

`vibebench preflight` is the single read-only adoption summary; use `vibebench project-scan`, `onboard`, and `workflow-check` when you want deeper component detail. `vibebench project-scan` is the read-only onboarding check; use `--strict` when invalid config or malformed `package.json` should fail automation. `vibebench config --show` validates and summarizes the active `.vibebench/config.yaml`. Use `python -m vibebench config --show --json` for machine-readable config inspection. Use `python -m vibebench config --check`, `python -m vibebench config --check --advice`, or `python -m vibebench config --check --json --advice` for focused consistency diagnostics and optional repair guidance. Add `--write-json PATH` or `--write-summary PATH` to persist config check artifacts.

`vibebench package-check` validates local package metadata, imports, console script configuration, README/license references, and key docs without network access or PyPI publishing. Add `--write-json PATH` or `--write-summary PATH` to save package-check artifacts.

`vibebench doctor` is a lightweight environment check for Python, Git, `.vibebench/config.yaml`, configured command executables, and whether `.vibebench/runs/` is writable. It does not run your configured checks. Use `python -m vibebench doctor --strict` for a stronger release/CI preflight that also expects recent run artifacts such as the manifest, bundle, and report. Add `--advice` to explain how to fix failed checks without modifying files. Use `python -m vibebench doctor --json`, `python -m vibebench doctor --json --strict`, or `python -m vibebench doctor --json --strict --advice` for machine-readable diagnostics. Run `python -m vibebench release-check` before tagging or publishing to combine config, package readiness, strict doctor, latest run, manifest, artifacts, CI plan, and whitespace readiness checks. Use `python -m vibebench release-checklist` for a read-only target-version checklist that never creates tags, releases, or files. Add `--write-json PATH` and `--write-summary PATH` to persist release-check artifacts.

## Release-Readiness Flow

Before preparing a tag or GitHub Release, run a local release-readiness pass:

```bash
python -m vibebench ci --dry-run
python -m vibebench ci
python -m vibebench release-check
python -m vibebench release-checklist
python -m vibebench doctor --strict
python -m vibebench manifest --check
```

For v0.2.0 details, see [../RELEASE_NOTES_v0.2.0.md](../RELEASE_NOTES_v0.2.0.md). In GitHub Actions, download `vibebench-run-artifacts` from the workflow run to inspect reports, manifests, bundles, config-check summaries, package-check summaries, trend artifacts, and `release-check.json`/`release-check.md`.

When planning future Codex milestones, use the [Codex task template](codex-task-template.md) to keep prompts bounded, cheap, and auditable.

## Show Run History

```bash
python -m vibebench history
python -m vibebench latest
python -m vibebench latest --json
python -m vibebench latest --all-paths
python -m vibebench latest --all-paths --json
python -m vibebench latest --artifact report --path-only
python -m vibebench trend
```

`vibebench latest` prints the newest valid run and artifact availability. Use `--all-paths` to print every available artifact path after a local run or downloaded CI artifact, `--artifact NAME` to focus on one artifact, or `--path-only` when a script needs only one available path.

By default history and trend use the 10 newest valid runs with `metrics.json`. You can change the limit, inspect another runs directory, export trend data as JSON, write `.vibebench/runs/<timestamp>/trend.md`, or persist machine-readable `.vibebench/runs/<timestamp>/trend.json`:

```bash
python -m vibebench history --limit 5
python -m vibebench history --runs-dir .vibebench/runs
python -m vibebench trend --limit 3
python -m vibebench trend --json
python -m vibebench trend --write-summary
python -m vibebench trend --write-json
```

## Save A Baseline Run

```bash
python -m vibebench baseline
python -m vibebench baseline --set latest
python -m vibebench baseline --set <run-id>
python -m vibebench compare --baseline
```

The baseline command stores metadata in `.vibebench/baseline.json` and validates that the referenced run and `metrics.json` still exist.

## Clean Old Local Runs

```bash
python -m vibebench clean
python -m vibebench clean --keep 5
python -m vibebench clean --keep 5 --yes
```

`vibebench clean` is dry-run by default. It preserves the newest runs, only considers direct run directories containing `metrics.json`, and deletes nothing unless `--yes` is provided.

## Run Checks

```bash
python -m vibebench check
```

The default config runs:

```bash
pytest -q
ruff check .
```

`vibebench check` writes:

```text
.vibebench/runs/<timestamp>/metrics.json
.vibebench/runs/<timestamp>/check.log
```

## Configure Risk Rules

`vibebench check` uses the `risk` section in `.vibebench/config.yaml` when present. CLI behavior falls back to built-in defaults when this section is absent.

```yaml
risk:
  max_changed_files: 20
  max_patch_lines: 500
  forbidden_paths:
    - .env
    - .env.*
    - secrets/
  secret_like_paths:
    - "*secret*"
    - "*token*"
  lockfiles:
    - package-lock.json
    - pnpm-lock.yaml
    - yarn.lock
    - poetry.lock
    - uv.lock
    - Pipfile.lock
    - requirements.lock
  test_path_patterns:
    - tests/
    - test_*.py
    - "*_test.py"
```

See [risk-rules.md](risk-rules.md) for the full policy reference.

## Enforce A Quality Gate

```bash
python -m vibebench gate
python -m vibebench gate --write-gate-summary
python -m vibebench gate --min-score 90 --max-risk low
python -m vibebench gate --baseline --write-gate-summary
```

`vibebench gate` evaluates an existing run, exits nonzero on failure, and can write `.vibebench/runs/<timestamp>/gate-summary.md`. By default, it reads thresholds from `.vibebench/config.yaml` when a `gate` section is present; CLI flags override config values for one run.

## Run The Full CI Pipeline

```bash
python -m vibebench ci
```

`vibebench ci` runs check, gate, config check artifacts, report, PR comment, explain, export, badge, status block, trend summaries, run-index artifacts, compare artifacts, manifest, GitHub annotations, bundle, and GitHub summary. Check and gate decide the final exit code by default, but artifact steps are still attempted on failure so CI logs and artifacts remain useful. Add `--fail-on-regression` when CI should also fail on a compare verdict of `regressed`; `--skip-compare` skips that compare step and overrides the guard. Add `--json` for machine-readable stdout or `--json-output PATH` to save the same payload while keeping normal human output. Use `--dry-run` or `--plan` to inspect the CI step order and skip behavior without executing checks or writing artifacts. Add `--write-plan` to write `ci-plan.json` and `ci-plan.md` under `.vibebench/runs/<timestamp>_plan/`; those files then work with `artifacts`, `bundle`, `manifest`, and `latest --artifact ci-plan-json`.

A practical compare policy flow:

```bash
# Normal CI: compare artifacts are reporting-only
python -m vibebench ci

# Enforce compare regression failure once
python -m vibebench ci --fail-on-regression

# Enable the same guard persistently in .vibebench/config.yaml
```

```yaml
compare:
  fail_on_regression: true
```

```bash
# Temporarily disable the configured guard for one run
python -m vibebench ci --no-fail-on-regression
```

Useful options:

```bash
python -m vibebench ci --min-score 90 --max-risk low
python -m vibebench ci --skip-report --skip-pr-comment
python -m vibebench ci --skip-export
python -m vibebench ci --skip-badge
python -m vibebench ci --skip-status-block
python -m vibebench ci --skip-trend
python -m vibebench ci --skip-config-check
python -m vibebench ci --dry-run
python -m vibebench ci --dry-run --fail-on-regression
python -m vibebench ci --dry-run --json
python -m vibebench ci --dry-run --write-plan
python -m vibebench ci --dry-run --write-plan --json
python -m vibebench ci --json
python -m vibebench ci --fail-on-regression
python -m vibebench ci --no-fail-on-regression
python -m vibebench ci --json-output /tmp/vibebench-ci.json
python -m vibebench ci --skip-annotate
python -m vibebench ci --bundle-include-report-assets
python -m vibebench ci --run-dir .vibebench/runs/<run-id>
python -m vibebench release-check
python -m vibebench release-check --json
python -m vibebench release-check --write-json /tmp/release-check.json
python -m vibebench release-check --write-summary /tmp/release-check.md
```

## Generate A Static HTML Report

```bash
python -m vibebench report
```

This writes:

```text
.vibebench/runs/<timestamp>/report/index.html
```

## Generate A PR Comment

```bash
python -m vibebench pr-comment
```

This writes:

```text
.vibebench/runs/<timestamp>/pr-comment.md
```

The Markdown is designed to paste into a pull request, issue, or review thread.


## Explain A Run

```bash
python -m vibebench explain
```

This writes:

```text
.vibebench/runs/<timestamp>/explain.md
```

The explanation describes command failures, Git diff risk signals, known risk findings, and suggested next actions. Use `--run-dir` for a specific run, `--output` for a custom path, or `--no-write` to print only.

## Bundle Run Artifacts

```bash
python -m vibebench manifest
python -m vibebench bundle
```

This writes:

```text
.vibebench/runs/<timestamp>/vibebench-bundle.zip
```

Use `--run-dir` to bundle a specific run, `--output` for a custom zip path, `--include-report-assets` to include the full `report/` directory recursively, and `--strict` to fail if any standard artifact is missing.

## Export A Run

```bash
python -m vibebench export
python -m vibebench export --pretty
python -m vibebench export --format markdown
```

The JSON export is stable machine-readable output for dashboards, badges, external tools, and CI aggregation. Use `--output` to write a file. The one-shot CI command writes `.vibebench/runs/<timestamp>/export.json` by default.

## Generate A Badge Artifact

```bash
python -m vibebench badge
python -m vibebench badge --format markdown
python -m vibebench badge --format url
python -m vibebench badge --format markdown --label "VibeScore"
```

This writes a Shields.io-compatible endpoint JSON file to `.vibebench/runs/<timestamp>/badge.json` by default. Markdown output writes `badge.md` for README copy/paste, and URL output writes `badge-url.txt`. Use `--label` to customize the visible label and `--output` to write a custom path for the selected format. `vibebench ci` generates `badge.json` and `badge.md` by default.

## Generate A README Status Block

```bash
python -m vibebench status-block
python -m vibebench status-block --title "Project Quality"
python -m vibebench status-block --no-include-artifacts
python -m vibebench status-block --output README-status.md
python -m vibebench status-block --readme README.md --write-readme
python -m vibebench status-block --readme README.md --check-readme
```

This writes `.vibebench/runs/<timestamp>/status-block.md`, a copy-pasteable README section with the current status, VibeScore, risk level, diff size, findings, optional badge, and generated artifacts. To keep a README block stable, add `<!-- VIBEBENCH_STATUS_START -->` and `<!-- VIBEBENCH_STATUS_END -->` marker lines, then use `--write-readme` to replace only the marked content. Use `--check-readme` in read-only validation when you want to detect a stale committed status block without modifying files.

## Inspect Run Artifacts

```bash
python -m vibebench manifest
python -m vibebench run-index
python -m vibebench artifacts
python -m vibebench artifacts --json
python -m vibebench artifacts --run-dir .vibebench/runs/<run-id>
python -m vibebench artifacts --only-available
```

`vibebench manifest` writes `.vibebench/runs/<timestamp>/manifest.json`, a machine-readable index of run metadata and artifact availability. `vibebench manifest --check` verifies that an existing manifest has not drifted from the run directory.

`vibebench run-index` summarizes recent run directories and can persist `run-index.json` / `run-index.md` with `--write-json PATH` and `--write-summary PATH`. It is tolerant of partial or corrupt older run folders and marks them instead of crashing.

`vibebench compare` compares the latest valid run against the previous valid run and persists `compare.json` / `compare.md`. It is reporting-only by default, so `regressed` and `insufficient-data` verdicts still exit successfully. Add `--fail-on-regression` when automation should fail only for `regressed`. Use `--json` for pure JSON stdout, `--write-json PATH` / `--write-summary PATH` for custom files, and `--base-run-dir PATH` plus `--head-run-dir PATH` or `--base RUN_ID` plus `--head RUN_ID` for explicit selection.

This lists known run artifacts, including config check artifacts, run-index artifacts, and compare artifacts, with availability and file sizes. Missing optional artifacts do not fail the command unless `--strict` is used. JSON output is intended for lightweight automation and dashboards.

## Emit GitHub Actions Annotations

```bash
python -m vibebench annotate
python -m vibebench annotate --no-github-actions
```

Annotations surface command failures and risk findings in GitHub Actions logs. They are reporting-only and exit 0 when annotations are emitted; use `vibebench gate` for pass/fail decisions.

## Generate A GitHub Actions Summary

```bash
python -m vibebench gh-summary
```

In GitHub Actions, this appends to `GITHUB_STEP_SUMMARY`. Locally, it writes:

```text
.vibebench/runs/<timestamp>/github-step-summary.md
```

## Compare Runs

```bash
python -m vibebench compare
python -m vibebench compare --fail-on-regression
```

This compares the latest run with the previous run and writes:

```text
.vibebench/runs/<latest-timestamp>/compare.json
.vibebench/runs/<latest-timestamp>/compare.md

`vibebench latest --artifact compare-json --path-only` and `vibebench latest --artifact compare-md --path-only` return the latest comparison artifact paths.

```

`--fail-on-regression` turns compare into an opt-in guard: it exits non-zero for `regressed`, but passes for `improved`, `stable`, `mixed`, and `insufficient-data`.

You can also compare explicit run directories:

```bash
python -m vibebench compare --base-run .vibebench/runs/<base> --current-run .vibebench/runs/<current>
```

## Try The Risk Demo

From the VibeBench repository:

```bash
python examples/risk-demo/create_risky_repo.py
cd /tmp/vibebench-risk-demo
python -m vibebench check
python -m vibebench report
python -m vibebench pr-comment
python -m vibebench explain
python -m vibebench bundle
```

The risk demo intentionally creates critical findings, so `vibebench check` is expected to exit non-zero.


## CI Artifacts

VibeBench Arena dogfoods itself in this repository's CI. The workflow runs `vibebench ci`, which enforces the policy in `.vibebench/config.yaml`, generates `config-check.json`, `config-check.md`, `explain.md`, writes `export.json`, `badge.json`, `badge.md`, `status-block.md`, `trend.md`, `trend.json`, `run-index.json`, `run-index.md`, `compare.json`, and `compare.md`, bundles run artifacts, emits GitHub annotations, writes the GitHub Actions job summary, and uploads selected `.vibebench/runs` outputs as the `vibebench-run-artifacts` artifact for review.

## Generated Files

Generated run artifacts are local outputs and should not be committed:

```text
.vibebench/runs/<timestamp>/
```
