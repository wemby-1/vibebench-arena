import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType


def load_demo_module() -> ModuleType:
    script_path = (
        Path(__file__).parents[1]
        / "examples"
        / "risk-demo"
        / "create_risky_repo.py"
    )
    spec = importlib.util.spec_from_file_location("risk_demo", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_status(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def test_risk_demo_creates_repo_with_intended_changes(tmp_path: Path) -> None:
    module = load_demo_module()
    demo_dir = module.create_demo_repo(tmp_path / "risk-demo")

    assert demo_dir.joinpath(".git").exists()
    assert demo_dir.joinpath(".vibebench", "config.yaml").exists()
    assert demo_dir.joinpath(".env.local").read_text(encoding="utf-8") == (
        "DEMO_API_KEY=not-a-real-secret\n"
    )
    assert demo_dir.joinpath("secrets", "config.json").exists()
    assert demo_dir.joinpath("package-lock.json").exists()
    assert not demo_dir.joinpath("tests", "test_app.py").exists()
    assert demo_dir.joinpath("tests", "test_health.py").exists()

    status = git_status(demo_dir)

    assert " M app.py" in status
    assert " D tests/test_app.py" in status
    assert "?? .env.local" in status
    assert "?? package-lock.json" in status
    assert "?? secrets/config.json" in status


def test_risk_demo_no_clean_keeps_existing_file(tmp_path: Path) -> None:
    module = load_demo_module()
    demo_dir = tmp_path / "risk-demo"
    demo_dir.mkdir()
    marker = demo_dir / "marker.txt"
    marker.write_text("keep me", encoding="utf-8")

    module.create_demo_repo(demo_dir, clean=False)

    assert marker.read_text(encoding="utf-8") == "keep me"
