# VibeBench Reference Project

This fixture is a compact, deterministic project used to generate the public
proof packet in `examples/showcase-artifacts/public-proof/`.

It demonstrates:

- a valid `.vibebench/config.yaml` with local-only check commands
- a GitHub Actions workflow that runs `python3 -m vibebench ci --adoption-policy`
- workflow-check, preflight, adoption-ready, CI evidence, manifest, report, and
  release-check paths against a realistic project shape
- no network calls, external services, lockfiles, secrets, or large generated data

It differs from a production project in a few important ways. The package is
tiny, the tests are intentionally simple, and the workflow installs VibeBench
from the repository checkout rather than from a release channel. The goal is to
exercise VibeBench evidence generation deterministically, not to model every
production release concern.

Run VibeBench against it from the repository root:

```bash
python3 -m vibebench ci -C examples/reference-project --adoption-policy --require-adoption-workflow --json
python3 -m vibebench workflow-check -C examples/reference-project --require-ci-mode adoption-policy --json
python3 -m vibebench preflight -C examples/reference-project --require-ci-mode adoption-policy --json
python3 -m vibebench adoption-ready -C examples/reference-project --json
```

The committed public packet is regenerated with:

```bash
python3 scripts/build_public_proof_packet.py --write
python3 scripts/build_public_proof_packet.py --check
```

This fixture does not prove production safety, security, compliance, release
quality, or suitability for any specific repository. It is demonstration
evidence showing that VibeBench can generate a reproducible, inspectable artifact
packet from real commands.
