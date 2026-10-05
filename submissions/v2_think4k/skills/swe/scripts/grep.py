"""Regex search over the repository, grouped by file (ripgrep is not installed).

Usage: grep.py PATTERN [--path SUBDIR] [--all-files] [-i] [--fixed] [--no-tests]
Searches .py files by default (--all-files for every text file). Skips .git and caches.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import emit, find_workspace, is_test_path, iter_files  # noqa: E402

TEXT_SUFFIXES = (".py", ".pyi", ".md", ".rst", ".txt", ".toml", ".cfg", ".ini", ".yaml", ".yml", ".json", ".html")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pattern")
    ap.add_argument("--path", default="")
    ap.add_argument("--all-files", action="store_true")
    ap.add_argument("-i", "--ignore-case", action="store_true")
    ap.add_argument("--fixed", action="store_true", help="treat PATTERN as a literal string")
    ap.add_argument("--no-tests", action="store_true")
    args = ap.parse_args()

    root = find_workspace()
    base = (root / args.path.removeprefix("/workspace/").lstrip("/")).resolve()
    if not base.exists():
        sys.exit(f"error: path {args.path} not found")
    pattern = re.escape(args.pattern) if args.fixed else args.pattern
    try:
        rx = re.compile(pattern, re.IGNORECASE if args.ignore_case else 0)
    except re.error as e:
        sys.exit(f"error: bad regex ({e}); use --fixed for literal text")

    files = [base] if base.is_file() else iter_files(base, TEXT_SUFFIXES if args.all_files else (".py",))
    out, n_hits, n_files = [], 0, 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        if args.no_tests and is_test_path(rel):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits = [(i, ln) for i, ln in enumerate(text.splitlines(), 1) if rx.search(ln)]
        if hits:
            n_files += 1
            n_hits += len(hits)
            out.append(f"{rel} ({len(hits)})")
            out += [f"  {i}: {ln.strip()[:160]}" for i, ln in hits[:8]]
            if len(hits) > 8:
                out.append(f"  ... {len(hits) - 8} more in this file")
    emit([f"{n_hits} matches in {n_files} files", *out] if out else ["no matches"])


if __name__ == "__main__":
    main()
