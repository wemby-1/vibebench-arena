#!/usr/bin/env python3
"""Build or check the committed public proof packet."""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "examples" / "reference-project"
PUBLIC_PACKET = ROOT / "examples" / "showcase-artifacts" / "public-proof"
CANONICAL_ROOT = "<reference-project>"
CANONICAL_RUN_ID = "public-proof-run"
CANONICAL_TIMESTAMP = "2026-07-10T00:00:00Z"
CURATED_FILES = [
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
    "adoption-ready.json",
    "adoption-ready.md",
    "artifact-inventory.json",
    "github-step-summary.md",
    "explain.md",
    "gate-summary.md",
    "report/index.html",
]
STATIC_FILES = ["README.md", "proof-packet-index.md"]
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


class BuildError(RuntimeError):
    """Raised when proof-packet generation fails."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="refresh committed packet")
    mode.add_argument("--check", action="store_true", help="verify committed packet")
    args = parser.parse_args()

    try:
        with tempfile.TemporaryDirectory(prefix="vibebench-public-proof-") as temp:
            generated = Path(temp) / "generated"
            build_packet(generated)
            if args.write:
                write_packet(generated)
                print(f"Wrote public proof packet to {PUBLIC_PACKET.relative_to(ROOT)}")
                return 0
            return check_packet(generated)
    except BuildError as exc:
        print(f"public proof packet build failed: {exc}", file=sys.stderr)
        return 1


def build_packet(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vibebench-reference-project-") as temp:
        workspace = Path(temp) / "reference-project"
        try:
            shutil.copytree(
                REFERENCE,
                workspace,
                ignore=shutil.ignore_patterns(
                    ".git",
                    ".pytest_cache",
                    "__pycache__",
                    "*.pyc",
                    ".vibebench/runs",
                    ".vibebench/baselines",
                ),
            )
        except OSError as exc:
            raise BuildError(f"could not copy reference project: {exc}") from exc
        init_git(workspace)
        run_ci(workspace)
        run_dir = latest_run_dir(workspace)
        run_command(
            [
                sys.executable,
                "-m",
                "vibebench",
                "adoption-ready",
                "-C",
                str(workspace),
                "--strict",
                "--json-output",
                str(run_dir / "adoption-ready.json"),
                "--summary-output",
                str(run_dir / "adoption-ready.md"),
            ],
            cwd=ROOT,
        )
        artifact_inventory = run_command(
            [
                sys.executable,
                "-m",
                "vibebench",
                "artifacts",
                "-C",
                str(workspace),
                "--run-dir",
                str(run_dir),
                "--only-available",
                "--json",
            ],
            cwd=ROOT,
        )
        (run_dir / "artifact-inventory.json").write_text(
            artifact_inventory.stdout,
            encoding="utf-8",
        )
        copy_curated_artifacts(run_dir, output_dir)
        write_static_packet_docs(output_dir)
        normalize_packet(output_dir, workspace, run_dir)
        refresh_inventory_sizes(output_dir)
        scan_for_leaks(output_dir)


def init_git(workspace: Path) -> None:
    run_command(["git", "init"], cwd=workspace)
    run_command(["git", "config", "user.name", "VibeBench Fixture"], cwd=workspace)
    run_command(
        ["git", "config", "user.email", "fixture@example.invalid"],
        cwd=workspace,
    )
    run_command(["git", "add", "."], cwd=workspace)
    run_command(["git", "commit", "-m", "fixture baseline"], cwd=workspace)


def run_ci(workspace: Path) -> None:
    result = run_command(
        [
            sys.executable,
            "-m",
            "vibebench",
            "ci",
            "-C",
            str(workspace),
            "--adoption-policy",
            "--require-adoption-workflow",
            "--preflight-require-ci-mode",
            "adoption-policy",
            "--workflow-check-require-ci-mode",
            "adoption-policy",
            "--skip-evidence-room",
            "--json",
        ],
        cwd=ROOT,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise BuildError(f"ci did not return JSON: {exc}") from exc
    if payload.get("status") != "passed":
        raise BuildError("ci reported a failed pipeline")


def latest_run_dir(workspace: Path) -> Path:
    runs_dir = workspace / ".vibebench" / "runs"
    candidates = sorted(path for path in runs_dir.iterdir() if path.is_dir())
    if not candidates:
        raise BuildError("ci did not create a run directory")
    return candidates[-1]


def copy_curated_artifacts(run_dir: Path, output_dir: Path) -> None:
    missing: list[str] = []
    for relative in CURATED_FILES:
        source = run_dir / relative
        target = output_dir / relative
        if not source.is_file():
            missing.append(relative)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    if missing:
        raise BuildError("missing expected artifacts: " + ", ".join(missing))


def write_static_packet_docs(output_dir: Path) -> None:
    for relative in STATIC_FILES:
        source = PUBLIC_PACKET / relative
        if source.is_file():
            shutil.copy2(source, output_dir / relative)
            continue
        raise BuildError(f"missing committed static packet doc: {relative}")


def normalize_packet(output_dir: Path, workspace: Path, run_dir: Path) -> None:
    replacements = {
        str(workspace.resolve()): CANONICAL_ROOT,
        str(run_dir.resolve()): f"{CANONICAL_ROOT}/.vibebench/runs/{CANONICAL_RUN_ID}",
        run_dir.name: CANONICAL_RUN_ID,
    }
    temp_root = str(workspace.parent.resolve())
    replacements[temp_root] = "<temporary-workspace>"

    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        if path.suffix != ".json":
            text = normalize_text(text)
        path.write_text(text, encoding="utf-8")

    for path in sorted(output_dir.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload = normalize_json(payload)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def normalize_text(text: str) -> str:
    text = re.sub(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)",
        CANONICAL_TIMESTAMP,
        text,
    )
    text = re.sub(r"Duration seconds: \d+\.\d+", "Duration seconds: 0.000", text)
    text = re.sub(r"Ran 2 tests in \d+\.\d+s", "Ran 2 tests in 0.000s", text)
    text = re.sub(r"\b\d+\.\d{3}s\b", "0.000s", text)
    text = re.sub(r"public-proof-run/report", "report", text)
    text = text.replace("fixture@example.invalid", "<fixture-email>")
    return text


def normalize_json(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"created_at", "generated_at"}:
                normalized[key] = CANONICAL_TIMESTAMP
            elif key == "duration_seconds":
                normalized[key] = 0.0
            elif key in {"run_dir", "metrics_path", "log_path"} and isinstance(
                item, str
            ):
                normalized[key] = item.replace(
                    f"{CANONICAL_ROOT}/.vibebench/runs/{CANONICAL_RUN_ID}",
                    f"{CANONICAL_ROOT}/.vibebench/runs/{CANONICAL_RUN_ID}",
                )
            else:
                normalized[key] = normalize_json(item)
        return normalized
    if isinstance(value, list):
        return [normalize_json(item) for item in value]
    if isinstance(value, str):
        return normalize_text(value)
    return value


def refresh_inventory_sizes(output_dir: Path) -> None:
    for relative in ["manifest.json", "artifact-inventory.json"]:
        path = output_dir / relative
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        artifacts = payload.get("artifacts")
        if isinstance(artifacts, list):
            for artifact in artifacts:
                if not isinstance(artifact, dict):
                    continue
                artifact_path = public_artifact_path(output_dir, artifact.get("path"))
                if artifact_path is not None and artifact_path.is_file():
                    artifact["available"] = True
                    artifact["size_bytes"] = artifact_path.stat().st_size
                elif artifact.get("available") is True:
                    artifact["available"] = False
                    artifact["size_bytes"] = None
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def public_artifact_path(output_dir: Path, path_value: object) -> Path | None:
    if not isinstance(path_value, str):
        return None
    prefix = ".vibebench/runs/public-proof-run/"
    if path_value.startswith(prefix):
        return output_dir / path_value.removeprefix(prefix)
    report_prefix = ".vibebench/runs/report/"
    if path_value.startswith(report_prefix):
        return output_dir / "report" / path_value.removeprefix(report_prefix)
    return None


def scan_for_leaks(output_dir: Path) -> None:
    matches: list[str] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                matches.append(f"{path.relative_to(output_dir)} matches {pattern}")
    if matches:
        raise BuildError("leak scan failed: " + "; ".join(matches[:10]))


def write_packet(generated: Path) -> None:
    for child in PUBLIC_PACKET.iterdir():
        if child.name in STATIC_FILES:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for source in sorted(generated.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(generated)
        target = PUBLIC_PACKET / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def check_packet(generated: Path) -> int:
    if not PUBLIC_PACKET.is_dir():
        print(f"public proof packet is missing: {PUBLIC_PACKET}", file=sys.stderr)
        return 1
    left = file_set(generated)
    right = file_set(PUBLIC_PACKET)
    if left != right:
        print("public proof packet file set differs", file=sys.stderr)
        print("missing committed files:", sorted(left - right), file=sys.stderr)
        print("extra committed files:", sorted(right - left), file=sys.stderr)
        return 1
    changed = [
        relative
        for relative in sorted(left)
        if not filecmp.cmp(
            generated / relative,
            PUBLIC_PACKET / relative,
            shallow=False,
        )
    ]
    if changed:
        print("public proof packet is stale; differing files:", file=sys.stderr)
        for relative in changed[:20]:
            print(f"  {relative}", file=sys.stderr)
        return 1
    scan_for_leaks(PUBLIC_PACKET)
    print("public proof packet is current")
    return 0


def file_set(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def run_command(
    command: list[str],
    *,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    python_path = str(ROOT)
    if env.get("PYTHONPATH"):
        python_path = python_path + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = python_path
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise BuildError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{detail}"
        )
    return completed


if __name__ == "__main__":
    raise SystemExit(main())
