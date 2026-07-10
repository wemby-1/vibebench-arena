# VibeBench Workflow Check

- Status: passed
- Workflow path: `<reference-project>/.github/workflows/ci.yml`
- Strict: false
- Detected CI modes: adoption-policy
- Passed: 10
- Warnings: 2
- Failed: 0
- Required CI modes: adoption-policy (missing: none)

## Checks

| Status | Severity | Check | Message |
| --- | --- | --- | --- |
| passed | info | Workflow file exists | Workflow file was found. |
| passed | info | Workflow file is readable | Workflow file was read successfully. |
| passed | info | Workflow file is not empty | Workflow file has content. |
| passed | info | Workflow has a name | Workflow contains name:. |
| passed | info | Workflow has triggers | Workflow contains on:. |
| passed | info | Workflow has jobs | Workflow contains jobs:. |
| passed | info | Workflow has a runner | Workflow contains runs-on:. |
| passed | info | Workflow has steps | Workflow contains steps:. |
| passed | info | Workflow runs VibeBench CI | Workflow includes a VibeBench CI invocation. |
| warning | warning | Workflow action is not pinned to a full commit SHA | Workflow uses 'actions/checkout@v4' without a full commit SHA pin. |
| warning | warning | Workflow action is not pinned to a full commit SHA | Workflow uses 'actions/setup-python@v5' without a full commit SHA pin. |
| passed | info | Required CI modes are present | Required CI modes: adoption-policy. Missing: none. |

## Findings

| Severity | Finding | Advice |
| --- | --- | --- |
| warning | Workflow action is not pinned to a full commit SHA | Pin third-party actions to reviewed commit SHAs, or allow an explicit prefix in workflow_check.policy.allowed_action_prefixes. |
| warning | Workflow action is not pinned to a full commit SHA | Pin third-party actions to reviewed commit SHAs, or allow an explicit prefix in workflow_check.policy.allowed_action_prefixes. |

## Policy

- Status: passed
- Source: config
- fail_on_blockers: true
- fail_on_errors: true
- fail_on_warnings: false
- require_config: true
- require_ci_ready: true
- required_ci_modes: adoption-policy

| Severity | Finding | Rule | Recommendation |
| --- | --- | --- | --- |
| info | Policy passed | none | No action needed. |

## Advice

- Use `python3 -m vibebench workflow-template` to preview a recommended workflow.
- Use `python3 -m vibebench workflow-check --strict` before relying on CI adoption.
- Use `python3 -m vibebench workflow-check --enforce-policy` to turn workflow findings into an explicit gate.
- The check is read-only and does not call GitHub or modify workflows.
