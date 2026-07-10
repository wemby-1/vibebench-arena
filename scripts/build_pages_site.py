#!/usr/bin/env python3
"""Build or check the GitHub Pages public launch site."""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DEMO = ROOT / "examples" / "showcase-artifacts" / "public-demo"
PUBLIC_DEMO_BUILDER = ROOT / "scripts" / "build_public_demo.py"
SITE_ASSETS = ROOT / "site" / "assets"
DEFAULT_OUTPUT = ROOT / "_site"
DEFAULT_REPOSITORY_URL = "https://github.com/wemby-1/vibebench-arena"
DEFAULT_BASE_URL = "https://wemby-1.github.io/vibebench-arena/"
DEFAULT_BASE_PATH = "/vibebench-arena/"
HOST_GITHUB_ENV_KEYS = {
    "GITHUB_ACTIONS",
    "GITHUB_STEP_SUMMARY",
    "GITHUB_OUTPUT",
    "GITHUB_ENV",
    "GITHUB_PATH",
    "GITHUB_WORKSPACE",
    "GITHUB_EVENT_PATH",
    "GITHUB_PAGES",
}
FORBIDDEN_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"/home/",
        r"/users/",
        r"/data/code/",
        r"/tmp/(?!vibebench-demo\b)",
        r"c:\\users\\",
        r"d:\\",
        r"\bghp_[A-Za-z0-9_]{20,}",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}",
        r"\bsk-[A-Za-z0-9_-]{20,}",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\b(?:authorization|api[_-]?key|token|secret|password)\s*[:=]",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    ]
]


class PagesBuildError(RuntimeError):
    """Raised when the Pages site cannot be built safely."""


@dataclass(frozen=True)
class SiteConfig:
    """Public site URL and repository settings."""

    base_url: str
    base_path: str
    repository_url: str

    @property
    def canonical_index(self) -> str:
        return normalized_url(self.base_url)


@dataclass(frozen=True)
class EvidenceData:
    """Loaded public-demo data used to render the launch site."""

    demo: dict[str, object]
    metrics: dict[str, object]
    workflow_check: dict[str, object]
    manifest: dict[str, object]
    artifacts: list[dict[str, object]]


class LinkParser(HTMLParser):
    """Collect links, asset references, headings, landmarks, and IDs."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.remote_runtime_assets: list[str] = []
        self.image_sources: list[tuple[str, str | None]] = []
        self.script_sources: list[str] = []
        self.headings: list[tuple[int, str]] = []
        self.landmarks: set[str] = set()
        self.ids: list[str] = []
        self.empty_links: list[str] = []
        self._current_heading: int | None = None
        self._heading_text: list[str] = []
        self._current_link: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = dict(attrs)
        href = values.get("href")
        src = values.get("src")
        element_id = values.get("id")
        if element_id:
            self.ids.append(element_id)
        if tag in {"header", "main", "nav", "footer", "section"}:
            self.landmarks.add(tag)
        if href:
            rel = set((values.get("rel") or "").lower().split())
            if is_runtime_link_tag(tag, rel) and href.startswith(("http://", "https://")):
                self.remote_runtime_assets.append(href)
            self.links.append(href)
            if tag == "a":
                self._current_link = href
                self._link_text = []
        if src:
            if src.startswith(("http://", "https://")):
                self.remote_runtime_assets.append(src)
            if tag == "script":
                self.script_sources.append(src)
            if tag == "img":
                self.image_sources.append((src, values.get("alt")))
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._current_heading = int(tag[1])
            self._heading_text = []

    def handle_data(self, data: str) -> None:
        if self._current_heading is not None:
            self._heading_text.append(data)
        if self._current_link is not None:
            self._link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._current_heading is not None and tag == f"h{self._current_heading}":
            text = " ".join("".join(self._heading_text).split())
            self.headings.append((self._current_heading, text))
            self._current_heading = None
            self._heading_text = []
        if tag == "a" and self._current_link is not None:
            text = " ".join("".join(self._link_text).split())
            if not text:
                self.empty_links.append(self._current_link)
            self._current_link = None
            self._link_text = []


def main() -> int:
    """Run the Pages site builder."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory where the static Pages site should be written.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate a deterministic build and compare an existing output tree.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Canonical GitHub Pages URL for metadata and sitemap entries.",
    )
    parser.add_argument(
        "--base-path",
        default=DEFAULT_BASE_PATH,
        help="GitHub project Pages path, used for metadata and validation.",
    )
    parser.add_argument(
        "--repository-url",
        default=DEFAULT_REPOSITORY_URL,
        help="Repository URL shown as ordinary outbound navigation.",
    )
    args = parser.parse_args()

    config = SiteConfig(
        base_url=normalized_url(args.base_url),
        base_path=normalized_base_path(args.base_path),
        repository_url=args.repository_url.rstrip("/"),
    )
    try:
        output_dir = resolve_output(args.output_dir)
        with tempfile.TemporaryDirectory(
            prefix="vibebench-pages-site-",
            dir=str(output_dir.parent),
        ) as temp:
            generated = Path(temp) / "site"
            build_pages_site(generated, config)
            if args.check:
                differences = compare_if_existing(generated, output_dir)
                if differences:
                    print("Pages site output differs:", file=sys.stderr)
                    for item in differences[:20]:
                        print(f"  {item}", file=sys.stderr)
                    return 1
                print("Pages site build is current")
                return 0
            write_site(generated, output_dir)
            print(f"Wrote Pages site to {display_path(output_dir)}")
            return 0
    except PagesBuildError as exc:
        print(f"Pages site build failed: {exc}", file=sys.stderr)
        return 1


