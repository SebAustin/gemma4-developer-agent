"""Kaggle eval kernel: run a submission bundle on a fixed task split with the official harness.

Rendered by `g4 kernel` (src/g4agent/kaggle_ops.py), which replaces the __G4_*__ placeholders.
Mirrors the official "Getting Started" notebook (wheelhouse install -> VllmServer -> Evaluator),
with vLLM settings matching the scorer documented in HARNESS_README (see GPU_MEMORY_UTILIZATION).
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
    "VLLM_ENGINE_READY_TIMEOUT_S": "1200",
    "VLLM_NO_USAGE_STATS": "1",
    "OTEL_SDK_DISABLED": "true",
    "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
})

# First-guess mount points; notebook and script kernels mount inputs under different roots,
# so each is confirmed (or found) by find_input before any GPU work starts.
DEFAULT_WHEELHOUSE_DIR = Path("/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse")
DEFAULT_DATA_DIRS = (Path("/kaggle/input/competitions/gemma-4-developer-agent"),
                     Path("/kaggle/input/gemma-4-developer-agent"))
DEFAULT_MODEL_DIR = Path("/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2")
# Scorer value per HARNESS_README 3.1. The official notebook's VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1
# makes 0.80 behave like ~0.62 (no KV cache once LoRA is enabled), so this kernel leaves it unset.
# See docs/diagnosis/v1-regression.md: with 0.90 + that variable, the server stopped answering after ~10 min.
GPU_MEMORY_UTILIZATION = 0.80
WORKING_DIR = Path("/kaggle/working")
AGENT_DIR = WORKING_DIR / "bundle"
RESULTS_DIR = WORKING_DIR / "results"
TARGET_MODEL_NAME = "gemma-4-31b-it-qat-w4a16-ct"


def find_input(defaults: tuple[Path, ...], marker: str, path_contains: str = "") -> Path:
    """Return the first directory holding ``marker`` (a filename or glob): the defaults first,
    then the shortest match anywhere under /kaggle/input whose path contains ``path_contains``."""
    for d in defaults:
        if glob.glob(str(d / marker)):
            return d
    hits = sorted({Path(p).parent for p in glob.glob(f"/kaggle/input/**/{marker}", recursive=True)
                   if path_contains in p}, key=lambda p: len(str(p)))
    if not hits:
        raise FileNotFoundError(f"no input containing {marker!r} ({path_contains!r}) under /kaggle/input")
    return hits[0]


def locate_inputs() -> tuple[Path, Path, Path]:
    """(data dir, model dir, wheelhouse dir), resolved up front so a missing input fails fast."""
    data_dir = find_input(DEFAULT_DATA_DIRS, "tasks.jsonl")
    model_dir = find_input((DEFAULT_MODEL_DIR,), "config.json", "gemma-4-31b-it-qat-w4a16-ct")
    wheelhouse = find_input((DEFAULT_WHEELHOUSE_DIR,), "swegemma-*.whl")
    return data_dir, model_dir, wheelhouse


def install_wheelhouse(src: Path) -> None:
    for pattern in ("/usr/local/lib/python*/dist-packages/*cutlass*.pth",
                    "/usr/local/lib/python*/site-packages/*cutlass*.pth"):
        for pth in glob.glob(pattern):
            try:
                os.unlink(pth)
            except OSError:
                pass
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


def start_server(model_dir: Path):
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
        model=str(model_dir), port=8000, host="127.0.0.1",
        tool_call_parser="gemma4", reasoning_parser="gemma4", max_model_len=32768,
        dtype="bfloat16", gpu_memory_utilization=GPU_MEMORY_UTILIZATION, enable_auto_tool_choice=True,
        # max_loras / max_lora_rank left to the harness defaults (adk_submission >= 0.2.12: one slot,
        # rank inferred from the adapters). Explicit 8 x 128 made the sampler warm-up OOM at 0.80.
        enable_lora=True,
        tensor_parallel_size=4 if gpus >= 4 else (2 if gpus >= 2 else 1), startup_timeout=60 * 20,
        # Dev runs never exceed CONCURRENCY parallel requests; vLLM's default (256) makes the sampler
        # warm-up OOM at 0.80 once LoRA buffers are allocated (sample bundle, 2026-10-03).
        extra_args=["--max-num-seqs", str(max(8, 2 * CONCURRENCY))],
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


SERVER_HANG = {"first_seen": None}  # set by the monitor; reported in run_meta.json


def start_monitor(server, interval_s: int = 20, stale_s: int = 120) -> None:
    """Watchdog: log host memory, vLLM processes, GPU memory and /health every interval_s, and
    flag a server hang (the vLLM log has not grown for stale_s and /health fails, or the log is
    stale while the engine reported running requests). An intermittent silent hang was seen in
    2 of 3 dev runs; see docs/diagnosis/v1-regression.md."""
    import threading
    import urllib.request

    out = WORKING_DIR / "monitor.log"

    def sample() -> str:
        mem = subprocess.run(["free", "-m"], capture_output=True, text=True).stdout.splitlines()
        procs = subprocess.run("ps -eo pid,rss,stat,comm,args --sort=-rss | grep -iE 'vllm|python' | grep -v grep | head -8",
                               shell=True, capture_output=True, text=True).stdout.strip()
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.used,utilization.gpu",
                              "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as r:
                health = str(r.status)
        except Exception as e:  # noqa: BLE001 - any failure is the signal we are looking for
            health = f"ERR {type(e).__name__}"
        oom = subprocess.run("dmesg 2>/dev/null | grep -iE 'killed process|out of memory' | tail -3",
                             shell=True, capture_output=True, text=True).stdout.strip()
        return (f"=== {time.strftime('%H:%M:%S')} health={health}\n{mem[1] if len(mem) > 1 else mem}\n"
                f"{gpu}\n{procs}\n{('OOM: ' + oom) if oom else ''}\n")

    log_path = Path(getattr(server, "log_path", "") or "/nonexistent")

    def check_hang(report: str) -> None:
        if SERVER_HANG["first_seen"] or not log_path.exists():
            return
        stale = time.time() - log_path.stat().st_mtime > stale_s
        if stale and ("health=200" not in report or "Running: 0 reqs" not in log_path.read_text(errors="replace")[-400:]):
            SERVER_HANG["first_seen"] = time.strftime("%H:%M:%S")
            print(f"[watchdog] inference server appears hung since {SERVER_HANG['first_seen']}", flush=True)

    def loop() -> None:
        while True:
            try:
                report = sample()
                check_hang(report)
                with out.open("a") as f:
                    f.write(report)
            except Exception as e:  # noqa: BLE001
                with out.open("a") as f:
                    f.write(f"monitor error: {e}\n")
            time.sleep(interval_s)

    threading.Thread(target=loop, daemon=True).start()


def keep_server_log(server) -> None:
    """Copy the inference server's log (a temp file) into the outputs and echo its capacity lines."""
    log_path = getattr(server, "log_path", None)
    if not log_path or not Path(log_path).exists():
        print("server log not found")
        return
    text = Path(log_path).read_text(errors="replace")
    (WORKING_DIR / "vllm_server.log").write_text(text)
    keys = ("KV cache", "Maximum concurrency", "Available KV", "Error", "error", "Traceback", "OOM", "preempt")
    lines = [ln for ln in text.splitlines() if any(k in ln for k in keys)]
    print("\n".join(lines[:40]) or "no capacity/error lines in server log")


