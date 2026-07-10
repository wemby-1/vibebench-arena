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

from vibebench.github_action import ACTION_PREVIEW_WARNING, action_workflow_payload

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
        r"\b(?:google-analytics|googletagmanager|gtag\(|plausible|segment\.com|mixpanel)\b",
        r"sourceMappingURL=",
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
    adoption_ready: dict[str, object]
    release_check: dict[str, object]
    manifest: dict[str, object]
    inventory: dict[str, object]
    artifacts: list[dict[str, object]]


@dataclass(frozen=True)
class RuntimeDependency:
    """A remote value that would be loaded at runtime by the browser."""

    dependency_type: str
    tag: str
    attribute: str
    value: str

    def describe(self) -> str:
        """Return a diagnostic string for workflow logs."""
        return (
            f"type={self.dependency_type} tag={self.tag} "
            f"attribute={self.attribute} value={self.value}"
        )


class LinkParser(HTMLParser):
    """Collect links, asset references, headings, landmarks, and IDs."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.remote_runtime_assets: list[RuntimeDependency] = []
        self.image_sources: list[tuple[str, str | None]] = []
        self.script_sources: list[str] = []
        self.headings: list[tuple[int, str]] = []
        self.landmarks: set[str] = set()
        self.ids: list[str] = []
        self.empty_links: list[str] = []
        self._current_script_type: str | None = None
        self._script_text: list[str] = []
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
        srcset = values.get("srcset")
        data = values.get("data")
        poster = values.get("poster")
        style = values.get("style")
        element_id = values.get("id")
        if element_id:
            self.ids.append(element_id)
        if tag in {"header", "main", "nav", "footer", "section"}:
            self.landmarks.add(tag)
        if href:
            rel = set((values.get("rel") or "").lower().split())
            if is_runtime_link_tag(tag, rel) and is_remote_url(href):
                self.remote_runtime_assets.append(
                    RuntimeDependency("link", tag, "href", href)
                )
            self.links.append(href)
            if tag == "a":
                self._current_link = href
                self._link_text = []
        if src:
            if is_runtime_src_tag(tag) and is_remote_url(src):
                self.remote_runtime_assets.append(
                    RuntimeDependency("source", tag, "src", src)
                )
            if tag == "script":
                self.script_sources.append(src)
            if tag == "img":
                self.image_sources.append((src, values.get("alt")))
        if srcset:
            for candidate in parse_srcset_urls(srcset):
                if is_runtime_srcset_tag(tag) and is_remote_url(candidate):
                    self.remote_runtime_assets.append(
                        RuntimeDependency("srcset", tag, "srcset", candidate)
                    )
        if data and tag == "object" and is_remote_url(data):
            self.remote_runtime_assets.append(
                RuntimeDependency("object", tag, "data", data)
            )
        if poster and tag == "video" and is_remote_url(poster):
            self.remote_runtime_assets.append(
                RuntimeDependency("poster", tag, "poster", poster)
            )
        if style:
            for url in remote_css_urls(style):
                self.remote_runtime_assets.append(
                    RuntimeDependency("css-url", tag, "style", url)
                )
        if tag == "script":
            self._current_script_type = values.get("type", "").lower()
            self._script_text = []
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._current_heading = int(tag[1])
            self._heading_text = []

    def handle_data(self, data: str) -> None:
        if self._current_script_type is not None:
            self._script_text.append(data)
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
        if tag == "script" and self._current_script_type is not None:
            if is_javascript_type(self._current_script_type):
                for url in remote_javascript_runtime_urls(
                    "".join(self._script_text),
                ):
                    self.remote_runtime_assets.append(
                        RuntimeDependency("javascript-runtime", tag, "text", url)
                    )
            self._current_script_type = None
            self._script_text = []


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
    adoption = read_json(root / "artifacts" / "adoption-ready.json")
    release = read_json(root / "artifacts" / "release-check.json")
    manifest = read_json(root / "artifacts" / "manifest.json")
    inventory = read_json(root / "artifacts" / "artifact-inventory.json")
    raw_artifacts = demo.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise PagesBuildError("demo.json does not contain an artifact list")
    artifacts = [item for item in raw_artifacts if isinstance(item, dict)]
    return EvidenceData(
        demo=demo,
        metrics=metrics,
        workflow_check=workflow,
        adoption_ready=adoption,
        release_check=release,
        manifest=manifest,
        inventory=inventory,
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
    for doc_name in ["adoption.md", "github-actions.md"]:
        text = (ROOT / "docs" / doc_name).read_text(encoding="utf-8")
        text = text.replace("GITHUB_STEP_SUMMARY", "the GitHub step summary file")
        (root / doc_name).write_text(text, encoding="utf-8")
    (root / "robots.txt").write_text(render_robots(config), encoding="utf-8")
    (root / "sitemap.xml").write_text(render_sitemap(config), encoding="utf-8")
    (root / "site.webmanifest").write_text(
        json.dumps(webmanifest(config), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def render_index(data: EvidenceData, config: SiteConfig) -> str:
    """Render the public launch site index."""
    title = "VibeBench Arena | Evidence explorer for AI-assisted code"
    description = (
        "VibeBench Arena turns AI-assisted repository work into local checks, "
        "risk signals, readiness reports, and reviewable evidence packets."
    )
    cards = evidence_cards(data)
    categories = artifact_categories(data.artifacts)
    artifacts = sorted(data.artifacts, key=artifact_sort_key)
    action_payload = action_workflow_payload(preset="minimal")
    social_image = urljoin(config.canonical_index, "assets/social-preview.svg")
    category_options = "".join(
        f'<option value="{escape(slug(name))}">{escape(name)}</option>'
        for name, _items in categories
    )
    command_cards = "".join(
        [
            command_panel(
                "First local check",
                "python3 -m vibebench ci --dry-run --json",
            ),
            command_panel(
                "Adoption readiness",
                "python3 -m vibebench adoption-ready --json",
            ),
            command_panel(
                "Rebuild this launch site",
                "python3 scripts/build_pages_site.py "
                "--output-dir review-output/pages-site",
            ),
            command_panel(
                "Verify deterministic demo",
                "python3 scripts/build_public_demo.py --check",
            ),
        ]
    )
    source = escape(str(data.demo.get("source", "Not included")))
    action_configurator = render_action_configurator(action_payload)
    security_url = f"{config.repository_url}/blob/main/SECURITY.md"
    trust_url = f"{config.repository_url}/blob/main/docs/trust-center.md"
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
  <meta property="og:image" content="{escape(social_image)}">
  <meta property="og:image:alt" content="VibeBench Arena evidence explorer preview">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(title)}">
  <meta name="twitter:description" content="{escape(description)}">
  <meta name="twitter:image" content="{escape(social_image)}">
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
        <a href="#overview">Overview</a>
        <a href="#evidence">Evidence</a>
        <a href="#paths">Paths</a>
        <a href="#artifacts">Artifacts</a>
        <a href="#trust">Trust</a>
        <a href="#diligence">Diligence</a>
        <a href="{escape(config.repository_url)}">GitHub</a>
      </div>
    </nav>
  </header>
  <main id="main">
    <section class="hero" id="home" aria-labelledby="hero-title">
      <div class="hero-copy">
        <p class="eyebrow">Local-first evidence for AI-assisted engineering</p>
        <h1 id="hero-title">VibeBench Arena</h1>
        <p class="hero-lede">
          Turn a repository changed by AI into checks, risk signals, adoption
          readiness, release notes, manifests, and proof that reviewers can inspect.
        </p>
        <p class="hero-note">
          Built from a reproducible reference-project run. This page summarizes
          committed demonstration evidence; it is not a hosted scanner and does
          not claim customers, revenue, funding, certification, or product-market fit.
        </p>
        <div class="hero-actions" aria-label="Primary actions">
          <a class="button primary" href="#evidence">Explore the evidence</a>
          <a class="button secondary" href="#try">Try it locally</a>
        </div>
        <ul class="audience-strip" aria-label="Who VibeBench is for">
          <li>Developers</li>
          <li>Technical reviewers</li>
          <li>Investors</li>
          <li>Community evaluators</li>
        </ul>
      </div>
      <aside class="proof-panel" aria-label="Current public proof summary">
        <span class="panel-kicker">Reference evidence snapshot</span>
        <strong>{escape(status_text(data.demo))}</strong>
        <dl>
          {definition("Run", "reference project")}
          {definition("Score", score_text(data.demo.get("score")))}
          {definition("Risk", str(data.demo.get("risk_level", "Not included")))}
          {definition("Artifacts", artifact_count_text(data.demo))}
        </dl>
        <a href="demo.json">Open source demo JSON</a>
      </aside>
    </section>

    <section class="section" id="overview" aria-labelledby="overview-title">
      <div class="section-heading">
        <p class="eyebrow">30-second product frame</p>
        <h2 id="overview-title">Evidence between AI-generated code and human trust</h2>
        <p>
          VibeBench runs local checks, records score and risk signals, verifies
          workflow and adoption readiness, and leaves behind JSON, Markdown,
          HTML, manifests, and proof packets. The goal is not to replace review;
          it is to make review concrete.
        </p>
      </div>
      <div class="how-grid" aria-label="How VibeBench works">
        {workflow_steps()}
      </div>
    </section>

    <section class="section alt" id="evidence" aria-labelledby="evidence-title">
      <div class="section-heading">
        <p class="eyebrow">Evidence-backed proof cards</p>
        <h2 id="evidence-title">Reference run signals, traced to files</h2>
        <p>
          Every value below is derived from committed machine-readable evidence.
          The run is a deterministic reference demonstration, not production
          customer usage.
        </p>
      </div>
      <div class="card-grid evidence-grid">
        {"".join(render_card(card) for card in cards)}
      </div>
    </section>

    <section class="section" id="paths" aria-labelledby="paths-title">
      <div class="section-heading">
        <p class="eyebrow">Audience paths</p>
        <h2 id="paths-title">Choose the route that matches the review job</h2>
        <p>
          The same reference evidence supports different questions. Start with
          the path closest to your role, then drill into artifacts.
        </p>
      </div>
      <div class="card-grid path-grid">
        {audience_paths(config)}
      </div>
    </section>

    <section class="section alt" id="artifacts" aria-labelledby="artifacts-title">
      <div class="section-heading">
        <p class="eyebrow">Interactive evidence explorer</p>
        <h2 id="artifacts-title">Filter the committed artifact map</h2>
        <p>
          Search by artifact name, explanation, category, type, or status. All
          available links are relative safe copies inside this static site.
          Optional missing artifacts remain visible without broken links.
        </p>
      </div>
      <form
        class="explorer-controls"
        data-artifact-filters
        aria-describedby="artifact-filter-status"
      >
        <div class="control-field">
          <label for="artifact-search">Search artifacts</label>
          <input
            id="artifact-search"
            name="q"
            type="search"
            placeholder="Try metrics, release, manifest, proof"
            autocomplete="off"
            data-filter-search
          >
        </div>
        <div class="control-field">
          <label for="artifact-category">Category</label>
          <select id="artifact-category" name="category" data-filter-category>
            <option value="all">All categories</option>
            {category_options}
          </select>
        </div>
        <div class="control-field">
          <label for="artifact-availability">Availability</label>
          <select
            id="artifact-availability"
            name="availability"
            data-filter-availability
          >
            <option value="all">All statuses</option>
            <option value="available">Available evidence</option>
            <option value="missing">Unavailable optional evidence</option>
          </select>
        </div>
        <button class="button secondary" type="reset" data-filter-reset>Reset</button>
      </form>
      <p class="filter-status" id="artifact-filter-status" aria-live="polite">
        Showing all {len(artifacts)} known reference artifacts.
      </p>
      <div class="artifact-results" data-artifact-results>
        {"".join(render_explorer_artifact(item) for item in artifacts)}
      </div>
      <p class="empty-state" data-empty-state hidden>
        No artifacts match these filters. Reset the explorer or try a broader search.
      </p>
      <details class="category-summary">
        <summary>Browse grouped categories without JavaScript</summary>
        <div class="artifact-groups">
          {"".join(render_artifact_group(name, items) for name, items in categories)}
        </div>
      </details>
    </section>

    <section class="section" id="try" aria-labelledby="try-title">
      <div class="section-heading">
        <p class="eyebrow">Try locally</p>
        <h2 id="try-title">Reproduce the reference site or run the CLI</h2>
        <p>
          The launch site is static, deterministic, and works without analytics
          or network runtime dependencies. These commands are visible and
          selectable even when JavaScript is disabled.
        </p>
      </div>
      <div class="command-grid">
        {command_cards}
      </div>
      <p class="copy-feedback" data-copy-feedback aria-live="polite"></p>
    </section>

    {action_configurator}

    <section class="section alt" id="review-path" aria-labelledby="review-path-title">
      <div class="section-heading">
        <p class="eyebrow">Five-minute path</p>
        <h2 id="review-path-title">A fast, evidence-first walkthrough</h2>
      </div>
      <ol class="timeline">
        {review_path()}
      </ol>
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
    <div>
      <strong>Built from committed reference evidence.</strong>
      <p>
        Evidence source: <code>{source}</code>.
        Base path: <code>{escape(config.base_path)}</code>.
      </p>
    </div>
    <nav aria-label="Footer links">
      <a href="{escape(config.repository_url)}">Source repository</a>
      <a href="{escape(security_url)}">Security policy</a>
      <a href="{escape(trust_url)}">Trust Center</a>
      <a href="demo.json">Demo JSON</a>
    </nav>
    <p>
      Runtime CSS, JavaScript, icons, and preview assets are local. No analytics,
      cookies, trackers, remote fonts, or CDN runtime assets are used.
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
    metrics_summary = data.metrics.get("summary")
    workflow_summary = data.workflow_check.get("summary")
    adoption_summary = data.adoption_ready.get("summary")
    release_checks = data.release_check.get("checks")
    manifest_artifacts = data.manifest.get("artifacts")
    return [
        card(
            "Overall status",
            status_text(demo),
            "Reference proof result from the public demo manifest.",
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
            "Checks passed",
            summary_text(metrics_summary, "passed_commands"),
            "Configured reference-project commands captured in metrics.json.",
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
            workflow_mode_text(data.workflow_check, workflow_summary),
            "Workflow-check results for the deterministic reference project.",
            "artifacts/workflow-check.json",
        ),
        card(
            "Adoption readiness",
            readiness_text(data.adoption_ready, adoption_summary),
            "Read-only adoption readiness from committed reference evidence.",
            "artifacts/adoption-ready.json",
        ),
        card(
            "Release readiness",
            release_text(data.release_check, release_checks),
            "Local release-check evidence; it does not publish or create a release.",
            "artifacts/release-check.json",
        ),
        card(
            "Manifest consistency",
            manifest_text(manifest_artifacts),
            "Manifest and inventory files are included for integrity review.",
            "artifacts/manifest.json",
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


def render_action_configurator(payload: dict[str, object]) -> str:
    """Render the reusable action configurator with a no-JS default snippet."""
    workflow = escape(str(payload["workflow"]))
    presets = payload.get("presets") if isinstance(payload.get("presets"), list) else []
    preset_options = "".join(
        f'<option value="{escape(str(item.get("name", "")))}">'
        f'{escape(str(item.get("name", "")).title())}</option>'
        for item in presets
        if isinstance(item, dict)
    )
    preset_data = escape(json.dumps(presets, sort_keys=True), quote=False)
    return clean_text(
        f"""
    <section class="section alt" id="integrate" aria-labelledby="integrate-title">
      <div class="section-heading">
        <p class="eyebrow">Integrate VibeBench</p>
        <h2 id="integrate-title">Generate a preview GitHub Actions workflow</h2>
        <p>
          Choose a preset and copy a small workflow that consumes the reusable
          composite action. The <code>@main</code> reference is preview/development
          only; production consumers should pin a future stable tag or reviewed
          commit SHA.
        </p>
      </div>
      <form class="action-configurator" data-action-configurator>
        <div class="control-field">
          <label for="action-preset">Preset</label>
          <select id="action-preset" name="preset" data-action-preset>
            {preset_options}
          </select>
        </div>
        <div class="control-field">
          <label for="action-config">Config path</label>
          <input
            id="action-config"
            name="config"
            type="text"
            value=""
            placeholder=".vibebench/config.yaml"
            data-action-config
          >
        </div>
        <div class="control-field">
          <label for="action-mode">Required mode</label>
          <input
            id="action-mode"
            name="required-mode"
            type="text"
            value="adoption"
            placeholder="adoption-policy"
            data-action-mode
          >
        </div>
        <label class="toggle-field" for="action-upload">
          <input id="action-upload" name="upload" type="checkbox" data-action-upload>
          <span>Upload evidence artifact</span>
        </label>
      </form>
      <p class="preview-warning">{escape(ACTION_PREVIEW_WARNING)}</p>
      <div class="command-card workflow-snippet">
        <pre id="action-workflow-snippet"><code>{workflow}</code></pre>
        <button
          class="button ghost copy-button"
          type="button"
          data-copy-target="action-workflow-snippet"
        >
          Copy workflow
        </button>
      </div>
      <p>
        Detailed adoption notes live in <a href="adoption.md">adoption.md</a>
        and <a href="github-actions.md">github-actions.md</a>.
      </p>
      <script type="application/json" id="action-preset-data">{preset_data}</script>
    </section>
