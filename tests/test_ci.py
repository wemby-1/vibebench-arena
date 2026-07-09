import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vibebench.cli import app
from vibebench.config import default_config_yaml
from vibebench.manifest import check_manifest

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_github_step_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent CI tests from writing to a real GitHub Actions summary."""
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


def config_path(root: Path) -> Path:
    return root / ".vibebench" / "config.yaml"


def workflow_path(root: Path) -> Path:
    return root / ".github" / "workflows" / "vibebench.yml"


def write_config(
    root: Path,
    test_command: str | None = None,
    *,
    fail_on_regression: bool | None = None,
    include_compare: bool = True,
    regression_policy: str | None = None,
) -> None:
    config_path(root).parent.mkdir(parents=True, exist_ok=True)
    selected_test_command = test_command or f"{sys.executable} -c 'print(1)'"
    config = default_config_yaml()
    config = config.replace("pytest -q", selected_test_command)
    config = config.replace("ruff check .", f"{sys.executable} -c 'print(2)'")
    if fail_on_regression is not None:
        config = config.replace(
            "fail_on_regression: false",
            f"fail_on_regression: {str(fail_on_regression).lower()}",
        )
    if not include_compare:
        config = config.replace(
            "compare:\n  fail_on_regression: false\n",
            "",
        )
    if regression_policy is not None:
        default_regression = (
            "regression:\n"
            "  enabled: false\n"
            "  baseline_label: null\n"
            "  require_baseline: false\n"
            "  max_score_drop: 0.0\n"
            "  max_risk_increase: 0.0\n"
            "  fail_on_missing_metrics: true\n"
        )
        config = config.replace(default_regression, regression_policy)
    config_path(root).write_text(config, encoding="utf-8")
    write_package_metadata(root)


def append_metrics_diff_policy(root: Path, policy_yaml: str) -> None:
    target = config_path(root)
    config = target.read_text(encoding="utf-8")
    if "metrics_diff:" in config:
        config = config.split("metrics_diff:\n", 1)[0].rstrip() + "\n"
    target.write_text(
        config + "metrics_diff:\n  policy:\n" + policy_yaml,
        encoding="utf-8",
    )


def append_project_scan_policy(root: Path, policy_yaml: str) -> None:
    target = config_path(root)
    config = target.read_text(encoding="utf-8")
    if "project_scan:" in config:
        config = config.split("project_scan:\n", 1)[0].rstrip() + "\n"
    target.write_text(
        config + "project_scan:\n  policy:\n" + policy_yaml,
        encoding="utf-8",
    )


def append_preflight_policy(root: Path, policy_yaml: str) -> None:
    target = config_path(root)
    config = target.read_text(encoding="utf-8")
    if "preflight:" in config:
        config = config.split("preflight:\n", 1)[0].rstrip() + "\n"
    target.write_text(
        config + "preflight:\n  policy:\n" + policy_yaml,
        encoding="utf-8",
    )


def append_onboard_policy(root: Path, policy_yaml: str) -> None:
    target = config_path(root)
    config = target.read_text(encoding="utf-8")
    if "onboard:" in config:
        config = config.split("onboard:\n", 1)[0].rstrip() + "\n"
    target.write_text(
        config + "onboard:\n  policy:\n" + policy_yaml,
        encoding="utf-8",
    )


def append_workflow_check_policy(root: Path, policy_yaml: str) -> None:
    target = config_path(root)
    config = target.read_text(encoding="utf-8")
    if "workflow_check:" in config:
        config = config.split("workflow_check:\n", 1)[0].rstrip() + "\n"
    target.write_text(
        config + "workflow_check:\n  policy:\n" + policy_yaml,
        encoding="utf-8",
    )


def write_minimal_vibebench_workflow(root: Path) -> Path:
    target = workflow_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        """name: VibeBench
on: [push]
jobs:
  vibebench:
    runs-on: ubuntu-latest
    steps:
      - run: python3 -m vibebench ci --json
""",
        encoding="utf-8",
    )
    return target


def write_package_metadata(root: Path) -> None:
    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    root.joinpath("README.md").write_text("# Demo\n", encoding="utf-8")
    root.joinpath("README.zh-CN.md").write_text("# Demo\n", encoding="utf-8")
    root.joinpath("LICENSE").write_text("Apache-2.0\n", encoding="utf-8")
    docs.joinpath("quickstart.md").write_text("# Quickstart\n", encoding="utf-8")
    docs.joinpath("github-actions.md").write_text("# Actions\n", encoding="utf-8")
    root.joinpath("ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    write_static_site_docs(docs)
    root.joinpath("pyproject.toml").write_text(
        """
[project]
name = "vibebench-arena"
version = "0.3.0"
readme = "README.md"
requires-python = ">=3.11"
license = { file = "LICENSE" }

[project.scripts]
vibebench = "vibebench.cli:main"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def write_static_site_docs(docs: Path) -> None:
    """Write the minimal docs site required by evidence-room generation."""
    index = """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>VibeBench Arena</title></head>
<body>
<h1>VibeBench Arena</h1>
<p>Codex-first quality console for vibe-coding projects.</p>
<a href="showcase.html">Product showcase</a>
<a href="evaluate.md">Evaluate</a>
<a href="adoption.md">Adopt</a>
<a href="demo.md">Demo</a>
<a href="product-strategy.md">Strategy</a>
<a href="commercial-potential.md">Commercial potential</a>
<a href="comparison.md">Comparison</a>
<a href="faq.md">FAQ</a>
<a href="pages.md">Pages</a>
<p>Review the self-contained proof.html report.</p>
<code>python3 -m vibebench proof --output-dir .vibebench/proof-packet --zip</code>
<p>VibeBench Arena is not a replacement for SWE-bench.</p>
</body>
</html>
""".strip()
    showcase = """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>VibeBench Arena</title></head>
<body>
<h1>VibeBench Arena</h1>
<p>Codex-first quality console for evidence-first review.</p>
<p>proof.html, proof.json, proof.md, proof-manifest.json, proof.zip</p>
<a href="showcase.html">Product showcase</a>
<a href="evaluate.md">Evaluate</a>
<a href="adoption.md">Adopt</a>
<a href="demo.md">Demo</a>
<a href="product-strategy.md">Strategy</a>
<a href="commercial-potential.md">Commercial potential</a>
<a href="comparison.md">Comparison</a>
<a href="faq.md">FAQ</a>
<a href="pages.md">Pages</a>
</body>
</html>
""".strip()
    pages = """
# Pages

`docs/index.html` is the static entry. `docs/showcase.html` is the product page.

Preview locally:

`python3 -m http.server 8000 --directory docs`

Manual setup: Settings, Pages, Deploy from a branch, main, /docs.

GitHub Pages is not enabled automatically.
""".strip()
    docs.joinpath("index.html").write_text(index + "\n", encoding="utf-8")
    docs.joinpath("showcase.html").write_text(showcase + "\n", encoding="utf-8")
    docs.joinpath("pages.md").write_text(pages + "\n", encoding="utf-8")
    docs.joinpath("review-hub.html").write_text(
        """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>VibeBench Arena Review Hub</title></head>
<body>
<h1>VibeBench Arena Review Hub</h1>
<a href="index.html">Site entry</a>
<a href="showcase.html">Product page</a>
<a href="reviewer-guide.md">Reviewer guide</a>
<a href="trust-center.html">Trust Center</a>
<a href="evaluate.md">Evaluate</a>
<a href="adoption.md">Adopt</a>
<a href="pages.md">Pages</a>
<p>vibebench-proof-packet vibebench-site-preview vibebench-evidence-room</p>
<code>python3 -m vibebench evidence-room --output-dir PATH --zip</code>
<code>python3 -m vibebench evidence-room --verify PATH</code>
<code>python3 -m vibebench ci --dry-run --json</code>
</body>
</html>
""".strip()
        + "\n",
        encoding="utf-8",
    )
    docs.joinpath("reviewer-guide.md").write_text(
        """
# VibeBench Arena Reviewer Guide

Run `python3 -m vibebench demo`.
Run `python3 -m vibebench proof --output-dir PATH --zip`.
Run `python3 -m vibebench evidence-room --output-dir PATH --zip`.
Run `python3 -m vibebench ci --dry-run --json`.

Download `vibebench-proof-packet`.
Download `vibebench-site-preview`.
Download `vibebench-evidence-room`.

Verify with `python3 -m vibebench proof --verify PATH`.
Verify with `python3 -m vibebench site-preview --verify PATH`.
Verify with `python3 -m vibebench evidence-room --verify PATH`.
""".strip()
        + "\n",
        encoding="utf-8",
    )
    docs.joinpath("trust-center.html").write_text(
        """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>VibeBench Arena Trust Center</title></head>
<body>
<h1>VibeBench Arena Trust Center</h1>
<p>Local-first Evidence-room Proof packet Static site preview Reviewer scorecard.</p>
<p>JSON output purity. Security and privacy boundaries.</p>
<p>This is project-maintained documentation, not a third-party audit.</p>
<a href="index.html">Site entry</a>
<a href="review-hub.html">Review hub</a>
<a href="reviewer-guide.md">Reviewer guide</a>
<a href="pages.md">Pages</a>
<a href="../SECURITY.md">Security policy</a>
<a href="../README.md">README</a>
<code>python3 -m vibebench evidence-room --verify PATH</code>
<code>python3 -m vibebench ci --dry-run --json</code>
</body>
</html>
""".strip()
        + "\n",
        encoding="utf-8",
    )
    docs.joinpath("trust-center.md").write_text(
        """
# VibeBench Arena Trust Center

Local-first operation.
Evidence-room package.
Proof packet.
Static site preview.
Reviewer scorecard.
JSON output purity.
Security and privacy boundaries.
This is project-maintained documentation, not a third-party audit.

```bash
python3 -m vibebench evidence-room --output-dir /tmp/vibebench-evidence-room --zip
python3 -m vibebench evidence-room --verify /tmp/vibebench-evidence-room
python3 -m vibebench proof --verify /tmp/vibebench-evidence-room/proof-packet
python3 -m vibebench site-preview --verify /tmp/vibebench-evidence-room/site-preview
python3 -m vibebench site-check
python3 -m vibebench ci --dry-run --json
python3 -m vibebench release-check
python3 -m vibebench doctor --strict
```
""".strip()
        + "\n",
        encoding="utf-8",
    )
    docs.joinpath("security-questionnaire.html").write_text(
        """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>VibeBench Arena Security Questionnaire</title></head>
<body>
<h1>VibeBench Arena Security Questionnaire</h1>
<p>This questionnaire is project-maintained documentation, not a third-party audit,
security certification, or compliance certification.</p>
<p>Local-first Evidence-room Proof packet Static site preview GitHub Actions
JSON stdout self-contained.</p>
<p>No cloud service is required for local evaluation. The local CLI does not
upload source code.</p>
<p>Local evaluation does not require secrets or tokens.</p>
<p>Generated static HTML uses relative links and avoids remote resources.</p>
<p>VibeBench is not claiming SOC 2 certification.</p>
<p>VibeBench is not claiming ISO 27001 certification.</p>
<p>VibeBench is not claiming an independent third-party audit.</p>
<a href="index.html">Site entry</a>
<a href="trust-center.html">Trust Center</a>
<a href="review-hub.html">Review hub</a>
<a href="reviewer-guide.md">Reviewer guide</a>
<a href="pages.md">Pages</a>
<a href="../SECURITY.md">Security policy</a>
<a href="../README.md">README</a>
<code>python3 -m vibebench evidence-room --verify PATH</code>
<code>python3 -m vibebench ci --dry-run --json</code>
</body>
</html>
""".strip()
        + "\n",
        encoding="utf-8",
    )
    docs.joinpath("security-questionnaire.md").write_text(
        """
# VibeBench Arena Security Questionnaire

This questionnaire is project-maintained documentation, not a third-party audit,
security certification, or compliance certification.

Local-first Evidence-room Proof packet Static site preview GitHub Actions
JSON stdout self-contained.

Local evaluation does not require secrets or tokens.

VibeBench is not claiming SOC 2 certification.
VibeBench is not claiming ISO 27001 certification.
VibeBench is not claiming an independent third-party audit.

```bash
python3 -m vibebench evidence-room --output-dir /tmp/vibebench-evidence-room --zip
python3 -m vibebench evidence-room --verify /tmp/vibebench-evidence-room
python3 -m vibebench evidence-room --verify PATH/evidence-room.zip
python3 -m vibebench proof --verify /tmp/vibebench-evidence-room/proof-packet
python3 -m vibebench site-preview --verify /tmp/vibebench-evidence-room/site-preview
python3 -m vibebench site-check
python3 -m vibebench ci --dry-run --json
python3 -m vibebench release-check
python3 -m vibebench doctor --strict
```
""".strip()
        + "\n",
        encoding="utf-8",
    )
    for name in [
        "evaluate.md",
        "adoption.md",
        "demo.md",
        "product-strategy.md",
        "commercial-potential.md",
        "comparison.md",
        "faq.md",
    ]:
        docs.joinpath(name).write_text(f"# {name}\n", encoding="utf-8")


