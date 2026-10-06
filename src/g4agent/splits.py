"""Deterministic, stratified dev splits over the public training tasks.

Kaggle GPU hours are scarce, so iteration runs on a small split. To keep scores comparable
across experiments, the splits are frozen in ``experiments/splits.json`` and never regenerated
silently (``write_splits`` refuses to overwrite a different split).
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

SPLIT_SIZES = {"smoke5": 5, "dev30": 30}
SOUND_SIZE = 40
SIZE_BUCKETS = ((5, "xs"), (20, "s"), (80, "m"), (10**9, "l"))


def load_tasks(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def patch_churn(patch: str) -> int:
    return sum(
        1 for line in patch.splitlines()
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    )


def size_bucket(churn: int) -> str:
    return next(name for limit, name in SIZE_BUCKETS if churn <= limit)


def _stable_key(instance_id: str) -> str:
    return hashlib.sha256(instance_id.encode()).hexdigest()


def stratified_sample(tasks: list[dict], n: int) -> list[str]:
    """Pick ``n`` tasks proportionally across (repo, size bucket) strata.

    Uses largest-remainder apportionment and a hash order inside each stratum, so the
    result depends only on the task set, not on file order or a RNG.
    """
    strata: dict[tuple[str, str], list[str]] = defaultdict(list)
    for t in tasks:
        strata[(t["repo"], size_bucket(patch_churn(t.get("patch", ""))))].append(t["instance_id"])
    for ids in strata.values():
        ids.sort(key=_stable_key)

    total = len(tasks)
    quotas = {k: n * len(v) / total for k, v in strata.items()}
    alloc = {k: int(q) for k, q in quotas.items()}
    leftover = n - sum(alloc.values())
    by_remainder = sorted(quotas, key=lambda k: (quotas[k] - alloc[k], k), reverse=True)
    for k in by_remainder[:leftover]:
        alloc[k] += 1
    picked = [i for k, ids in sorted(strata.items()) for i in ids[: alloc[k]]]
    return sorted(picked)


def make_splits(tasks: list[dict], resolvable: set[str] | None = None) -> dict[str, list[str]]:
    splits = {name: stratified_sample(tasks, size) for name, size in SPLIT_SIZES.items()}
    if resolvable is not None:
        # Sound tasks: the reference fix resolves them in the Kaggle env, so a miss is the agent's.
        splits["sound40"] = stratified_sample([t for t in tasks if t["instance_id"] in resolvable], SOUND_SIZE)
    splits["full"] = sorted(t["instance_id"] for t in tasks)
    # Repo-held-out split for measuring generalization to unseen repos (the test set is
    # drawn from private repos): train on everything except rich, evaluate on rich.
    splits["holdout_rich"] = sorted(t["instance_id"] for t in tasks if t["repo"] == "Textualize/rich")
    return splits


def write_splits(tasks_path: str | Path, out_path: str | Path, *, oracle_path: str | Path | None = None,
                 force: bool = False) -> dict[str, list[str]]:
    """Write the splits; new split names may be added, existing ones must not change."""
    resolvable = None
    if oracle_path is not None:
        oracle = json.loads(Path(oracle_path).read_text(encoding="utf-8"))
        if "resolvable" not in oracle:
            raise ValueError(f"{oracle_path} has no 'resolvable' list (expected an oracle kernel result)")
        resolvable = set(oracle["resolvable"])
    splits = make_splits(load_tasks(tasks_path), resolvable)
    out = Path(out_path)
    if out.exists() and not force:
        existing = json.loads(out.read_text(encoding="utf-8"))
        changed = [k for k in existing if k in splits and existing[k] != splits[k]]
        if changed:
            raise RuntimeError(f"{out} already holds different splits ({', '.join(changed)}); pass "
                               "force=True to replace them (this invalidates comparisons with earlier experiments)")
        splits = {**existing, **splits}
        if splits == existing:
            return existing
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(splits, indent=1) + "\n", encoding="utf-8")
    return splits