def build_pages_site(output_dir: Path, config: SiteConfig) -> None:
    """Build and validate a deployable static launch site."""
    verify_public_demo_current()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(
        PUBLIC_DEMO,
        output_dir,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
    )
    data = load_evidence(output_dir)
    write_assets(output_dir)
    write_launch_pages(output_dir, data, config)
    write_supporting_files(output_dir, config)
    validate_site(output_dir, config)


def verify_public_demo_current() -> None:
    """Verify the committed public demo before publishing it."""
    completed = subprocess.run(
        [sys.executable, str(PUBLIC_DEMO_BUILDER), "--check"],
        cwd=ROOT,
        env=builder_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise PagesBuildError(f"public demo is not current: {detail}")


def load_evidence(root: Path) -> EvidenceData:
    """Load deterministic evidence JSON from the copied public demo."""
    demo = read_json(root / "demo.json")
    metrics = read_json(root / "artifacts" / "metrics.json")
    workflow = read_json(root / "artifacts" / "workflow-check.json")
    manifest = read_json(root / "artifacts" / "manifest.json")
    raw_artifacts = demo.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise PagesBuildError("demo.json does not contain an artifact list")
    artifacts = [item for item in raw_artifacts if isinstance(item, dict)]
    return EvidenceData(
        demo=demo,
        metrics=metrics,
        workflow_check=workflow,
        manifest=manifest,
        artifacts=artifacts,
    )


def write_assets(root: Path) -> None:
    """Copy maintained local assets into the generated site."""
    target = root / "assets"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(SITE_ASSETS, target)


def write_launch_pages(root: Path, data: EvidenceData, config: SiteConfig) -> None:
    """Write the launch page and 404 page."""
    index = render_index(data, config)
    (root / "index.html").write_text(index, encoding="utf-8")
    (root / "404.html").write_text(render_404(config), encoding="utf-8")


def write_supporting_files(root: Path, config: SiteConfig) -> None:
    """Write deterministic public files required by Pages and crawlers."""
    (root / ".nojekyll").write_text("", encoding="utf-8")
    (root / "robots.txt").write_text(render_robots(config), encoding="utf-8")
    (root / "sitemap.xml").write_text(render_sitemap(config), encoding="utf-8")
    (root / "site.webmanifest").write_text(
        json.dumps(webmanifest(config), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def render_index(data: EvidenceData, config: SiteConfig) -> str:
    """Render the public launch site index."""
    title = "VibeBench Arena | Codex-first quality and evidence gate"
    description = (
        "VibeBench Arena runs checks, enforces policy, generates evidence, "
        "and publishes reviewer-ready proof for vibe-coded projects."
    )
    cards = evidence_cards(data)
    categories = categorize_artifacts(data.artifacts)
    return clean_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description)}">
  <link rel="canonical" href="{escape(config.canonical_index)}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="VibeBench Arena">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:url" content="{escape(config.canonical_index)}">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{escape(title)}">
  <meta name="twitter:description" content="{escape(description)}">
  <meta name="theme-color" content="#15302f">
  <link rel="icon" href="assets/icon.svg" type="image/svg+xml">
  <link rel="manifest" href="site.webmanifest">
  <link rel="stylesheet" href="assets/site.css">
  <script type="application/ld+json">{json_ld(config)}</script>
  <script src="assets/site.js" defer></script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="site-header">
    <nav class="nav" aria-label="Primary navigation">
      <a class="brand" href="#home" aria-label="VibeBench Arena home">
        <span class="brand-mark" aria-hidden="true">VB</span>
        <span>VibeBench Arena</span>
      </a>
      <button
        class="nav-toggle"
        type="button"
        aria-expanded="false"
        aria-controls="nav-links"
      >
        Menu
      </button>
      <div class="nav-links" id="nav-links">
        <a href="#live-demo">Live Demo</a>
        <a href="#evidence">Evidence</a>
        <a href="#artifacts">Artifacts</a>
        <a href="#adoption">Adoption</a>
        <a href="#trust">Trust</a>
        <a href="#diligence">Diligence</a>
        <a href="{escape(config.repository_url)}">GitHub</a>
      </div>
    </nav>
  </header>
  <main id="main">
    <section class="hero" id="home" aria-labelledby="hero-title">
      <div class="hero-copy">
        <p class="eyebrow">Codex-first quality and evidence gate</p>
        <h1 id="hero-title">VibeBench Arena</h1>
        <p class="hero-lede">
          Run checks, enforce policy, generate evidence, and publish
          reviewer-ready proof for vibe-coded projects.
        </p>
        <div class="hero-actions" aria-label="Primary actions">
          <a class="button primary" href="#evidence">Explore the live proof</a>
          <a class="button secondary" href="#adoption">Run the 5-minute quickstart</a>
          <a class="button ghost" href="{escape(config.repository_url)}">
            View GitHub repository
          </a>
        </div>
      </div>
      <aside class="proof-panel" aria-label="Current public proof summary">
        <span class="panel-kicker">Verified from committed evidence</span>
        <strong>{escape(status_text(data.demo))}</strong>
        <dl>
          {definition("Project", str(data.demo.get("project", "Not included")))}
          {definition("Score", score_text(data.demo.get("score")))}
          {definition("Risk", str(data.demo.get("risk_level", "Not included")))}
          {definition("Artifacts", artifact_count_text(data.demo))}
        </dl>
      </aside>
    </section>

    <section class="section" id="live-demo" aria-labelledby="live-demo-title">
      <div class="section-heading">
        <p class="eyebrow">Public launch site</p>
        <h2 id="live-demo-title">Understand the project in 30 seconds</h2>
        <p>
          This site presents the committed VibeBench public demo and proof
          packet as a static, reproducible launch page. It separates product
          positioning from evidence-backed artifacts and does not run as a
          hosted scanning service.
        </p>
      </div>
      <div class="how-grid" aria-label="How VibeBench works">
        {workflow_steps()}
      </div>
    </section>

    <section class="section alt" id="evidence" aria-labelledby="evidence-title">
      <div class="section-heading">
        <p class="eyebrow">Evidence-backed summary</p>
        <h2 id="evidence-title">Concrete proof within 3 minutes</h2>
        <p>
          These cards are derived from committed JSON artifacts. When evidence
          is unavailable, the site labels it as unavailable instead of
          inventing a metric.
        </p>
      </div>
      <div class="card-grid evidence-grid">
        {"".join(render_card(card) for card in cards)}
      </div>
    </section>

    <section class="section" id="artifacts" aria-labelledby="artifacts-title">
      <div class="section-heading">
        <p class="eyebrow">Artifact Explorer</p>
        <h2 id="artifacts-title">Inspect the reference demo evidence</h2>
        <p>
          Artifacts are grouped by reviewer task. Available files link to
          committed safe copies; unavailable optional artifacts are visible but
          are not linked as if present.
        </p>
      </div>
      <div class="artifact-groups">
        {"".join(render_artifact_group(name, items) for name, items in categories)}
      </div>
    </section>

    <section class="section alt" id="adoption" aria-labelledby="adoption-title">
      <div class="section-heading">
        <p class="eyebrow">Five-minute path</p>
        <h2 id="adoption-title">Reproduce or adopt it in 5 minutes</h2>
      </div>
      <ol class="timeline">
        {review_path()}
      </ol>
      <div class="command-panel">
        <p>Local verification commands:</p>
        <pre><code>python3 scripts/build_public_demo.py --check
python3 scripts/build_public_proof_packet.py --check
python3 scripts/build_pages_site.py --output-dir review-output/pages-site
python3 scripts/build_pages_site.py --check</code></pre>
      </div>
    </section>

    <section class="section" id="audiences" aria-labelledby="audiences-title">
      <div class="section-heading">
        <p class="eyebrow">Entry points</p>
        <h2 id="audiences-title">Choose the review path that matches your role</h2>
      </div>
      <div class="card-grid audience-grid">
        {audience_cards(config)}
      </div>
    </section>

    <section class="section alt" id="trust" aria-labelledby="trust-title">
      <div class="section-heading">
        <p class="eyebrow">Trust boundaries</p>
        <h2 id="trust-title">What the site proves, and what it does not</h2>
        <p>
          The public launch site summarizes supplied VibeBench evidence. It
          does not independently prove security, replace human code review,
          certify compliance, prove customer adoption, or establish revenue,
          funding, or product-market fit.
        </p>
      </div>
      <ul class="boundary-list">
        {render_boundaries(data)}
      </ul>
    </section>

    <section class="section" id="diligence" aria-labelledby="diligence-title">
      <div class="section-heading">
        <p class="eyebrow">Technical diligence</p>
        <h2 id="diligence-title">Evidence, architecture, and investor review</h2>
        <p>
          Use these repository documents to inspect the product thesis,
          technical design, proof matrix, and diligence framing. They are
          supporting documentation, not proof of market traction.
        </p>
      </div>
      <div class="link-grid">
        {supporting_links(config)}
      </div>
    </section>
  </main>
  <footer class="site-footer">
    <p>
      Built from the committed public demo. Evidence source:
      <code>{escape(str(data.demo.get("source", "Not included")))}</code>.
    </p>
    <p>
      Base path: <code>{escape(config.base_path)}</code>.
      Runtime assets are local and the core content works without JavaScript.
    </p>
  </footer>
</body>
</html>"""
    )


def render_404(config: SiteConfig) -> str:
    """Render a small project-Pages-safe 404 page."""
    return clean_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Page not found | VibeBench Arena</title>
  <meta name="description" content="Return to the VibeBench Arena public launch site.">
  <link rel="stylesheet" href="assets/site.css">
  <link rel="icon" href="assets/icon.svg" type="image/svg+xml">
  <meta name="theme-color" content="#15302f">
</head>
<body class="not-found">
  <a class="skip-link" href="#main">Skip to content</a>
  <main id="main" class="not-found-main">
    <h1>Page not found</h1>
    <p>
      The VibeBench Arena public site is static and served under
      <code>{escape(config.base_path)}</code>.
    </p>
    <p>
      <a class="button primary" href="index.html">
        Return to the public launch site
      </a>
    </p>
  </main>
</body>
</html>"""
    )


