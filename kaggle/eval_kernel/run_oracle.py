"""CPU-only Kaggle kernel: measure the reference-fix ceiling of the Kaggle notebook environment.

A scripted model applies each task's gold patch through the real harness (subprocess sandbox,
Kaggle host packages) and Phase-2 verification grades it. Tasks that fail here cannot be solved
by any agent in Kaggle dev runs, so dev scores are reported against this ceiling.
Rendered by `g4 oracle-kernel`; outputs /kaggle/working/oracle_results.jsonl.
"""

import asyncio
import base64
import glob
import importlib
import io
import json
import subprocess
import sys
import types as _types
import zipfile
from pathlib import Path

BUNDLE_ZIP_B64 = "__G4_BUNDLE_B64__"
TASK_IDS = json.loads("""__G4_TASK_IDS__""")
SCRIPTED_MODEL_SRC = base64.b64decode("__G4_SCRIPTED_MODEL_B64__").decode()

DATA_DIR = Path("/kaggle/input/competitions/gemma-4-developer-agent")
WORKING_DIR = Path("/kaggle/working")
AGENT_DIR = WORKING_DIR / "bundle"
MODEL = "gemma-4-31b-it-qat-w4a16-ct"
HARNESS_WHEELS = ("swegemma", "adk_submission", "adk_eval_core", "google_adk", "google_genai")


def install_harness() -> None:
    hits = glob.glob("/kaggle/input/**/gemma-4-developer-agent-wheelhouse", recursive=True)
    wheels = [w for d in hits for w in glob.glob(f"{d}/*.whl") if Path(w).name.startswith(HARNESS_WHEELS)]
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "--force-reinstall", *wheels],
                   check=True)
    importlib.invalidate_caches()


def main() -> None:
    global DATA_DIR
    install_harness()
    if not (DATA_DIR / "tasks.jsonl").exists():
        hits = sorted(glob.glob("/kaggle/input/**/tasks.jsonl", recursive=True), key=len)
        if not hits:
            raise FileNotFoundError("tasks.jsonl not found under /kaggle/input")
        DATA_DIR = Path(hits[0]).parent
    AGENT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(BUNDLE_ZIP_B64))) as zf:
        zf.extractall(AGENT_DIR)
    scripted = _types.ModuleType("scripted_model")
    exec(SCRIPTED_MODEL_SRC, scripted.__dict__)

    from adk_submission import ModelRegistry
    from swegemma.config import EvalConfig, build_submission_limits
    from swegemma.evaluate import Evaluator
    from swegemma.models import load_tasks

    tasks = [t for t in load_tasks(DATA_DIR / "tasks.jsonl") if t.instance_id in set(TASK_IDS)]
    limits, gen = build_submission_limits()
    out = WORKING_DIR / "oracle_results.jsonl"
    for t in tasks:
        models = ModelRegistry()
        models.register(MODEL, scripted.ScriptedLlm(model=MODEL, plan=scripted.oracle_plan(t), step=0))
        config = EvalConfig(
            tasks_path=DATA_DIR / "tasks.jsonl", snapshots_dir=DATA_DIR / "snapshots",
            results_dir=WORKING_DIR / "results", submission_dir=AGENT_DIR, models=models,
            sandbox="subprocess", wheels_dir=DATA_DIR / "wheels",
            graph_dir=str(DATA_DIR / "graphs"), embeddings_dir=str(DATA_DIR / "embeddings"),
            timeout_seconds=300, max_time_minutes=15, max_tool_calls=40, max_turns=30,
            limits=limits, generation_constraints=gen, task_ids=[t.instance_id], display_mode="quiet",
        )
        r = asyncio.run(Evaluator(config).run()).task_results[0]
        row = {"instance_id": t.instance_id, "resolved": bool(r.resolved), "error": (r.error or "")[:300]}
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(row, flush=True)
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    print(f"oracle ceiling: {sum(r['resolved'] for r in rows)}/{len(rows)}")


if __name__ == "__main__":
    main()