"""
    )


def artifact_categories(
    artifacts: list[dict[str, object]],
) -> list[tuple[str, list[dict[str, object]]]]:
    """Group artifacts into reviewer-oriented categories."""
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in artifacts:
        grouped.setdefault(artifact_category(item), []).append(item)
    return [
        (name, sorted(grouped.get(name, []), key=artifact_sort_key))
        for name in artifact_category_order()
        if grouped.get(name)
    ]


def artifact_category_order() -> tuple[str, ...]:
    """Return deterministic artifact category order."""
    return (
        "Summary",
        "Checks",
        "Scoring",
        "Risk",
        "Reports",
        "Manifest and inventory",
        "Adoption and workflow readiness",
        "Release readiness",
        "Bundles and proof material",
        "Trend and comparison",
        "Other evidence",
    )


def artifact_category(item: dict[str, object]) -> str:
    """Return a reviewer-facing artifact category."""
    value = str(item.get("path") or item.get("name") or "").lower()
    if "readme" in value or "github-step-summary" in value or "explain" in value:
        return "Summary"
    if "config" in value or "check.log" in value or "gate" in value:
        return "Checks"
    if "metrics" in value:
        return "Scoring"
    if "risk" in value:
        return "Risk"
    if "report" in value:
        return "Reports"
    if "manifest" in value or "inventory" in value:
        return "Manifest and inventory"
    if any(key in value for key in ("workflow", "preflight", "adoption", "onboard")):
        return "Adoption and workflow readiness"
    if "release" in value or "package" in value or "ci-plan" in value:
        return "Release readiness"
    if any(key in value for key in ("proof", "bundle", "share", "security")):
        return "Bundles and proof material"
    if any(key in value for key in ("trend", "compare", "run-index")):
        return "Trend and comparison"
    return "Other evidence"


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


def render_explorer_artifact(item: dict[str, object]) -> str:
    """Render one filterable explorer artifact row."""
    name = str(item.get("name") or item.get("path") or "Unnamed artifact")
    path = str(item.get("path") or name)
    description = str(item.get("description") or artifact_description(name))
    file_type = str(item.get("file_type") or Path(name).suffix.lstrip(".") or "file")
    size = item.get("size_bytes")
    available = bool(item.get("available"))
    link = str(item.get("link")) if available and item.get("link") else ""
    category = artifact_category(item)
    availability = "available" if available else "missing"
    status = "Available" if available else "Unavailable optional evidence"
    size_text = f"{size} bytes" if isinstance(size, int) else "Not included"
    search = " ".join([name, path, description, file_type, category, availability])
    action = (
        f'<a class="artifact-action" href="{escape(link)}">Open artifact</a>'
        if link
        else '<span class="artifact-action muted">Unavailable optional evidence</span>'
    )
    return f"""<article
  class="artifact-result {availability}"
  data-artifact-card
  data-category="{escape(slug(category))}"
  data-availability="{availability}"
  data-search="{escape(search.lower())}"
