# VibeBench Arena Security Questionnaire

This questionnaire is project-maintained documentation, not a third-party audit, security certification, or compliance certification. It is written for external teams, maintainers, investors, and enterprise adopters who need a factual view of VibeBench Arena's local-first security posture, privacy boundaries, generated artifacts, CI behavior, verification commands, and non-claims.

Local users should review artifacts before publishing or sharing them.

## Q&A

### Does VibeBench require cloud services?

No. VibeBench is local-first for normal evaluation. The core proof packet, Static site preview, Evidence-room package, verification commands, and JSON stdout workflows run from a local repository checkout. GitHub Actions is optional CI infrastructure.

### Does VibeBench upload source code?

The local CLI does not upload source code. It reads the working tree, runs configured local commands, and writes local artifacts. If a repository runs VibeBench in GitHub Actions, GitHub Actions may upload configured artifact bundles from that CI run.

### Does VibeBench require secrets or tokens for local evaluation?

No. Local evaluation does not require secrets or tokens. Teams should avoid adding secrets to repositories and should inspect generated artifacts before sharing them.

### What files does the Proof packet contain?

The Proof packet contains `proof.html`, `proof.json`, `proof.md`, `proof-manifest.json`, and optional `proof.zip`. The HTML report is intended to be self-contained.

### What files does the Static site preview contain?

The Static site preview contains `index.html`, `showcase.html`, `site-check.json`, `site-preview.md`, and optional `site-preview.zip`.

### What files does the Evidence-room contain?

The Evidence-room contains a self-opening `index.html`, review hub files, reviewer guide, Trust Center files, this Security Questionnaire, reviewer scorecard files, `evidence-room.html`, `evidence-room.md`, `evidence-room.json`, a nested Proof packet, a nested Static site preview, and optional `evidence-room.zip`.

### What does GitHub Actions upload?

When configured CI runs, GitHub Actions can upload downloadable proof packet, site preview, and evidence-room artifacts. Those uploads are CI artifacts, not package publication, release creation, repository settings changes, or automatic GitHub Pages enablement.

### Are generated HTML reports self-contained?

Generated HTML reports are intended to be self-contained static HTML. The Proof packet HTML, Evidence-room HTML, Trust Center HTML, review hub, scorecard, and Security Questionnaire should be inspectable without a hosted service.

### Are remote resources allowed in generated static reports?

No. Generated static reports intended for sharing should avoid remote resources, external assets, scripts, and image dependencies.

### Are absolute local paths allowed in public/static HTML outputs?

No. Public/static HTML outputs should avoid absolute local paths and should use relative links or placeholders.

### Is JSON stdout intended to be machine-readable and pure JSON?

Yes. Commands with `--json` are expected to write pure JSON stdout so automation can parse output without scraping human text.

### How can a reviewer reproduce the Evidence-room locally?

Run:

```bash
python3 -m vibebench evidence-room --output-dir /tmp/vibebench-evidence-room --zip
```

### How can a reviewer verify the Evidence-room?

Run either directory or zip verification:

```bash
python3 -m vibebench evidence-room --verify /tmp/vibebench-evidence-room
python3 -m vibebench evidence-room --verify /tmp/vibebench-evidence-room/evidence-room.zip
python3 -m vibebench proof --verify /tmp/vibebench-evidence-room/proof-packet
python3 -m vibebench site-preview --verify /tmp/vibebench-evidence-room/site-preview
```

### How are unsafe publishing markers checked?

Run:

```bash
python3 -m vibebench site-check
python3 -m vibebench ci --dry-run --json
python3 -m vibebench release-check
python3 -m vibebench doctor --strict
```

These checks are evidence and readiness checks. They do not replace human review.

### What does the project not claim?

VibeBench does not claim that generated code is correct or safe, does not replace human review, does not provide a sandbox, does not provide a hosted security product, does not promise business outcomes, and does not automatically publish packages, create releases, enable GitHub Pages, or change repository settings.

### Is this SOC 2 or ISO 27001 certification?

No. VibeBench is not claiming SOC 2 certification. VibeBench is not claiming ISO 27001 certification.

### Has there been an independent third-party audit?

No. VibeBench is not claiming an independent third-party audit.

### How should teams handle sensitive repositories?

Treat generated artifacts as review materials. Run VibeBench locally first, inspect outputs before sharing, avoid committing secrets, and avoid distributing artifacts from sensitive repositories until a human reviewer has checked the files.

### How should teams review CI artifacts before sharing?

Download the CI artifacts, open the Evidence-room from `index.html`, inspect the Proof packet and Static site preview, verify the package, and confirm the artifacts do not contain sensitive data before forwarding them outside the team.

Before sharing an evidence room, proof packet, static preview, or zip externally, run:

```bash
python3 -m vibebench share-check PATH
python3 -m vibebench share-check PATH --json
```

The scanner is a local pre-sharing aid, not a security certification, not a third-party audit, and not a guarantee. Users should still manually review artifacts before publishing.

### Where is the security policy?

See [SECURITY.md](../SECURITY.md).

### How should security issues be reported?

Follow the repository [Security Policy](../SECURITY.md). Do not disclose sensitive vulnerability details in a public issue before maintainers have had a chance to review them.
