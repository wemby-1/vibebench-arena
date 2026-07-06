from pathlib import Path

GUIDE_PATH = Path("docs/reviewer-guide.md")
HUB_PATH = Path("docs/review-hub.html")

BANNED_MARKERS = [
    "http://",
    "https://",
    "<script",
    "/tmp/",
    "/home/",
    "/data/code/",
    "guaranteed",
    "best in the world",
    "unicorn",
    "millions of users",
    "revenue",
    "funding guaranteed",
]


def test_reviewer_guide_exists_and_contains_required_review_path() -> None:
    assert GUIDE_PATH.is_file()
    content = GUIDE_PATH.read_text(encoding="utf-8")

    assert "VibeBench Arena" in content
    assert "python3 -m vibebench demo" in content
    assert "python3 -m vibebench proof --output-dir" in content
    assert "python3 -m vibebench evidence-room --output-dir" in content
    assert "python3 -m vibebench ci --dry-run --json" in content
    assert "vibebench-proof-packet" in content
    assert "vibebench-site-preview" in content
    assert "vibebench-evidence-room" in content
    assert "python3 -m vibebench proof --verify PATH" in content
    assert "python3 -m vibebench site-preview --verify PATH" in content
    assert "python3 -m vibebench evidence-room --verify PATH" in content


def test_review_hub_exists_and_contains_required_content() -> None:
    assert HUB_PATH.is_file()
    content = HUB_PATH.read_text(encoding="utf-8")

    assert "VibeBench Arena" in content
    assert "Review Hub" in content
    assert "evidence-room" in content
    assert "vibebench-evidence-room" in content
    assert "vibebench-proof-packet" in content
    assert "vibebench-site-preview" in content
    assert "python3 -m vibebench evidence-room --output-dir" in content
    assert "python3 -m vibebench evidence-room --verify" in content
    assert "python3 -m vibebench ci --dry-run --json" in content


def test_review_hub_links_to_key_local_docs() -> None:
    content = HUB_PATH.read_text(encoding="utf-8")

    for link in [
        'href="index.html"',
        'href="showcase.html"',
        'href="reviewer-guide.md"',
        'href="evaluate.md"',
        'href="adoption.md"',
        'href="pages.md"',
    ]:
        assert link in content


def test_review_hub_stays_static_local_and_honest() -> None:
    content = HUB_PATH.read_text(encoding="utf-8").lower()

    for marker in BANNED_MARKERS:
        assert marker not in content


def test_reviewer_guide_stays_local_and_honest() -> None:
    content = GUIDE_PATH.read_text(encoding="utf-8").lower()

    for marker in BANNED_MARKERS:
        assert marker not in content