>
  <div>
    <p class="artifact-meta">{escape(category)} · {escape(file_type)}</p>
    <h3>{escape(human_name(name))}</h3>
    <p>{escape(description)}</p>
  </div>
  <dl>
    {definition("Status", status)}
    {definition("Path", path)}
    {definition("Size", size_text)}
  </dl>
  {action}
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


def audience_paths(config: SiteConfig) -> str:
    """Render audience-specific launch-site paths."""
    quickstart_url = f"{config.repository_url}/blob/main/docs/quickstart.md"
    proof_matrix_url = f"{config.repository_url}/blob/main/docs/proof-matrix.md"
    investor_url = f"{config.repository_url}/blob/main/docs/investor-brief.md"
    diligence_url = (
        f"{config.repository_url}/blob/main/docs/technical-due-diligence.md"
    )
    security_url = f"{config.repository_url}/blob/main/SECURITY.md"
    paths = [
        (
            "Developer",
            (
                "Install, run the first local gate, inspect adoption readiness, "
                "and wire CI when ready."
            ),
            [
                ("Copy first-run command", "#try"),
                ("Review adoption readiness", "artifacts/adoption-ready.md"),
                ("Open quickstart", quickstart_url),
            ],
        ),
        (
            "Technical reviewer",
            (
                "Inspect score, status, risk, checks, proof packet, inventory, "
                "and non-claims."
            ),
            [
                ("Open proof packet", "artifacts/proof-packet-index.md"),
                ("Inspect metrics", "artifacts/metrics.json"),
                ("Read proof matrix", proof_matrix_url),
            ],
        ),
        (
            "Investor / product reviewer",
            (
                "Understand the wedge, product direction, and technical "
                "defensibility without treating hypotheses as traction."
            ),
            [
                ("Read investor brief", investor_url),
                ("Review diligence", diligence_url),
                ("Inspect evidence", "#evidence"),
            ],
        ),
        (
            "Community evaluator",
            (
                "Reproduce the reference project, browse representative "
                "artifacts, and find contribution and security context."
            ),
            [
                ("Browse artifacts", "#artifacts"),
                ("View source", config.repository_url),
                ("Security policy", security_url),
            ],
        ),
    ]
    rendered = []
    for title, detail, links in paths:
        rendered_links = "".join(
            f'<a href="{escape(href)}">{escape(label)}</a>' for label, href in links
        )
        rendered.append(
            f"""<article class="path-card">
  <h3>{escape(title)}</h3>
  <p>{escape(detail)}</p>
  <div class="path-actions">{rendered_links}</div>
</article>"""
        )
    return "".join(rendered)


