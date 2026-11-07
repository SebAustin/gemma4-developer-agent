"""End-to-end harness check on local Docker with the scripted oracle model (no GPU).

Usage: python -m g4agent.oracle_run --bundle submissions/v1_scaffold --split smoke5 [--plan empty]
Writes the harness's normal artifacts under results/oracle-<bundle>-<split>/ (or
results/empty-<bundle>-<split>/ for --plan empty, which submits without edits); tool calls and
their (truncated) responses are in logs/<id>.log.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .local_env import activate, build_task_wheels
from .scripted_model import PLANS, ScriptedLlm

ROOT = Path(__file__).resolve().parents[2]
MODEL = "gemma-4-31b-it-qat-w4a16-ct"


def local_wheels(data: Path, instance_id: str) -> Path:
    """Per-task wheel set: public wheels + missing test deps, filtered to the snapshot's pins,
    without the repo's own package (see g4agent.local_env and docs/HARNESS_NOTES.md)."""
    merged = data / "wheels_local"
    source = merged if merged.is_dir() else data / "wheels"
    wheels = build_task_wheels(data / "snapshots" / f"{instance_id}.tgz", source, data / "wheels_task")
    activate(wheels)
    return wheels


async def run_one(task, bundle: Path, results: Path, data: Path, plan: str = "oracle"):
    from adk_submission import ModelRegistry
    from swegemma.config import EvalConfig, build_submission_limits
    from swegemma.evaluate import Evaluator

    model = ScriptedLlm(model=MODEL, plan=PLANS[plan](task), step=0)
    models = ModelRegistry()
    models.register(MODEL, model)
    limits, gen_constraints = build_submission_limits()
    config = EvalConfig(
        tasks_path=data / "tasks.jsonl", snapshots_dir=data / "snapshots", results_dir=results,
        submission_dir=bundle, models=models, sandbox="docker", wheels_dir=local_wheels(data, task.instance_id),
        graph_dir=str(data / "graphs"), embeddings_dir=str(data / "embeddings"),
        timeout_seconds=300, max_time_minutes=15, max_tool_calls=40, max_turns=30,
        limits=limits, generation_constraints=gen_constraints, task_ids=[task.instance_id],
        display_mode="quiet",
    )
    result = await Evaluator(config).run()
    return result.task_results[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", default=str(ROOT / "submissions" / "v1_scaffold"))
    ap.add_argument("--split", default="smoke5")
    ap.add_argument("--data", default=str(ROOT / "data"))
    ap.add_argument("--plan", choices=sorted(PLANS), default="oracle")
    args = ap.parse_args()

    from swegemma.models import load_tasks

    bundle, data = Path(args.bundle).resolve(), Path(args.data)
    ids = set(json.loads((ROOT / "experiments" / "splits.json").read_text())[args.split])
    tasks = [t for t in load_tasks(data / "tasks.jsonl") if t.instance_id in ids]
    results = ROOT / "results" / f"{args.plan}-{bundle.name}-{args.split}"
    resolved = 0
    log = results / "oracle_results.jsonl"
    results.mkdir(parents=True, exist_ok=True)
    for t in tasks:
        r = asyncio.run(run_one(t, bundle, results, data, args.plan))
        resolved += bool(r.resolved)
        with log.open("a") as f:
            f.write(json.dumps({"instance_id": t.instance_id, "resolved": bool(r.resolved),
                                "error": r.error}) + "\n")
        print(f"{t.instance_id:22s} resolved={r.resolved} tool_calls={r.tool_calls} "
              f"err={(r.error or '')[:120]}", flush=True)
    print(f"\n{args.plan} plan resolved {resolved}/{len(tasks)}")


if __name__ == "__main__":
    main()
