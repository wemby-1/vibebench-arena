import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "examples" / "reference-project"
PACKET = ROOT / "examples" / "showcase-artifacts" / "public-proof"
BUILDER = ROOT / "scripts" / "build_public_proof_packet.py"
EXPECTED_REFERENCE_FILES = [
    "README.md",
    "pyproject.toml",
    ".vibebench/config.yaml",
    ".github/workflows/ci.yml",
    "reference_app/calculator.py",
    "tests/test_calculator.py",
]
EXPECTED_PACKET_FILES = [
    "README.md",
    "proof-packet-index.md",
    "metrics.json",
    "manifest.json",
    "config-check.json",
    "config-check.md",
    "workflow-check.json",
    "workflow-check.md",
    "preflight.json",
    "preflight.md",
    "release-check.json",
    "release-check.md",
    "gate-summary.md",
    "report/index.html",
]
JSON_PACKET_FILES = [
    "metrics.json",
    "manifest.json",
    "config-check.json",
    "workflow-check.json",
    "preflight.json",
    "release-check.json",
    "adoption-ready.json",
    "artifact-inventory.json",
]
FORBIDDEN_PATTERNS = [
    r"/home/",
    r"/data/",
    r"yangdongjiang",
    r"user-Super-Server",
    r"10\.106\.",
    r"api_key\s*[:=]",
    r"API_KEY\s*[:=]",
    r"bearer\s+[A-Za-z0-9._-]+",
    r"password\s*[:=]",
    r"secret\s*[:=]",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
]


def test_reference_project_expected_files_exist() -> None:
    for relative in EXPECTED_REFERENCE_FILES:
        assert (REFERENCE / relative).is_file(), relative


def test_reference_config_parses_successfully() -> None:
    payload = yaml.safe_load((REFERENCE / ".vibebench/config.yaml").read_text())
    assert payload["project"]["name"] == "vibebench-reference-project"
    assert payload["checks"]["test"]
    assert payload["workflow_check"]["policy"]["required_ci_modes"] == [
        "adoption-policy"
    ]


def test_reference_workflow_exposes_adoption_policy_mode() -> None:
    workflow = (REFERENCE / ".github/workflows/ci.yml").read_text()
    assert "python3 -m vibebench ci" in workflow
    assert "--adoption-policy" in workflow
    assert "--require-adoption-workflow" in workflow


def test_public_packet_expected_artifacts_exist_and_json_parses() -> None:
    for relative in EXPECTED_PACKET_FILES:
        assert (PACKET / relative).is_file(), relative
    for relative in JSON_PACKET_FILES:
        payload = json.loads((PACKET / relative).read_text())
        assert isinstance(payload, dict)


def test_public_packet_contains_no_forbidden_paths_or_credentials() -> None:
    for path in PACKET.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            assert not re.search(pattern, text, flags=re.IGNORECASE), (
                path.relative_to(ROOT),
                pattern,
            )


def test_public_packet_matches_builder_check_and_is_read_only() -> None:
    before = {
        path.relative_to(PACKET).as_posix(): path.read_bytes()
        for path in PACKET.rglob("*")
        if path.is_file()
    }
    completed = subprocess.run(
        [sys.executable, str(BUILDER), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    after = {
        path.relative_to(PACKET).as_posix(): path.read_bytes()
        for path in PACKET.rglob("*")
        if path.is_file()
    }
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "current" in completed.stdout
    assert after == before


def test_builder_failure_returns_non_zero_and_useful_output(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    spec = importlib.util.spec_from_file_location("proof_builder", BUILDER)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REFERENCE", tmp_path / "missing-reference")
    monkeypatch.setattr(sys, "argv", [str(BUILDER), "--check"])

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code != 0
    assert "public proof packet build failed" in captured.err


def test_internal_public_packet_links_resolve() -> None:
    markdown_files = [
        PACKET / "README.md",
        PACKET / "proof-packet-index.md",
        ROOT / "docs" / "public-proof-packet.md",
    ]
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for markdown in markdown_files:
        text = markdown.read_text(encoding="utf-8")
        for match in link_pattern.finditer(text):
            target = match.group(1)
            if "://" in target or target.startswith("#"):
                continue
            target_path = (markdown.parent / target.split("#", 1)[0]).resolve()
            assert target_path.exists(), f"{markdown}: {target}"
