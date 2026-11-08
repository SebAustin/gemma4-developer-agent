"""Per-run budget statistics: time, call-cap hits, token use per model call.

Usage: python3 -I scripts/budget_stats.py <call cap> <results_dir> [<call cap> <results_dir> ...]
"""
import json, statistics as st, sys
from pathlib import Path

TASKS_LB = 120

def run(cap: int, d: Path) -> None:
    rows = [json.loads(l) for l in (d / "task_results.jsonl").read_text().splitlines() if l.strip()]
    dur = [r["duration_seconds"] for r in rows]
    capped = [r for r in rows if (r.get("tool_calls") or 0) >= cap]
    slow = [r for r in rows if r["duration_seconds"] >= 480]
    comp, prompt, ncalls = [], [], []
    for tr in (d / "traces").glob("trace_*.json"):
        steps = [s for s in json.loads(tr.read_text())["steps"] if s.get("source") == "agent"]
        ncalls.append(len(steps))
        for s in steps:
            m = s.get("metrics") or {}
            if m.get("completion_tokens") is not None:
                comp.append(m["completion_tokens"])
            if m.get("prompt_tokens") is not None:
                prompt.append(m["prompt_tokens"])
    print(f"{d.parent.name}")
    print(f"  resolved {sum(r['resolved'] for r in rows)}/{len(rows)} | sum {sum(dur)/3600:.2f} h, mean {st.mean(dur):.0f} s, median {st.median(dur):.0f} s, max {max(dur):.0f} s"
          f" | 120-task projection {TASKS_LB*st.mean(dur)/3600:.1f} h")
    print(f"  used all {cap} calls: {len(capped)} ({sum(r['resolved'] for r in capped)} resolved) | >= 8 min: {len(slow)} ({sum(r['resolved'] for r in slow)} resolved)")
    print(f"  model steps/task median {st.median(ncalls):.0f} | completion tokens/step median {st.median(comp):.0f}, mean {st.mean(comp):.0f}, total {sum(comp)/1e6:.2f} M"
          f" | prompt tokens/step median {st.median(prompt):.0f}")

args = sys.argv[1:]
for cap, d in zip(args[::2], args[1::2]):
    run(int(cap), Path(d))
