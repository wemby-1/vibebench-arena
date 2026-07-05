# VibeBench Quickstart Demo

Purpose: run a short copy-paste demo of the VibeBench quality console from a fresh clone or current checkout.

```bash
python3 -m vibebench config --path
python3 -m vibebench config --show --json
python3 -m vibebench ci --dry-run
python3 -m vibebench ci
python3 -m vibebench latest --all-paths
python3 -m vibebench artifacts --json
python3 -m vibebench release-check
python3 -m vibebench release-audit --zip --output-dir /tmp/vibebench-release-audit-demo
```

Expected outputs:

- configuration path and JSON config summary
- a dry-run plan for the local quality pipeline
- a completed `.vibebench/runs/<timestamp>/` run
- artifact paths for reports, summaries, manifests, bundles, and release-check files
- a release readiness table
- `/tmp/vibebench-release-audit-demo/release-audit.zip`

Cleanup:

```bash
rm -rf /tmp/vibebench-release-audit-demo
```

No publish, upload, tag, or GitHub Release happens during this quickstart demo.

## Keeping Codex Tasks Bounded

For Codex-first / vibe-coding work, keep each milestone small enough to verify:

- inspect only necessary files
- run focused checks before full checks
- stop after repeated failures and report the exact command/error
- finish with changed files, checks, commit hash, push status, and final git status
