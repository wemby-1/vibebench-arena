# Risk Rules

VibeBench analyzes the current uncommitted Git diff against `HEAD`. It is designed as a local pre-commit or pre-push quality gate.

Risk detection is configurable in `.vibebench/config.yaml` with the `risk` section. If `risk` is absent, VibeBench falls back to the built-in defaults. The older `risk_rules` section remains supported for backward compatibility.

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
    - "*credential*"
    - "*credentials*"
    - "*private_key*"
    - "*api_key*"
    - "*apikey*"
    - "*password*"
    - "*passwd*"
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
    - __tests__/
    - "*.test.ts"
    - "*.test.tsx"
    - "*.spec.ts"
    - "*.spec.tsx"
```

## Forbidden Paths

If a changed path matches `risk.forbidden_paths`, VibeBench emits `forbidden_paths_touched` with critical severity. Exact paths, simple glob patterns, and directory prefixes ending in `/` are supported.

## Secret-Like Paths

If a changed path matches `risk.secret_like_paths`, VibeBench emits `secret_like_files_touched` with high severity. Matching is path-based and case-insensitive; VibeBench does not scan file contents.

## Deleted Tests

Deleted files matching `risk.test_path_patterns` emit `tests_deleted` with high severity. The legacy `risk_rules.warn_if_tests_deleted` option can still disable this finding for older configs.

## Changed Tests

Changed files matching `risk.test_path_patterns` emit `test_files_changed` with info severity. This does not reduce score, but it helps reviewers see that tests were touched.

## Lockfiles

Changed files matching `risk.lockfiles` emit `lockfiles_changed` with warning severity. The legacy `risk_rules.warn_if_lockfiles_changed` option can still disable this finding for older configs.

## Large Patch

If total added plus deleted lines exceeds `risk.max_patch_lines`, VibeBench emits `large_patch` with warning severity.

## Too Many Files Changed

If changed file count exceeds `risk.max_changed_files`, VibeBench emits `many_files_changed` with warning severity.

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
