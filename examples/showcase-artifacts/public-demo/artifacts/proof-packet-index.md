# Public Proof Packet Index

Generated from: `examples/reference-project/`

Regenerate:

```bash
python3 scripts/build_public_proof_packet.py --write
```

Check freshness:

```bash
python3 scripts/build_public_proof_packet.py --check
```

## Reading Order

1. `README.md` for provenance and normalization notes.
2. `metrics.json` for the core check result.
3. `config-check.json` and `config-check.md` for configuration validity.
4. `workflow-check.json` and `workflow-check.md` for adoption-policy workflow detection.
5. `preflight.json` and `preflight.md` for read-only adoption readiness.
6. `release-check.json` and `release-check.md` for release-readiness signals.
7. `manifest.json` for artifact inventory and checksums.
8. `gate-summary.md` for quality gate interpretation.
9. `report/index.html` for the browsable run report.

This packet is demonstration evidence only. It does not certify production
security, compliance, reliability, or future behavior.
