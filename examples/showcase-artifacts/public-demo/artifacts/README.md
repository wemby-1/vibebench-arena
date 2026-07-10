# Public Proof Packet

This directory is generated from `examples/reference-project/` by:

```bash
python3 scripts/build_public_proof_packet.py --write
```

Check whether the committed packet is current:

```bash
python3 scripts/build_public_proof_packet.py --check
```

The files are demonstration evidence from real VibeBench commands. They are not
a security audit, certification, compliance report, or formal proof of
production safety.

Normalized fields include temporary workspace paths, generated run identifiers,
timestamps, command durations, absolute artifact paths, and host-specific Git
metadata. Pass/fail status, scores, findings, detected CI mode, and evidence
relationships are preserved.

Start with `proof-packet-index.md`, then inspect the JSON/Markdown pairs for
config-check, workflow-check, preflight, release-check, and the static report at
`report/index.html`.
