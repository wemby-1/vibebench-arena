# VibeBench Preflight

- Status: needs_attention
- Strict: false
- Detected stack: python
- Requested profile: auto
- Resolved profile: python
- Config status: valid
- Workflow status: passed (1 discovered)
- Workflow template preview: `<reference-project>/.github/workflows/vibebench.yml`

## Recommendations

- Required CI modes: adoption-policy
- Missing required CI modes: none

- Validate the existing VibeBench config before CI adoption.
- Review existing workflows with workflow-check before relying on them.
- Run ci --dry-run before the first full ci execution.

## Suggested Command Sequence

- `python3 -m vibebench config --check`
- `python3 -m vibebench workflow-check --strict`
- `python3 -m vibebench ci --dry-run`
- `python3 -m vibebench ci`

## Policy

- Status: passed
- Source: config
- Enforced: true
- Default preflight remains report-only unless enforcement is requested.

| Severity | Finding | Rule | Recommendation |
| --- | --- | --- | --- |
| info | Policy passed | none | No action needed. |
