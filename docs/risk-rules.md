# Risk Rules

VibeBench analyzes the current uncommitted Git diff against `HEAD`. It is designed as a local pre-commit or pre-push quality gate.

## Configured Forbidden Paths

Configured in `.vibebench/config.yaml`:

```yaml
risk_rules:
  forbidden_paths:
    - .env
    - .env.*
    - secrets/
```

If a changed path matches one of these rules, VibeBench emits `forbidden_paths_touched` with critical severity.

## Secret-Like Paths

VibeBench flags paths containing case-insensitive keywords such as `secret`, `token`, `credential`, `private_key`, `api_key`, `apikey`, `password`, or `passwd`.

This emits `secret_like_files_touched` with high severity. It is path-based; it does not scan file contents in v0.1.0.

## Deleted Tests

Deleted files that look like tests emit `tests_deleted` with high severity when `warn_if_tests_deleted` is enabled.

Recognized examples include:

- `tests/`
- `test_*.py`
- `*_test.py`
- `__tests__/`
- `*.test.ts`, `*.test.tsx`, `*.spec.ts`, `*.spec.tsx`

## Changed Tests

Changed test files emit `test_files_changed` with info severity. This does not reduce score, but it helps reviewers see that tests were touched.

## Lockfiles

Changed lockfiles emit `lockfiles_changed` with warning severity when `warn_if_lockfiles_changed` is enabled.

Recognized lockfiles include:

- `package-lock.json`
- `pnpm-lock.yaml`
- `yarn.lock`
- `poetry.lock`
- `uv.lock`
- `Pipfile.lock`
- `requirements.lock`

## Large Patch

If total added plus deleted lines exceeds `large_patch_lines`, VibeBench emits `large_patch` with warning severity.

## Too Many Files Changed

If more than 20 files changed, VibeBench emits `many_files_changed` with warning severity.

## Scoring Impact

VibeScore starts at 100.

- failed command: -40
- critical finding: -30
- high finding: -20
- warning finding: -8
- info finding: no score impact

The score is clamped to `0..100`.

Risk levels:

- `85-100`: low
- `65-84`: medium
- `40-64`: high
- `0-39`: critical

Overall status fails if any configured command fails or any critical finding exists.

## Limitations

- VibeBench v0.1.0 analyzes uncommitted working-tree changes against `HEAD`.
- Secret-like detection is path-based, not content-based.
- Risk rules can produce false positives and should support, not replace, human review.
- Generated reports may include paths and command output snippets; review artifacts before sharing outside your team.
