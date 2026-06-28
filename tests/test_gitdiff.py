import subprocess
from pathlib import Path

from vibebench.config import RiskConfig, RiskRulesConfig
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

def risk_config(**overrides: object) -> RiskConfig:
    values = RiskConfig().model_dump()
    values.update(overrides)
    return RiskConfig.model_validate(values)

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

def test_default_risk_config_matches_existing_detection(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo / ".env.local", "TOKEN=value\n")
    write(repo / "package-lock.json", "{}\n")

    analysis, findings = analyze_git_diff(repo, risk_config())

    assert analysis.forbidden_paths_touched == [".env.local"]
    assert analysis.lockfiles_changed == ["package-lock.json"]
    assert {"forbidden_paths_touched", "lockfiles_changed"}.issubset(
        finding_codes(findings)
    )

def test_custom_max_changed_files_triggers_warning(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo / "a.py", "a\n")
    write(repo / "b.py", "b\n")

    _analysis, findings = analyze_git_diff(repo, risk_config(max_changed_files=1))

    assert "many_files_changed" in finding_codes(findings)

def test_custom_max_patch_lines_triggers_warning(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo / "src" / "app.py", "changed\nline\n")

    _analysis, findings = analyze_git_diff(repo, risk_config(max_patch_lines=1))

    assert "large_patch" in finding_codes(findings)

def test_custom_forbidden_paths_are_used(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo / "private" / "config.json", "{}\n")

    analysis, findings = analyze_git_diff(
        repo, risk_config(forbidden_paths=["private/"])
    )

    assert analysis.forbidden_paths_touched == ["private/config.json"]
    assert "forbidden_paths_touched" in finding_codes(findings)

def test_custom_secret_like_paths_are_used(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo / "certs" / "server.pem", "fake\n")

    analysis, findings = analyze_git_diff(
        repo, risk_config(secret_like_paths=["*.pem"])
    )

    assert analysis.secret_like_files_touched == ["certs/server.pem"]
    assert "secret_like_files_touched" in finding_codes(findings)

def test_custom_lockfiles_are_used(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo / "custom.lock", "v1\n")
    run(["git", "add", "custom.lock"], repo)
    run(["git", "commit", "-m", "add custom lock"], repo)
    write(repo / "custom.lock", "v2\n")

    analysis, findings = analyze_git_diff(repo, risk_config(lockfiles=["custom.lock"]))

    assert analysis.lockfiles_changed == ["custom.lock"]
    assert "lockfiles_changed" in finding_codes(findings)

def test_custom_test_path_patterns_are_used(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo / "specs" / "app_check.py", "def test_custom():\n    assert True\n")

    analysis, findings = analyze_git_diff(
        repo, risk_config(test_path_patterns=["specs/"])
    )

    assert analysis.test_files_changed == ["specs/app_check.py"]
    assert "test_files_changed" in finding_codes(findings)