def command_panel(title: str, command: str) -> str:
    """Render one copyable command panel."""
    element_id = slug(title)
    return f"""<article class="command-card">
  <h3>{escape(title)}</h3>
  <pre><code id="{element_id}-command">{escape(command)}</code></pre>
  <button
    class="button ghost copy-button"
    type="button"
    data-copy-target="{element_id}-command"
  >
    Copy command
  </button>
</article>"""


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
        "description": (
            "Evidence explorer and local-first quality gate for AI-assisted "
            "repositories."
        ),
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
        root / "assets" / "social-preview.svg",
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
            detail = parser.remote_runtime_assets[0].describe()
            raise PagesBuildError(
                f"{path.relative_to(root)} loads remote runtime asset: {detail}"
            )
        validate_links(root, path, parser.links + parser.script_sources)

    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PagesBuildError(f"site contains symlink: {path.relative_to(root)}")
        if not path.is_file() or path.suffix.lower() not in text_suffixes():
            continue
        scan_text(path, root)

    validate_base_path(root, config)
    validate_performance_budgets(root)


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


def validate_performance_budgets(root: Path) -> None:
    """Validate deterministic uncompressed launch-site budgets."""
    budgets = [
        ("index.html", root / "index.html", 150 * 1024),
        ("local JavaScript", root / "assets" / "site.js", 40 * 1024),
        ("local CSS", root / "assets" / "site.css", 80 * 1024),
    ]
    for label, path, maximum in budgets:
        size = path.stat().st_size
        if size > maximum:
            raise PagesBuildError(
                f"{label} exceeds size budget: {size} bytes > {maximum} bytes; "
                "reduce inline content or local asset size"
            )


