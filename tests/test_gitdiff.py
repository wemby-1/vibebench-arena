import subprocess
from pathlib import Path

from vibebench.config import RiskRulesConfig
from vibebench.gitdiff import RiskFinding, analyze_git_diff
from vibebench.runner import score_from_failures


def run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def init_repo(path: Path) -> Path:
    run(["git", "init"], path)
    run(["git", "config", "user.name", "Test User"], path)
    run(["git", "config", "user.email", "test@example.com"], path)
    write(path / "src" / "app.py", "print('hello')\n")
    write(path / "tests" / "test_app.py", "def test_app():\n    assert True\n")
    run(["git", "add", "."], path)
    run(["git", "commit", "-m", "initial"], path)
    return path


def rules(large_patch_lines: int = 500) -> RiskRulesConfig:
    return RiskRulesConfig(
        forbidden_paths=[".env", ".env.*", "secrets/"],
        warn_if_tests_deleted=True,
        warn_if_lockfiles_changed=True,
        large_patch_lines=large_patch_lines,
    )


def finding_codes(findings: list[RiskFinding]) -> set[str]:
    return {finding.code for finding in findings}


def test_no_git_repo_does_not_crash(tmp_path: Path) -> None:
    analysis, findings = analyze_git_diff(tmp_path, rules())

    assert analysis.git_available is False
    assert analysis.warnings
    assert finding_codes(findings) == {"git_unavailable"}


def test_clean_git_repo_returns_zero_changed_files(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    analysis, findings = analyze_git_diff(repo, rules())

    assert analysis.git_available is True
    assert analysis.changed_file_count == 0
    assert analysis.changed_files == []
    assert findings == []


def test_modified_normal_source_file_is_detected(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo / "src" / "app.py", "print('changed')\n")

    analysis, findings = analyze_git_diff(repo, rules())

    assert analysis.modified_files == ["src/app.py"]
    assert analysis.changed_file_count == 1
    assert findings == []


def test_deleted_test_file_is_detected(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "tests" / "test_app.py").unlink()

    analysis, findings = analyze_git_diff(repo, rules())

    assert analysis.tests_deleted == ["tests/test_app.py"]
    assert "tests_deleted" in finding_codes(findings)


def test_env_local_is_forbidden_path(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo / ".env.local", "TOKEN=value\n")

    analysis, findings = analyze_git_diff(repo, rules())

    assert analysis.forbidden_paths_touched == [".env.local"]
    assert any(
        finding.code == "forbidden_paths_touched"
        and finding.severity == "critical"
        for finding in findings
    )


def test_secrets_directory_is_forbidden_path(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo / "secrets" / "config.json", "{}\n")

    analysis, findings = analyze_git_diff(repo, rules())

    assert analysis.forbidden_paths_touched == ["secrets/config.json"]
    assert "forbidden_paths_touched" in finding_codes(findings)


def test_package_lock_changed_is_detected(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo / "package-lock.json", "{}\n")
    run(["git", "add", "package-lock.json"], repo)
    run(["git", "commit", "-m", "add lockfile"], repo)
    write(repo / "package-lock.json", '{"changed": true}\n')

    analysis, findings = analyze_git_diff(repo, rules())

    assert analysis.lockfiles_changed == ["package-lock.json"]
    assert "lockfiles_changed" in finding_codes(findings)


def test_large_patch_triggers_warning(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo / "src" / "app.py", "\n".join(str(i) for i in range(20)) + "\n")

    analysis, findings = analyze_git_diff(repo, rules(large_patch_lines=5))

    assert analysis.total_patch_lines > 5
    assert "large_patch" in finding_codes(findings)


def test_scoring_decreases_for_findings() -> None:
    findings = [
        RiskFinding(severity="critical", code="critical", message="critical"),
        RiskFinding(severity="high", code="high", message="high"),
        RiskFinding(severity="warning", code="warning", message="warning"),
        RiskFinding(severity="info", code="info", message="info"),
    ]

    assert score_from_failures(0, findings) == 42
    assert score_from_failures(1, findings) == 2
