from pathlib import Path

INDEX_PATH = Path("docs/index.html")
PAGES_PATH = Path("docs/pages.md")


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
