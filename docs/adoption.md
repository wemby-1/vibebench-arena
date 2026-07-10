# Adopt VibeBench Arena Safely

VibeBench Arena helps individuals and teams make AI-assisted coding work reviewable. Treat it as a local-first quality gate and evidence layer, not as an autonomous deploy bot.

## Adoption Principles

- Start local.
- Inspect artifacts before trusting them.
- Keep AI-generated work reviewable.
- Prefer reproducible commands over hand-wavy claims.
- Keep human judgment in the loop.

## First 30 Minutes

For an external review or team kickoff, the [showcase page](showcase.md) and [showcase demo kit](../examples/showcase-artifacts/README.md) provide a 5-minute path before the fuller adoption rollout below.

```bash
python3 -m vibebench ci --dry-run --json
python3 -m vibebench ci
python3 -m vibebench latest --all-paths
python3 -m vibebench adoption-ready --json
python3 -m vibebench release-check --json
```

This gives a new team enough to see the local gate, inspect the produced evidence, and understand whether the repository is moving toward broader adoption or release readiness.

## How A Project Adopts VibeBench

1. Run `ci --dry-run --json` so maintainers can see the planned pipeline without creating run artifacts.
2. Run `preflight --json` to inspect setup signals without creating config, workflows, dependency files, runs, or baselines.
3. Run `init --profile auto --dry-run --json` to preview the config VibeBench would create.
4. Run `init --profile auto` only when you are ready to add `.vibebench/config.yaml`.
5. Preview workflow integration with `workflow-template`, then write a workflow only after review with `workflow-template --write`.
6. Run `workflow-check` to verify the existing workflow shape.
7. Run `ci`, inspect artifacts, and decide whether the project should stay report-only or become policy-gated.

`init` writes config only. It does not install dependencies, overwrite config without `--force`, create run/baseline outputs, call GitHub, publish packages, or create releases.

## What Adoption-Ready Means

`adoption-ready` is a compact read-only adoption workflow readiness report. It is intended to answer whether a repository has enough visible setup, workflow, environment, and release-readiness evidence for a team to start relying on VibeBench.

It does not mean:

- the code is correct
- the repo is safe to publish automatically
- the project has external certification
- human review can be skipped
- adoption will succeed organizationally

Use it as an evidence-backed readiness signal, not as a guarantee.

## How The Readiness Checks Fit Together

Use the checks as a ladder, not as a single magic score:

- `project-scan`: read-only project inspection; detects stack signals, config status, and recommended init profile.
- `onboard`: read-only human adoption plan; surfaces blockers, warnings, and suggested next actions.
- `preflight`: the safest read-only entry point; combines setup, onboarding, workflow-template preview, and workflow-check signals.
- `workflow-check`: verifies whether existing workflows match expected VibeBench CI modes.
- `adoption-ready`: combines workflow, doctor, and release-readiness signals into one compact adoption answer.
- `release-check`: records local release-readiness evidence without tagging, publishing, or creating a GitHub Release.
- `doctor --strict`: verifies the local environment plus expected artifacts for stricter CI/release-style confidence.

When enabled in CI, these checks can leave evidence such as `project-scan.json`, `onboard.md`, `preflight.json`, `workflow-check.md`, and `release-check.md` inside the run directory.

## Workflow CI Mode Readiness

VibeBench workflow checks can detect generated CI modes:

- `default`: the normal VibeBench CI gate.
- `adoption`: report-only adoption evidence in addition to the normal run.
- `adoption-policy`: adoption evidence with policy-capable checks enforced.

Useful commands:

```bash
python3 -m vibebench workflow-template --ci-mode adoption
python3 -m vibebench workflow-template --ci-mode adoption-policy
python3 -m vibebench workflow-check
python3 -m vibebench workflow-check --require-ci-mode adoption-policy
```

`workflow-template` is preview-only unless `--write` is passed. `workflow-check` is read-only by default and does not modify workflow files.

In CI, `ci --workflow-check-require-ci-mode MODE` records required-mode expectations while remaining report-only unless workflow-check policy enforcement is enabled. `workflow_check.policy.required_ci_modes` can enforce required modes when `workflow-check --enforce-policy`, `ci --workflow-check-policy`, or `ci --adoption-policy` is used.

## Report-Only Versus Policy-Gated Modes

Report-only mode records evidence but does not fail the run for adoption findings:

```bash
python3 -m vibebench ci --preflight
python3 -m vibebench ci --workflow-check
python3 -m vibebench ci --adoption
```

Policy-gated mode writes the same artifact names but allows configured adoption checks to fail CI:

```bash
python3 -m vibebench preflight --enforce-policy
python3 -m vibebench workflow-check --enforce-policy
python3 -m vibebench ci --preflight-policy
python3 -m vibebench ci --workflow-check-policy
python3 -m vibebench ci --adoption-policy
```

This split is deliberate. Teams can collect evidence first, discuss what it means, then opt into gates once the checks match their workflow.

## Suggested One-Week Pilot

1. Pick one repository, one maintainer, and one AI coding workflow.
2. Run VibeBench on small changes only.
3. Compare a VibeBench evidence packet against the team's normal review process.
4. Decide which artifacts reviewers actually use.
5. Add workflow mode requirements only after the team agrees on the expected CI shape.
6. Move from report-only to policy-gated checks only after the evidence is understandable.

## Adoption Checklist

- Local commands pass.
- Generated artifacts are understandable to reviewers.
- The team knows where to find `metrics.json`, `manifest.json`, summaries, and bundles.
- Workflow mode expectations are explicit.
- No credentials or sensitive local paths are committed.
- Publishing, tagging, release creation, and uploads remain separate explicit actions.
- The team understands that VibeBench supports review; it does not replace review.

For a shorter command path, see [quickstart](quickstart.md). For artifact explanations, see [artifact gallery](artifact-gallery.md). For project-maintained boundaries around artifacts, local-first behavior, and claims, see the [Trust Center](trust-center.md).
