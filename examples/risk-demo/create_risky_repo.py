#!/usr/bin/env python3
"""Create a deterministic risky repository for VibeBench demos."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

DEFAULT_OUTPUT = Path("/tmp/vibebench-risk-demo")

APP_BASELINE = '''def add(left: int, right: int) -> int:
    """Return the sum of two integers."""
    return left + right


def health() -> str:
    """Return the application health status."""
    return "ok"
'''

TEST_APP = '''from app import add


def test_add() -> None:
    assert add(2, 3) == 5
'''

TEST_HEALTH = '''from app import health


def test_health() -> None:
    assert health() == "ok"
'''

CONFIG = """project:
  name: vibebench-risk-demo

checks:
  test:
    - pytest -q
  lint:
    - ruff check .

risk_rules:
  forbidden_paths:
    - .env
    - .env.*
    - secrets/
  warn_if_tests_deleted: true
  warn_if_lockfiles_changed: true
  large_patch_lines: 30
"""

PYPROJECT = """[project]
name = "vibebench-risk-demo"
version = "0.0.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
line-length = 88
target-version = "py311"
"""

PACKAGE_LOCK = """{
  "name": "vibebench-risk-demo",
  "lockfileVersion": 3,
  "packages": {}
}
"""

GITIGNORE = """__pycache__/
.pytest_cache/
.ruff_cache/
.vibebench/runs/
"""


class DemoError(Exception):
    """Raised when the demo repository cannot be created."""


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Create a risky demo repository for VibeBench Arena."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Demo repository path. Defaults to {DEFAULT_OUTPUT}.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove an existing output directory before creation.",
    )
    return parser.parse_args()


def run(command: list[str], cwd: Path) -> None:
    """Run a command, raising a readable error if it fails."""
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        output_parts = [completed.stdout.strip(), completed.stderr.strip()]
        output = "\n".join(part for part in output_parts if part)
        raise DemoError(f"Command failed: {' '.join(command)}\n{output}")


def create_demo_repo(output: Path, clean: bool = True) -> Path:
    """Create a risky demo repository and return its path."""
    demo_dir = output.resolve()
    if demo_dir.exists() and clean:
        shutil.rmtree(demo_dir)
    demo_dir.mkdir(parents=True, exist_ok=True)

    write_baseline(demo_dir)
    initialize_git(demo_dir)
    introduce_risks(demo_dir)
    return demo_dir


def write_baseline(demo_dir: Path) -> None:
    """Write the clean baseline project files."""
    (demo_dir / "tests").mkdir(parents=True, exist_ok=True)
    (demo_dir / ".vibebench").mkdir(parents=True, exist_ok=True)
    (demo_dir / "app.py").write_text(APP_BASELINE, encoding="utf-8")
    (demo_dir / "tests" / "test_app.py").write_text(TEST_APP, encoding="utf-8")
    (demo_dir / "tests" / "test_health.py").write_text(TEST_HEALTH, encoding="utf-8")
    (demo_dir / ".vibebench" / "config.yaml").write_text(CONFIG, encoding="utf-8")
    (demo_dir / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (demo_dir / ".gitignore").write_text(GITIGNORE, encoding="utf-8")


def initialize_git(demo_dir: Path) -> None:
    """Initialize git and commit the clean baseline."""
    run(["git", "init"], demo_dir)
    run(["git", "config", "user.name", "VibeBench Demo"], demo_dir)
    run(["git", "config", "user.email", "demo@example.com"], demo_dir)
    run(["git", "add", "."], demo_dir)
    run(["git", "commit", "-m", "baseline demo project"], demo_dir)


def introduce_risks(demo_dir: Path) -> None:
    """Introduce deterministic risky uncommitted changes."""
    (demo_dir / ".env.local").write_text(
        "DEMO_API_KEY=not-a-real-secret\n", encoding="utf-8"
    )
    secrets_dir = demo_dir / "secrets"
    secrets_dir.mkdir(exist_ok=True)
    (secrets_dir / "config.json").write_text(
        '{\n  "token": "not-a-real-secret"\n}\n', encoding="utf-8"
    )
    (demo_dir / "tests" / "test_app.py").unlink()
    (demo_dir / "package-lock.json").write_text(PACKAGE_LOCK, encoding="utf-8")
    append_large_patch(demo_dir / "app.py")


def append_large_patch(app_path: Path) -> None:
    """Append enough harmless lines to exceed the demo large-patch threshold."""
    lines = ["", "", "DEMO_PATCH_NOTES = ["]
    lines.extend(f'    "demo risk line {index:02d}",' for index in range(40))
    lines.append("]")
    lines.append("")
    app_path.write_text(
        app_path.read_text(encoding="utf-8") + "\n".join(lines),
        encoding="utf-8",
    )


def print_next_steps(demo_dir: Path) -> None:
    """Print the commands a user can run next."""
    print(f"Created VibeBench risk demo repository: {demo_dir}")
    print()
    print("Next commands:")
    print(f"  cd {demo_dir}")
    print("  python -m vibebench check")
    print("  python -m vibebench report")
    print("  python -m vibebench pr-comment")
    print()
    print("Expected findings:")
    print("  - forbidden_paths_touched: .env.local, secrets/config.json")
    print("  - secret_like_files_touched: secrets/config.json")
    print("  - tests_deleted: tests/test_app.py")
    print("  - lockfiles_changed: package-lock.json")
    print("  - large_patch: app.py exceeds the demo threshold")


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    demo_dir = create_demo_repo(args.output, clean=not args.no_clean)
    print_next_steps(demo_dir)


if __name__ == "__main__":
    main()
