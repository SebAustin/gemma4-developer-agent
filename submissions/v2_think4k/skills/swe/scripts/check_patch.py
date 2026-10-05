"""Pre-submit gate: inspect the working-tree diff exactly as submit_patch will capture it.

Usage: check_patch.py [--full]

Reports: changed files, problems that make the graded patch fail or get discarded
(syntax errors, edits to tests/configs that the grader reverts, scratch files that leak into
the patch, empty diff) and a compact diff. Exit status 1 when a blocking problem exists.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import emit, find_workspace, is_test_path  # noqa: E402

PROTECTED = {"conftest.py", "pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg", ".pytest.ini",
             "sitecustomize.py", "usercustomize.py", "_swegemma_stubs.py"}
SCRATCH_HINTS = ("repro", "reproduce", "scratch", "debug", "tmp", "temp", "check_", "verify", "demo")


def git(root, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True).stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="show the whole diff (default: first 3000 chars)")
    args = ap.parse_args()
    root = find_workspace()

    base = "_swegemma_baseline" if git(root, "rev-parse", "--verify", "-q", "_swegemma_baseline").strip() else "HEAD"
    # .adk_exec_*.py is the harness wrapper that is running this script; it is removed afterwards.
    untracked = [p for p in git(root, "ls-files", "--others", "--exclude-standard").splitlines()
                 if p and not p.rsplit("/", 1)[-1].startswith(".adk_exec_")]
    changed = [p for p in git(root, "diff", "--name-only", base).splitlines() if p]
    files = sorted(set(changed) | set(untracked))

    blocking, warnings = [], []
    if not files:
        blocking.append("EMPTY PATCH: no source changes yet. Every task needs a code change.")
    for rel in files:
        name = rel.rsplit("/", 1)[-1]
        path = root / rel
        if name in PROTECTED:
            warnings.append(f"{rel}: test/config file is RESET by the grader; your change here is discarded. "
                            f"Revert it: git checkout {base} -- {rel}")
        elif is_test_path(rel):
            warnings.append(f"{rel}: test files are reset/ignored by the grader (fine for your own checks, "
                            "but the fix must live in source files)")
        elif rel in untracked and any(h in name.lower() for h in SCRATCH_HINTS):
            blocking.append(f"{rel}: looks like a scratch file and WILL be included in the patch. "
                            f"Delete it (rm {rel}) or keep scratch files under /tmp.")
        elif rel in untracked and "/" not in rel:
            warnings.append(f"{rel}: new file at the repository root will be in the patch; "
                            f"delete it (rm {rel}) unless the fix needs it")
        if rel.endswith(".py") and path.is_file():
            try:
                compile(path.read_text(encoding="utf-8", errors="replace"), rel, "exec")
            except SyntaxError as e:
                blocking.append(f"{rel}:{e.lineno}: SYNTAX ERROR: {e.msg}")
        if not path.exists() and rel in changed:
            warnings.append(f"{rel}: file deleted; make sure that is intended")

    stat = git(root, "diff", "--stat", base).strip()
    diff = git(root, "diff", base)
    for rel in untracked:
        diff += f"\n+++ new file: {rel}\n" + (root / rel).read_text(encoding="utf-8", errors="replace")[:1500]
    limit = 20000 if args.full else 3000
    out = [f"files in patch: {len(files)}"] + [f"  {f}{' (new)' if f in untracked else ''}" for f in files]
    out += [f"BLOCKING: {b}" for b in blocking] + [f"WARNING: {w}" for w in warnings]
    if not blocking:
        out.append("OK: no blocking problems. If your targeted tests pass, call submit_patch.")
    out += ["", stat, "", diff[:limit] + ("\n...[diff truncated; use --full]" if len(diff) > limit else "")]
    emit(out, limit=limit + 3000)
    sys.exit(1 if blocking else 0)


if __name__ == "__main__":
    main()