def evidence_cards(data: EvidenceData) -> list[dict[str, str]]:
    """Return evidence summary cards derived from committed JSON."""
    demo = data.demo
    workflow_summary = data.workflow_check.get("summary")
    manifest_artifacts = data.manifest.get("artifacts")
    return [
        card(
            "Current status",
            status_text(demo),
            "Overall public proof result from demo.json.",
            "demo.json",
        ),
        card(
            "VibeScore",
            score_text(demo.get("score")),
            "Quality score emitted by the reference run metrics.",
            "artifacts/metrics.json",
        ),
        card(
            "Risk level",
            str(demo.get("risk_level", "Not included")),
            "Risk classification from the committed metrics artifact.",
            "artifacts/metrics.json",
        ),
        card(
            "Artifacts",
            artifact_count_text(demo),
            "Available evidence files in the public demo.",
            "demo.json",
        ),
        card(
            "Workflow readiness",
            summary_text(workflow_summary, "passed"),
            "Workflow-check results for the deterministic reference project.",
            "artifacts/workflow-check.json",
        ),
        card(
            "Manifest consistency",
            manifest_text(manifest_artifacts),
            "Manifest and inventory files are included for integrity review.",
            "artifacts/manifest.json",
        ),
        card(
            "Share-check status",
            evidence_status(demo, "share_check"),
            "Shows whether share-check evidence was included in this demo.",
            evidence_link(demo, "share_check"),
        ),
        card(
            "Reproducibility",
            "Check command included",
            "The committed proof packet can be checked without network access.",
            "artifacts/proof-packet-index.md",
        ),
    ]