def init_git_repo(root: Path) -> None:
    """Create a clean git baseline for check runs."""
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=root,
        check=True,
        capture_output=True,
    )


def sample_metrics(
    *,
    status: str = "passed",
    score: int = 100,
    risk: str = "low",
    findings: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "project_name": "demo-project",
        "created_at": "2026-06-29T12:00:00Z",
        "overall_status": status,
        "score": score,
        "risk_level": risk,
        "command_results": [],
        "diff_analysis": {
            "git_available": True,
            "changed_files": [],
            "deleted_files": [],
            "added_files": [],
            "modified_files": [],
            "renamed_files": [],
            "test_files_changed": [],
            "tests_deleted": [],
            "forbidden_paths_touched": [],
            "secret_like_files_touched": [],
            "lockfiles_changed": [],
            "total_added_lines": 0,
            "total_deleted_lines": 0,
            "total_patch_lines": 0,
            "changed_file_count": 0,
            "warnings": [],
            "file_changes": [],
        },
        "risk_findings": findings or [],
        "summary": {
            "total_commands": 0,
            "passed_commands": 0,
            "failed_commands": 0,
            "total_findings": len(findings or []),
            "critical_findings": 0,
            "high_findings": 0,
            "warning_findings": 0,
            "info_findings": 0,
        },
    }


def write_run(
    project_root: Path,
    name: str = "20260629_120000",
    *,
    metrics: dict[str, object] | None = None,
    with_report_asset: bool = False,
) -> Path:
    run_dir = project_root / ".vibebench" / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics or sample_metrics(), indent=2),
        encoding="utf-8",
    )
    (run_dir / "check.log").write_text("check log\n", encoding="utf-8")
    if with_report_asset:
        asset_dir = run_dir / "report" / "assets"
        asset_dir.mkdir(parents=True)
        asset_dir.joinpath("style.css").write_text("body {}\n", encoding="utf-8")
    return run_dir


def latest_run(root: Path) -> Path:
    return sorted((root / ".vibebench" / "runs").iterdir())[-1]


def zip_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return sorted(archive.namelist())


def test_ci_command_succeeds_on_clean_passing_run(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Final CI verdict: passed" in result.output
    run_dir = latest_run(tmp_path)
    assert run_dir.joinpath("metrics.json").exists()


def test_ci_command_creates_standard_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    run_dir = latest_run(tmp_path)
    assert run_dir.joinpath("report", "index.html").exists()
    assert run_dir.joinpath("pr-comment.md").exists()
    assert run_dir.joinpath("explain.md").exists()
    assert run_dir.joinpath("vibebench-bundle.zip").exists()
    assert run_dir.joinpath("export.json").exists()
    assert run_dir.joinpath("badge.json").exists()
    assert run_dir.joinpath("badge.md").exists()
    assert run_dir.joinpath("status-block.md").exists()
    assert run_dir.joinpath("trend.md").exists()
    assert run_dir.joinpath("trend.json").exists()
    assert run_dir.joinpath("run-index.json").exists()
    assert run_dir.joinpath("run-index.md").exists()
    assert run_dir.joinpath("compare.json").exists()
    assert run_dir.joinpath("compare.md").exists()
    assert not run_dir.joinpath("metrics-check.json").exists()
    assert not run_dir.joinpath("metrics-check.md").exists()
    assert not run_dir.joinpath("project-scan.json").exists()
    assert not run_dir.joinpath("project-scan.md").exists()
    assert not run_dir.joinpath("onboard.json").exists()
    assert not run_dir.joinpath("onboard.md").exists()
    assert not run_dir.joinpath("regression-check.json").exists()
    assert not run_dir.joinpath("regression-check.md").exists()
    assert run_dir.joinpath("evidence-room", "evidence-room.html").exists()
    assert run_dir.joinpath("evidence-room", "evidence-room.json").exists()
    assert run_dir.joinpath("evidence-room", "evidence-room.md").exists()
    assert run_dir.joinpath("evidence-room", "evidence-room.zip").exists()
    assert run_dir.joinpath("evidence-room", "proof-packet", "proof.html").exists()
    assert run_dir.joinpath("evidence-room", "site-preview", "index.html").exists()
    assert run_dir.joinpath("config-check.json").exists()
    assert run_dir.joinpath("config-check.md").exists()
    assert run_dir.joinpath("package-check.json").exists()
    assert run_dir.joinpath("package-check.md").exists()
    assert run_dir.joinpath("manifest.json").exists()
    assert "config-check" in result.output
    assert "manifest-check" in result.output
    assert run_dir.joinpath("gate-summary.md").exists()
    assert run_dir.joinpath("github-step-summary.md").exists()


def test_ci_attempts_artifacts_when_gate_fails(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path, metrics=sample_metrics(score=70))

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 1
    assert "gate" in result.output
    assert "failed" in result.output
    assert run_dir.joinpath("report", "index.html").exists()
    assert run_dir.joinpath("pr-comment.md").exists()
    assert run_dir.joinpath("explain.md").exists()
    assert run_dir.joinpath("vibebench-bundle.zip").exists()
    assert run_dir.joinpath("export.json").exists()
    assert run_dir.joinpath("badge.json").exists()
    assert run_dir.joinpath("badge.md").exists()
    assert run_dir.joinpath("status-block.md").exists()
    assert run_dir.joinpath("trend.md").exists()
    assert run_dir.joinpath("trend.json").exists()
    assert run_dir.joinpath("run-index.json").exists()
    assert run_dir.joinpath("run-index.md").exists()
    assert run_dir.joinpath("compare.json").exists()
    assert run_dir.joinpath("compare.md").exists()
    assert run_dir.joinpath("evidence-room", "evidence-room.html").exists()
    assert run_dir.joinpath("evidence-room", "evidence-room.zip").exists()
    assert run_dir.joinpath("config-check.json").exists()
    assert run_dir.joinpath("config-check.md").exists()
    assert run_dir.joinpath("manifest.json").exists()
    assert run_dir.joinpath("github-step-summary.md").exists()


def test_skip_flags_skip_artifact_generation(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-report",
            "--skip-pr-comment",
            "--skip-explain",
            "--skip-bundle",
            "--skip-export",
            "--skip-badge",
            "--skip-status-block",
            "--skip-trend",
            "--skip-run-index",
            "--skip-compare",
            "--skip-evidence-room",
            "--skip-config-check",
            "--skip-package-check",
            "--skip-manifest",
            "--skip-gh-summary",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("report", "index.html").exists()
    assert not run_dir.joinpath("pr-comment.md").exists()
    assert not run_dir.joinpath("explain.md").exists()
    assert not run_dir.joinpath("vibebench-bundle.zip").exists()
    assert not run_dir.joinpath("export.json").exists()
    assert not run_dir.joinpath("badge.json").exists()
    assert not run_dir.joinpath("badge.md").exists()
    assert not run_dir.joinpath("status-block.md").exists()
    assert not run_dir.joinpath("trend.md").exists()
    assert not run_dir.joinpath("trend.json").exists()
    assert not run_dir.joinpath("run-index.json").exists()
    assert not run_dir.joinpath("run-index.md").exists()
    assert not run_dir.joinpath("compare.json").exists()
    assert not run_dir.joinpath("compare.md").exists()
    assert not run_dir.joinpath("evidence-room").exists()
    assert not run_dir.joinpath("config-check.json").exists()
    assert not run_dir.joinpath("config-check.md").exists()
    assert not run_dir.joinpath("package-check.json").exists()
    assert not run_dir.joinpath("package-check.md").exists()
    assert not run_dir.joinpath("manifest.json").exists()
    assert not run_dir.joinpath("github-step-summary.md").exists()
    assert "skipped" in result.output


def test_ci_skip_evidence_room_preserves_other_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-evidence-room",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["evidence-room"]["status"] == "skipped"
    assert steps["evidence-room"]["message"] == "skipped by flag"
    assert run_dir.joinpath("manifest.json").exists()
    assert run_dir.joinpath("vibebench-bundle.zip").exists()
    assert run_dir.joinpath("report", "index.html").exists()
    assert not run_dir.joinpath("evidence-room").exists()


def test_bundle_include_report_assets_passes_through(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path, with_report_asset=True)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-report",
            "--bundle-include-report-assets",
        ],
    )

    assert result.exit_code == 0
    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "report/assets/style.css" in names


def test_bundle_strict_passes_through(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-report",
            "--skip-pr-comment",
            "--skip-explain",
            "--skip-export",
            "--skip-badge",
            "--skip-status-block",
            "--skip-trend",
            "--skip-gh-summary",
            "--bundle-strict",
        ],
    )

    assert result.exit_code == 1
    assert "bundle" in result.output
    assert "bundle" in result.output
    assert "failed" in result.output


def test_gate_override_flags_affect_gate_decision(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path, metrics=sample_metrics(score=70))

    failed = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )
    passed = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--min-score",
            "70",
            "--max-risk",
            "medium",
            "--allow-findings",
            "0",
        ],
    )

    assert failed.exit_code == 1
    assert passed.exit_code == 0


def test_no_require_status_passed_override(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(
        tmp_path,
        metrics=sample_metrics(status="failed", score=100, risk="low"),
    )

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--no-require-status-passed",
        ],
    )

    assert result.exit_code == 0


def test_run_dir_mode_does_not_create_fresh_check_run(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    run_dirs = list((tmp_path / ".vibebench" / "runs").iterdir())
    assert result.exit_code == 0
    assert run_dirs == [run_dir]
    assert "using --run-dir" in result.output


def test_ci_writes_only_to_explicit_github_summary_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)
    summary_file = tmp_path / "step-summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 0
    assert summary_file.exists()
    assert "# VibeBench Summary" in summary_file.read_text(encoding="utf-8")
    assert not run_dir.joinpath("github-step-summary.md").exists()


def test_invalid_run_dir_fails_clearly(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--run-dir", str(tmp_path / "x")],
    )

    assert result.exit_code == 1
    assert "Run directory does not exist" in result.output


def test_ci_runs_export_and_badge_before_bundle_and_summary(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--run-dir", str(run_dir)],
    )

    assert result.exit_code == 0
    assert run_dir.joinpath("export.json").exists()
    assert run_dir.joinpath("badge.json").exists()
    assert run_dir.joinpath("badge.md").exists()
    assert run_dir.joinpath("status-block.md").exists()
    assert run_dir.joinpath("trend.md").exists()
    assert run_dir.joinpath("trend.json").exists()
    assert run_dir.joinpath("config-check.json").exists()
    assert run_dir.joinpath("config-check.md").exists()
    assert run_dir.joinpath("manifest.json").exists()
    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "export.json" in names
    assert "badge.json" in names
    assert "badge.md" in names
    assert "status-block.md" in names
    assert "trend.md" in names
    assert "trend.json" in names
    assert "config-check.json" in names
    assert "config-check.md" in names
    assert "manifest.json" in names
    summary = run_dir.joinpath("github-step-summary.md").read_text(encoding="utf-8")
    assert "`export.json` (available)" in summary
    assert "`badge.json` (available)" in summary
    assert "`badge.md` (available)" in summary
    assert "`status-block.md` (available)" in summary
    assert "`trend.md` (available)" in summary
    assert "`trend.json` (available)" in summary
    assert "`manifest.json` (available)" in summary
    assert result.output.index("manifest") < result.output.index("bundle")
    assert result.output.index("manifest-check") < result.output.index("bundle")


def test_ci_skip_export_skips_export_generation(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-export",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("export.json").exists()
    assert "export" in result.output
    assert "skipped" in result.output


def test_ci_skip_badge_skips_badge_generation(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-badge",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("badge.json").exists()
    assert not run_dir.joinpath("badge.md").exists()
    assert "badge" in result.output
    assert "skipped" in result.output


def test_ci_skip_status_block_skips_status_block_generation(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-status-block",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("status-block.md").exists()
    assert "status-block" in result.output
    assert "skipped" in result.output


def test_ci_skip_trend_skips_trend_generation(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-trend",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("trend.md").exists()
    assert not run_dir.joinpath("trend.json").exists()
    assert "trend" in result.output
    assert "skipped" in result.output


def test_ci_runs_annotations_by_default(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(
        tmp_path,
        metrics=sample_metrics(
            findings=[
                {
                    "severity": "warning",
                    "code": "demo_warning",
                    "message": "Review this change.",
                    "paths": ["src/app.py"],
                }
            ]
        ),
    )

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--allow-findings",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert "annotate" in result.output
    assert "::warning" in result.output
    assert "demo_warning" in result.output


def test_ci_skip_annotate_suppresses_annotation_output(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(
        tmp_path,
        metrics=sample_metrics(
            findings=[
                {
                    "severity": "warning",
                    "code": "demo_warning",
                    "message": "Review this change.",
                    "paths": ["src/app.py"],
                }
            ]
        ),
    )

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--allow-findings",
            "1",
            "--skip-annotate",
        ],
    )

    assert result.exit_code == 0
    assert "annotate" in result.output
    assert "skipped" in result.output
    assert "::warning" not in result.output
    assert "demo_warning" not in result.output


def test_ci_dry_run_does_not_create_run_or_execute_commands(tmp_path: Path) -> None:
    marker = tmp_path / "executed.txt"
    command = (
        "python -c "
        f"'from pathlib import Path; Path({str(marker)!r}).write_text(\"ran\")'"
    )
    write_config(tmp_path, command)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path), "--dry-run"])

    assert result.exit_code == 0
    assert "VibeBench CI plan" in result.output
    assert "Dry run" in result.output
    assert "Final CI verdict: planned" in result.output
    assert not marker.exists()
    assert not (tmp_path / ".vibebench" / "runs").exists()


def test_ci_dry_run_human_output_includes_ordered_steps(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path), "--dry-run"])

    assert result.exit_code == 0
    expected_steps = [
        "check",
        "gate",
        "config-check",
        "package-check",
        "report",
        "pr-comment",
        "explain",
        "export",
        "badge",
        "status-block",
        "trend",
        "run-index",
        "compare",
        "evidence-room",
        "manifest",
        "manifest-check",
        "release-check",
        "annotate",
        "bundle",
        "gh-summary",
    ]
    positions = [result.output.index(step) for step in expected_steps]
    assert positions == sorted(positions)


