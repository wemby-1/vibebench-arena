# VibeBench Public Demo

Project: `vibebench-reference-project`

Result: `passed` with score `100` and
risk `low`.

Open `index.html` directly in a browser. The portal is self-contained and does
not require a server, CDN, external JavaScript, external CSS, remote fonts,
analytics, or network access.

## Review Path

- Verify the overall result, score, and risk level.
- Inspect workflow and adoption readiness evidence.
- Inspect findings and command results.
- Open the main report when it is available and safe to include.
- Review trust boundaries and non-claims.
- Reproduce the committed proof packet before relying on it externally.

## Reproduction

```bash
python3 scripts/build_public_proof_packet.py --check
```

## Boundaries

- The portal summarizes the supplied VibeBench evidence.
- It does not independently prove security.
- It does not replace human code review.
- It does not certify regulatory compliance.
- It does not prove product-market fit, revenue, customer adoption, or funding.
- It should not fabricate users, customers, benchmarks, or commercial traction.
