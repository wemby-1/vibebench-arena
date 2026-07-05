# Sample Artifact Pack

This is a small checked-in sample artifact pack for GitHub visitors who want to browse what VibeBench outputs look like without running the tool first.

The files are illustrative and safe to browse. Real outputs are generated locally by VibeBench in your own checkout when you run the commands below.

This sample artifact pack intentionally includes:

- no secrets, tokens, API keys, emails, or personal names
- no local absolute paths or user-specific paths
- no large files, zip files, or binary files
- deterministic example values such as `sample-baseline`, `sample-current`, and `2026-01-01T00:00:00Z`

## Files

| File | Illustrates | Related VibeBench command |
| --- | --- | --- |
| `ci-plan.json` | Planned CI pipeline steps before execution. | `python3 -m vibebench ci --dry-run --json` |
| `ci-summary.md` | Human-readable CI run summary. | `python3 -m vibebench ci` |
| `artifact-inventory.json` | Machine-readable artifact inventory. | `python3 -m vibebench artifacts --json` |
| `compare-summary.md` | Run-to-run comparison summary. | `python3 -m vibebench compare` |
| `release-audit-summary.md` | Local release audit summary. | `python3 -m vibebench release-audit` |
| `manifest.json` | Run artifact manifest. | `python3 -m vibebench manifest` |

Generated VibeBench outputs normally live in local run directories such as `.vibebench/runs/<run-id>/`. The checked-in files here are only a compact, static sample for documentation and GitHub browsing.
