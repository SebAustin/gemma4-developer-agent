"""Find where a symbol is defined and where it is used.

Usage: symbol.py NAME [--refs N]
NAME may be `func`, `Class`, `Class.method` or a dotted module path suffix.
Prints definitions (file:line, signature, first docstring line) then reference sites grouped
by file (tests listed separately).
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import emit, find_workspace, is_test_path, iter_files  # noqa: E402


def definitions(tree: ast.AST, parts: list[str]):
    """Yield (qualname, node) for defs whose qualified name ends with ``parts``."""
    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = prefix + [child.name]
                if qual[-len(parts):] == parts:
                    yield ".".join(qual), child
                yield from walk(child, qual)
            elif isinstance(child, (ast.Assign, ast.AnnAssign)) and len(parts) == 1:
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                for t in targets:
                    if isinstance(t, ast.Name) and t.id == parts[0]:
                        yield ".".join(prefix + [t.id]), child
    yield from walk(tree, [])


def signature(src_lines: list[str], node: ast.AST) -> str:
    line = src_lines[node.lineno - 1].strip()
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        doc = ast.get_docstring(node)
        end = getattr(node, "end_lineno", node.lineno)
        extra = f"  (lines {node.lineno}-{end})"
        if doc:
            extra += f"  # {doc.strip().splitlines()[0][:100]}"
        return line[:160] + extra
    return line[:160]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--refs", type=int, default=12, help="max files with references to show")
    args = ap.parse_args()

    root = find_workspace()
    parts = [p for p in args.name.split(".") if p]
    leaf = parts[-1]
    word = re.compile(rf"\b{re.escape(leaf)}\b")

    defs, refs, test_refs = [], defaultdict(list), defaultdict(list)
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if leaf not in src:
            continue
        lines = src.splitlines()
        try:
            tree = ast.parse(src)
        except (SyntaxError, ValueError):
            tree = None
        def_lines = set()
        if tree is not None:
            for qual, node in definitions(tree, parts):
                defs.append(f"{rel}:{node.lineno}  {qual}\n    {signature(lines, node)}")
                def_lines.add(node.lineno)
        bucket = test_refs if is_test_path(rel) else refs
        for i, text in enumerate(lines, 1):
            if i not in def_lines and word.search(text):
                bucket[rel].append(f"{i}: {text.strip()[:140]}")

    out = [f"== definitions of {args.name} ({len(defs)})"]
    out += defs[:15] or ["(none found; try a shorter name or grep.py)"]
    for title, bucket in (("references in source", refs), ("references in tests", test_refs)):
        files = sorted(bucket.items(), key=lambda kv: -len(kv[1]))
        out.append(f"== {title} ({sum(len(v) for v in bucket.values())} lines in {len(files)} files)")
        for rel, hits in files[: args.refs]:
            out.append(f"{rel} ({len(hits)})")
            out += [f"    {h}" for h in hits[:3]]
    emit(out)


if __name__ == "__main__":
    main()
