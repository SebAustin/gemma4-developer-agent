"""Show the structure of a Python file, or the numbered source of one symbol in it.

Usage: outline.py FILE              -> classes/functions with line ranges
       outline.py FILE --symbol X   -> source of X (e.g. `Console.print`) with line numbers
"""

from __future__ import annotations

import argparse
import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import emit, find_workspace  # noqa: E402

MAX_SYMBOL_LINES = 200


def walk(node, depth, prefix, out):
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = "class" if isinstance(child, ast.ClassDef) else "def"
            qual = f"{prefix}{child.name}"
            out.append((depth, kind, qual, child.lineno, child.end_lineno, child))
            walk(child, depth + 1, qual + ".", out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--symbol")
    args = ap.parse_args()

    root = find_workspace()
    rel = args.file.removeprefix("/workspace/").lstrip("/")
    path = root / rel
    if not path.is_file():
        sys.exit(f"error: {rel} not found under the repository root")
    src = path.read_text(encoding="utf-8", errors="replace")
    lines = src.splitlines()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        sys.exit(f"error: {rel} does not parse: line {e.lineno}: {e.msg}")
    items: list = []
    walk(tree, 0, "", items)

    if args.symbol:
        matches = [it for it in items if it[2] == args.symbol or it[2].endswith("." + args.symbol)]
        if not matches:
            sys.exit(f"error: {args.symbol} not defined in {rel}; run without --symbol to list symbols")
        _, _, qual, start, end, node = matches[0]
        first = min([d.lineno for d in getattr(node, "decorator_list", [])] + [start])
        last = min(end, first + MAX_SYMBOL_LINES - 1)
        out = [f"{rel}:{first}-{end}  {qual}" + (f"  (showing first {MAX_SYMBOL_LINES} lines)" if last < end else "")]
        out += [f"{i:5d}  {lines[i - 1]}" for i in range(first, last + 1)]
        emit(out, limit=12000)
        return

    out = [f"{rel}  ({len(lines)} lines)"]
    out += [f"{'  ' * d}{kind} {qual}  L{s}-{e}" for d, kind, qual, s, e, _ in items]
    emit(out, limit=6000)


if __name__ == "__main__":
    main()
