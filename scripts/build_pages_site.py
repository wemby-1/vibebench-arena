#!/usr/bin/env python3
"""Build or check the GitHub Pages public demo site."""

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
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DEMO = ROOT / "examples" / "showcase-artifacts" / "public-demo"
PUBLIC_DEMO_BUILDER = ROOT / "scripts" / "build_public_demo.py"
DEFAULT_OUTPUT = ROOT / "_site"
REPOSITORY_URL = "https://github.com/wemby-1/vibebench-arena"
PAGES_URL = "https://wemby-1.github.io/vibebench-arena/"
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


class LinkParser(HTMLParser):
    """Collect links and runtime asset references from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.remote_assets: list[str] = []
        self.script_sources: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = dict(attrs)
        href = values.get("href")
        src = values.get("src")
        if href:
            if tag == "link" and href.startswith(("http://", "https://")):
                self.remote_assets.append(href)
            self.links.append(href)
        if src:
            if src.startswith(("http://", "https://")):
                self.remote_assets.append(src)
            if tag == "script":
                self.script_sources.append(src)


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
    args = parser.parse_args()

    try:
        output_dir = resolve_output(args.output_dir)
        with tempfile.TemporaryDirectory(
            prefix="vibebench-pages-site-",
            dir=str(output_dir.parent),
        ) as temp:
            generated = Path(temp) / "site"
            build_pages_site(generated)
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


def build_pages_site(output_dir: Path) -> None:
    """Build and validate a deployable static Pages site."""
    verify_public_demo_current()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(
        PUBLIC_DEMO,
        output_dir,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
    )
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    enhance_index(output_dir / "index.html")
    validate_site(output_dir)


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


def enhance_index(index_path: Path) -> None:
    """Add a deterministic live-site entry banner to the copied portal."""
    text = index_path.read_text(encoding="utf-8")
    marker = "  <main>\n"
    if marker not in text:
        raise PagesBuildError("index.html does not contain the expected main element")
    enhanced = text.replace(marker, marker + live_demo_banner(), 1)
    index_path.write_text(clean_text(enhanced), encoding="utf-8")


def live_demo_banner() -> str:
    """Return the Pages-specific intro section."""
    return f"""    <section class="panel live-demo" id="live-demo">
      <p class="eyebrow">Live GitHub Pages Demo</p>
      <h2>VibeBench Arena</h2>
      <p>
        A static presentation of committed, reproducible VibeBench evidence for
        AI-assisted engineering review. It helps visitors see what was checked,
        how to inspect artifacts, and how to reproduce the public proof packet
        locally.
      </p>
      <p>
        This site is built from the deterministic public demo in the repository.
        It is not an independent hosted scanning service.
      </p>
      <p>
        <a href="{REPOSITORY_URL}">Open the repository</a>
        <span>Expected Pages URL: {PAGES_URL}</span>
      </p>
    </section>
"""


def validate_site(root: Path) -> None:
    """Validate HTML, JSON, links, runtime assets, and leak markers."""
    required = [root / "index.html", root / "demo.json", root / "README.md"]
    for path in required:
        if not path.is_file():
            raise PagesBuildError(f"missing required site file: {path.name}")
    if not (root / ".nojekyll").is_file():
        raise PagesBuildError("missing required .nojekyll file")

    for path in sorted(root.rglob("*.json")):
        json.loads(path.read_text(encoding="utf-8"))

    for path in sorted(root.rglob("*.html")):
        parser = LinkParser()
        parser.feed(path.read_text(encoding="utf-8"))
        if parser.remote_assets:
            raise PagesBuildError(
                f"{path.relative_to(root)} loads remote runtime assets"
            )
        if parser.script_sources:
            raise PagesBuildError(f"{path.relative_to(root)} contains script sources")
        validate_links(root, path, parser.links)

    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PagesBuildError(f"site contains symlink: {path.relative_to(root)}")
        if not path.is_file() or path.suffix.lower() not in text_suffixes():
            continue
        scan_text(path, root)


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
    validate_site(generated)
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
    return {".html", ".json", ".md", ".txt", ".yml", ".yaml", ".css"}


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
    )


if __name__ == "__main__":
    raise SystemExit(main())