def test_ci_dry_run_json_outputs_plan_payload(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "planned"
    assert payload["dry_run"] is True
    assert payload["run_dir"] is None
    assert payload["run_id"] is None
    assert [step["name"] for step in payload["steps"]] == [
        "check",
        "gate",
        "config-check",
        "package-check",
        "report",
        "pr-comment",
        "explain",
        "export",
        "badge",
        "status-block",
        "trend",
        "run-index",
        "compare",
        "evidence-room",
        "manifest",
        "manifest-check",
        "release-check",
        "annotate",
        "bundle",
        "gh-summary",
    ]
    assert "project-scan" not in [step["name"] for step in payload["steps"]]
    assert "onboard" not in [step["name"] for step in payload["steps"]]
    assert "workflow-check" not in [step["name"] for step in payload["steps"]]
    for step in payload["steps"]:
        assert set(step) == {
            "name",
            "status",
            "exit_code",
            "artifact",
            "message",
            "duration_seconds",
        }
        assert step["status"] == "planned"
        assert step["exit_code"] is None
        if step["name"] == "evidence-room":
            assert step["artifact"] == "evidence-room"
        else:
            assert step["artifact"] is None
        assert step["duration_seconds"] is None


def test_ci_dry_run_metrics_check_json_includes_planned_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--metrics-check",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["metrics-check"]["status"] == "planned"
    assert "metrics.json contract" in steps["metrics-check"]["message"]


def test_ci_dry_run_skip_metrics_check_json_includes_skipped_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-metrics-check",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["metrics-check"]["status"] == "skipped"
    assert steps["metrics-check"]["message"] == "Skipped by --skip-metrics-check"


def test_ci_dry_run_workflow_check_json_includes_planned_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--workflow-check",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["workflow-check"]["status"] == "planned"
    assert steps["workflow-check"]["artifact"] == "workflow-check.json"


def test_ci_dry_run_skip_workflow_check_suppresses_enabled_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--workflow-check",
            "--skip-workflow-check",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["workflow-check"]["status"] == "skipped"
    assert steps["workflow-check"]["message"] == "Skipped by --skip-workflow-check"


def test_ci_dry_run_workflow_check_policy_json_includes_planned_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--workflow-check-policy",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["workflow-check"]["status"] == "planned"
    assert "policy enforcement" in steps["workflow-check"]["message"]


def test_ci_dry_run_workflow_check_required_mode_json_includes_planned_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--workflow-check-require-ci-mode",
            "adoption-policy",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert steps["workflow-check"]["status"] == "planned"
    assert "requiring CI modes: adoption-policy" in steps["workflow-check"]["message"]


ADOPTION_STEP_NAMES = [
    "project-scan",
    "onboard",
    "preflight",
    "workflow-check",
    "workflow-template",
]


def adoption_steps(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {step["name"]: step for step in payload["steps"]}


def assert_adoption_report_only_steps(
    steps: dict[str, dict[str, object]],
) -> None:
    assert steps["project-scan"]["status"] == "planned"
    assert "policy enforcement" not in str(steps["project-scan"]["message"])
    assert steps["onboard"]["status"] == "planned"
    assert "policy enforcement" not in str(steps["onboard"]["message"])
    assert steps["workflow-template"]["status"] == "planned"
    assert steps["workflow-template"]["artifact"] == "workflow-template.json"
    assert steps["workflow-check"]["status"] == "planned"
    assert "policy enforcement" not in str(steps["workflow-check"]["message"])
    assert steps["preflight"]["status"] == "planned"
    assert "report-only" in str(steps["preflight"]["message"])


def assert_adoption_policy_steps(
    steps: dict[str, dict[str, object]],
) -> None:
    assert steps["project-scan"]["status"] == "planned"
    assert "policy enforcement" in str(steps["project-scan"]["message"])
    assert steps["onboard"]["status"] == "planned"
    assert "policy enforcement" in str(steps["onboard"]["message"])
    assert steps["workflow-template"]["status"] == "planned"
    assert "policy enforcement" not in str(steps["workflow-template"]["message"])
    assert steps["workflow-check"]["status"] == "planned"
    assert "policy enforcement" in str(steps["workflow-check"]["message"])
    assert steps["preflight"]["status"] == "planned"
    assert "policy enforcement" in str(steps["preflight"]["message"])


def test_ci_dry_run_adoption_json_includes_report_only_suite(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--adoption", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert_adoption_report_only_steps(adoption_steps(payload))


def test_ci_dry_run_adoption_policy_json_includes_enforced_suite(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--adoption-policy",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert_adoption_policy_steps(adoption_steps(payload))


def test_ci_dry_run_adoption_and_policy_can_be_combined(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--adoption",
            "--adoption-policy",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert_adoption_policy_steps(adoption_steps(payload))


def test_ci_dry_run_adoption_with_explicit_policy_flag_upgrades_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--adoption",
            "--workflow-check-policy",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = adoption_steps(payload)
    assert result.exit_code == 0
    assert steps["project-scan"]["status"] == "planned"
    assert "policy enforcement" not in str(steps["project-scan"]["message"])
    assert steps["onboard"]["status"] == "planned"
    assert "policy enforcement" not in str(steps["onboard"]["message"])
    assert steps["workflow-template"]["status"] == "planned"
    assert "policy enforcement" in str(steps["workflow-check"]["message"])
    assert steps["preflight"]["status"] == "planned"
    assert "report-only" in str(steps["preflight"]["message"])


def test_ci_dry_run_default_omits_adoption_suite(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--json"],
    )

    payload = json.loads(result.output)
    step_names = [step["name"] for step in payload["steps"]]
    assert result.exit_code == 0
    for name in ADOPTION_STEP_NAMES:
        assert name not in step_names


@pytest.mark.parametrize("preset_flag", ["--adoption", "--adoption-policy"])
@pytest.mark.parametrize(
    ("skip_flag", "step_name"),
    [
        ("--skip-project-scan", "project-scan"),
        ("--skip-onboard", "onboard"),
        ("--skip-workflow-template", "workflow-template"),
        ("--skip-workflow-check", "workflow-check"),
        ("--skip-preflight", "preflight"),
    ],
)
def test_ci_dry_run_adoption_skip_flags_suppress_preset_parts(
    tmp_path: Path,
    preset_flag: str,
    skip_flag: str,
    step_name: str,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            preset_flag,
            skip_flag,
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = adoption_steps(payload)
    assert result.exit_code == 0
    assert steps[step_name]["status"] == "skipped"
    assert str(steps[step_name]["message"]).startswith("Skipped by ")


def test_ci_dry_run_workflow_template_json_includes_planned_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--workflow-template",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["workflow-template"]["status"] == "planned"
    assert steps["workflow-template"]["artifact"] == "workflow-template.json"


def test_ci_dry_run_skip_workflow_template_suppresses_enabled_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--workflow-template",
            "--skip-workflow-template",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["workflow-template"]["status"] == "skipped"
    assert (
        steps["workflow-template"]["message"] == "Skipped by --skip-workflow-template"
    )


def test_ci_dry_run_onboard_json_includes_planned_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--onboard",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["onboard"]["status"] == "planned"
    assert "onboarding plan artifacts" in steps["onboard"]["message"]


def test_ci_dry_run_default_omits_onboard_step(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--json"],
    )

    payload = json.loads(result.output)
    step_names = [step["name"] for step in payload["steps"]]
    assert result.exit_code == 0
    assert "onboard" not in step_names


def test_ci_dry_run_skip_onboard_json_includes_skipped_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-onboard",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["onboard"]["status"] == "skipped"
    assert steps["onboard"]["message"] == "Skipped by --skip-onboard"


def test_ci_dry_run_onboard_policy_json_includes_enforced_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--onboard-policy",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["onboard"]["status"] == "planned"
    assert "policy enforcement" in steps["onboard"]["message"]


def test_ci_dry_run_preflight_json_includes_planned_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--preflight",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["preflight"]["status"] == "planned"
    assert steps["preflight"]["artifact"] == "preflight.json"


def test_ci_dry_run_preflight_required_mode_implies_preflight_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--preflight-require-ci-mode",
            "default",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["preflight"]["status"] == "planned"
    assert steps["preflight"]["artifact"] == "preflight.json"
    assert "required CI modes: default" in steps["preflight"]["message"]


def test_ci_dry_run_preflight_required_mode_dedupes(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--preflight-require-ci-mode",
            "adoption-policy",
            "--preflight-require-ci-mode",
            "default",
            "--preflight-require-ci-mode",
            "adoption-policy",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert "required CI modes: default, adoption-policy" in steps["preflight"][
        "message"
    ]


def test_ci_preflight_required_mode_invalid_value_fails_clearly(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--preflight-require-ci-mode",
            "preview",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert result.exception is not None
    assert "--preflight-require-ci-mode must be one of" in str(result.exception)


def test_ci_dry_run_skip_preflight_suppresses_required_mode(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-preflight",
            "--preflight-require-ci-mode",
            "default",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["preflight"]["status"] == "skipped"
    assert steps["preflight"]["message"] == "Skipped by --skip-preflight"


def test_ci_dry_run_default_omits_preflight_step(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--json"],
    )

    payload = json.loads(result.output)
    step_names = [step["name"] for step in payload["steps"]]
    assert result.exit_code == 0
    assert "preflight" not in step_names


def test_ci_dry_run_skip_preflight_suppresses_enabled_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--preflight",
            "--skip-preflight",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["preflight"]["status"] == "skipped"
    assert steps["preflight"]["message"] == "Skipped by --skip-preflight"




def test_ci_dry_run_preflight_policy_json_includes_enforced_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--preflight-policy",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["preflight"]["status"] == "planned"
    assert steps["preflight"]["artifact"] == "preflight.json"
    assert "policy enforcement" in steps["preflight"]["message"]


def test_ci_dry_run_skip_preflight_suppresses_policy_mode(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--preflight-policy",
            "--skip-preflight",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["preflight"]["status"] == "skipped"
    assert steps["preflight"]["message"] == "Skipped by --skip-preflight"


def test_ci_dry_run_project_scan_json_includes_planned_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--project-scan",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["project-scan"]["status"] == "planned"
    assert "project-scan report" in steps["project-scan"]["message"]


def test_ci_dry_run_project_scan_policy_json_includes_enforced_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--project-scan-policy",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["project-scan"]["status"] == "planned"
    assert "policy enforcement" in steps["project-scan"]["message"]


def test_ci_dry_run_skip_project_scan_json_includes_skipped_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-project-scan",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["project-scan"]["status"] == "skipped"
    assert steps["project-scan"]["message"] == "Skipped by --skip-project-scan"


def test_ci_onboard_writes_reports_and_json_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--onboard", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("onboard.json").read_text())
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert "VibeBench onboarding" not in result.output
    assert payload["run_id"] == run_dir.name
    assert steps["onboard"]["status"] == "passed"
    assert steps["onboard"]["artifact"].endswith("onboard.json")
    assert report["project_root"] == str(tmp_path.resolve())
    assert "suggested_commands" in report
    assert run_dir.joinpath("onboard.md").exists()

    artifacts = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )
    artifact_map = {
        item["name"]: item for item in json.loads(artifacts.output)["artifacts"]
    }
    assert artifacts.exit_code == 0
    assert artifact_map["onboard-json"]["available"] is True
    assert artifact_map["onboard-md"]["available"] is True

    latest_json = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "onboard-json",
            "--path-only",
        ],
    )
    latest_md = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "onboard-md",
            "--path-only",
        ],
    )
    assert latest_json.exit_code == 0
    assert latest_json.output.strip().endswith("onboard.json")
    assert latest_md.exit_code == 0
    assert latest_md.output.strip().endswith("onboard.md")

    manifest = check_manifest(tmp_path, run_dir)
    manifest_payload = json.loads(run_dir.joinpath("manifest.json").read_text())
    manifest_artifacts = {item["name"]: item for item in manifest_payload["artifacts"]}
    assert manifest.passed is True
    assert manifest_artifacts["onboard-json"]["available"] is True
    assert manifest_artifacts["onboard-md"]["available"] is True

    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "onboard.json" in names
    assert "onboard.md" in names

    summary = run_dir.joinpath("github-step-summary.md").read_text(encoding="utf-8")
    assert "`onboard.json` (available)" in summary
    assert "`onboard.md` (available)" in summary


def test_ci_onboard_policy_writes_reports_and_enforces_success(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--onboard-policy", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("onboard.json").read_text())
    assert result.exit_code == 0
    assert steps["onboard"]["status"] == "passed"
    assert "policy passed" in steps["onboard"]["message"]
    assert report["policy_enforced"] is True
    assert report["policy_status"] == "passed"
    assert report["policy_findings"] == []
    assert run_dir.joinpath("onboard.md").exists()


def test_ci_onboard_policy_enforces_failure(tmp_path: Path) -> None:
    write_config(tmp_path)
    append_onboard_policy(
        tmp_path,
        """    require_ci_ready: true
""",
    )
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--onboard-policy", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("onboard.json").read_text())
    assert result.exit_code == 1
    assert steps["onboard"]["status"] == "failed"
    assert report["policy_status"] == "failed"
    assert "ci_ready_required" in {
        finding["id"] for finding in report["policy_findings"]
    }


def test_ci_onboard_remains_report_only_with_policy_failure(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    append_onboard_policy(
        tmp_path,
        """    require_ci_ready: true
""",
    )
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--onboard", "--json"],
    )

    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("onboard.json").read_text())
    assert result.exit_code == 0
    assert "policy_status" not in report


def test_ci_skip_onboard_suppresses_onboard_policy(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--onboard-policy",
            "--skip-onboard",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 0
    assert steps["onboard"]["status"] == "skipped"
    assert not run_dir.joinpath("onboard.json").exists()
    assert not run_dir.joinpath("onboard.md").exists()


def test_ci_skip_onboard_suppresses_onboard_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--onboard",
            "--skip-onboard",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 0
    assert steps["onboard"]["status"] == "skipped"
    assert not run_dir.joinpath("onboard.json").exists()
    assert not run_dir.joinpath("onboard.md").exists()


def test_ci_project_scan_writes_reports_and_json_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--project-scan", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("project-scan.json").read_text())
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert "VibeBench project scan" not in result.output
    assert payload["run_id"] == run_dir.name
    assert steps["project-scan"]["status"] == "passed"
    assert steps["project-scan"]["artifact"].endswith("project-scan.json")
    assert report["config_present"] is True
    assert report["config_valid"] is True
    assert run_dir.joinpath("project-scan.md").exists()

    artifacts = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )
    artifact_map = {
        item["name"]: item for item in json.loads(artifacts.output)["artifacts"]
    }
    assert artifacts.exit_code == 0
    assert artifact_map["project-scan-json"]["available"] is True
    assert artifact_map["project-scan-md"]["available"] is True

    latest_json = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "project-scan-json",
            "--path-only",
        ],
    )
    latest_md = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "project-scan-md",
            "--path-only",
        ],
    )
    assert latest_json.exit_code == 0
    assert latest_json.output.strip().endswith("project-scan.json")
    assert latest_md.exit_code == 0
    assert latest_md.output.strip().endswith("project-scan.md")

    manifest = check_manifest(tmp_path, run_dir)
    manifest_payload = json.loads(run_dir.joinpath("manifest.json").read_text())
    manifest_artifacts = {item["name"]: item for item in manifest_payload["artifacts"]}
    assert manifest.passed is True
    assert manifest_artifacts["project-scan-json"]["available"] is True
    assert manifest_artifacts["project-scan-md"]["available"] is True

    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "project-scan.json" in names
    assert "project-scan.md" in names

    summary = run_dir.joinpath("github-step-summary.md").read_text(encoding="utf-8")
    assert "`project-scan.json` (available)" in summary
    assert "`project-scan.md` (available)" in summary


def test_ci_project_scan_policy_writes_reports_and_enforces_success(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--project-scan-policy", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("project-scan.json").read_text())
    assert result.exit_code == 0
    assert steps["project-scan"]["status"] == "passed"
    assert "policy passed" in steps["project-scan"]["message"]
    assert report["policy_enforced"] is True
    assert report["policy_status"] == "passed"
    assert run_dir.joinpath("project-scan.md").exists()

    artifacts = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )
    artifact_map = {
        item["name"]: item for item in json.loads(artifacts.output)["artifacts"]
    }
    assert artifact_map["project-scan-json"]["available"] is True
    assert artifact_map["project-scan-md"]["available"] is True
    assert "project-scan.json" in zip_names(run_dir / "vibebench-bundle.zip")


ADOPTION_ARTIFACT_FILES = [
    "project-scan.json",
    "project-scan.md",
    "onboard.json",
    "onboard.md",
    "workflow-template.json",
    "workflow-template.md",
    "workflow-template.yml",
    "workflow-check.json",
    "workflow-check.md",
    "preflight.json",
    "preflight.md",
]


def assert_adoption_artifacts_exist(run_dir: Path) -> None:
    for name in ADOPTION_ARTIFACT_FILES:
        assert run_dir.joinpath(name).exists(), name


def test_ci_adoption_writes_report_only_evidence_pack(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--adoption", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert "VibeBench" not in result.output
    assert_adoption_artifacts_exist(run_dir)
    assert steps["project-scan"]["status"] == "passed"
    assert steps["onboard"]["status"] == "passed"
    assert steps["workflow-template"]["status"] == "passed"
    assert steps["workflow-check"]["status"] == "passed"
    assert steps["preflight"]["status"] == "passed"
    assert "policy_status" not in json.loads(
        run_dir.joinpath("preflight.json").read_text(encoding="utf-8")
    )
    assert not workflow_path(tmp_path).exists()
    assert not tmp_path.joinpath("node_modules").exists()
    assert not tmp_path.joinpath("package-lock.json").exists()


def test_ci_adoption_policy_writes_same_artifact_names(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    tmp_path.joinpath("tests").mkdir()
    write_minimal_vibebench_workflow(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--adoption-policy", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert_adoption_artifacts_exist(run_dir)
    assert "policy passed" in steps["project-scan"]["message"]
    assert "policy passed" in steps["onboard"]["message"]
    assert "policy passed" in steps["workflow-check"]["message"]
    assert "policy passed" in steps["preflight"]["message"]
    for artifact_name in [
        "project-scan.json",
        "onboard.json",
        "workflow-check.json",
        "preflight.json",
    ]:
        report = json.loads(run_dir.joinpath(artifact_name).read_text())
        assert report["policy_status"] == "passed"


def test_ci_adoption_artifacts_are_discoverable(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--adoption", "--json"],
    )
    run_dir = latest_run(tmp_path)
    artifacts = runner.invoke(
        app, ["artifacts", "--project-root", str(tmp_path), "--json"]
    )
    artifact_map = {
        item["name"]: item for item in json.loads(artifacts.output)["artifacts"]
    }
    expected_aliases = [
        "project-scan-json",
        "onboard-json",
        "workflow-template-yml",
        "workflow-check-json",
        "preflight-json",
    ]

    assert result.exit_code == 0
    assert artifacts.exit_code == 0
    for alias in expected_aliases:
        assert artifact_map[alias]["available"] is True
    assert check_manifest(tmp_path, run_dir).passed is True
    names = zip_names(run_dir / "vibebench-bundle.zip")
    for name in ADOPTION_ARTIFACT_FILES:
        assert name in names


def test_ci_preflight_writes_report_only_artifacts(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--preflight", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    preflight_json = run_dir / "preflight.json"
    preflight_md = run_dir / "preflight.md"
    report = json.loads(preflight_json.read_text(encoding="utf-8"))
    markdown = preflight_md.read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert "VibeBench Preflight" not in result.output
    assert payload["run_id"] == run_dir.name
    assert steps["preflight"]["status"] == "passed"
    assert steps["preflight"]["artifact"].endswith("preflight.json")
    assert report["project_root"] == str(tmp_path.resolve())
    assert report["strict"] is False
    assert set(
        [
            "status",
            "config",
            "project_scan",
            "onboard",
            "workflow_template",
            "workflow_check",
            "recommendations",
            "commands",
        ]
    ).issubset(report)
    assert "# VibeBench Preflight" in markdown
    assert "- Status:" in markdown

    artifacts = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )
    artifact_map = {
        item["name"]: item for item in json.loads(artifacts.output)["artifacts"]
    }
    assert artifacts.exit_code == 0
    assert artifact_map["preflight-json"]["available"] is True
    assert artifact_map["preflight-md"]["available"] is True

    latest_json = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "preflight-json",
            "--path-only",
        ],
    )
    latest_md = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "preflight-md",
            "--path-only",
        ],
    )
    assert latest_json.exit_code == 0
    assert latest_json.output.strip().endswith("preflight.json")
    assert latest_md.exit_code == 0
    assert latest_md.output.strip().endswith("preflight.md")

    manifest_payload = json.loads(run_dir.joinpath("manifest.json").read_text())
    manifest_artifacts = {item["name"]: item for item in manifest_payload["artifacts"]}
    assert manifest_artifacts["preflight-json"]["available"] is True
    assert manifest_artifacts["preflight-md"]["available"] is True

    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "preflight.json" in names
    assert "preflight.md" in names

    summary = run_dir.joinpath("github-step-summary.md").read_text(encoding="utf-8")
    assert "`preflight.json` (available)" in summary
    assert "`preflight.md` (available)" in summary


