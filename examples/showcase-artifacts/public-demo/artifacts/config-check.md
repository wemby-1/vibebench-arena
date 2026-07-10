# VibeBench Config Check

- Config path: `<reference-project>/.vibebench/config.yaml`
- Overall status: `passed`
- Advice mode: `enabled`

| Check | Status | Message |
| --- | --- | --- |
| config_file_exists | passed | Config file found at <reference-project>/.vibebench/config.yaml |
| config_validates | passed | Config parses and validates successfully |
| project_name | passed | Project name is present |
| command_groups | passed | 2 command group(s) contain commands |
| command_strings | passed | All configured command strings are non-empty |
| gate_policy | passed | Gate policy is internally consistent (min_score=90, max_risk=low, allow_findings=0) |
| risk_policy | passed | Risk policy is internally consistent (max_changed_files=20, max_patch_lines=500) |
| regression_policy | passed | Regression policy is internally consistent (enabled=false, baseline_label=none, require_baseline=false, max_score_drop=0, max_risk_increase=0) |
| metrics_diff_policy | passed | Metrics-diff policy is internally consistent (enabled=false, baseline_label=stable, fail_on_added_errors=false, fail_on_added_warnings=false, fail_on_removed_metrics=false, max_score_drop=0, max_risk_increase=0, rules=none) |
| project_scan_policy | passed | Project-scan policy is internally consistent (enabled=true, require_config_valid=true, require_supported_stack=true, allowed_profiles=python,generic, fail_on_error_findings=true, fail_on_warning_findings=false) |
| onboard_policy | passed | Onboard policy is internally consistent (enabled=true, fail_on_blockers=true, fail_on_errors=true, fail_on_warnings=false, require_config=true, require_ci_ready=true) |
| workflow_check_policy | passed | Workflow-check policy is internally consistent (enabled=true, fail_on_blockers=true, fail_on_errors=true, fail_on_warnings=false, require_config=true, require_ci_ready=true, required_ci_modes=adoption-policy, allowed_workflow_names=none, allowed_action_prefixes=none) |
| preflight_policy | passed | Preflight policy is internally consistent (enabled=true, fail_on_blockers=true, fail_on_errors=true, fail_on_warnings=false, require_config=true, require_project_scan_ready=true, require_onboard_ready=true, require_workflow_check_ready=true, require_workflow_template_ready=false) |

## Advice

- `regression_policy`: For a stable pinned regression gate, run `python3 -m vibebench baseline --set-latest --label stable`, then set regression.enabled=true, regression.baseline_label=stable, and regression.require_baseline=true in .vibebench/config.yaml.
- `metrics_diff_policy`: Set metrics_diff.policy.enabled=true and configure per-metric rules such as latency_ms.max_increase or pass_rate.max_drop when metrics-diff drift should become an explicit gate.
