"""Offline localization benchmark for the `locate.py` skill script (no GPU needed).

For each task: extract its snapshot, run locate.py on the problem statement through the real
skill wrapper, and check where the gold source files (non-test files in the reference patch)
rank. Reports Hit@1/3/5/10 and MRR, overall and per repo.
"""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import defaultdict
from pathlib import Path

from .skill_runner import run_skill_script
from .splits import load_tasks

ROOT = Path(__file__).resolve().parents[2]
TEST_RE = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")


def gold_files(patch: str) -> list[str]:
    files = re.findall(r"^\+\+\+ b/(\S+)", patch, re.M)
    return [f for f in files if f.endswith(".py") and not TEST_RE.search(f)]


def extract_snapshot(snapshots: Path, instance_id: str, cache: Path) -> Path:
    dest = cache / instance_id
    if not dest.exists():
        dest.mkdir(parents=True)
        with tarfile.open(snapshots / f"{instance_id}.tgz") as tf:
            tf.extractall(dest, filter="data")
    gits = sorted(dest.rglob(".git"), key=lambda p: len(p.parts))
    if not gits:
        raise RuntimeError(f"{instance_id}: snapshot has no .git directory")
    return gits[0].parent


def ranked_files(stdout: str) -> list[str]:
    out = []
    for line in stdout.splitlines():
        m = re.match(r"^\s*[\d.]+\s+(\S+\.py)", line)
        if m:
            out.append(m.group(1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", default=str(ROOT / "submissions" / "v1_scaffold"))
    ap.add_argument("--split", default="full")
    ap.add_argument("--data", default=str(ROOT / "data"))
    ap.add_argument("--cache", default=str(ROOT / "data" / "extracted"))
    ap.add_argument("--out", default=None, help="optional JSONL with per-task ranks")
    args = ap.parse_args()

    data = Path(args.data)
    split = set(json.loads((ROOT / "experiments" / "splits.json").read_text())[args.split])
    tasks = [t for t in load_tasks(data / "tasks.jsonl") if t["instance_id"] in split]
    skill = Path(args.bundle) / "skills" / "swe"
    rows, per_repo = [], defaultdict(list)
    for t in tasks:
        gold = gold_files(t["patch"])
        if not gold:
            continue
        repo_dir = extract_snapshot(data / "snapshots", t["instance_id"], Path(args.cache))
        res = run_skill_script(skill, "scripts/locate.py", [t["problem_statement"], "--top", "10"], repo_dir)
        ranks = ranked_files(res.stdout)
        best = min((ranks.index(g) + 1 for g in gold if g in ranks), default=None)
        row = {"instance_id": t["instance_id"], "repo": t["repo"], "rank": best, "gold": gold, "top3": ranks[:3]}
        rows.append(row)
        per_repo[t["repo"]].append(best)
        print(f"{t['instance_id']:22s} rank={best}  gold={gold[:2]}  top1={ranks[:1]}")

    def summary(ranks: list[int | None]) -> str:
        n = len(ranks) or 1
        hit = lambda k: sum(1 for r in ranks if r is not None and r <= k) / n  # noqa: E731
        mrr = sum(1 / r for r in ranks if r) / n
        return f"n={len(ranks):3d}  hit@1={hit(1):.2f}  hit@3={hit(3):.2f}  hit@5={hit(5):.2f}  hit@10={hit(10):.2f}  mrr={mrr:.3f}"

    print("\nALL      ", summary([r["rank"] for r in rows]))
    for repo, ranks in sorted(per_repo.items()):
        print(f"{repo:9s}", summary(ranks))
    if args.out:
        Path(args.out).write_text("".join(json.dumps(r) + "\n" for r in rows))


if __name__ == "__main__":
    main()