def test_ci_skip_preflight_suppresses_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--preflight",
            "--skip-preflight",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 0
    assert steps["preflight"]["status"] == "skipped"
    assert not run_dir.joinpath("preflight.json").exists()
    assert not run_dir.joinpath("preflight.md").exists()




def test_ci_preflight_required_mode_writes_required_mode_artifacts(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)
    write_minimal_vibebench_workflow(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--preflight-require-ci-mode",
            "default",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("preflight.json").read_text())
    markdown = run_dir.joinpath("preflight.md").read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert steps["preflight"]["status"] == "passed"
    assert "required CI modes default; missing none" in steps["preflight"][
        "message"
    ]
    assert report["workflow_check"]["required_ci_modes"] == ["default"]
    assert report["workflow_check"]["missing_required_ci_modes"] == []
    assert "- Required CI modes: default" in markdown
    assert "- Missing required CI modes: none" in markdown


def test_ci_preflight_required_mode_report_only_when_missing(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)
    write_minimal_vibebench_workflow(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--preflight",
            "--preflight-require-ci-mode",
            "adoption",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("preflight.json").read_text())
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert steps["preflight"]["status"] == "passed"
    assert "missing adoption" in steps["preflight"]["message"]
    assert report["workflow_check"]["required_ci_modes"] == ["adoption"]
    assert report["workflow_check"]["missing_required_ci_modes"] == ["adoption"]