def scan_text(path: Path, root: Path) -> None:
    """Scan one generated text file for obvious unsafe content."""
    text = path.read_text(encoding="utf-8", errors="replace")
    for dependency in remote_text_runtime_dependencies(path, text):
        raise PagesBuildError(
            f"{path.relative_to(root)} loads remote runtime asset: "
            f"{dependency.describe()}"
        )
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


def is_runtime_src_tag(tag: str) -> bool:
    """Return whether a src attribute loads a runtime asset."""
    return tag in {
        "audio",
        "embed",
        "iframe",
        "img",
        "input",
        "script",
        "source",
        "track",
        "video",
    }


def is_runtime_srcset_tag(tag: str) -> bool:
    """Return whether a srcset attribute loads runtime image media."""
    return tag in {"img", "source"}


def is_remote_url(value: str) -> bool:
    """Return whether a URL is remote."""
    return value.strip().lower().startswith(("http://", "https://"))


def parse_srcset_urls(value: str) -> list[str]:
    """Extract URL candidates from a srcset attribute."""
    return [
        candidate.strip().split()[0]
        for candidate in value.split(",")
        if candidate.strip()
    ]


def remote_css_urls(text: str) -> list[str]:
    """Return remote URLs loaded through CSS url(...)."""
    urls: list[str] = []
    for match in re.finditer(r"url\(\s*(['\"]?)(.*?)\1\s*\)", text, re.IGNORECASE):
        url = match.group(2).strip()
        if is_remote_url(url):
            urls.append(url)
    return urls