def card(title: str, value: str, detail: str, link: str | None) -> dict[str, str]:
    """Build one card dictionary."""
    return {
        "title": title,
        "value": value,
        "detail": detail,
        "link": link or "",
    }


def render_card(item: dict[str, str]) -> str:
    """Render one evidence card."""
    link = item["link"]
    action = (
        f'<a href="{escape(link)}">Open evidence</a>'
        if link and not link.startswith("#")
        else '<span class="muted">Evidence not included</span>'
    )
    return f"""<article class="card evidence-card">
  <h3>{escape(item["title"])}</h3>
  <p class="metric">{escape(item["value"])}</p>
  <p>{escape(item["detail"])}</p>
  {action}
</article>"""


def categorize_artifacts(
    artifacts: list[dict[str, object]],
) -> list[tuple[str, list[dict[str, object]]]]:
    """Group artifacts into reviewer-oriented categories."""
    buckets: list[tuple[str, tuple[str, ...]]] = [
        ("Decision evidence", ("metrics", "gate", "explain", "config")),
        ("Workflow evidence", ("workflow", "preflight", "adoption", "release")),
        ("Review surfaces", ("report", "github-step-summary", "README")),
        ("Integrity and manifests", ("manifest", "inventory", "proof-packet")),
        ("Trend and comparison", ("trend", "compare", "run-index", "metrics-diff")),
        ("Trust and sharing", ("share", "security", "trust", "scorecard", "bundle")),
    ]
    remaining = list(artifacts)
    grouped: list[tuple[str, list[dict[str, object]]]] = []
    for title, keys in buckets:
        selected = [
            item
            for item in remaining
            if any(key in str(item.get("path", item.get("name", ""))) for key in keys)
        ]
        remaining = [item for item in remaining if item not in selected]
        grouped.append((title, sorted(selected, key=artifact_sort_key)))
    if remaining:
        grouped.append(
            ("Other known artifacts", sorted(remaining, key=artifact_sort_key))
        )
    return grouped


