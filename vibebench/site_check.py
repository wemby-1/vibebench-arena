"""Static site readiness checks for the GitHub Pages-ready docs site."""

import json
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urlparse

REQUIRED_FILES = ("index.html", "showcase.html", "pages.md")
HTML_FILES = ("index.html", "showcase.html")
SITE_FILES = ("index.html", "showcase.html", "pages.md")
INDEX_REQUIRED_CONTENT = (
    "VibeBench Arena",
    "Codex-first quality console",
    "showcase.html",
    "evaluate.md",
    "adoption.md",
    "proof.html",
    "python3 -m vibebench proof --output-dir .vibebench/proof-packet --zip",
    "not a replacement for SWE-bench",
)
PAGES_REQUIRED_CONTENT = (
    "python3 -m http.server 8000 --directory docs",
    "Settings",
    "Pages",
    "main",
    "/docs",
    "GitHub Pages is not enabled automatically",
)
HTML_FORBIDDEN_MARKERS = (
    "http://",
    "https://",
    "<script",
    "</script",
    "cdn",
    "/tmp/",
    "/home/",
    "/data/code/",
)
BANNED_CLAIMS_OR_MARKERS = (
    "guaranteed stars",
    "guaranteed funding",
    "millions of users",
    "enterprise customers",
    "market leader",
    "best in the world",
    "token",
    "api key",
    "password",
    "secret",
)
REQUIRED_DOC_LINKS = (
    "showcase.html",
    "evaluate.md",
    "adoption.md",
    "demo.md",
    "product-strategy.md",
    "commercial-potential.md",
    "comparison.md",
    "faq.md",
    "pages.md",
)


@dataclass(frozen=True)
class SiteCheck:
    """A single site readiness check result."""

    name: str
    status: str
    message: str


class _HrefParser(HTMLParser):
    """Collect href attributes from static HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value)


def run_site_check(root: Path, *, root_label: str | None = None) -> dict[str, object]:
    """Run deterministic static site readiness checks."""
    site_root = root
    checked_files = list(REQUIRED_FILES)
    checks = [
        _check_required_files(site_root),
        _check_required_content(site_root),
        _check_html_safety(site_root),
        _check_claims_and_sensitive_markers(site_root),
        _check_relative_links(site_root),
    ]
    status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return {
        "status": status,
        "root": root_label if root_label is not None else site_root.as_posix(),
        "checked_files": checked_files,
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "message": check.message,
            }
            for check in checks
        ],
    }


def site_check_json(payload: dict[str, object]) -> str:
    """Serialize a site-check payload as stable JSON."""
    return json.dumps(payload, indent=2, sort_keys=True)


def write_site_check_json(payload: dict[str, object], output: Path) -> None:
    """Write a site-check JSON payload to disk."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(site_check_json(payload) + "\n", encoding="utf-8")


def _check_required_files(root: Path) -> SiteCheck:
    missing = [
        relative_path
        for relative_path in REQUIRED_FILES
        if not root.joinpath(relative_path).is_file()
    ]
    if missing:
        return SiteCheck(
            name="required_files",
            status="failed",
            message="Missing required site files: " + ", ".join(missing),
        )
    return SiteCheck(
        name="required_files",
        status="passed",
        message="Required site files are present.",
    )


def _check_required_content(root: Path) -> SiteCheck:
    missing: list[str] = []
    index_text = _read_optional(root / "index.html")
    pages_text = _read_optional(root / "pages.md")
    for phrase in INDEX_REQUIRED_CONTENT:
        if phrase not in index_text:
            missing.append(f"index.html: {phrase}")
    for phrase in PAGES_REQUIRED_CONTENT:
        if phrase not in pages_text:
            missing.append(f"pages.md: {phrase}")

    if missing:
        return SiteCheck(
            name="required_content",
            status="failed",
            message="Missing required content: " + "; ".join(missing),
        )
    return SiteCheck(
        name="required_content",
        status="passed",
        message="Required proof, evaluation, and Pages setup content is present.",
    )


def _check_html_safety(root: Path) -> SiteCheck:
    matches: list[str] = []
    for relative_path in HTML_FILES:
        text = _read_optional(root / relative_path).lower()
        for marker in HTML_FORBIDDEN_MARKERS:
            if marker in text:
                matches.append(f"{relative_path}: {marker}")

    if matches:
        return SiteCheck(
            name="html_safety",
            status="failed",
            message="Forbidden static HTML marker found: " + "; ".join(matches),
        )
    return SiteCheck(
        name="html_safety",
        status="passed",
        message=(
            "Static HTML contains no remote URLs, scripts, CDN markers, "
            "or local absolute paths."
        ),
    )


def _check_claims_and_sensitive_markers(root: Path) -> SiteCheck:
    matches: list[str] = []
    for relative_path in SITE_FILES:
        text = _read_optional(root / relative_path).lower()
        for marker in BANNED_CLAIMS_OR_MARKERS:
            if marker in text:
                matches.append(f"{relative_path}: {marker}")

    if matches:
        return SiteCheck(
            name="claims_and_sensitive_markers",
            status="failed",
            message="Banned claim or sensitive marker found: " + "; ".join(matches),
        )
    return SiteCheck(
        name="claims_and_sensitive_markers",
        status="passed",
        message="Site files avoid banned hype claims and sensitive publishing markers.",
    )


def _check_relative_links(root: Path) -> SiteCheck:
    links_by_page = {
        relative_path: _html_hrefs(root / relative_path) for relative_path in HTML_FILES
    }
    all_hrefs = {
        _normalize_href(href)
        for hrefs in links_by_page.values()
        for href in hrefs
        if _should_check_href(href)
    }
    missing_required_links = [
        relative_path
        for relative_path in REQUIRED_DOC_LINKS
        if relative_path not in all_hrefs
    ]
    broken_links: list[str] = []
    for page, hrefs in links_by_page.items():
        page_path = root / page
        for href in hrefs:
            if not _should_check_href(href):
                continue
            target = page_path.parent / _normalize_href(href)
            if not target.is_file():
                broken_links.append(f"{page}: {href}")

    if missing_required_links or broken_links:
        messages: list[str] = []
        if missing_required_links:
            messages.append(
                "Missing required relative links: "
                + ", ".join(missing_required_links)
            )
        if broken_links:
            messages.append("Broken relative links: " + "; ".join(broken_links))
        return SiteCheck(
            name="relative_links",
            status="failed",
            message=" ".join(messages),
        )
    return SiteCheck(
        name="relative_links",
        status="passed",
        message="Required local docs links are present and resolvable.",
    )


def _read_optional(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _html_hrefs(path: Path) -> list[str]:
    parser = _HrefParser()
    if path.is_file():
        parser.feed(path.read_text(encoding="utf-8"))
    return parser.hrefs


def _should_check_href(href: str) -> bool:
    clean_href = _normalize_href(href)
    parsed = urlparse(clean_href)
    if not clean_href or clean_href.startswith(("#", "../")):
        return False
    return not parsed.scheme and not parsed.netloc


def _normalize_href(href: str) -> str:
    return urldefrag(href.strip())[0]
