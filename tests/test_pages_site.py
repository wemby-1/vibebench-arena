import hashlib
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import yaml

INDEX_PATH = Path("docs/index.html")
PAGES_PATH = Path("docs/pages.md")
ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_pages_site.py"
PUBLIC_DEMO = ROOT / "examples" / "showcase-artifacts" / "public-demo"
PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class LinkParser(HTMLParser):
    """Collect links and runtime asset references."""

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


def test_pages_site_files_exist() -> None:
    assert INDEX_PATH.is_file()
    assert PAGES_PATH.is_file()


def test_pages_index_contains_required_entry_content() -> None:
    content = INDEX_PATH.read_text(encoding="utf-8")

    assert "VibeBench Arena" in content
    assert "Codex-first quality console" in content
    assert "showcase.html" in content
    assert "evaluate.md" in content
    assert "adoption.md" in content
    assert "proof.html" in content
    assert (
        "python3 -m vibebench proof --output-dir .vibebench/proof-packet --zip"
        in content
    )
    assert "not a replacement for SWE-bench" in content


def test_pages_setup_guide_contains_manual_setup_steps() -> None:
    content = PAGES_PATH.read_text(encoding="utf-8")

    assert "python3 -m http.server 8000 --directory docs" in content
    assert "Settings" in content
    assert "Pages" in content
    assert "main" in content
    assert "/docs" in content
    assert "does not enable GitHub Pages automatically" in content


def test_pages_index_stays_static_local_and_honest() -> None:
    content = INDEX_PATH.read_text(encoding="utf-8").lower()
    banned = [
        "http://",
        "https://",
        "<script",
        "/tmp/",
        "/home/",
        "/data/code/",
        "guaranteed stars",
        "guaranteed funding",
        "millions of users",
        "market leader",
        "best in the world",
        "token",
        "api key",
        "password",
        "secret",
    ]

    for phrase in banned:
        assert phrase not in content


def test_pages_builder_creates_site_index_and_nojekyll(tmp_path: Path) -> None:
    output = build_pages(tmp_path)

    assert (output / "index.html").is_file()
    assert (output / ".nojekyll").is_file()
    assert "Live GitHub Pages Demo" in (output / "index.html").read_text(
        encoding="utf-8"
    )


def test_pages_builder_includes_expected_public_demo_artifacts(
    tmp_path: Path,
) -> None:
    output = build_pages(tmp_path)

    for relative in [
        "demo.json",
        "README.md",
        "artifacts/metrics.json",
        "artifacts/manifest.json",
        "artifacts/artifact-inventory.json",
        "artifacts/report/index.html",
        "artifacts/workflow-check.json",
        "artifacts/proof-packet-index.md",
    ]:
        assert (output / relative).is_file(), relative


def test_pages_generated_html_json_and_links_are_valid(tmp_path: Path) -> None:
    output = build_pages(tmp_path)

    for path in output.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    for path in output.rglob("*.html"):
        parser = LinkParser()
        parser.feed(path.read_text(encoding="utf-8"))
        assert not parser.remote_assets
        assert not parser.script_sources
        for link in parser.links:
            if not link or link.startswith(("#", "http://", "https://")):
                continue
            assert not link.startswith("/")
            target = (path.parent / link.split("#", 1)[0]).resolve()
            target.relative_to(output.resolve())
            assert target.exists(), f"{path}: {link}"


def test_pages_site_has_no_local_paths_or_secret_like_values(tmp_path: Path) -> None:
    output = build_pages(tmp_path)
    text = combined_text(output)

    forbidden = [
        r"/home/",
        r"/data/code/",
        r"/tmp/(?!vibebench-demo\b)",
        r"ghp_[A-Za-z0-9_]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"authorization\s*[:=]",
        r"api[_-]?key\s*[:=]",
        r"password\s*[:=]",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    ]
    for pattern in forbidden:
        assert not re.search(pattern, text, flags=re.IGNORECASE), pattern


def test_pages_site_does_not_make_unsupported_claims(tmp_path: Path) -> None:
    output = build_pages(tmp_path)
    lowered = combined_text(output).lower()

    for marker in [
        "soc 2 certified",
        "iso 27001 certified",
        "independently audited",
        "guaranteed secure",
        "enterprise certified",
        "millions of users",
        "funding guaranteed",
        "unicorn",
    ]:
        assert marker not in lowered


