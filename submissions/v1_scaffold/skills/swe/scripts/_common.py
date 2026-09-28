"""Shared helpers for skill scripts (stdlib only; runs on Python 3.12/3.13 in the sandbox).

Skill scripts are materialized into a temporary directory and run with that directory as
cwd, so the repository root must be discovered. In the Docker sandbox it is /workspace; in
the subprocess sandbox it is a host temp dir that the harness puts on sys.path/PYTHONPATH.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

MAX_OUTPUT_CHARS = 4000
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".tox", ".venv", "venv",
             "node_modules", "build", "dist", ".eggs", "site", "htmlcov"}


def find_workspace() -> Path:
    candidates = [os.environ.get("SWE_WORKSPACE", "")]
    candidates += sys.path[:3]
    candidates += os.environ.get("PYTHONPATH", "").split(os.pathsep)
    candidates += [os.environ.get("PWD", ""), "/workspace"]
    for c in candidates:
        if c and (Path(c) / ".git").exists():
            return Path(c).resolve()
    sys.exit("error: could not locate the repository root (/workspace)")


def iter_files(root: Path, suffixes: tuple[str, ...] = (".py",)):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info"))
        for name in sorted(filenames):
            # .adk_exec_*.py is the harness wrapper running this very script (it embeds the query).
            if name.startswith(".adk_exec_"):
                continue
            if not suffixes or name.endswith(suffixes):
                yield Path(dirpath) / name


def is_test_path(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    return (name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"
            or any(p in ("tests", "test", "testing") for p in parts[:-1]))


def emit(lines: list[str], limit: int = MAX_OUTPUT_CHARS) -> None:
    """Print lines, stopping before the output budget is exceeded."""
    used = 0
    for i, line in enumerate(lines):
        if used + len(line) + 1 > limit:
            print(f"... [{len(lines) - i} more lines truncated; narrow the query]")
            return
        print(line)
        used += len(line) + 1
