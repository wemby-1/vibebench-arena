# Quickstart

VibeBench Arena is a local-first quality gate for Codex-first and AI-assisted coding projects. This page is the shortest practical path from a repository checkout to reviewable evidence without turning the guide into a command dump.

If you are evaluating the project quickly for a review, adoption discussion, or technical demo, start with the [showcase page](showcase.md) and [showcase demo kit](../examples/showcase-artifacts/README.md), then return here for the practical setup path.

## 1. Install And Run Once

```bash
git clone git@github.com:wemby-1/vibebench-arena.git
cd vibebench-arena
python3 -m pip install -e ".[dev]"
python3 -m vibebench ci
```

`vibebench ci` runs the local quality pipeline and writes a timestamped directory under:

```text
.vibebench/runs/<timestamp>/
```

The exact steps depend on config, but a normal run can include checks, gate evaluation, report files, summaries, a manifest, release-check evidence, compare/trend outputs, annotations, and a bundle. The check and gate decide the pass/fail verdict; artifact steps are still useful when a run fails because they explain what happened.

To preview the pipeline before running checks or writing run artifacts:

```bash
python3 -m vibebench ci --dry-run --json
```

## 2. Inspect The Outputs

```bash
python3 -m vibebench latest --all-paths
python3 -m vibebench artifacts --json
```

Start with these files:

- `metrics.json`: score, risk level, command results, diff size, and finding counts.
- `manifest.json`: machine-readable inventory of the run and artifact availability.
- `github-step-summary.md`: a concise CI-friendly human summary.
- `report/index.html`: a static local report when report generation is enabled.
- `pr-comment.md` and `explain.md`: reviewer-facing summaries when enabled.
- `release-check.json` / `release-check.md`: local release-readiness evidence when present.
- `compare.json` / `compare.md` and `trend.json` / `trend.md`: run movement and recent history when available.

Generated run artifacts are local outputs and should not be committed.

## 3. Bundle Evidence For Review

```bash
python3 -m vibebench bundle
python3 -m vibebench latest --artifact bundle --path-only
```

`bundle` packages the latest run into `vibebench-bundle.zip`. Use it when a teammate, reviewer, or evaluator needs the evidence packet without rerunning your local environment.

For a broader browseable review package:

```bash
python3 -m vibebench evidence-room --output-dir /tmp/vibebench-evidence-room --zip
python3 -m vibebench evidence-room --verify /tmp/vibebench-evidence-room
```

Open `index.html` first, then inspect `share-check.md` if you are preparing to share the package outside your local machine.

For a polished public demo portal from a run or the committed proof packet:

```bash
python3 -m vibebench public-demo \
  --proof-packet examples/showcase-artifacts/public-proof \
  --output-dir /tmp/vibebench-demo
```

Open `/tmp/vibebench-demo/index.html` directly. The portal is deterministic, self-contained, and designed for reviewers who should not need to learn the whole CLI before inspecting the evidence.

The same committed demo is published as a static GitHub Pages site at
[`https://wemby-1.github.io/vibebench-arena/`](https://wemby-1.github.io/vibebench-arena/).
To reproduce the Pages output locally:

```bash
python3 scripts/build_public_demo.py --check
python3 scripts/build_pages_site.py --output-dir /tmp/vibebench-pages-site
python3 scripts/build_pages_site.py --check
```

The Pages site is a static presentation of committed evidence. It is not a
hosted scanning service and does not add new claims beyond the artifacts it
publishes.

## 4. Check Adoption Readiness

```bash
python3 -m vibebench adoption-ready --json
python3 -m vibebench preflight --json
python3 -m vibebench workflow-check
```

- `adoption-ready --json` gives a compact machine-readable adoption answer. It is read-only unless you explicitly pass output paths.
- `preflight --json` is the safest read-only setup check. It summarizes project scan, onboarding, workflow-template preview, and workflow-check signals without creating config, runs, baselines, dependencies, or workflow files.
- `workflow-check` validates existing workflow files read-only and reports detected VibeBench CI modes such as `default`, `adoption`, and `adoption-policy`.

When you want these signals retained as CI artifacts, opt in explicitly:

```bash
python3 -m vibebench ci --adoption
python3 -m vibebench ci --adoption-policy
python3 -m vibebench ci --workflow-check
python3 -m vibebench ci --preflight
```

`ci --adoption` is report-only and writes adoption evidence such as `project-scan.json`, `onboard.json`, `workflow-check.json`, and `preflight.json` when enabled. `ci --adoption-policy` turns policy-capable adoption checks into gates while keeping workflow-template preview/report-only. Default CI behavior is unchanged unless you pass one of these flags or configure the matching policy.

## 5. Check Workflow CI Mode

```bash
python3 -m vibebench workflow-template
python3 -m vibebench workflow-template --ci-mode adoption
python3 -m vibebench workflow-template --ci-mode adoption-policy
python3 -m vibebench workflow-check --require-ci-mode adoption-policy
```

`workflow-template` previews a conservative GitHub Actions workflow. It writes `.github/workflows/vibebench.yml` only when `--write` is passed, and it does not call GitHub, enable Pages, add credentials, publish packages, or create releases.

`workflow-check --require-ci-mode MODE` is useful when a team expects a specific generated workflow shape. In CI, `--workflow-check-require-ci-mode MODE` records the expectation while keeping workflow-check report-only unless policy enforcement is also enabled.

## 6. Check Release Readiness

```bash
python3 -m vibebench release-check --json
python3 -m vibebench doctor --strict
python3 -m vibebench manifest --check
```

- `release-check --json` combines config, package readiness, strict doctor, latest run, manifest, artifacts, CI plan, and whitespace readiness into a local release-readiness report.
- `doctor --strict` confirms the environment and expected artifacts are healthy enough for stricter CI/release-style use.
- `manifest --check` verifies that an existing manifest still matches the run directory.

These commands stay local. They do not bump versions, create tags, publish packages, upload files, call the GitHub API, or create a GitHub Release.

## 7. Optional Regression And Metrics Checks

```bash
python3 -m vibebench metrics-check
python3 -m vibebench regression-check
python3 -m vibebench compare --json
```

`metrics-check` validates that a run has usable score/risk data. `compare` explains movement between runs and is reporting-only unless regression failure is explicitly enabled. `regression-check` is the higher-level score/risk gate against a selected baseline; it is not a benchmark certification.

For stable adoption gates, prefer pinned baselines over automatic previous-run inference:

```bash
python3 -m vibebench ci --json
python3 -m vibebench baseline --promote-latest --label stable --dry-run --json
python3 -m vibebench baseline --promote-latest --label stable
python3 -m vibebench baseline --show --label stable --json
```

CI does not auto-promote baselines.

## 8. Before Sharing Artifacts

```bash
python3 -m vibebench share-check PATH
python3 -m vibebench share-check PATH --json
```

Use `share-check` before sharing an evidence room, public demo, proof packet, static preview, bundle, directory, or zip. It is a local pre-sharing aid, not a security certification, third-party audit, or guarantee. Manually review artifacts before publishing them.

For broader rollout guidance, see [adoption](adoption.md). For artifact explanations, see [artifact gallery](artifact-gallery.md). For project-maintained boundaries, see the [Trust Center](trust-center.md).
