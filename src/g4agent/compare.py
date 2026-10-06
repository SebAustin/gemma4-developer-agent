"""Paired comparison of two eval runs on the same tasks.

The leaderboard moves by about ±0.06 between identical submissions, so variants are compared
on dev runs, task by task. Only discordant tasks (resolved by one run, not the other) carry
information; the exact McNemar test is a two-sided binomial test on them.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from dataclasses import dataclass, field
from math import comb
from pathlib import Path

ERROR_LABEL_CHARS = 45
TOP_ERRORS = 3


def load_results(run: str | Path) -> list[dict]:
    """Rows of ``task_results.jsonl`` from a run directory (searched recursively) or the file itself."""
    run = Path(run)
    path = run if run.is_file() else next(iter(sorted(run.rglob("task_results.jsonl"))), None)
    if path is None:
        raise FileNotFoundError(f"no task_results.jsonl under {run}")
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def mcnemar_exact(a_wins: int, b_wins: int) -> float:
    n = a_wins + b_wins
    if n == 0:
        return 1.0
    tail = sum(comb(n, k) for k in range(min(a_wins, b_wins) + 1)) / 2**n
    return min(1.0, 2 * tail)


@dataclass(frozen=True)
class Comparison:
    both: list[str]
    a_only: list[str]
    b_only: list[str]
    neither: list[str]
    unpaired: list[str]
    a_rows: dict[str, dict] = field(repr=False)
    b_rows: dict[str, dict] = field(repr=False)

    @property
    def p_value(self) -> float:
        return mcnemar_exact(len(self.a_only), len(self.b_only))

    def format(self, name_a: str = "A", name_b: str = "B") -> str:
        n = len(self.both) + len(self.a_only) + len(self.b_only) + len(self.neither)
        lines = [
            f"paired tasks: {n} (unpaired: {len(self.unpaired)})",
            f"resolved: {name_a} {len(self.both) + len(self.a_only)}/{n}, {name_b} {len(self.both) + len(self.b_only)}/{n}",
            f"both {len(self.both)} | {name_a} only {len(self.a_only)} | {name_b} only {len(self.b_only)} | "
            f"neither {len(self.neither)} | exact McNemar p = {self.p_value:.3f}",
        ]
        for label, ids in ((f"{name_a} only", self.a_only), (f"{name_b} only", self.b_only)):
            if ids:
                lines.append(f"  {label}: {', '.join(ids)}")
        if n == 0:
            return "\n".join(lines)
        for name, rows in ((name_a, self.a_rows), (name_b, self.b_rows)):
            paired = [rows[i] for i in self.both + self.a_only + self.b_only + self.neither]
            errors = Counter((r.get("error") or "none")[:ERROR_LABEL_CHARS] for r in paired).most_common(TOP_ERRORS)
            lines.append(f"  {name}: median {statistics.median(r.get('duration_seconds') or 0 for r in paired):.0f} s, "
                         f"median {statistics.median(r.get('tool_calls') or 0 for r in paired):.0f} calls, "
                         f"errors {errors}")
        return "\n".join(lines)


def compare_runs(a: list[dict], b: list[dict]) -> Comparison:
    a_rows = {r["instance_id"]: r for r in a}
    b_rows = {r["instance_id"]: r for r in b}
    paired = sorted(a_rows.keys() & b_rows.keys())
    buckets: dict[tuple[bool, bool], list[str]] = {(x, y): [] for x in (True, False) for y in (True, False)}
    for i in paired:
        buckets[(bool(a_rows[i].get("resolved")), bool(b_rows[i].get("resolved")))].append(i)
    return Comparison(
        both=buckets[(True, True)], a_only=buckets[(True, False)], b_only=buckets[(False, True)],
        neither=buckets[(False, False)], unpaired=sorted(a_rows.keys() ^ b_rows.keys()),
        a_rows=a_rows, b_rows=b_rows,
    )
