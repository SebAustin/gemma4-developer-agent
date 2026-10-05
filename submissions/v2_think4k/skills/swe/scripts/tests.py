"""Find and run the tests relevant to a change (never the whole suite).

Usage: tests.py find TARGET          TARGET = source file path, module or symbol name
       tests.py run  TEST [TEST ...] [-k EXPR] [--timeout SECONDS]
`run` takes test files or node ids (tests/test_x.py::test_y) and prints a compact summary:
the pass/fail line plus the shortest useful traceback of each failure.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import PurePosixPath

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import emit, find_workspace, is_test_path, iter_files  # noqa: E402

FAILURE_BUDGET = 3000


def find(root, target: str) -> None:
    target = target.removeprefix("/workspace/").lstrip("/")
    stem = PurePosixPath(target).stem if target.endswith(".py") else target.split(".")[-1]
    module = target[:-3].replace("/", ".") if target.endswith(".py") else target
    word = re.compile(rf"\b{re.escape(stem)}\b")
    ranked = []
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        if not is_test_path(rel) or not PurePosixPath(rel).name.startswith(("test", "conftest")) and not rel.endswith("_test.py"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        score = 10 * (stem.lower() in PurePosixPath(rel).stem.lower())
        score += 5 * (module in text) + min(20, len(word.findall(text)))
        if score:
            ranked.append((score, rel))
    ranked.sort(key=lambda r: (-r[0], r[1]))
    lines = [f"{s:4d}  {rel}" for s, rel in ranked[:15]] or [f"no tests reference {stem}"]
    emit([f"tests related to {target} (score, file):", *lines])


def summarize(output: str) -> list[str]:
    lines = output.splitlines()
    summary = [ln for ln in lines
               if re.match(r"^=*\s*(\d+ (passed|failed|errors?|skipped|xfailed|xpassed|deselected)|no tests ran)"
                           r".* in [\d.]+s.*$", ln)]
    failed = [ln for ln in lines if ln.startswith(("FAILED ", "ERROR "))]
    out = summary[-1:] or ["(no pytest summary line; raw tail below)"]
    out += failed[:15]
    if "= FAILURES =" in output or "= ERRORS =" in output:
        start = min(i for i in (output.find("= FAILURES ="), output.find("= ERRORS =")) if i >= 0)
        section = output[start:]
        end = section.find("short test summary info")
        section = section[: end if end > 0 else None]
        if len(section) > FAILURE_BUDGET:
            section = section[:FAILURE_BUDGET // 2] + "\n...[snip]...\n" + section[-FAILURE_BUDGET // 2:]
        out += ["", section.rstrip()]
    elif not summary:
        out += lines[-40:]
    return out


def run(root, targets: list[str], k: str | None, timeout: int) -> None:
    targets = [t.removeprefix("/workspace/").lstrip("/") for t in targets]
    if not targets or any(t in (".", "", "tests", "test") for t in targets):
        sys.exit("error: give specific test files or node ids; running the whole suite is too slow")
    cmd = [sys.executable, "-m", "pytest", *targets, "-q", "--tb=short", "-p", "no:cacheprovider",
           "--no-header", "-rfE"]
    if k:
        cmd += ["-k", k]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        sys.exit(f"error: tests exceeded {timeout}s; run fewer tests (use -k or a node id)")
    emit([f"$ pytest {' '.join(targets)}" + (f" -k '{k}'" if k else "") + f"  (exit {proc.returncode})",
          *summarize(proc.stdout + proc.stderr)], limit=6000)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find")
    f.add_argument("target")
    r = sub.add_parser("run")
    r.add_argument("targets", nargs="+")
    r.add_argument("-k")
    r.add_argument("--timeout", type=int, default=240)
    args = ap.parse_args()
    root = find_workspace()
    if args.cmd == "find":
        find(root, args.target)
    else:
        run(root, args.targets, args.k, args.timeout)


if __name__ == "__main__":
    main()
