from pathlib import Path

GUIDE_PATH = Path("docs/reviewer-guide.md")
HUB_PATH = Path("docs/review-hub.html")
TRUST_MARKDOWN_PATH = Path("docs/trust-center.md")
TRUST_HTML_PATH = Path("docs/trust-center.html")
QUESTIONNAIRE_MARKDOWN_PATH = Path("docs/security-questionnaire.md")
QUESTIONNAIRE_HTML_PATH = Path("docs/security-questionnaire.html")

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

TRUST_BANNED_MARKERS = [
    "http://",
    "https://",
    "<script",
    "/tmp/",
    "/home/",
    "/data/code/",
    "soc 2 certified",
    "iso 27001 certified",
    "audited by",
    "independently audited",
    "guaranteed secure",
    "enterprise certified",
    "millions of users",
    "revenue",
    "funding guaranteed",
    "unicorn",
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
        'href="trust-center.html"',
        'href="security-questionnaire.html"',
        'href="evaluate.md"',
        'href="adoption.md"',
        'href="pages.md"',
    ]:
        assert link in content


def test_review_hub_stays_static_local_and_honest() -> None:
    content = HUB_PATH.read_text(encoding="utf-8").lower()

    for marker in BANNED_MARKERS:
        assert marker not in content


def test_trust_center_markdown_exists_and_contains_required_sections() -> None:
    assert TRUST_MARKDOWN_PATH.is_file()
    content = TRUST_MARKDOWN_PATH.read_text(encoding="utf-8")

    for expected in [
        "# VibeBench Arena Trust Center",
        "Local-first",
        "Evidence-room",
        "Proof packet",
        "Static site preview",
        "Reviewer scorecard",
        "JSON output purity",
        "Security and privacy",
        "not a third-party audit",
        "Responsible disclosure",
        (
            "python3 -m vibebench evidence-room --output-dir "
            "/tmp/vibebench-evidence-room --zip"
        ),
        "python3 -m vibebench evidence-room --verify /tmp/vibebench-evidence-room",
        "python3 -m vibebench proof --verify /tmp/vibebench-evidence-room/proof-packet",
        (
            "python3 -m vibebench site-preview --verify "
            "/tmp/vibebench-evidence-room/site-preview"
        ),
        "python3 -m vibebench site-check",
        "python3 -m vibebench ci --dry-run --json",
        "python3 -m vibebench release-check",
        "python3 -m vibebench doctor --strict",
    ]:
        assert expected in content


def test_trust_center_html_exists_links_and_stays_static_local() -> None:
    assert TRUST_HTML_PATH.is_file()
    content = TRUST_HTML_PATH.read_text(encoding="utf-8")
    lowered = content.lower()

    for expected in [
        "Trust Center",
        "Local-first",
        "Evidence-room",
        "Proof packet",
        "Static site preview",
        "Reviewer scorecard",
        "JSON output purity",
        "Security and privacy",
        "not a third-party audit",
        "python3 -m vibebench evidence-room --verify",
        "python3 -m vibebench ci --dry-run --json",
        'href="index.html"',
        'href="review-hub.html"',
        'href="reviewer-guide.md"',
        'href="security-questionnaire.html"',
        'href="pages.md"',
        'href="../SECURITY.md"',
        'href="../README.md"',
    ]:
        assert expected in content

    for marker in TRUST_BANNED_MARKERS:
        assert marker not in lowered


def test_security_questionnaire_markdown_exists_and_contains_required_topics() -> None:
    assert QUESTIONNAIRE_MARKDOWN_PATH.is_file()
    content = QUESTIONNAIRE_MARKDOWN_PATH.read_text(encoding="utf-8")

    for expected in [
        "# VibeBench Arena Security Questionnaire",
        "local-first",
        "Evidence-room",
        "Proof packet",
        "Static site preview",
        "GitHub Actions",
        "JSON stdout",
        "self-contained",
        "not a third-party audit",
        "not claiming SOC 2 certification",
        "not claiming ISO 27001 certification",
        "not claiming an independent third-party audit",
        (
            "python3 -m vibebench evidence-room --output-dir "
            "/tmp/vibebench-evidence-room --zip"
        ),
        "python3 -m vibebench evidence-room --verify /tmp/vibebench-evidence-room",
        (
            "python3 -m vibebench evidence-room --verify "
            "/tmp/vibebench-evidence-room/evidence-room.zip"
        ),
        "python3 -m vibebench proof --verify /tmp/vibebench-evidence-room/proof-packet",
        (
            "python3 -m vibebench site-preview --verify "
            "/tmp/vibebench-evidence-room/site-preview"
        ),
        "python3 -m vibebench site-check",
        "python3 -m vibebench ci --dry-run --json",
        "python3 -m vibebench release-check",
        "python3 -m vibebench doctor --strict",
        "How should security issues be reported?",
    ]:
        assert expected in content


def test_security_questionnaire_html_exists_links_and_stays_static_local() -> None:
    assert QUESTIONNAIRE_HTML_PATH.is_file()
    content = QUESTIONNAIRE_HTML_PATH.read_text(encoding="utf-8")
    lowered = content.lower()

    for expected in [
        "Security Questionnaire",
        "local-first",
        "Evidence-room",
        "Proof packet",
        "Static site preview",
        "GitHub Actions",
        "JSON stdout",
        "self-contained",
        "not a third-party audit",
        "not claiming SOC 2 certification",
        "not claiming ISO 27001 certification",
        "python3 -m vibebench evidence-room --verify",
        "python3 -m vibebench ci --dry-run --json",
        'href="index.html"',
        'href="trust-center.html"',
        'href="review-hub.html"',
        'href="reviewer-guide.md"',
        'href="pages.md"',
        'href="../SECURITY.md"',
        'href="../README.md"',
    ]:
        assert expected in content

    for marker in TRUST_BANNED_MARKERS:
        assert marker not in lowered


def test_security_questionnaire_allows_honest_non_claim_language() -> None:
    content = QUESTIONNAIRE_HTML_PATH.read_text(encoding="utf-8")

    assert "not claiming SOC 2 certification" in content
    assert "not claiming ISO 27001 certification" in content


def test_reviewer_guide_stays_local_and_honest() -> None:
    content = GUIDE_PATH.read_text(encoding="utf-8").lower()

    for marker in BANNED_MARKERS:
        assert marker not in content
