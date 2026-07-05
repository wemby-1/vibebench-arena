from pathlib import Path

SHOWCASE_PATH = Path("docs/showcase.html")


def test_showcase_page_exists_and_contains_required_content() -> None:
    content = SHOWCASE_PATH.read_text(encoding="utf-8")

    assert SHOWCASE_PATH.is_file()
    assert "VibeBench Arena" in content
    assert "Codex-first quality console" in content
    assert "proof.html" in content
    assert "proof.json" in content
    assert "proof-manifest.json" in content
    assert (
        "python3 -m vibebench proof --output-dir .vibebench/proof-packet --zip"
        in content
    )
    assert "doctor --strict" in content
    assert "not a replacement for SWE-bench" in content


def test_showcase_page_stays_self_contained_and_honest() -> None:
    content = SHOWCASE_PATH.read_text(encoding="utf-8").lower()
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
