# Public Proof Packet

The public proof packet gives reviewers a browsable VibeBench evidence set
without asking them to install or run the project first. It is generated from the
deterministic fixture at
[`examples/reference-project/`](../examples/reference-project/).

The committed packet lives at
[`examples/showcase-artifacts/public-proof/`](../examples/showcase-artifacts/public-proof/).
It is demonstration evidence, not a security audit, certification, compliance
report, or formal proof of production safety.

## How It Is Generated

The repository-native builder copies the reference project into a temporary
workspace, initializes local Git state, runs real VibeBench commands, selects a
small review-friendly artifact subset, normalizes volatile metadata, and writes
only curated files into the public packet directory.

Regenerate it:

```bash
python3 scripts/build_public_proof_packet.py --write
```

Detect staleness without modifying committed files:

```bash
python3 scripts/build_public_proof_packet.py --check
```

Normalized fields include temporary paths, run identifiers, generated
timestamps, command durations, absolute artifact paths, and host-specific Git
metadata. Evaluation results, scores, findings, detected CI modes, and evidence
meaning are preserved.

## Recommended Reading Order

1. [`README.md`](../examples/showcase-artifacts/public-proof/README.md) explains
   provenance and limitations.
2. [`proof-packet-index.md`](../examples/showcase-artifacts/public-proof/proof-packet-index.md)
   gives a compact artifact map.
3. [`metrics.json`](../examples/showcase-artifacts/public-proof/metrics.json)
   is the core check result.
4. [`config-check.md`](../examples/showcase-artifacts/public-proof/config-check.md)
   and [`config-check.json`](../examples/showcase-artifacts/public-proof/config-check.json)
   show configuration validity.
5. [`workflow-check.md`](../examples/showcase-artifacts/public-proof/workflow-check.md)
   and [`workflow-check.json`](../examples/showcase-artifacts/public-proof/workflow-check.json)
   show adoption-policy workflow detection.
6. [`preflight.md`](../examples/showcase-artifacts/public-proof/preflight.md)
   and [`preflight.json`](../examples/showcase-artifacts/public-proof/preflight.json)
   show read-only adoption readiness.
7. [`release-check.md`](../examples/showcase-artifacts/public-proof/release-check.md)
   and [`release-check.json`](../examples/showcase-artifacts/public-proof/release-check.json)
   summarize release-readiness signals.
8. [`manifest.json`](../examples/showcase-artifacts/public-proof/manifest.json)
   records artifact names and checksums.
9. [`gate-summary.md`](../examples/showcase-artifacts/public-proof/gate-summary.md)
   explains the quality gate result.
10. [`report/index.html`](../examples/showcase-artifacts/public-proof/report/index.html)
    is the static HTML report.

## What It Supports

For investors, the packet makes the evidence-first story concrete: claims about
CI readiness, review artifacts, and reproducibility can be inspected directly in
the repository.

For technical evaluators, the packet provides a reproducible fixture and a
strict `--check` path. If the CLI behavior changes and the packet is not
refreshed, `--check` exits non-zero and lists stale files.

## What It Does Not Prove

The packet does not prove that VibeBench is suitable for every production
repository, that a downstream project is secure, that release processes are
compliant, or that generated evidence should replace human review. It proves
only that the committed demonstration artifacts can be regenerated from the
reference project using the repository's current VibeBench CLI.
