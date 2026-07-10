# VibeBench Release Check

- Project root: `<reference-project>`
- Status: `not-ready`
- Latest run: `public-proof-run`

| Check | Status | Message |
| --- | --- | --- |
| config | passed | Config consistency check passed |
| package_check | passed | Package readiness check passed |
| package_build | passed | Local package build readiness is opt-in; run python -m vibebench package-check --build before publishing. |
| doctor_strict | failed | strict_bundle: Required file is missing: <reference-project>/.vibebench/runs/public-proof-run/vibebench-bundle.zip |
| latest_run | passed | Latest valid run: public-proof-run |
| manifest | passed | Manifest is consistent |
| artifacts | passed | Artifact inventory generated (32 available) |
| run_index | passed | Run index generated (1 indexed, 1 seen) |
| compare | passed | Compare readiness checked; insufficient data is non-fatal |
| ci_plan | passed | CI dry-run plan produced |
| git_diff_check | passed | git diff --check passed |
