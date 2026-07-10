#!/usr/bin/env python3
"""Build or check the committed public demo portal."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PROOF = ROOT / "examples" / "showcase-artifacts" / "public-proof"
PUBLIC_DEMO = ROOT / "examples" / "showcase-artifacts" / "public-demo"
HOST_GITHUB_ENV_KEYS = {
    "GITHUB_ACTIONS",
    "GITHUB_STEP_SUMMARY",
    "GITHUB_OUTPUT",
    "GITHUB_ENV",
    "GITHUB_PATH",
    "GITHUB_WORKSPACE",
    "GITHUB_EVENT_PATH",
}


def main() -> int:
    """Run the public-demo builder."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="refresh committed demo")
    mode.add_argument("--check", action="store_true", help="verify committed demo")
    args = parser.parse_args()

    command = [
        sys.executable,
        "-m",
        "vibebench",
        "public-demo",
        "--proof-packet",
        str(PUBLIC_PROOF.relative_to(ROOT)),
        "--output-dir",
        str(PUBLIC_DEMO.relative_to(ROOT)),
    ]
    if args.check:
        command.append("--check")

    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=builder_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        sys.stderr.write(completed.stdout)
        return completed.returncode
    sys.stdout.write(completed.stdout)
    if args.check:
        print("public demo portal is current")
    else:
        print(f"Wrote public demo portal to {PUBLIC_DEMO.relative_to(ROOT)}")
    return 0


def builder_env() -> dict[str, str]:
    """Return a controlled environment for reproducible demo generation."""
    env = os.environ.copy()
    for key in HOST_GITHUB_ENV_KEYS:
        env.pop(key, None)
    python_path = str(ROOT)
    if env.get("PYTHONPATH"):
        python_path = python_path + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = python_path
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("NO_COLOR", "1")
    env.setdefault("COLUMNS", "120")
    return env


if __name__ == "__main__":
    raise SystemExit(main())