def test_pages_repeated_build_is_deterministic(tmp_path: Path) -> None:
    first = build_pages(tmp_path / "one")
    second = build_pages(tmp_path / "two")

    assert snapshot_hashes(first) == snapshot_hashes(second)


def test_pages_check_passes_without_existing_default_site() -> None:
    result = run_builder("--check")

    assert result.returncode == 0, result.stderr + result.stdout
    assert "current" in result.stdout


def test_pages_check_fails_for_tampered_output(tmp_path: Path) -> None:
    output = build_pages(tmp_path)
    (output / "index.html").write_text("tampered\n", encoding="utf-8")

    result = run_builder("--output-dir", str(output), "--check")

    assert result.returncode != 0
    assert "changed: index.html" in result.stderr


def test_pages_arbitrary_output_dir_works(tmp_path: Path) -> None:
    output = tmp_path / "custom-pages-output"

    result = run_builder("--output-dir", str(output))

    assert result.returncode == 0, result.stderr + result.stdout
    assert (output / "index.html").is_file()
    assert (output / ".nojekyll").is_file()


def test_pages_simulated_github_actions_environment_is_isolated(
    tmp_path: Path,
) -> None:
    output = tmp_path / "actions-site"
    host_summary = tmp_path / "host-summary.md"
    host_summary.write_text("host summary\n", encoding="utf-8")
    root_runs_before = snapshot_optional_tree(ROOT / ".vibebench" / "runs")
    root_baselines_before = snapshot_optional_tree(ROOT / ".vibebench" / "baselines")
    env = os.environ.copy()
    env.update(
        {
            "GITHUB_ACTIONS": "true",
            "CI": "true",
            "GITHUB_PAGES": "true",
            "GITHUB_STEP_SUMMARY": str(host_summary),
        }
    )

    result = run_builder("--output-dir", str(output), env=env)

    assert result.returncode == 0, result.stderr + result.stdout
    assert host_summary.read_text(encoding="utf-8") == "host summary\n"
    assert str(host_summary) not in combined_text(output)
    assert snapshot_optional_tree(ROOT / ".vibebench" / "runs") == root_runs_before
    assert (
        snapshot_optional_tree(ROOT / ".vibebench" / "baselines")
        == root_baselines_before
    )


def test_pages_workflow_has_required_pages_structure() -> None:
    workflow = yaml.safe_load(PAGES_WORKFLOW.read_text(encoding="utf-8"))

    assert workflow["name"] == "Deploy public demo"
    assert "push" in workflow[True]
    assert workflow[True]["push"]["branches"] == ["main"]
    assert "workflow_dispatch" in workflow[True]
    assert workflow["permissions"] == {
        "contents": "read",
        "pages": "write",
        "id-token": "write",
    }
    assert workflow["concurrency"]["group"] == "pages"
    assert set(workflow["jobs"]) == {"build", "deploy"}
    assert workflow["jobs"]["deploy"]["needs"] == "build"
    assert workflow["jobs"]["deploy"]["environment"]["name"] == "github-pages"

    build_steps = workflow["jobs"]["build"]["steps"]
    deploy_steps = workflow["jobs"]["deploy"]["steps"]
    assert step_uses(build_steps, "actions/configure-pages@v5")
    assert step_uses(build_steps, "actions/upload-pages-artifact@v4")
    assert step_uses(deploy_steps, "actions/deploy-pages@v4")
    assert step_run_contains(
        build_steps,
        "python3 scripts/build_pages_site.py --output-dir _site",
    )
    upload_step = next(
        step
        for step in build_steps
        if step.get("uses") == "actions/upload-pages-artifact@v4"
    )
    assert upload_step["with"]["path"] == "_site"


def test_existing_ci_workflow_does_not_publish_pages() -> None:
    content = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "scripts/build_pages_site.py" not in content
    assert "actions/configure-pages" not in content
    assert "actions/upload-pages-artifact" not in content
    assert "actions/deploy-pages" not in content


def build_pages(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    output = tmp_path / "site"
    result = run_builder("--output-dir", str(output))
    assert result.returncode == 0, result.stderr + result.stdout
    return output


def run_builder(
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BUILDER), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def snapshot_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def snapshot_optional_tree(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def combined_text(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.suffix.lower() in {".html", ".json", ".md", ".txt", ".yml", ".yaml"}
    )


def step_uses(steps: list[dict[str, object]], value: str) -> bool:
    return any(step.get("uses") == value for step in steps)


def step_run_contains(steps: list[dict[str, object]], value: str) -> bool:
    return any(value in str(step.get("run", "")) for step in steps)
