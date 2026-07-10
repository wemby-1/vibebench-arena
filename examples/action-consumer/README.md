# VibeBench Action Consumer Fixture

This is demonstration/reference material for a repository that consumes the
repository-root VibeBench composite action. It is intentionally small and is not
the VibeBench source repository.

Expected behavior:

- `preset: minimal` runs the core quality gate and produces a run directory.
- `preset: strict` runs adoption-policy evidence and expects the included
  workflow/config shape.
- `preset: proof` follows the same strict path while keeping standard evidence
  artifacts available for review.

The fixture is a normal non-static-site consumer. Static-site readiness is not
expected unless a workflow explicitly passes `required-mode: static-site`.

No generated `.vibebench/runs` outputs are committed.
