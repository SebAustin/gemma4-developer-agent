"""Per-run trace statistics: compaction events, recovery-rule use, malformed edit_file calls.

Usage: python3 -I trace_stats.py <results_dir> [<results_dir> ...]
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

THRESHOLD = 14_336
MALFORMED = "mandatory input parameters are not present"


def _calls(step: dict) -> list[dict]:
    return step.get("tool_calls") or []


def _call_text(call: dict) -> str:
    return json.dumps(call.get("arguments", call), ensure_ascii=False)


def trace_stats(path: Path) -> dict:
    steps = json.loads(path.read_text(encoding="utf-8"))["steps"]
    agent = [s for s in steps if s.get("source") == "agent"]
    compactions, prev = [], None
    for i, s in enumerate(agent, 1):
        pt = (s.get("metrics") or {}).get("prompt_tokens")
        if pt is not None and prev is not None and prev >= THRESHOLD and pt < prev * 0.7:
            compactions.append(i)
        if pt is not None:
            prev = pt
    first = compactions[0] if compactions else None
    recovery_after = False
    malformed = 0
    for i, s in enumerate(agent, 1):
        obs = json.dumps(s.get("observation") or "", ensure_ascii=False)
        malformed += obs.count(MALFORMED)
        if first and i >= first:
            if any("git status --short" in _call_text(c) for c in _calls(s)):
                recovery_after = True
    return {"compactions": compactions, "recovery_after": recovery_after, "malformed": malformed}


def run_stats(results: Path) -> None:
    rows = {json.loads(l)["instance_id"]: json.loads(l) for l in (results / "task_results.jsonl").read_text().splitlines() if l.strip()}
    per = {}
    for tr in sorted((results / "traces").glob("trace_*.json")):
        iid = tr.stem.removeprefix("trace_")
        per[iid] = trace_stats(tr)
    hit = [k for k, v in per.items() if v["compactions"]]
    firsts = [per[k]["compactions"][0] for k in hit]
    resolved = lambda k: bool(rows.get(k, {}).get("resolved"))
    print(f"{results.parent.name}: {len(per)} traces")
    print(f"  compaction fired in {len(hit)}/{len(per)} tasks; median first at agent step "
          f"{statistics.median(firsts) if firsts else '-'}; total events {sum(len(per[k]['compactions']) for k in hit)}")
    print(f"  resolved with compaction {sum(map(resolved, hit))}/{len(hit)}, "
          f"without {sum(resolved(k) for k in per if k not in hit)}/{len(per) - len(hit)}")
    print(f"  ran 'git status --short' after first compaction: {sum(per[k]['recovery_after'] for k in hit)}/{len(hit)}")
    mal = {k: v["malformed"] for k, v in per.items() if v["malformed"]}
    print(f"  malformed edit_file replies: {sum(mal.values())} in {len(mal)} tasks")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        run_stats(Path(arg))