def test_ci_preflight_policy_required_mode_keeps_existing_policy_semantics(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    append_preflight_policy(tmp_path, "    require_onboard_ready: false\n")
    init_git_repo(tmp_path)
    write_minimal_vibebench_workflow(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--preflight-policy",
            "--preflight-require-ci-mode",
            "adoption",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("preflight.json").read_text())
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert steps["preflight"]["status"] == "failed"
    assert "policy failed" in steps["preflight"]["message"]
    assert "missing adoption" in steps["preflight"]["message"]
    assert report["policy_status"] == "failed"
    assert report["workflow_check"]["missing_required_ci_modes"] == ["adoption"]


def test_ci_skip_preflight_suppresses_required_mode_artifacts(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)
    write_minimal_vibebench_workflow(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--skip-preflight",
            "--preflight-require-ci-mode",
            "default",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 0
    assert steps["preflight"]["status"] == "skipped"
    assert not run_dir.joinpath("preflight.json").exists()
    assert not run_dir.joinpath("preflight.md").exists()


def test_ci_preflight_policy_writes_reports_and_enforces_success(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    append_preflight_policy(tmp_path, "    require_onboard_ready: false\n")
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--preflight-policy", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("preflight.json").read_text(encoding="utf-8"))
    markdown = run_dir.joinpath("preflight.md").read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert steps["preflight"]["status"] == "passed"
    assert "policy passed" in steps["preflight"]["message"]
    assert report["policy_enforced"] is True
    assert report["policy_status"] == "passed"
    assert report["policy_findings"] == []
    assert "## Policy" in markdown


def test_ci_preflight_policy_enforces_failure(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--preflight-policy", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("preflight.json").read_text(encoding="utf-8"))
    assert result.exit_code == 1
    assert result.output.lstrip().startswith("{")
    assert steps["preflight"]["status"] == "failed"
    assert report["policy_status"] == "failed"
    assert "onboard_ready_required" in {
        finding["id"] for finding in report["policy_findings"]
    }


def test_ci_preflight_remains_report_only_with_policy_failure(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--preflight", "--json"],
    )

    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("preflight.json").read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert "policy_status" not in report


def test_ci_skip_preflight_suppresses_policy_mode_too(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--preflight-policy",
            "--skip-preflight",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 0
    assert steps["preflight"]["status"] == "skipped"
    assert not run_dir.joinpath("preflight.json").exists()
    assert not run_dir.joinpath("preflight.md").exists()


def test_ci_workflow_check_require_ci_mode_default_enables_step_and_passes(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)
    write_minimal_vibebench_workflow(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--workflow-check-require-ci-mode",
            "default",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("workflow-check.json").read_text())
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert payload["status"] == "passed"
    assert steps["workflow-check"]["status"] == "passed"
    assert (
        "required CI modes default; missing none"
        in steps["workflow-check"]["message"]
    )
    assert report["required_ci_modes"] == ["default"]
    assert report["missing_required_ci_modes"] == []


def test_ci_workflow_check_require_ci_mode_adoption_fails_clearly(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)
    write_minimal_vibebench_workflow(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--workflow-check-require-ci-mode",
            "adoption",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("workflow-check.json").read_text())
    assert result.exit_code == 1
    assert result.output.lstrip().startswith("{")
    assert payload["status"] == "failed"
    assert steps["workflow-check"]["status"] == "failed"
    assert "missing adoption" in steps["workflow-check"]["message"]
    assert report["required_ci_modes"] == ["adoption"]
    assert report["missing_required_ci_modes"] == ["adoption"]


def test_ci_workflow_check_require_ci_mode_adoption_policy_fails_clearly(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)
    write_minimal_vibebench_workflow(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--workflow-check-require-ci-mode",
            "adoption-policy",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("workflow-check.json").read_text())
    assert result.exit_code == 1
    assert result.output.lstrip().startswith("{")
    assert payload["status"] == "failed"
    assert steps["workflow-check"]["status"] == "failed"
    assert "missing adoption-policy" in steps["workflow-check"]["message"]
    assert report["required_ci_modes"] == ["adoption-policy"]
    assert report["missing_required_ci_modes"] == ["adoption-policy"]


def test_ci_workflow_check_require_ci_mode_dedupes_in_stable_order(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)
    workflow = workflow_path(tmp_path)
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        """name: VibeBench
on:
  pull_request:
jobs:
  vibebench:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - run: python3 -m vibebench ci --adoption-policy
      - run: python3 -m vibebench ci --adoption
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--workflow-check-require-ci-mode",
            "adoption-policy",
            "--workflow-check-require-ci-mode",
            "adoption",
            "--workflow-check-require-ci-mode",
            "adoption-policy",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("workflow-check.json").read_text())
    assert result.exit_code == 0
    assert report["required_ci_modes"] == ["adoption", "adoption-policy"]
    assert report["missing_required_ci_modes"] == []
    assert payload["status"] == "passed"


def test_ci_workflow_check_require_ci_mode_invalid_value_fails_clearly(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--workflow-check-require-ci-mode",
            "preview",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert result.exception is not None
    assert "--workflow-check-require-ci-mode must be one of" in str(result.exception)


def test_ci_workflow_check_require_ci_mode_skip_conflict_fails_fast(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--workflow-check-require-ci-mode",
            "default",
            "--skip-workflow-check",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert result.exception is not None
    assert "cannot be combined with --skip-workflow-check" in str(result.exception)


def test_ci_workflow_check_writes_report_only_artifacts(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--workflow-check", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    workflow_json = run_dir / "workflow-check.json"
    workflow_md = run_dir / "workflow-check.md"
    report = json.loads(workflow_json.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert steps["workflow-check"]["status"] == "passed"
    assert steps["workflow-check"]["artifact"].endswith("workflow-check.json")
    assert workflow_json.exists()
    assert workflow_md.exists()
    assert report["safe_preview_only"] is True
    assert "required_ci_modes" not in report
    assert "missing_required_ci_modes" not in report
    assert not (tmp_path / ".github" / "workflows").exists()

    artifacts = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )
    artifact_map = {
        item["name"]: item for item in json.loads(artifacts.output)["artifacts"]
    }
    assert artifact_map["workflow-check-json"]["available"] is True
    assert artifact_map["workflow-check-md"]["available"] is True

    latest_json = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "workflow-check-json",
            "--path-only",
        ],
    )
    latest_md = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "workflow-check-md",
            "--path-only",
        ],
    )
    assert latest_json.exit_code == 0
    assert latest_md.exit_code == 0
    assert latest_json.output.strip().endswith("workflow-check.json")
    assert latest_md.output.strip().endswith("workflow-check.md")

    manifest_payload = json.loads(run_dir.joinpath("manifest.json").read_text())
    manifest_artifacts = {item["name"]: item for item in manifest_payload["artifacts"]}
    assert manifest_artifacts["workflow-check-json"]["available"] is True
    assert manifest_artifacts["workflow-check-md"]["available"] is True

    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "workflow-check.json" in names
    assert "workflow-check.md" in names

    summary = run_dir.joinpath("github-step-summary.md").read_text(encoding="utf-8")
    assert "`workflow-check.json` (available)" in summary
    assert "`workflow-check.md` (available)" in summary


def test_ci_workflow_check_remains_report_only_without_workflow(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--workflow-check", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("workflow-check.json").read_text())
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert steps["workflow-check"]["status"] == "passed"
    assert report["workflow_path"] is None
    assert report["summary"]["warning"] >= 1


def test_ci_skip_workflow_check_suppresses_artifacts(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--workflow-check",
            "--skip-workflow-check",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 0
    assert steps["workflow-check"]["status"] == "skipped"
    assert not run_dir.joinpath("workflow-check.json").exists()
    assert not run_dir.joinpath("workflow-check.md").exists()


def test_ci_workflow_check_policy_enforces_failure(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--workflow-check-policy", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("workflow-check.json").read_text())
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert steps["workflow-check"]["status"] == "failed"
    assert report["policy_evaluated"] is True
    assert report["policy_status"] == "failed"


def test_ci_workflow_check_policy_passes_with_ready_workflow(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)
    workflow = workflow_path(tmp_path)
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        """name: VibeBench
on:
  pull_request:
jobs:
  vibebench:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - run: python3 -m vibebench ci
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--workflow-check-policy", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("workflow-check.json").read_text())
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert steps["workflow-check"]["status"] == "passed"
    assert report["policy_evaluated"] is True
    assert report["policy_status"] == "passed"


def test_ci_workflow_check_policy_evaluates_required_ci_modes(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    append_workflow_check_policy(
        tmp_path,
        """    fail_on_blockers: false
    fail_on_errors: false
    fail_on_warnings: false
    require_config: true
    require_ci_ready: false
    required_ci_modes:
      - adoption-policy
    allowed_workflow_names: []
    allowed_action_prefixes: []
""",
    )
    init_git_repo(tmp_path)
    write_minimal_vibebench_workflow(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--workflow-check-policy", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("workflow-check.json").read_text())
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert steps["workflow-check"]["status"] == "failed"
    assert report["policy_status"] == "failed"
    assert report["effective_policy"]["required_ci_modes"] == ["adoption-policy"]
    assert any(
        finding["rule"] == "required_ci_modes"
        for finding in report["policy_findings"]
    )


def test_ci_skip_workflow_check_suppresses_policy_mode_too(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--workflow-check-policy",
            "--skip-workflow-check",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 0
    assert steps["workflow-check"]["status"] == "skipped"
    assert not run_dir.joinpath("workflow-check.json").exists()
    assert not run_dir.joinpath("workflow-check.md").exists()


def test_ci_workflow_template_writes_report_only_artifacts(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--workflow-template", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    workflow_json = run_dir / "workflow-template.json"
    workflow_md = run_dir / "workflow-template.md"
    workflow_yml = run_dir / "workflow-template.yml"
    report = json.loads(workflow_json.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert steps["workflow-template"]["status"] == "passed"
    assert steps["workflow-template"]["artifact"].endswith("workflow-template.json")
    assert workflow_json.exists()
    assert workflow_md.exists()
    assert workflow_yml.exists()
    assert "name: VibeBench" in workflow_yml.read_text(encoding="utf-8")
    assert report["ci_mode"] == "adoption"
    assert not (tmp_path / ".github" / "workflows").exists()


def test_ci_skip_workflow_template_suppresses_artifacts(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--workflow-template",
            "--skip-workflow-template",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 0
    assert steps["workflow-template"]["status"] == "skipped"
    assert not run_dir.joinpath("workflow-template.json").exists()
    assert not (tmp_path / ".github" / "workflows").exists()


def test_ci_project_scan_policy_enforces_failure(tmp_path: Path) -> None:
    write_config(tmp_path)
    append_project_scan_policy(
        tmp_path,
        """    allowed_profiles:
      - node
""",
    )
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--project-scan-policy", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("project-scan.json").read_text())
    assert result.exit_code == 1
    assert steps["project-scan"]["status"] == "failed"
    assert report["policy_status"] == "failed"
    assert "recommended_profile_not_allowed" in {
        finding["id"] for finding in report["policy_findings"]
    }


def test_ci_project_scan_report_only_ignores_policy_failure(tmp_path: Path) -> None:
    write_config(tmp_path)
    append_project_scan_policy(
        tmp_path,
        """    allowed_profiles:
      - node
""",
    )
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--project-scan", "--json"],
    )

    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("project-scan.json").read_text())
    assert result.exit_code == 0
    assert "policy_status" not in report


def test_ci_project_scan_policy_conflicts_with_skip_project_scan(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--project-scan-policy",
            "--skip-project-scan",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert "--project-scan-policy cannot be combined" in result.output


def test_ci_metrics_check_writes_reports_and_json_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--metrics-check", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("metrics-check.json").read_text())
    assert result.exit_code == 0
    assert payload["run_id"] == run_dir.name
    assert steps["metrics-check"]["status"] == "passed"
    assert steps["metrics-check"]["artifact"].endswith("metrics-check.json")
    assert report["status"] == "passed"
    assert report["usable_for_regression"] is True
    assert run_dir.joinpath("metrics-check.md").exists()

    artifacts = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )
    artifact_map = {
        item["name"]: item for item in json.loads(artifacts.output)["artifacts"]
    }
    assert artifacts.exit_code == 0
    assert artifact_map["metrics-check-json"]["available"] is True
    assert artifact_map["metrics-check-md"]["available"] is True

    latest_json = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "metrics-check-json",
            "--path-only",
        ],
    )
    latest_md = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "metrics-check-md",
            "--path-only",
        ],
    )
    assert latest_json.exit_code == 0
    assert latest_json.output.strip().endswith("metrics-check.json")
    assert latest_md.exit_code == 0
    assert latest_md.output.strip().endswith("metrics-check.md")

    manifest = check_manifest(tmp_path, run_dir)
    manifest_payload = json.loads(run_dir.joinpath("manifest.json").read_text())
    manifest_artifacts = {item["name"]: item for item in manifest_payload["artifacts"]}
    assert manifest.passed is True
    assert manifest_artifacts["metrics-check-json"]["available"] is True
    assert manifest_artifacts["metrics-check-md"]["available"] is True

    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "metrics-check.json" in names
    assert "metrics-check.md" in names

    summary = run_dir.joinpath("github-step-summary.md").read_text(encoding="utf-8")
    assert "`metrics-check.json` (available)" in summary
    assert "`metrics-check.md` (available)" in summary
    assert "VibeBench CI" not in result.output


def test_ci_dry_run_metrics_diff_json_includes_planned_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--metrics-diff",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["metrics-diff"]["status"] == "planned"
    assert "compare metrics" in steps["metrics-diff"]["message"]


def test_ci_dry_run_skip_metrics_diff_json_includes_skipped_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-metrics-diff",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["metrics-diff"]["status"] == "skipped"
    assert steps["metrics-diff"]["message"] == "Skipped by --skip-metrics-diff"


def test_ci_metrics_diff_writes_reports_and_json_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)
    write_run(tmp_path, "20200101_000000", metrics=sample_metrics(score=100))

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--metrics-diff", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("metrics-diff.json").read_text())
    assert result.exit_code == 0
    assert steps["metrics-diff"]["status"] in {"passed", "skipped"}
    assert run_dir.joinpath("metrics-diff.json").exists()
    assert run_dir.joinpath("metrics-diff.md").exists()
    assert report["status"] in {"passed", "skipped"}
    assert "VibeBench CI" not in result.output

    artifacts = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )
    artifact_map = {
        item["name"]: item for item in json.loads(artifacts.output)["artifacts"]
    }
    assert artifacts.exit_code == 0
    assert artifact_map["metrics-diff-json"]["available"] is True
    assert artifact_map["metrics-diff-md"]["available"] is True

    latest_json = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "metrics-diff-json",
            "--path-only",
        ],
    )
    latest_md = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "metrics-diff-md",
            "--path-only",
        ],
    )
    assert latest_json.exit_code == 0
    assert latest_json.output.strip().endswith("metrics-diff.json")
    assert latest_md.exit_code == 0
    assert latest_md.output.strip().endswith("metrics-diff.md")

    manifest = check_manifest(tmp_path, run_dir)
    manifest_payload = json.loads(run_dir.joinpath("manifest.json").read_text())
    manifest_artifacts = {item["name"]: item for item in manifest_payload["artifacts"]}
    assert manifest.passed is True
    assert manifest_artifacts["metrics-diff-json"]["available"] is True
    assert manifest_artifacts["metrics-diff-md"]["available"] is True

    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "metrics-diff.json" in names
    assert "metrics-diff.md" in names

    summary = run_dir.joinpath("github-step-summary.md").read_text(encoding="utf-8")
    assert "`metrics-diff.json` (available)" in summary
    assert "`metrics-diff.md` (available)" in summary


