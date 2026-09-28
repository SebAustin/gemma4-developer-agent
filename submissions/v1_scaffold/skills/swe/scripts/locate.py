"""Rank repository source files by relevance to issue text.

Usage: locate.py "<issue text, error message or keywords>" [--tests] [--top N]

BM25 over identifier tokens (whole identifiers plus their snake/camel sub-words), plus
bonuses for files that *define* a symbol named in the query and for path matches.
Issue-template boilerplate, URLs and HTML comments are ignored. Test files are excluded
unless --tests is given.
"""

from __future__ import annotations

import argparse
import ast
import math
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import emit, find_workspace, is_test_path, iter_files  # noqa: E402

STOPWORDS = set("""
a an and are as at be but by can could do does did for from has have had how i if in into is it its
not of on or should so that the their them then there these this those to was we were when which
while will with would you your our us my me also just only very more most some any all each other
such than too via per may might must shall about after before again against between both during
out over under up down off own same few nor now here where why what who whom
bug issue error errors fix fixes fixed fixing add adds added adding support supports use uses used
using new none true false self cls return returns value values example examples code python version
expected actual behavior behaviour work works working like want make makes made case cases way
problem problems thing things currently current instead because since however still see note
pull request discussion discussions github team member members please start typo typos obvious
link linked open create created related continuation comment comments thanks thank feature
description docs doc documentation test tests testing https http www com org html md
""".split())
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
DOTTED_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
NOISE_RE = re.compile(r"<!--.*?-->|https?://\S+|\[[^\]]*\]\([^)]*\)|#\d+", re.S)
CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
K1, B = 1.2, 0.75
AUX_DIRS = ("scripts/", "docs/", "docs_src/", "examples/", "benchmarks/", "tools/")


def subwords(ident: str) -> list[str]:
    out = []
    for part in ident.split("_"):
        out += [w.lower() for w in CAMEL_RE.findall(part)]
    return out


def tokenize(text: str) -> Counter:
    counts: Counter = Counter()
    for ident in IDENT_RE.findall(text):
        low = ident.lower()
        counts[low] += 1
        subs = subwords(ident)
        if len(subs) > 1:
            counts.update(subs)
    return counts


def query_terms(text: str) -> tuple[Counter, set[str]]:
    """Return weighted query tokens and the set of code-like identifiers (for def matching)."""
    text = NOISE_RE.sub(" ", text)
    weights: Counter = Counter()
    code_idents: set[str] = set()
    for dotted in DOTTED_RE.findall(text):
        code_idents.update(p.lower() for p in dotted.split("."))
    for ident in IDENT_RE.findall(text):
        low = ident.lower()
        is_code = "_" in ident or any(c.isupper() for c in ident[1:]) or low in code_idents
        if len(low) >= 3 and low not in STOPWORDS:
            weights[low] = max(weights[low], 2.0 if is_code else 1.0)
            if is_code:
                code_idents.add(low)
        for sw in subwords(ident):
            if len(sw) >= 3 and sw not in STOPWORDS:
                weights[sw] = max(weights[sw], 0.7)
    for m in re.findall(r"`([^`\n]{2,60})`", text):  # inline code is a strong signal
        for ident in IDENT_RE.findall(m):
            low = ident.lower()
            if len(low) >= 3 and low not in STOPWORDS:
                weights[low] = 2.5
                code_idents.add(low)
    return weights, code_idents


def defined_symbols(src: str) -> dict[str, int]:
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return {}
    out: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.setdefault(node.name.lower(), node.lineno)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="+")
    ap.add_argument("--tests", action="store_true", help="include test files")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()

    root = find_workspace()
    query = " ".join(args.text)
    weights, code_idents = query_terms(query)
    if not weights:
        sys.exit("error: no usable identifiers or keywords in the query")
    mentioned_paths = set(re.findall(r"[\w./-]+\.py", query))

    docs = []
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        if not args.tests and is_test_path(rel):
            continue
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        docs.append((rel, tokenize(src), defined_symbols(src)))
    if not docs:
        sys.exit("error: no Python files found")

    n = len(docs)
    avg_len = sum(sum(tf.values()) for _, tf, _ in docs) / n
    df = Counter()
    for _, tf, _ in docs:
        df.update(t for t in weights if t in tf)
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in weights}

    ranked = []
    for rel, tf, syms in docs:
        length = sum(tf.values()) or 1
        score, hits = 0.0, []
        path_tokens = set(subwords(rel.replace("/", "_").replace(".", "_"))) | set(re.split(r"[/_.]", rel.lower()))
        for t, w in weights.items():
            f = tf.get(t, 0)
            if f:
                score += w * idf[t] * f * (K1 + 1) / (f + K1 * (1 - B + B * length / avg_len))
            if t in syms and t in code_idents:
                score += 2.5 * w * idf[t]
                hits.append(f"def {t}@{syms[t]}")
            if t in path_tokens:
                score += 1.5 * w * idf[t]
        if any(rel.endswith(p.lstrip("./")) for p in mentioned_paths):
            score += 50
        if rel.startswith(AUX_DIRS) and not any(rel.startswith(p) for p in mentioned_paths):
            score *= 0.6
        if score > 0:
            ranked.append((score, rel, hits))
    ranked.sort(key=lambda r: (-r[0], r[1]))

    top_terms = sorted(weights, key=lambda t: -weights[t] * idf[t])[:20]
    lines = [f"query terms: {', '.join(top_terms)}", ""]
    for score, rel, hits in ranked[: args.top]:
        defs = f"  [{'; '.join(hits[:5])}]" if hits else ""
        lines.append(f"{score:7.1f}  {rel}{defs}")
    if not ranked:
        lines.append("no matching files; try other keywords or grep.py")
    emit(lines)


if __name__ == "__main__":
    main()