def render_artifact_group(title: str, items: list[dict[str, object]]) -> str:
    """Render one artifact group."""
    rows = "".join(render_artifact(item) for item in items)
    return f"""<section class="artifact-group" aria-labelledby="{slug(title)}-title">
  <h3 id="{slug(title)}-title">{escape(title)}</h3>
  <div class="artifact-list">
    {rows}
  </div>
</section>"""


def render_artifact(item: dict[str, object]) -> str:
    """Render one artifact row."""
    name = str(item.get("name") or item.get("path") or "Unnamed artifact")
    description = str(item.get("description") or artifact_description(name))
    file_type = str(item.get("file_type") or Path(name).suffix.lstrip(".") or "file")
    size = item.get("size_bytes")
    available = bool(item.get("available"))
    link = item.get("link") if available else None
    status = "Available" if available else "Unavailable optional evidence"
    title = escape(human_name(name))
    size_text = f"{size} bytes" if isinstance(size, int) else "Not included"
    if link:
        heading = f'<a href="{escape(str(link))}">{title}</a>'
    else:
        heading = f"<span>{title}</span>"
    return f"""<article class="artifact-item {'available' if available else 'missing'}">
  <div>
    <h4>{heading}</h4>
    <p>{escape(description)}</p>
  </div>
  <dl>
    {definition("Status", status)}
    {definition("Type", file_type)}
    {definition("Size", size_text)}
  </dl>
</article>"""


def workflow_steps() -> str:
    """Render the how-it-works workflow."""
    steps = [
        ("Code change", "A human or coding agent changes the repository."),
        (
            "VibeBench checks",
            "Configured tests, lint, and readiness checks run locally or in CI.",
        ),
        (
            "Policy gate",
            "Scores, risk findings, and required workflow modes are evaluated.",
        ),
        (
            "Evidence artifacts",
            "JSON, Markdown, HTML, manifests, and summaries are written.",
        ),
        (
            "Reviewable proof",
            "A proof packet or public demo gives reviewers a stable entry point.",
        ),
        (
            "Public or private review",
            "Teams decide what to share while preserving non-claims.",
        ),
    ]
    return "".join(
        f"""<article class="workflow-step">
  <span aria-hidden="true">{index}</span>
  <h3>{escape(title)}</h3>
  <p>{escape(detail)}</p>
</article>"""
        for index, (title, detail) in enumerate(steps, start=1)
    )


def review_path() -> str:
    """Render the five-minute review path."""
    items = [
        (
            "Minute 0-1",
            "Understand the problem",
            "Use the hero and workflow section to see why evidence matters.",
            "#home",
        ),
        (
            "Minute 1-2",
            "Inspect the quality decision",
            "Open metrics and gate evidence before trusting the summary.",
            "artifacts/metrics.json",
        ),
        (
            "Minute 2-3",
            "Inspect evidence artifacts",
            "Use the artifact explorer to review reports, manifests, and summaries.",
            "#artifacts",
        ),
        (
            "Minute 3-4",
            "Check workflow readiness",
            "Review adoption, preflight, workflow-check, and release-check outputs.",
            "artifacts/workflow-check.json",
        ),
        (
            "Minute 4-5",
            "Reproduce locally",
            "Run the deterministic public-demo and proof-packet check commands.",
            "artifacts/proof-packet-index.md",
        ),
    ]
    return "".join(
        f"""<li>
  <span>{escape(minute)}</span>
  <div>
    <h3>{escape(title)}</h3>
    <p>{escape(detail)}</p>
    <a href="{escape(link)}">Open step evidence</a>
  </div>
</li>"""
        for minute, title, detail, link in items
    )


def render_boundaries(data: EvidenceData) -> str:
    """Render explicit public-site non-claims and trust boundaries."""
    items = data.demo.get("trust_boundaries", [])
    if not isinstance(items, list):
        return "<li>The site summarizes supplied VibeBench evidence only.</li>"
    return "".join(f"<li>{escape(str(item))}</li>" for item in items)