def test_ci_dry_run_regression_check_json_includes_planned_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--regression-check",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["regression-check"]["status"] == "planned"
    assert "missing baseline would be skipped" in steps["regression-check"]["message"]


def test_ci_dry_run_regression_check_require_baseline_message(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--regression-check",
            "--require-regression-baseline",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert "require a baseline" in steps["regression-check"]["message"]


def test_ci_regression_check_skips_cleanly_without_baseline(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--regression-check", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 0
    assert steps["regression-check"]["status"] == "skipped"
    assert run_dir.joinpath("regression-check.json").exists()
    assert run_dir.joinpath("regression-check.md").exists()
    report = json.loads(run_dir.joinpath("regression-check.json").read_text())
    assert report["status"] == "skipped"


def test_ci_regression_check_requires_baseline_when_requested(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--regression-check",
            "--require-regression-baseline",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert steps["regression-check"]["status"] == "failed"
    assert run_dir.joinpath("regression-check.json").exists()


def test_ci_regression_check_writes_reports_when_baseline_exists(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)
    write_run(tmp_path, "20200101_000000", metrics=sample_metrics(score=100))

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--regression-check", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("regression-check.json").read_text())
    assert result.exit_code == 0
    assert steps["regression-check"]["status"] == "passed"
    assert run_dir.name == payload["run_id"]
    assert report["status"] == "passed"
    assert run_dir.joinpath("regression-check.md").exists()
    assert "VibeBench CI" not in result.output

    artifacts = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )
    artifact_map = {
        item["name"]: item for item in json.loads(artifacts.output)["artifacts"]
    }
    assert artifacts.exit_code == 0
    assert artifact_map["regression-check-json"]["available"] is True
    assert artifact_map["regression-check-md"]["available"] is True

    latest_json = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "regression-check-json",
            "--path-only",
        ],
    )
    latest_md = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "regression-check-md",
            "--path-only",
        ],
    )
    assert latest_json.exit_code == 0
    assert latest_json.output.strip().endswith("regression-check.json")
    assert latest_md.exit_code == 0
    assert latest_md.output.strip().endswith("regression-check.md")

    manifest = check_manifest(tmp_path, run_dir)
    manifest_payload = json.loads(run_dir.joinpath("manifest.json").read_text())
    manifest_artifacts = {item["name"]: item for item in manifest_payload["artifacts"]}
    assert manifest.passed is True
    assert manifest_artifacts["regression-check-json"]["available"] is True
    assert manifest_artifacts["regression-check-md"]["available"] is True

    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "regression-check.json" in names
    assert "regression-check.md" in names


def test_ci_regression_check_uses_pinned_baseline_label(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)
    baseline = write_run(tmp_path, "20260706_110000", metrics=sample_metrics(score=100))
    pin = runner.invoke(
        app,
        [
            "baseline",
            "--project-root",
            str(tmp_path),
            "--set-run",
            baseline.name,
            "--label",
            "stable",
        ],
    )
    assert pin.exit_code == 0

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--regression-check",
            "--baseline-label",
            "stable",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("regression-check.json").read_text())
    assert result.exit_code == 0
    assert steps["regression-check"]["status"] == "passed"
    assert report["baseline_source"] == "pinned"
    assert report["baseline_label"] == "stable"
    assert run_dir.joinpath("regression-check.md").exists()


def test_ci_dry_run_fail_on_regression_mentions_compare_guard(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--fail-on-regression"],
    )

    assert result.exit_code == 0
    assert "compare" in result.output
    assert "Would run compare with" in result.output
    assert "regression guard" in result.output


def test_ci_dry_run_skip_compare_overrides_fail_on_regression(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-compare",
            "--fail-on-regression",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["compare"]["status"] == "skipped"
    assert steps["compare"]["message"] == "Skipped by --skip-compare"


def test_ci_dry_run_fail_on_regression_json_stays_clean(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--fail-on-regression",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert payload["status"] == "planned"
    assert steps["compare"]["status"] == "planned"
    assert steps["compare"]["message"] == "Would run compare with regression guard"


def test_ci_default_dry_run_compare_step_remains_reporting_only(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["compare"]["message"] == "Would run compare"


def test_ci_missing_compare_config_keeps_regression_guard_disabled(
    tmp_path: Path,
) -> None:
    write_config(tmp_path, include_compare=False)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert payload["regression_guard"] == {
        "enabled": False,
        "source": "default",
        "message": "Disabled by default.",
    }
    assert steps["compare"]["message"] == "Would run compare"


def test_ci_config_true_enables_regression_guard(
    tmp_path: Path,
) -> None:
    write_config(tmp_path, fail_on_regression=True)
    write_run(tmp_path, "20260629_120000", metrics=sample_metrics(score=100))
    head = write_run(tmp_path, "20260629_130000", metrics=sample_metrics(score=90))

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(head),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 1
    assert payload["regression_guard"]["enabled"] is True
    assert payload["regression_guard"]["source"] == "config"
    assert steps["compare"]["status"] == "failed"


def test_ci_fail_on_regression_overrides_config_false(
    tmp_path: Path,
) -> None:
    write_config(tmp_path, fail_on_regression=False)
    write_run(tmp_path, "20260629_120000", metrics=sample_metrics(score=100))
    head = write_run(tmp_path, "20260629_130000", metrics=sample_metrics(score=90))

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(head),
            "--fail-on-regression",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 1
    assert payload["regression_guard"]["enabled"] is True
    assert payload["regression_guard"]["source"] == "cli"
    assert steps["compare"]["status"] == "failed"


def test_ci_no_fail_on_regression_overrides_config_true(
    tmp_path: Path,
) -> None:
    write_config(tmp_path, fail_on_regression=True)
    write_run(tmp_path, "20260629_120000", metrics=sample_metrics(score=100))
    head = write_run(tmp_path, "20260629_130000", metrics=sample_metrics(score=90))

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(head),
            "--no-fail-on-regression",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert payload["regression_guard"]["enabled"] is False
    assert payload["regression_guard"]["source"] == "cli"
    assert steps["compare"]["status"] == "passed"


def test_ci_skip_compare_overrides_enabled_regression_guard(
    tmp_path: Path,
) -> None:
    write_config(tmp_path, fail_on_regression=True)
    write_run(tmp_path, "20260629_120000", metrics=sample_metrics(score=100))
    head = write_run(tmp_path, "20260629_130000", metrics=sample_metrics(score=90))

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(head),
            "--skip-compare",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert payload["regression_guard"] == {
        "enabled": False,
        "source": "cli",
        "message": "Disabled because --skip-compare skips compare.",
    }
    assert steps["compare"]["status"] == "skipped"
    assert not head.joinpath("compare.json").exists()


@pytest.mark.parametrize(
    ("config_value", "args", "expected_enabled", "expected_source"),
    [
        (True, [], True, "config"),
        (False, ["--fail-on-regression"], True, "cli"),
        (True, ["--no-fail-on-regression"], False, "cli"),
    ],
)
def test_ci_dry_run_json_exposes_regression_guard_policy(
    tmp_path: Path,
    config_value: bool,
    args: list[str],
    expected_enabled: bool,
    expected_source: str,
) -> None:
    write_config(tmp_path, fail_on_regression=config_value)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--json", *args],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["regression_guard"]["enabled"] is expected_enabled
    assert payload["regression_guard"]["source"] == expected_source
    assert payload["regression_guard"]["message"]


def test_ci_fail_on_regression_fails_compare_step_after_writing_artifacts(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    write_run(tmp_path, "20260629_120000", metrics=sample_metrics(score=100))
    head = write_run(tmp_path, "20260629_130000", metrics=sample_metrics(score=90))

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(head),
            "--fail-on-regression",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    compare_payload = json.loads(head.joinpath("compare.json").read_text())
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert steps["compare"]["status"] == "failed"
    assert steps["compare"]["exit_code"] == 1
    assert steps["compare"]["artifact"] == str(head / "compare.json")
    assert "Regression guard failed" in steps["compare"]["message"]
    assert compare_payload["verdict"] == "regressed"
    assert compare_payload["regression_guard"]["status"] == "failed"


def test_ci_plan_alias_json_outputs_plan_payload(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--plan", "--json"],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "planned"
    assert payload["dry_run"] is True


def test_ci_dry_run_skip_flags_mark_steps_skipped(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-manifest",
            "--skip-config-check",
            "--skip-package-check",
            "--skip-bundle",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["config-check"]["status"] == "skipped"
    assert steps["config-check"]["message"] == "Skipped by --skip-config-check"
    assert steps["package-check"]["status"] == "skipped"
    assert steps["package-check"]["message"] == "Skipped by --skip-package-check"
    assert steps["manifest"]["status"] == "skipped"
    assert steps["manifest-check"]["status"] == "skipped"
    assert steps["manifest"]["message"] == "Skipped by --skip-manifest"
    assert steps["manifest-check"]["message"] == "Skipped by --skip-manifest"
    assert steps["bundle"]["status"] == "skipped"
    assert steps["bundle"]["message"] == "Skipped by --skip-bundle"
    assert steps["check"]["status"] == "planned"


def test_ci_dry_run_skip_evidence_room_marks_step_skipped(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-evidence-room",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["evidence-room"]["status"] == "skipped"
    assert steps["evidence-room"]["artifact"] == "evidence-room"
    assert steps["evidence-room"]["message"] == "Skipped by --skip-evidence-room"
    assert steps["manifest"]["status"] == "planned"
    assert steps["bundle"]["status"] == "planned"


def test_ci_dry_run_json_output_writes_plan_file(tmp_path: Path) -> None:
    write_config(tmp_path)
    output_path = tmp_path / "ci-plan.json"

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--json-output",
            str(output_path),
        ],
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert payload["status"] == "planned"
    assert payload["dry_run"] is True
    assert "VibeBench CI plan" in result.output
    assert "CI JSON:" in result.output


def test_ci_dry_run_json_and_output_use_same_payload(tmp_path: Path) -> None:
    write_config(tmp_path)
    output_path = tmp_path / "ci-plan.json"

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--json",
            "--json-output",
            str(output_path),
        ],
    )

    stdout_payload = json.loads(result.output)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert stdout_payload == file_payload


def test_ci_dry_run_write_plan_creates_plan_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--write-plan"],
    )

    assert result.exit_code == 0
    plan_dir = latest_run(tmp_path)
    assert plan_dir.name.endswith("_plan")
    assert plan_dir.joinpath("metrics.json").exists()
    assert plan_dir.joinpath("ci-plan.json").exists()
    assert plan_dir.joinpath("ci-plan.md").exists()
    payload = json.loads(plan_dir.joinpath("ci-plan.json").read_text())
    markdown = plan_dir.joinpath("ci-plan.md").read_text(encoding="utf-8")
    assert payload["status"] == "planned"
    assert payload["dry_run"] is True
    assert "# VibeBench CI Plan" in markdown
    assert "| check | planned |" in markdown
    assert "CI plan directory:" in result.output


def test_ci_dry_run_write_plan_json_stdout_stays_clean(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--write-plan",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    plan_dir = latest_run(tmp_path)
    file_payload = json.loads(plan_dir.joinpath("ci-plan.json").read_text())
    assert result.exit_code == 0
    assert payload == file_payload
    assert "CI plan directory" not in result.output
    assert plan_dir.joinpath("ci-plan.md").exists()


def test_ci_dry_run_plan_output_overrides(tmp_path: Path) -> None:
    write_config(tmp_path)
    json_output = tmp_path / "custom-plan.json"
    markdown_output = tmp_path / "custom-plan.md"

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--plan-json-output",
            str(json_output),
            "--plan-summary-output",
            str(markdown_output),
        ],
    )

    assert result.exit_code == 0
    assert json.loads(json_output.read_text())["status"] == "planned"
    assert "# VibeBench CI Plan" in markdown_output.read_text(encoding="utf-8")
    assert not (tmp_path / ".vibebench" / "runs").exists()


def test_ci_dry_run_written_plan_reflects_skip_flags(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--write-plan",
            "--skip-bundle",
            "--skip-manifest",
        ],
    )

    assert result.exit_code == 0
    plan_dir = latest_run(tmp_path)
    payload = json.loads(plan_dir.joinpath("ci-plan.json").read_text())
    markdown = plan_dir.joinpath("ci-plan.md").read_text(encoding="utf-8")
    steps = {step["name"]: step for step in payload["steps"]}
    assert steps["bundle"]["status"] == "skipped"
    assert steps["manifest"]["status"] == "skipped"
    assert steps["manifest-check"]["status"] == "skipped"
    assert "| bundle | skipped |" in markdown
    assert "Skipped by --skip-manifest" in markdown


def test_ci_plan_artifacts_are_discoverable(tmp_path: Path) -> None:
    write_config(tmp_path)
    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--write-plan"],
    )
    assert result.exit_code == 0
    plan_dir = latest_run(tmp_path)

    artifacts = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )
    artifact_payload = json.loads(artifacts.output)
    artifact_map = {item["name"]: item for item in artifact_payload["artifacts"]}
    assert artifacts.exit_code == 0
    assert artifact_map["ci-plan.json"]["available"] is True
    assert artifact_map["ci-plan.md"]["available"] is True

    latest = runner.invoke(
        app,
        [
            "latest",
            "--project-root",
            str(tmp_path),
            "--artifact",
            "ci-plan-json",
            "--path-only",
        ],
    )
    assert latest.exit_code == 0
    assert latest.output.strip().endswith("ci-plan.json")

    bundle = runner.invoke(
        app,
        ["bundle", "--project-root", str(tmp_path), "--run-dir", str(plan_dir)],
    )
    assert bundle.exit_code == 0
    names = zip_names(plan_dir / "vibebench-bundle.zip")
    assert "ci-plan.json" in names
    assert "ci-plan.md" in names

    manifest = runner.invoke(
        app,
        ["manifest", "--project-root", str(tmp_path), "--run-dir", str(plan_dir)],
    )
    assert manifest.exit_code == 0
    manifest_payload = json.loads(plan_dir.joinpath("manifest.json").read_text())
    manifest_artifacts = {item["name"]: item for item in manifest_payload["artifacts"]}
    assert manifest_artifacts["ci-plan.json"]["available"] is True
    assert manifest_artifacts["ci-plan.md"]["available"] is True


