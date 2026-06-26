# VibeBench Risk Demo

This demo creates a temporary repository with a clean baseline commit, then leaves several intentionally risky uncommitted changes for VibeBench to inspect.

The default output path is:

```bash
/tmp/vibebench-risk-demo
```

## What It Creates

The script builds a tiny Python project with:

- `app.py`
- `tests/test_app.py`
- `tests/test_health.py`
- `.vibebench/config.yaml`
- `pyproject.toml`

It initializes Git, commits the clean baseline, then introduces risky uncommitted changes:

- creates `.env.local` with fake demo-only content
- creates `secrets/config.json` with fake demo-only content
- deletes `tests/test_app.py` while keeping `tests/test_health.py` passing
- creates `package-lock.json`
- appends a large harmless patch to `app.py`

No real secrets are used.

## Run The Demo

From the VibeBench Arena repository:

```bash
python examples/risk-demo/create_risky_repo.py
cd /tmp/vibebench-risk-demo
python -m vibebench check
python -m vibebench report
python -m vibebench pr-comment
```

`vibebench check` is expected to exit non-zero because critical findings make the run fail. That is the point of this demo.

## Expected Findings

The demo should trigger:

- `forbidden_paths_touched` for `.env.local` and `secrets/config.json`
- `secret_like_files_touched` for `secrets/config.json`
- `tests_deleted` for `tests/test_app.py`
- `lockfiles_changed` for `package-lock.json`
- `large_patch` because the demo threshold is intentionally low

Expected result:

- VibeScore drops below 100
- risk level is not low when critical or high findings exist
- overall status fails because forbidden paths are critical

Generated artifacts stay inside the temporary demo repository under `.vibebench/runs/` and should not be committed.