def remote_javascript_runtime_urls(text: str) -> list[str]:
    """Return remote URLs loaded by common JavaScript runtime APIs."""
    urls: list[str] = []
    pattern = re.compile(
        r"""
        (?:
          \bfetch\s*\(\s*
          |\bimportScripts\s*\(\s*
          |\bnew\s+WebSocket\s*\(\s*
          |\bimport\s*\(\s*
        )
        (?P<quote>['"])(?P<url>https?://[^'"]+)(?P=quote)
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    for match in pattern.finditer(text):
        urls.append(match.group("url"))
    return urls


def is_javascript_type(value: str) -> bool:
    """Return whether an inline script type should be scanned as JavaScript."""
    return value in {"", "module", "text/javascript", "application/javascript"}


def remote_text_runtime_dependencies(path: Path, text: str) -> list[RuntimeDependency]:
    """Return remote runtime dependencies from CSS or JavaScript text files."""
    suffix = path.suffix.lower()
    if suffix == ".css":
        return [
            RuntimeDependency("css-url", "css", "url", url)
            for url in remote_css_urls(text)
        ]
    if suffix == ".js":
        return [
            RuntimeDependency("javascript-runtime", "javascript", "text", url)
            for url in remote_javascript_runtime_urls(text)
        ]
    return []


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
        label = key.replace("_commands", "").replace("_", " ")
        return f"{summary[key]} {label}"
    return "Not included"


def workflow_mode_text(data: dict[str, object], summary: object) -> str:
    """Return detected workflow mode text."""
    modes = data.get("detected_ci_modes")
    if isinstance(modes, list) and modes:
        return ", ".join(str(mode) for mode in modes)
    return summary_text(summary, "passed")


def readiness_text(data: dict[str, object], summary: object) -> str:
    """Return adoption readiness text."""
    status = str(data.get("status", "Not included"))
    if isinstance(summary, dict) and isinstance(summary.get("passed"), int):
        return f"{status} ({summary['passed']} checks)"
    return status


def release_text(data: dict[str, object], checks: object) -> str:
    """Return release readiness text without hiding non-ready evidence."""
    status = str(data.get("status", "Not included"))
    if isinstance(checks, list):
        passed = sum(
            1
            for item in checks
            if isinstance(item, dict) and item.get("status") == "passed"
        )
        return f"{status} ({passed}/{len(checks)} checks passed)"
    return status


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
