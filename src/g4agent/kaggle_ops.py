"""Render a self-contained Kaggle eval kernel for (bundle, split).

The kernel script embeds the packaged bundle (base64) and the task ids, so a run is fully
reproducible from its own source. Pushing is left to the user (`kaggle kernels push -p DIR`),
because it spends GPU quota.
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
from pathlib import Path

from .package import bundle_hash, package_bundle

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "kaggle" / "eval_kernel" / "run_eval.py"
ORACLE_TEMPLATE = ROOT / "kaggle" / "eval_kernel" / "run_oracle.py"
SUBMISSION_TEMPLATE = ROOT / "kaggle" / "eval_kernel" / "make_submission.py"
MAX_EMBEDDED_BYTES = 5 * 1024 * 1024  # adapters must go through a Kaggle dataset instead


def kaggle_username() -> str:
    out = subprocess.run(["kaggle", "config", "view"], capture_output=True, text=True, check=True).stdout
    match = re.search(r"^- username:\s*(\S+)", out, re.M)
    if not match:
        raise RuntimeError("could not read the Kaggle username from `kaggle config view`")
    return match.group(1)


def render_kernel(bundle: str | Path, task_ids: list[str], run_name: str, *, concurrency: int = 4,
                  out_root: str | Path = ROOT / "kaggle" / "runs", username: str | None = None) -> Path:
    bundle = Path(bundle)
    slug = re.sub(r"[^a-z0-9-]+", "-", f"g4-eval-{run_name}".lower()).strip("-")[:50]
    out_dir = Path(out_root) / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_path = package_bundle(bundle, out_dir / "bundle.zip")
    payload = zip_path.read_bytes()
    zip_path.unlink()
    if len(payload) > MAX_EMBEDDED_BYTES:
        raise RuntimeError("bundle too large to embed (LoRA adapters?); attach it as a Kaggle dataset")

    script = TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "__G4_RUN_NAME__": run_name,
        "__G4_BUNDLE_B64__": base64.b64encode(payload).decode(),
        "__G4_TASK_IDS__": json.dumps(sorted(task_ids)),
        "__G4_CONCURRENCY__": str(concurrency),
    }
    for key, value in replacements.items():
        script = script.replace(key, value)
    (out_dir / "run_eval.py").write_text(script, encoding="utf-8")

    metadata = {
        "id": f"{username or kaggle_username()}/{slug}",
        "title": slug,
        "code_file": "run_eval.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_tpu": False,
        "enable_internet": False,
        "machine_shape": "NvidiaL4",
        "dataset_sources": ["metric/gemma-4-developer-agent-wheelhouse"],
        "competition_sources": ["gemma-4-developer-agent"],
        "model_sources": ["google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2"],
        "kernel_sources": [],
    }
    (out_dir / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (out_dir / "run_info.json").write_text(json.dumps(
        {"run_name": run_name, "bundle": str(bundle), "bundle_hash": bundle_hash(bundle),
         "n_tasks": len(task_ids), "concurrency": concurrency}, indent=2) + "\n", encoding="utf-8")
    return out_dir


def render_oracle_kernel(bundle: str | Path, task_ids: list[str], *, out_root: str | Path = ROOT / "kaggle" / "runs",
                         username: str | None = None) -> Path:
    """CPU kernel that measures the Kaggle-environment ceiling by applying gold patches."""
    bundle = Path(bundle)
    out_dir = Path(out_root) / "g4-oracle-kaggle-env"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = package_bundle(bundle, out_dir / "bundle.zip")
    payload = zip_path.read_bytes()
    zip_path.unlink()
    scripted_src = (Path(__file__).parent / "scripted_model.py").read_bytes()
    script = ORACLE_TEMPLATE.read_text(encoding="utf-8")
    for key, value in {
        "__G4_BUNDLE_B64__": base64.b64encode(payload).decode(),
        "__G4_TASK_IDS__": json.dumps(sorted(task_ids)),
        "__G4_SCRIPTED_MODEL_B64__": base64.b64encode(scripted_src).decode(),
    }.items():
        script = script.replace(key, value)
    (out_dir / "run_oracle.py").write_text(script, encoding="utf-8")
    metadata = {
        "id": f"{username or kaggle_username()}/g4-oracle-kaggle-env", "title": "g4-oracle-kaggle-env",
        "code_file": "run_oracle.py", "language": "python", "kernel_type": "script", "is_private": True,
        "enable_gpu": False, "enable_tpu": False, "enable_internet": False,
        "dataset_sources": ["metric/gemma-4-developer-agent-wheelhouse"],
        "competition_sources": ["gemma-4-developer-agent"], "model_sources": [], "kernel_sources": [],
    }
    (out_dir / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return out_dir


def render_submission_kernel(bundle: str | Path, *, out_root: str | Path = ROOT / "kaggle" / "runs",
                             username: str | None = None) -> Path:
    """CPU kernel that outputs submission.zip; code competitions only accept kernel outputs."""
    bundle = Path(bundle)
    out_dir = Path(out_root) / "g4-submission"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = package_bundle(bundle, out_dir / "bundle.zip")
    payload = zip_path.read_bytes()
    zip_path.unlink()
    script = SUBMISSION_TEMPLATE.read_text(encoding="utf-8")
    script = script.replace("__G4_BUNDLE_B64__", base64.b64encode(payload).decode())
    script = script.replace("__G4_BUNDLE_HASH__", bundle_hash(bundle))
    (out_dir / "make_submission.py").write_text(script, encoding="utf-8")
    metadata = {
        "id": f"{username or kaggle_username()}/g4-submission", "title": "g4-submission",
        "code_file": "make_submission.py", "language": "python", "kernel_type": "script", "is_private": True,
        "enable_gpu": False, "enable_tpu": False, "enable_internet": False,
        "dataset_sources": [], "competition_sources": ["gemma-4-developer-agent"], "model_sources": [],
        "kernel_sources": [],
    }
    (out_dir / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return out_dir
