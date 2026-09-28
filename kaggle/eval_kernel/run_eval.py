"""Kaggle eval kernel: run a submission bundle on a fixed task split with the official harness.

Rendered by `g4 kernel` (src/g4agent/kaggle_ops.py), which replaces the __G4_*__ placeholders.
Mirrors the official "Getting Started" notebook (wheelhouse install -> VllmServer -> Evaluator),
with vLLM settings matching the scorer (gpu_memory_utilization 0.80, max_model_len 32768).
Outputs /kaggle/working/results/** and /kaggle/working/run_meta.json.
"""

import asyncio
import base64
import glob
import importlib
import io
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

RUN_NAME = "__G4_RUN_NAME__"
BUNDLE_ZIP_B64 = "__G4_BUNDLE_B64__"
TASK_IDS = json.loads("""__G4_TASK_IDS__""")
CONCURRENCY = int("__G4_CONCURRENCY__")

os.environ.update({
    "LITELLM_LOCAL_MODEL_COST_MAP": "True",
    "TRANSFORMERS_NO_TF": "1",
    "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
    "VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS": "1",
    "VLLM_ENGINE_READY_TIMEOUT_S": "1200",
    "VLLM_NO_USAGE_STATS": "1",
    "OTEL_SDK_DISABLED": "true",
    "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
})

WHEELHOUSE_DIR = Path("/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse")
DATA_DIR = Path("/kaggle/input/competitions/gemma-4-developer-agent")
MODEL_PATH = Path("/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2")
WORKING_DIR = Path("/kaggle/working")
AGENT_DIR = WORKING_DIR / "bundle"
RESULTS_DIR = WORKING_DIR / "results"
TARGET_MODEL_NAME = "gemma-4-31b-it-qat-w4a16-ct"


def find_input(path: Path, name: str) -> Path:
    """Kaggle mounts inputs under slightly different roots depending on the image."""
    if path.exists():
        return path
    hits = [Path(p) for p in glob.glob(f"/kaggle/input/**/{name}", recursive=True)]
    if not hits:
        raise FileNotFoundError(f"input {name} not found under /kaggle/input")
    return hits[0]


def install_wheelhouse() -> None:
    for pattern in ("/usr/local/lib/python*/dist-packages/*cutlass*.pth",
                    "/usr/local/lib/python*/site-packages/*cutlass*.pth"):
        for pth in glob.glob(pattern):
            try:
                os.unlink(pth)
            except OSError:
                pass
    src = find_input(WHEELHOUSE_DIR, "gemma-4-developer-agent-wheelhouse")
    tmp_whl = Path("/tmp/wheelhouse")
    tmp_whl.mkdir(parents=True, exist_ok=True)
    for w in src.glob("*.whl"):
        if "cutlass" in w.name.lower():
            continue
        name = w.name.replace("cu128", "+cu128") if ("cu128" in w.name and "+" not in w.name) else w.name
        if not (tmp_whl / name).exists():
            os.symlink(w, tmp_whl / name)
    wheels = sorted(str(w) for w in tmp_whl.glob("*.whl"))
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "--force-reinstall", *wheels],
                   check=True)
    importlib.invalidate_caches()


def unpack_bundle() -> None:
    AGENT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(BUNDLE_ZIP_B64))) as zf:
        zf.extractall(AGENT_DIR)


def start_server():
    import torch
    import litellm
    from adk_submission import VllmConfig, VllmServer, discover_adapters
    from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
    from swegemma.models.discovery import validate_single_declared_model

    litellm.drop_params = True
    declared = validate_single_declared_model(AGENT_DIR)
    adapters = discover_adapters(str(AGENT_DIR), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)
    gpus = torch.cuda.device_count()
    cfg = VllmConfig(
        model=str(find_input(MODEL_PATH, "gemma-4-31b-it-qat-w4a16-ct")), port=8000, host="127.0.0.1",
        tool_call_parser="gemma4", reasoning_parser="gemma4", max_model_len=32768,
        dtype="bfloat16", gpu_memory_utilization=0.80, enable_auto_tool_choice=True,
        enable_lora=True, max_loras=8, max_lora_rank=128,
        tensor_parallel_size=4 if gpus >= 4 else (2 if gpus >= 2 else 1), startup_timeout=60 * 20,
    )
    server = VllmServer(cfg, adapter_manifest=adapters)
    server.start()
    models = server.create_model_registry(aliases=[declared, TARGET_MODEL_NAME], model_prefix="openai/",
                                          api_key="EMPTY")
    return server, models, adapters, gpus


def load_eval_section() -> dict:
    import yaml
    path = AGENT_DIR / "eval_config.yaml"
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw.get("evaluation", raw)


def main() -> None:
    t0 = time.time()
    install_wheelhouse()
    unpack_bundle()
    server, models, adapters, gpus = start_server()
    t_server = time.time()

    from google.adk.agents.context_cache_config import ContextCacheConfig
    from google.adk.apps._configs import EventsCompactionConfig
    from swegemma.config import EvalConfig, build_submission_limits
    from swegemma.evaluate import Evaluator

    ev = load_eval_section()
    limits, gen_constraints = build_submission_limits()
    turns = ev.get("max_turns", ev.get("max_llm_calls"))
    config = EvalConfig(
        tasks_path=DATA_DIR / "tasks.jsonl", snapshots_dir=DATA_DIR / "snapshots",
        results_dir=RESULTS_DIR, submission_dir=AGENT_DIR, models=models, sandbox="subprocess",
        timeout_seconds=int(ev.get("timeout_seconds", 300)),
        max_time_minutes=float(ev.get("max_time_minutes", 60.0)),
        max_tool_calls=int(ev.get("max_tool_calls", 100)),
        max_turns=int(turns) if turns is not None else None,
        limits=limits, generation_constraints=gen_constraints, adapter_manifest=adapters,
        context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
        # Scorer values per HARNESS_README section 7.2.
        events_compaction_config=EventsCompactionConfig(compaction_interval=5, overlap_size=2,
                                                        token_threshold=14336, event_retention_size=5),
        graph_dir=str(DATA_DIR / "graphs"), embeddings_dir=str(DATA_DIR / "embeddings"),
        wheels_dir=DATA_DIR / "wheels", task_ids=TASK_IDS, concurrency=CONCURRENCY,
        display_mode="quiet", verbose=False,
    )
    result = asyncio.run(Evaluator(config).run())
    t_end = time.time()

    rows = [{"instance_id": r.instance_id, "resolved": bool(r.resolved), "tool_calls": r.tool_calls,
             "duration_s": round(r.duration_seconds or 0.0, 1), "patch_chars": len(r.agent_patch or ""),
             "error": (r.error or "")[:300]} for r in result.task_results]
    meta = {
        "run_name": RUN_NAME, "n_tasks": len(TASK_IDS), "concurrency": CONCURRENCY, "gpus": gpus,
        "eval_config": ev, "setup_s": round(t_server - t0, 1), "eval_s": round(t_end - t_server, 1),
        "resolved": sum(r["resolved"] for r in rows),
        "resolution_rate": round(sum(r["resolved"] for r in rows) / max(1, len(rows)), 4),
        "tasks": rows,
    }
    (WORKING_DIR / "run_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: v for k, v in meta.items() if k != "tasks"}, indent=1))
    server.stop()


if __name__ == "__main__":
    main()
