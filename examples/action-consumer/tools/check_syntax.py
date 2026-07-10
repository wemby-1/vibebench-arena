#!/usr/bin/env python3
"""Compile the demonstration package without writing bytecode."""

from __future__ import annotations

import py_compile
from pathlib import Path

for path in sorted(Path("consumer_app").rglob("*.py")):
    py_compile.compile(str(path), doraise=True)
