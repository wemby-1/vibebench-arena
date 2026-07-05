# Contributing

Thanks for helping improve VibeBench Arena. The project is intentionally small and milestone-driven, so the best contributions are focused, tested, and easy to review.

## Development Setup

```bash
python -m pip install -e ".[dev]"
python -m vibebench init
```

## Local Checks

Run lint and tests before opening a pull request:

```bash
python -m ruff check .
python -m pytest -q
```

Run VibeBench against the repository itself:

```bash
python -m vibebench check
python -m vibebench report
python -m vibebench pr-comment
```

Generated files under `.vibebench/runs/` are local artifacts and should not be committed.

## How To Contribute

- Use the issue templates for bug reports, feature requests, demo feedback, and real AI coding use cases.
- Open focused PRs with clear verification commands and reviewable evidence.
- Prefer small docs, artifact, CLI, or test improvements over broad rewrites.
- If you are proposing a use case, describe the workflow, the review pain, and the artifacts that would make it easier to audit.
- Remove credentials, private paths, proprietary code, and generated `.vibebench/runs/` outputs before posting or committing.

## Contribution Style

- Keep pull requests small and focused.
- Prefer clear implementation over broad abstractions.
- Match existing Typer, Pydantic, Rich, and pytest patterns.
- Update docs when behavior, commands, config, or output changes.
- Avoid adding dependencies unless the benefit is clear for a local-first CLI.

## Adding Risk Rules

When adding or changing risk rules:

- add deterministic tests using temporary Git repositories
- document the rule in `docs/risk-rules.md`
- include the scoring impact if the rule affects VibeScore
- keep messages readable for developers new to the tool

## Adding Docs Or Examples

Docs and examples should be reproducible from a clean checkout. Do not include credentials, private paths, proprietary code, or generated `.vibebench/runs/` outputs.
