"""The Kaggle eval kernel template, rendered with dummy values and imported as a module."""

import importlib.util
import json
from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parents[1] / "kaggle" / "eval_kernel" / "run_eval.py"


@pytest.fixture
def kernel(tmp_path, monkeypatch):
    script = TEMPLATE.read_text()
    for key, value in {"__G4_RUN_NAME__": "test", "__G4_BUNDLE_B64__": "",
                       "__G4_TASK_IDS__": json.dumps(["a_1", "b_2", "c_3"]), "__G4_CONCURRENCY__": "2"}.items():
        script = script.replace(key, value)
    path = tmp_path / "rendered_kernel.py"
    path.write_text(script)
    spec = importlib.util.spec_from_file_location("rendered_kernel", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "WORKING_DIR", tmp_path / "working")
    monkeypatch.setattr(module, "RESULTS_DIR", tmp_path / "working" / "results")
    return module


def test_find_input_prefers_existing_default(kernel, tmp_path):
    default = tmp_path / "competitions" / "slug"
    default.mkdir(parents=True)
    (default / "tasks.jsonl").write_text("")
    assert kernel.find_input((tmp_path / "missing", default), "tasks.jsonl") == default


def test_find_input_supports_glob_markers(kernel, tmp_path):
    (tmp_path / "wheels").mkdir()
    (tmp_path / "wheels" / "swegemma-0.2.7-py3-none-any.whl").write_text("")
    assert kernel.find_input((tmp_path / "wheels",), "swegemma-*.whl") == tmp_path / "wheels"


def test_find_input_fails_clearly_when_nothing_matches(kernel, tmp_path):
    with pytest.raises(FileNotFoundError, match="no-such-marker"):
        kernel.find_input((tmp_path,), "no-such-marker.json", "unlikely-path-fragment")


def test_run_meta_reports_partial_results(kernel):
    kernel.RESULTS_DIR.mkdir(parents=True)
    rows = [{"instance_id": "a_1", "resolved": True, "tool_calls": 7, "duration_seconds": 80.0,
             "agent_patch_size": 900, "error": None},
            {"instance_id": "b_2", "resolved": False, "tool_calls": 40, "duration_seconds": 300.0,
             "agent_patch_size": 0, "error": "budget exhausted"}]
    (kernel.RESULTS_DIR / "task_results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

    meta = kernel.write_run_meta(gpus=4, ev={}, setup_s=600, eval_s=1200, status="crashed")

    saved = json.loads((kernel.WORKING_DIR / "run_meta.json").read_text())
    assert saved == meta
    assert meta["status"] == "crashed" and meta["n_finished"] == 2 and meta["n_tasks"] == 3
    assert meta["resolved"] == 1 and meta["resolution_rate"] == round(1 / 3, 4)
    assert meta["tasks"][1]["error"] == "budget exhausted"


def test_run_meta_without_any_finished_task(kernel):
    kernel.WORKING_DIR.mkdir(parents=True)
    meta = kernel.write_run_meta(gpus=4, ev={}, setup_s=1, eval_s=0, status="crashed")
    assert meta["n_finished"] == 0 and meta["resolved"] == 0