def audience_cards(config: SiteConfig) -> str:
    """Render audience-specific entry points."""
    audiences = [
        (
            "Developers",
            "Start with quickstart, CLI checks, adoption-ready, and workflow setup.",
            "artifacts/adoption-ready.md",
        ),
        (
            "Reviewers",
            "Open the report, proof packet index, evidence artifacts, and review path.",
            "artifacts/report/index.html",
        ),
        (
            "Security / compliance evaluators",
            (
                "Inspect trust boundaries, share-check expectations, manifests, "
                "and non-claims."
            ),
            "#trust",
        ),
        (
            "Investors / partners",
            (
                "Use the investor brief, proof matrix, and technical diligence "
                "docs without treating them as market traction."
            ),
            "#diligence",
        ),
        (
            "Maintainers",
            (
                "Use VibeBench to preserve a reproducible evidence trail around "
                "AI-assisted changes."
            ),
            config.repository_url,
        ),
    ]
    return "".join(
        f"""<article class="card audience-card">
  <h3>{escape(title)}</h3>
  <p>{escape(detail)}</p>
  <a href="{escape(link)}">Start here</a>
</article>"""
        for title, detail, link in audiences
    )


def supporting_links(config: SiteConfig) -> str:
    """Render supporting diligence links."""
    links = [
        ("Technical Due Diligence", "docs/technical-due-diligence.md"),
        ("Investor Brief", "docs/investor-brief.md"),
        ("Proof Matrix", "docs/proof-matrix.md"),
        ("Demo Script", "docs/demo-script.md"),
        ("Quickstart", "docs/quickstart.md"),
        ("Public Proof Packet Tour", "docs/public-proof-packet.md"),
    ]
    return "".join(
        f"""<a class="link-card" href="{escape(href)}">
  <span>{escape(title)}</span>
  <small>Repository documentation</small>
</a>"""
        for title, path in links
        for href in [f"{config.repository_url}/blob/main/{path}"]
    )


def render_robots(config: SiteConfig) -> str:
    """Render robots.txt."""
    return clean_text(
        f"""User-agent: *
Allow: {config.base_path}

Sitemap: {urljoin(config.canonical_index, "sitemap.xml")}
"""
    )


def render_sitemap(config: SiteConfig) -> str:
    """Render deterministic sitemap XML."""
    urls = ["", "404.html", "demo.json", "artifacts/report/index.html"]
    entries = "\n".join(
        f"  <url><loc>{escape(urljoin(config.canonical_index, item))}</loc></url>"
        for item in urls
    )
    return clean_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>
