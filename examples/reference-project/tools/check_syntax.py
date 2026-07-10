"""Validate fixture Python syntax without writing bytecode."""

from __future__ import annotations

import ast
from pathlib import Path


def main() -> int:
    paths = [
        *sorted(Path("reference_app").glob("*.py")),
        *sorted(Path("tests").glob("*.py")),
    ]
    for path in paths:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