def write_run_meta(gpus: int, ev: dict, setup_s: float, eval_s: float, status: str) -> dict:
    """Summarize from the harness's append-only task_results.jsonl, so a crashed or timed-out
    run still reports every task that finished."""
    path = RESULTS_DIR / "task_results.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    tasks = [{"instance_id": r.get("instance_id"), "resolved": bool(r.get("resolved")),
              "tool_calls": r.get("tool_calls"), "duration_s": r.get("duration_seconds"),
              "patch_chars": r.get("agent_patch_size"), "error": (r.get("error") or "")[:300]} for r in rows]
    resolved = sum(t["resolved"] for t in tasks)
    meta = {
        "run_name": RUN_NAME, "status": status, "n_tasks": len(TASK_IDS), "n_finished": len(tasks),
        "concurrency": CONCURRENCY, "gpus": gpus, "eval_config": ev, "setup_s": round(setup_s, 1),
        "eval_s": round(eval_s, 1), "server_hang_at": SERVER_HANG["first_seen"], "resolved": resolved,
        "resolution_rate": round(resolved / max(1, len(TASK_IDS)), 4), "tasks": tasks,
    }
    (WORKING_DIR / "run_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: v for k, v in meta.items() if k != "tasks"}, indent=1))
    return meta


def main() -> None:
    t0 = time.time()
    data_dir, model_dir, wheelhouse = locate_inputs()
    install_wheelhouse(wheelhouse)
    unpack_bundle()
    ev = load_eval_section()
    server, models, adapters, gpus = start_server(model_dir)
    start_monitor(server)
    t_server = time.time()
    status = "crashed"
    try:
        from google.adk.agents.context_cache_config import ContextCacheConfig
        from google.adk.apps._configs import EventsCompactionConfig
        from swegemma.config import EvalConfig, build_submission_limits
        from swegemma.evaluate import Evaluator

        limits, gen_constraints = build_submission_limits()
        turns = ev.get("max_turns", ev.get("max_llm_calls"))
        config = EvalConfig(
            tasks_path=data_dir / "tasks.jsonl", snapshots_dir=data_dir / "snapshots",
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
            graph_dir=str(data_dir / "graphs"), embeddings_dir=str(data_dir / "embeddings"),
            wheels_dir=data_dir / "wheels", task_ids=TASK_IDS, concurrency=CONCURRENCY,
            display_mode="quiet", verbose=False,
        )
        asyncio.run(Evaluator(config).run())
        status = "complete"
    finally:
        write_run_meta(gpus, ev, t_server - t0, time.time() - t_server, status)
        keep_server_log(server)
        server.stop()


if __name__ == "__main__":
    main()