"""
    )


def webmanifest(config: SiteConfig) -> dict[str, object]:
    """Return a deterministic web manifest."""
    return {
        "name": "VibeBench Arena",
        "short_name": "VibeBench",
        "description": "Codex-first quality and evidence gate for vibe-coded projects.",
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "background_color": "#f6f2e8",
        "theme_color": "#15302f",
        "icons": [
            {
                "src": "assets/icon.svg",
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any",
            }
        ],
        "id": config.base_path,
    }


def json_ld(config: SiteConfig) -> str:
    """Return conservative JSON-LD metadata."""
    payload = {
        "@context": "https://schema.org",
        "@type": "SoftwareSourceCode",
        "name": "VibeBench Arena",
        "description": "Codex-first quality and evidence gate for vibe-coded projects.",
        "codeRepository": config.repository_url,
        "url": config.canonical_index,
        "programmingLanguage": "Python",
        "license": "https://www.apache.org/licenses/LICENSE-2.0",
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).replace(
        "</",
        "<\\/",
    )


def validate_site(root: Path, config: SiteConfig) -> None:
    """Validate HTML, JSON, XML, links, runtime assets, and leak markers."""
    required = [
        root / "index.html",
        root / "404.html",
        root / "demo.json",
        root / "README.md",
        root / ".nojekyll",
        root / "robots.txt",
        root / "sitemap.xml",
        root / "site.webmanifest",
        root / "assets" / "site.css",
        root / "assets" / "site.js",
        root / "assets" / "icon.svg",
    ]
    for path in required:
        if not path.is_file():
            raise PagesBuildError(f"missing required site file: {path.name}")

    for path in sorted(root.rglob("*.json")):
        json.loads(path.read_text(encoding="utf-8"))
    json.loads((root / "site.webmanifest").read_text(encoding="utf-8"))
    ElementTree.fromstring((root / "sitemap.xml").read_text(encoding="utf-8"))

    for path in sorted(root.rglob("*.html")):
        parser = LinkParser()
        parser.feed(path.read_text(encoding="utf-8"))
        if path.name in {"index.html", "404.html"} and path.parent == root:
            validate_html_accessibility(path, root, parser)
        if parser.remote_runtime_assets:
            raise PagesBuildError(
                f"{path.relative_to(root)} loads remote runtime assets"
            )
        validate_links(root, path, parser.links + parser.script_sources)

    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PagesBuildError(f"site contains symlink: {path.relative_to(root)}")
        if not path.is_file() or path.suffix.lower() not in text_suffixes():
            continue
        scan_text(path, root)

    validate_base_path(root, config)


def validate_html_accessibility(
    html_path: Path,
    root: Path,
    parser: LinkParser,
) -> None:
    """Run basic accessibility-oriented static checks."""
    html = html_path.read_text(encoding="utf-8")
    relative = html_path.relative_to(root)
    if "<html lang=\"en\">" not in html:
        raise PagesBuildError(f"{relative} is missing lang metadata")
    if 'href="#main"' not in html:
        raise PagesBuildError(f"{relative} is missing skip-to-content link")
    h1_count = sum(1 for level, _text in parser.headings if level == 1)
    if h1_count != 1:
        raise PagesBuildError(f"{relative} must contain exactly one h1")
    required_landmarks = {"main"}
    if html_path.name == "index.html":
        required_landmarks.update({"header", "nav", "footer"})
    missing = sorted(required_landmarks - parser.landmarks)
    if missing:
        raise PagesBuildError(f"{relative} missing landmarks: {', '.join(missing)}")
    for _src, alt in parser.image_sources:
        if alt is None:
            raise PagesBuildError(f"{relative} contains an image without alt text")
    if parser.empty_links:
        raise PagesBuildError(f"{relative} contains empty links")
    duplicate_ids = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
    if duplicate_ids:
        raise PagesBuildError(
            f"{relative} has duplicate ids: {', '.join(duplicate_ids)}"
        )
    heading_levels = [level for level, _text in parser.headings]
    for previous, current in zip(heading_levels, heading_levels[1:], strict=False):
        if current - previous > 1:
            raise PagesBuildError(f"{relative} skips heading levels")
    css = (root / "assets" / "site.css").read_text(encoding="utf-8")
    if ":focus-visible" not in css:
        raise PagesBuildError("site.css is missing keyboard focus styles")


def validate_links(root: Path, html_path: Path, links: list[str]) -> None:
    """Validate internal links while allowing ordinary outbound navigation."""
    for link in links:
        if (
            not link
            or link.startswith("#")
            or link.startswith(("http://", "https://", "mailto:"))
        ):
            continue
        if link.startswith("/"):
            raise PagesBuildError(f"{html_path.relative_to(root)} has absolute link")
        target = (html_path.parent / link.split("#", 1)[0]).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise PagesBuildError(
                f"{html_path.relative_to(root)} links outside site: {link}"
            ) from exc
        if not target.exists():
            raise PagesBuildError(
                f"{html_path.relative_to(root)} has missing link: {link}"
            )


def validate_base_path(root: Path, config: SiteConfig) -> None:
    """Validate project Pages subpath metadata and avoid root-relative links."""
    html = (root / "index.html").read_text(encoding="utf-8")
    if f"<code>{escape(config.base_path)}</code>" not in html:
        raise PagesBuildError("index.html does not expose the configured base path")
    manifest = json.loads((root / "site.webmanifest").read_text(encoding="utf-8"))
    if manifest.get("id") != config.base_path:
        raise PagesBuildError("site.webmanifest does not use the configured base path")


def scan_text(path: Path, root: Path) -> None:
    """Scan one generated text file for obvious unsafe content."""
    text = path.read_text(encoding="utf-8", errors="replace")
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            raise PagesBuildError(
                f"{path.relative_to(root)} matches unsafe pattern: {pattern.pattern}"
            )
    lowered = text.lower()
    for marker in unsupported_claim_markers():
        if marker in lowered:
            raise PagesBuildError(
                f"{path.relative_to(root)} contains unsupported claim marker: {marker}"
            )


def compare_if_existing(generated: Path, output_dir: Path) -> list[str]:
    """Compare generated bytes with an existing output directory when present."""
    if not output_dir.exists():
        return []
    if output_dir.is_file():
        return [f"output path is a file: {display_path(output_dir)}"]
    expected = file_set(generated)
    actual = file_set(output_dir)
    differences: list[str] = []
    for relative in sorted(expected - actual):
        differences.append(f"missing: {relative}")
    for relative in sorted(actual - expected):
        differences.append(f"added: {relative}")
    for relative in sorted(expected & actual):
        if not filecmp.cmp(generated / relative, output_dir / relative, shallow=False):
            differences.append(f"changed: {relative}")
    return differences


def write_site(generated: Path, output_dir: Path) -> None:
    """Write the generated site atomically enough for local use."""
    if output_dir.exists():
        if output_dir.is_file():
            raise PagesBuildError(f"output path is a file: {display_path(output_dir)}")
        shutil.rmtree(output_dir)
    shutil.copytree(generated, output_dir)


def read_json(path: Path) -> dict[str, object]:
    """Read a JSON object from path."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PagesBuildError(f"{path.name} must contain a JSON object")
    return data