def test_ci_plan_output_options_require_plan_mode(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--write-plan"],
    )

    assert result.exit_code == 1
    assert "require --dry-run or --plan" in result.output


def test_ci_json_outputs_parseable_payload(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert payload["run_dir"] == str(run_dir.resolve())
    assert payload["run_id"] == run_dir.name
    step_names = [step["name"] for step in payload["steps"]]
    assert step_names == [
        "check",
        "gate",
        "config-check",
        "package-check",
        "report",
        "pr-comment",
        "explain",
        "export",
        "badge",
        "status-block",
        "trend",
        "run-index",
        "compare",
        "evidence-room",
        "manifest",
        "manifest-check",
        "release-check",
        "annotate",
        "bundle",
        "gh-summary",
    ]
    for step in payload["steps"]:
        assert set(step) == {
            "name",
            "status",
            "exit_code",
            "artifact",
            "message",
            "duration_seconds",
        }
        assert step["status"] in {"passed", "failed", "skipped"}
        assert isinstance(step["exit_code"], int)
        assert isinstance(step["duration_seconds"], int | float)
        assert step["duration_seconds"] >= 0


def test_ci_json_output_writes_payload_file(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)
    output_path = tmp_path / "ci-result.json"

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--json-output",
            str(output_path),
        ],
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert output_path.exists()
    assert payload["status"] == "passed"
    assert payload["run_id"] == run_dir.name
    assert "Final CI verdict: passed" in result.output
    assert "CI JSON:" in result.output


def test_ci_json_and_json_output_use_same_payload(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)
    output_path = tmp_path / "ci-result.json"

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--json",
            "--json-output",
            str(output_path),
        ],
    )

    stdout_payload = json.loads(result.output)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert stdout_payload == file_payload


def test_ci_json_reflects_skipped_steps(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-export",
            "--skip-badge",
            "--skip-status-block",
            "--skip-trend",
            "--skip-config-check",
            "--skip-manifest",
            "--skip-annotate",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    for name in [
        "export",
        "badge",
        "status-block",
        "trend",
        "config-check",
        "manifest",
        "manifest-check",
        "annotate",
    ]:
        assert steps[name]["status"] == "skipped"
        assert steps[name]["exit_code"] == 0
        assert steps[name]["artifact"] is None
        assert steps[name]["message"] == "skipped by flag"


def test_ci_json_reports_failed_required_step(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path, metrics=sample_metrics(score=70))

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert steps["gate"]["status"] == "failed"
    assert steps["gate"]["exit_code"] == 1


def test_ci_json_suppresses_annotation_stdout(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(
        tmp_path,
        metrics=sample_metrics(
            findings=[
                {
                    "severity": "warning",
                    "code": "demo_warning",
                    "message": "Review this change.",
                    "paths": ["src/app.py"],
                }
            ]
        ),
    )

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--allow-findings",
            "1",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert "::warning" not in result.output
    assert "demo_warning" not in result.output
    steps = {step["name"]: step for step in payload["steps"]}
    assert steps["annotate"]["status"] == "passed"


def test_init_does_not_create_generated_workflow(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert not workflow_path(tmp_path).exists()


def test_active_github_workflow_uses_ci_command() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python -m ruff check ." in workflow
    assert "python -m pytest -q" in workflow
    assert "python -m vibebench ci" in workflow
    assert "pull-requests: write" in workflow
    assert "if: github.event_name == 'pull_request'" in workflow
    assert "python -m vibebench pr-comment --post --no-fail-on-error" in workflow
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in workflow
    assert "actions/upload-artifact@v7" in workflow
    assert "name: vibebench-run-artifacts" in workflow
    assert ".vibebench/runs/**/metrics.json" in workflow
    assert ".vibebench/runs/**/release-check.md" in workflow
    assert ".vibebench/runs/**/package-check.json" in workflow
    assert ".vibebench/runs/**/package-check.md" in workflow
    assert "vibebench check" not in workflow


def test_active_github_workflow_uploads_proof_packet_artifact() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "Generate proof packet" in workflow
    assert "proof --output-dir .vibebench/proof-packet --zip" in workflow
    assert "actions/upload-artifact" in workflow
    assert "name: vibebench-proof-packet" in workflow
    assert ".vibebench/proof-packet" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "VibeBench Proof Packet" in workflow
    assert "Generated successfully" in workflow
    assert "Reproduce locally" in workflow
    assert "GitHub Actions run artifacts area" in workflow
    assert "proof.html" in workflow
    assert "proof.json" in workflow
    assert "proof.md" in workflow
    assert "proof-manifest.json" in workflow
    assert "proof.zip" in workflow


def test_active_github_workflow_uploads_static_site_preview_artifact() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python3 -m vibebench site-preview" in workflow
    assert "--output-dir .vibebench/site-preview" in workflow
    assert "--zip" in workflow
    assert "python3 -m vibebench site-check" in workflow
    assert ".vibebench/site-preview" in workflow
    assert "vibebench-site-preview" in workflow
    assert "actions/upload-artifact@v7" in workflow
    assert "vibebench-proof-packet" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "python3 -m http.server 8000 --directory docs" in workflow
    assert "index.html" in workflow
    assert "showcase.html" in workflow
    assert "pages.md" in workflow


def test_active_github_workflow_uploads_evidence_room_artifact() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python3 -m vibebench evidence-room" in workflow
    assert "--output-dir .vibebench/evidence-room" in workflow
    assert "--zip" in workflow
    assert "vibebench-evidence-room" in workflow
    assert "actions/upload-artifact" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "evidence-room.html" in workflow
    assert "evidence-room.json" in workflow
    assert "evidence-room.md" in workflow
    assert "evidence-room.zip" in workflow
    assert "proof-packet" in workflow
    assert "site-preview" in workflow
    assert "vibebench-proof-packet" in workflow
    assert "vibebench-site-preview" in workflow
    assert "not an automatically published GitHub Pages deployment" in workflow


def test_example_github_workflow_posts_pr_comments_safely() -> None:
    workflow = Path("docs/examples/github-actions/vibebench.yml").read_text(
        encoding="utf-8"
    )

    assert "pull-requests: write" in workflow
    assert "if: github.event_name == 'pull_request'" in workflow
    assert "python -m vibebench pr-comment --post --no-fail-on-error" in workflow
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in workflow
    assert "actions/upload-artifact@v7" in workflow


def test_ci_skip_manifest_skips_manifest_generation(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-manifest",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("manifest.json").exists()
    assert "manifest" in result.output
    assert "manifest-check" in result.output
    assert "skipped" in result.output


def test_ci_skip_config_check_skips_config_check_generation(tmp_path: Path) -> None:
    write_config(tmp_path)
    run_dir = write_run(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--run-dir",
            str(run_dir),
            "--skip-config-check",
        ],
    )

    assert result.exit_code == 0
    assert not run_dir.joinpath("config-check.json").exists()
    assert not run_dir.joinpath("config-check.md").exists()
    assert "config-check" in result.output
    assert "skipped" in result.output


def test_ci_dry_run_skip_run_index_marks_step_skipped(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-run-index",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["run-index"]["status"] == "skipped"
    assert steps["run-index"]["message"] == "Skipped by --skip-run-index"


def test_ci_skip_run_index_skips_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--skip-run-index",
        ],
    )

    assert result.exit_code == 0
    run_dir = latest_run(tmp_path)
    assert not run_dir.joinpath("run-index.json").exists()
    assert not run_dir.joinpath("run-index.md").exists()
    assert "run-index" in result.output


def test_ci_dry_run_skip_compare_marks_step_skipped(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-compare",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["compare"]["status"] == "skipped"
    assert steps["compare"]["message"] == "Skipped by --skip-compare"


def test_ci_skip_compare_skips_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--skip-compare",
        ],
    )

    assert result.exit_code == 0
    run_dir = latest_run(tmp_path)
    assert not run_dir.joinpath("compare.json").exists()
    assert not run_dir.joinpath("compare.md").exists()
    assert "compare" in result.output


def test_ci_dry_run_skip_package_check_marks_step_skipped(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-package-check",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["package-check"]["status"] == "skipped"
    assert steps["package-check"]["message"] == "Skipped by --skip-package-check"


def test_ci_accepts_skip_package_check_option(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--skip-package-check"],
    )

    assert result.exit_code == 0
    assert "package-check" in result.output
    assert "skipped" in result.output


def test_ci_skip_package_check_skips_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--skip-package-check",
        ],
    )

    assert result.exit_code == 0
    run_dir = latest_run(tmp_path)
    assert not run_dir.joinpath("package-check.json").exists()
    assert not run_dir.joinpath("package-check.md").exists()
    assert "package-check" in result.output


def test_ci_dry_run_skip_release_check_marks_step_skipped(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--skip-release-check",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["release-check"]["status"] == "skipped"
    assert steps["release-check"]["message"] == "Skipped by --skip-release-check"


def test_ci_accepts_skip_release_check_option(tmp_path: Path) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--skip-release-check"],
    )

    assert result.exit_code == 0
    assert "release-check" in result.output
    assert "skipped" in result.output


def test_ci_refreshes_manifest_after_late_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    manifest_check = check_manifest(tmp_path, latest_run(tmp_path))
    assert manifest_check.passed is True


def test_ci_generates_release_check_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    run_dir = latest_run(tmp_path)
    assert run_dir.joinpath("release-check.json").exists()
    assert run_dir.joinpath("release-check.md").exists()
    payload = json.loads(run_dir.joinpath("release-check.json").read_text())
    assert payload["status"] in {"ready", "not-ready"}


def test_ci_skip_release_check_skips_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--skip-release-check",
        ],
    )

    assert result.exit_code == 0
    run_dir = latest_run(tmp_path)
    assert not run_dir.joinpath("release-check.json").exists()
    assert not run_dir.joinpath("release-check.md").exists()
    assert "release-check" in result.output