def file_set(root: Path) -> set[str]:
    """Return deterministic regular file paths below root."""
    return {
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def resolve_output(path: Path) -> Path:
    """Resolve output path relative to the repository root."""
    selected = path if path.is_absolute() else ROOT / path
    selected = selected.resolve()
    if not selected.parent.exists():
        raise PagesBuildError(f"output parent does not exist: {selected.parent}")
    return selected


def builder_env() -> dict[str, str]:
    """Return a controlled environment for reproducible site generation."""
    env = os.environ.copy()
    for key in HOST_GITHUB_ENV_KEYS:
        env.pop(key, None)
    python_path = str(ROOT)
    if env.get("PYTHONPATH"):
        python_path = python_path + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = python_path
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("NO_COLOR", "1")
    env.setdefault("COLUMNS", "120")
    return env


def clean_text(value: str) -> str:
    """Strip trailing whitespace while preserving final newline."""
    return "\n".join(line.rstrip() for line in value.splitlines()) + "\n"


def display_path(path: Path) -> str:
    """Return a stable display path."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name if path.is_absolute() else path.as_posix()


def text_suffixes() -> set[str]:
    """Return text suffixes scanned in the Pages site."""
    return {
        ".html",
        ".json",
        ".md",
        ".txt",
        ".xml",
        ".webmanifest",
        ".yml",
        ".yaml",
        ".css",
        ".js",
        ".svg",
    }


def unsupported_claim_markers() -> tuple[str, ...]:
    """Return unsupported positive claim markers."""
    return (
        "soc 2 certified",
        "iso 27001 certified",
        "independently audited",
        "guaranteed secure",
        "enterprise certified",
        "millions of users",
        "funding guaranteed",
        "unicorn",
        "market leader",
        "best in the world",
    )


def is_runtime_link_tag(tag: str, rel: set[str]) -> bool:
    """Return whether a link tag loads a runtime asset."""
    return tag == "link" and bool(
        rel & {"stylesheet", "preload", "modulepreload", "icon", "manifest"}
    )


def definition(term: str, value: str) -> str:
    """Render a compact definition pair."""
    return f"<dt>{escape(term)}</dt><dd>{escape(value)}</dd>"


def status_text(data: dict[str, object]) -> str:
    """Return public status text."""
    return str(data.get("overall_status") or data.get("status") or "Not included")


def score_text(value: object) -> str:
    """Return public score text."""
    return str(value) if isinstance(value, int | float) else "Not included"


def artifact_count_text(data: dict[str, object]) -> str:
    """Return available/known artifact count text."""
    available = data.get("available_artifact_count")
    total = data.get("artifact_count")
    if isinstance(available, int) and isinstance(total, int):
        return f"{available}/{total} available"
    return "Not included"


def summary_text(summary: object, key: str) -> str:
    """Return a summary count from a JSON summary object."""
    if isinstance(summary, dict) and isinstance(summary.get(key), int):
        return f"{summary[key]} {key}"
    return "Not included"


def manifest_text(artifacts: object) -> str:
    """Return manifest count text."""
    if isinstance(artifacts, list):
        available = sum(
            1 for item in artifacts if isinstance(item, dict) and item.get("available")
        )
        return f"{available}/{len(artifacts)} manifest entries available"
    return "Manifest included"


def evidence_status(data: dict[str, object], evidence_id: str) -> str:
    """Return evidence status for an evidence id."""
    for item in data.get("evidence", []):
        if isinstance(item, dict) and item.get("id") == evidence_id:
            return str(item.get("status", "Not included"))
    return "Not included"


def evidence_link(data: dict[str, object], evidence_id: str) -> str | None:
    """Return evidence link for an evidence id."""
    for item in data.get("evidence", []):
        if isinstance(item, dict) and item.get("id") == evidence_id:
            link = item.get("link")
            return str(link) if link else None
    return None


def artifact_sort_key(item: dict[str, object]) -> tuple[int, str]:
    """Sort available artifacts first, then by stable path/name."""
    return (
        0 if item.get("available") else 1,
        str(item.get("path") or item.get("name")),
    )


def artifact_description(name: str) -> str:
    """Return a fallback artifact explanation."""
    return f"Known VibeBench artifact for reviewer inspection: {name}."


def human_name(value: str) -> str:
    """Return a readable artifact name."""
    return value.replace("-", " ").replace("_", " ")


def slug(value: str) -> str:
    """Return a simple deterministic HTML id slug."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def normalized_url(value: str) -> str:
    """Normalize URL to a trailing slash."""
    return value if value.endswith("/") else value + "/"


def normalized_base_path(value: str) -> str:
    """Normalize a project Pages base path."""
    stripped = value.strip()
    if not stripped.startswith("/"):
        stripped = "/" + stripped
    if not stripped.endswith("/"):
        stripped += "/"
    return stripped


if __name__ == "__main__":
    raise SystemExit(main())