def test_ci_bundle_includes_release_check_artifacts(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    run_dir = latest_run(tmp_path)
    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "package-check.json" in names
    assert "package-check.md" in names
    assert "run-index.json" in names
    assert "run-index.md" in names
    assert "compare.json" in names
    assert "compare.md" in names
    assert "release-check.json" in names
    assert "release-check.md" in names


def test_ci_evidence_room_is_discoverable_and_bundled(tmp_path: Path) -> None:
    write_config(tmp_path)
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path), "--json"])

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["evidence-room"]["status"] == "passed"
    run_dir = latest_run(tmp_path)
    evidence_dir = run_dir / "evidence-room"
    assert evidence_dir.joinpath("index.html").exists()
    assert evidence_dir.joinpath("review-hub.html").exists()
    assert evidence_dir.joinpath("reviewer-guide.md").exists()
    assert evidence_dir.joinpath("trust-center.html").exists()
    assert evidence_dir.joinpath("trust-center.md").exists()
    assert evidence_dir.joinpath("security-questionnaire.html").exists()
    assert evidence_dir.joinpath("security-questionnaire.md").exists()
    assert evidence_dir.joinpath("review-scorecard.html").exists()
    assert evidence_dir.joinpath("review-scorecard.md").exists()
    assert evidence_dir.joinpath("review-scorecard.json").exists()
    assert evidence_dir.joinpath("share-check.json").exists()
    assert evidence_dir.joinpath("share-check.md").exists()
    share_check_payload = json.loads(
        evidence_dir.joinpath("share-check.json").read_text(encoding="utf-8")
    )
    assert share_check_payload["status"] == "passed"
    assert evidence_dir.joinpath("evidence-room.html").exists()
    assert evidence_dir.joinpath("evidence-room.json").exists()
    assert evidence_dir.joinpath("evidence-room.md").exists()
    assert evidence_dir.joinpath("evidence-room.zip").exists()
    assert evidence_dir.joinpath("proof-packet", "proof.html").exists()
    assert evidence_dir.joinpath("site-preview", "site-preview.md").exists()

    artifacts = runner.invoke(
        app,
        ["artifacts", "--project-root", str(tmp_path), "--json"],
    )
    artifact_map = {
        item["name"]: item for item in json.loads(artifacts.output)["artifacts"]
    }
    assert artifacts.exit_code == 0
    for name in [
        "evidence-room-index-html",
        "evidence-room-review-hub-html",
        "evidence-room-reviewer-guide-md",
        "evidence-room-trust-center-html",
        "evidence-room-trust-center-md",
        "evidence-room-security-questionnaire-html",
        "evidence-room-security-questionnaire-md",
        "evidence-room-scorecard-html",
        "evidence-room-scorecard-md",
        "evidence-room-scorecard-json",
        "evidence-room-share-check-json",
        "evidence-room-share-check-md",
        "evidence-room-html",
        "evidence-room-json",
        "evidence-room-md",
        "evidence-room-zip",
        "evidence-room-dir",
    ]:
        assert artifact_map[name]["available"] is True

    for artifact_name, suffix in [
        ("evidence-room-index-html", "evidence-room/index.html"),
        ("evidence-room-review-hub-html", "evidence-room/review-hub.html"),
        ("evidence-room-reviewer-guide-md", "evidence-room/reviewer-guide.md"),
        ("evidence-room-trust-center-html", "evidence-room/trust-center.html"),
        ("evidence-room-trust-center-md", "evidence-room/trust-center.md"),
        (
            "evidence-room-security-questionnaire-html",
            "evidence-room/security-questionnaire.html",
        ),
        (
            "evidence-room-security-questionnaire-md",
            "evidence-room/security-questionnaire.md",
        ),
        ("evidence-room-scorecard-html", "evidence-room/review-scorecard.html"),
        ("evidence-room-scorecard-md", "evidence-room/review-scorecard.md"),
        ("evidence-room-scorecard-json", "evidence-room/review-scorecard.json"),
        ("evidence-room-share-check-json", "evidence-room/share-check.json"),
        ("evidence-room-share-check-md", "evidence-room/share-check.md"),
        ("evidence-room-html", "evidence-room/evidence-room.html"),
        ("evidence-room-json", "evidence-room/evidence-room.json"),
        ("evidence-room-md", "evidence-room/evidence-room.md"),
        ("evidence-room-zip", "evidence-room/evidence-room.zip"),
        ("evidence-room-dir", "evidence-room"),
    ]:
        latest = runner.invoke(
            app,
            [
                "latest",
                "--project-root",
                str(tmp_path),
                "--artifact",
                artifact_name,
                "--path-only",
            ],
        )
        assert latest.exit_code == 0
        assert latest.output.strip().endswith(suffix)

    manifest_result = check_manifest(tmp_path, run_dir)
    assert manifest_result.passed is True
    manifest_payload = json.loads(run_dir.joinpath("manifest.json").read_text())
    manifest_artifacts = {item["name"]: item for item in manifest_payload["artifacts"]}
    assert manifest_artifacts["evidence-room-index-html"]["available"] is True
    assert manifest_artifacts["evidence-room-review-hub-html"]["available"] is True
    assert manifest_artifacts["evidence-room-reviewer-guide-md"]["available"] is True
    assert manifest_artifacts["evidence-room-trust-center-html"]["available"] is True
    assert manifest_artifacts["evidence-room-trust-center-md"]["available"] is True
    assert (
        manifest_artifacts["evidence-room-security-questionnaire-html"]["available"]
        is True
    )
    assert (
        manifest_artifacts["evidence-room-security-questionnaire-md"]["available"]
        is True
    )
    assert manifest_artifacts["evidence-room-scorecard-html"]["available"] is True
    assert manifest_artifacts["evidence-room-scorecard-md"]["available"] is True
    assert manifest_artifacts["evidence-room-scorecard-json"]["available"] is True
    assert manifest_artifacts["evidence-room-share-check-json"]["available"] is True
    assert manifest_artifacts["evidence-room-share-check-md"]["available"] is True
    assert manifest_artifacts["evidence-room-html"]["available"] is True
    assert manifest_artifacts["evidence-room-dir"]["available"] is True

    names = zip_names(run_dir / "vibebench-bundle.zip")
    assert "evidence-room/index.html" in names
    assert "evidence-room/review-hub.html" in names
    assert "evidence-room/reviewer-guide.md" in names
    assert "evidence-room/trust-center.html" in names
    assert "evidence-room/trust-center.md" in names
    assert "evidence-room/security-questionnaire.html" in names
    assert "evidence-room/security-questionnaire.md" in names
    assert "evidence-room/review-scorecard.html" in names
    assert "evidence-room/review-scorecard.md" in names
    assert "evidence-room/review-scorecard.json" in names
    assert "evidence-room/share-check.json" in names
    assert "evidence-room/share-check.md" in names
    assert "evidence-room/evidence-room.html" in names
    assert "evidence-room/evidence-room.json" in names
    assert "evidence-room/evidence-room.md" in names
    assert "evidence-room/evidence-room.zip" in names
    assert "evidence-room/proof-packet/proof.html" not in names


def test_ci_config_regression_enabled_runs_check_by_default(
    tmp_path: Path,
) -> None:
    write_config(
        tmp_path,
        regression_policy=(
            "regression:\n"
            "  enabled: true\n"
            "  require_baseline: false\n"
            "  max_score_drop: 0.0\n"
            "  max_risk_increase: 0.0\n"
            "  fail_on_missing_metrics: true\n"
        ),
    )
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path), "--json"])

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("regression-check.json").read_text())
    assert result.exit_code == 0
    assert steps["regression-check"]["status"] == "skipped"
    assert report["policy_source"] == "config"


def test_ci_config_regression_disabled_does_not_run_by_default(
    tmp_path: Path,
) -> None:
    write_config(
        tmp_path,
        regression_policy=(
            "regression:\n"
            "  enabled: false\n"
            "  baseline_label: stable\n"
            "  require_baseline: true\n"
            "  max_score_drop: 0.0\n"
            "  max_risk_increase: 0.0\n"
            "  fail_on_missing_metrics: true\n"
        ),
    )
    init_git_repo(tmp_path)

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path), "--json"])

    steps = {step["name"]: step for step in json.loads(result.output)["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 0
    assert "regression-check" not in steps
    assert not run_dir.joinpath("regression-check.json").exists()


def test_ci_regression_check_forces_disabled_config(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        regression_policy=(
            "regression:\n"
            "  enabled: false\n"
            "  require_baseline: false\n"
            "  max_score_drop: 0.0\n"
            "  max_risk_increase: 0.0\n"
            "  fail_on_missing_metrics: true\n"
        ),
    )
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--regression-check", "--json"],
    )

    steps = {step["name"]: step for step in json.loads(result.output)["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("regression-check.json").read_text())
    assert result.exit_code == 0
    assert steps["regression-check"]["status"] == "skipped"
    assert report["policy_source"] == "cli"


def test_ci_skip_regression_check_disables_config_enabled_policy(
    tmp_path: Path,
) -> None:
    write_config(
        tmp_path,
        regression_policy=(
            "regression:\n"
            "  enabled: true\n"
            "  require_baseline: true\n"
            "  max_score_drop: 0.0\n"
            "  max_risk_increase: 0.0\n"
            "  fail_on_missing_metrics: true\n"
        ),
    )
    init_git_repo(tmp_path)

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--skip-regression-check", "--json"],
    )

    steps = {step["name"]: step for step in json.loads(result.output)["steps"]}
    run_dir = latest_run(tmp_path)
    assert result.exit_code == 0
    assert "regression-check" not in steps
    assert not run_dir.joinpath("regression-check.json").exists()


def test_ci_dry_run_json_reflects_config_enabled_regression_check(
    tmp_path: Path,
) -> None:
    write_config(
        tmp_path,
        regression_policy=(
            "regression:\n"
            "  enabled: true\n"
            "  baseline_label: stable\n"
            "  require_baseline: true\n"
            "  max_score_drop: 2\n"
            "  max_risk_increase: 1\n"
            "  fail_on_missing_metrics: false\n"
        ),
    )

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--dry-run", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["regression-check"]["status"] == "planned"
    assert "policy=config" in steps["regression-check"]["message"]
    assert "stable" in steps["regression-check"]["message"]


def test_ci_regression_check_uses_config_baseline_label(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        regression_policy=(
            "regression:\n"
            "  enabled: true\n"
            "  baseline_label: stable\n"
            "  require_baseline: true\n"
            "  max_score_drop: 0.0\n"
            "  max_risk_increase: 0.0\n"
            "  fail_on_missing_metrics: true\n"
        ),
    )
    init_git_repo(tmp_path)
    baseline = write_run(tmp_path, "20260706_100000", metrics=sample_metrics(score=100))
    pin = runner.invoke(
        app,
        [
            "baseline",
            "--project-root",
            str(tmp_path),
            "--set-run",
            baseline.name,
            "--label",
            "stable",
        ],
    )
    assert pin.exit_code == 0

    result = runner.invoke(app, ["ci", "--project-root", str(tmp_path), "--json"])

    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("regression-check.json").read_text())
    assert result.exit_code == 0
    assert report["baseline_source"] == "pinned"
    assert report["baseline_label"] == "stable"
    assert report["policy_source"] == "config"


def test_ci_dry_run_metrics_diff_policy_json_includes_enforced_step(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "ci",
            "--project-root",
            str(tmp_path),
            "--dry-run",
            "--metrics-diff-policy",
            "--json",
        ],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    assert result.exit_code == 0
    assert steps["metrics-diff"]["status"] == "planned"
    assert "policy enforcement" in steps["metrics-diff"]["message"]
    assert not (tmp_path / ".vibebench" / "runs").exists()


def test_ci_metrics_diff_policy_writes_artifacts_and_fails(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    append_metrics_diff_policy(tmp_path, "    enabled: false\n")
    init_git_repo(tmp_path)
    write_run(tmp_path, "20200101_000000", metrics=sample_metrics(score=101))

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--metrics-diff-policy", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("metrics-diff.json").read_text())
    assert result.exit_code == 1
    assert steps["metrics-diff"]["status"] == "failed"
    assert report["policy_enforced"] is True
    assert report["policy_status"] == "failed"
    assert run_dir.joinpath("metrics-diff.md").exists()


def test_ci_metrics_diff_policy_writes_artifacts_and_passes(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    append_metrics_diff_policy(tmp_path, "    enabled: false\n")
    init_git_repo(tmp_path)
    write_run(tmp_path, "20200101_000000", metrics=sample_metrics(score=90))

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--metrics-diff-policy", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("metrics-diff.json").read_text())
    assert result.exit_code == 0
    assert steps["metrics-diff"]["status"] == "passed"
    assert report["policy_status"] == "passed"
    assert report["policy_error_count"] == 0


def test_ci_metrics_diff_remains_report_only_with_policy_regression(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    append_metrics_diff_policy(tmp_path, "    enabled: false\n")
    init_git_repo(tmp_path)
    write_run(tmp_path, "20200101_000000", metrics=sample_metrics(score=101))

    result = runner.invoke(
        app,
        ["ci", "--project-root", str(tmp_path), "--metrics-diff", "--json"],
    )

    payload = json.loads(result.output)
    steps = {step["name"]: step for step in payload["steps"]}
    run_dir = latest_run(tmp_path)
    report = json.loads(run_dir.joinpath("metrics-diff.json").read_text())
    assert result.exit_code == 0
    assert steps["metrics-diff"]["status"] == "passed"
    assert "policy_status" not in report
    assert report["summary"]["regressed_count"] >= 1
