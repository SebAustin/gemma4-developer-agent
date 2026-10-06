import json

import pytest

from g4agent.compare import compare_runs, load_results


def _rows(resolved: dict[str, bool]) -> list[dict]:
    return [{"instance_id": i, "resolved": r, "duration_seconds": 100.0, "tool_calls": 10, "error": None}
            for i, r in resolved.items()]


def test_pairs_tasks_and_splits_them_by_outcome():
    a = _rows({"t1": True, "t2": True, "t3": False, "t4": False, "only_a": True})
    b = _rows({"t1": True, "t2": False, "t3": True, "t4": False, "only_b": True})

    c = compare_runs(a, b)

    assert (c.both, c.a_only, c.b_only, c.neither) == (["t1"], ["t2"], ["t3"], ["t4"])
    assert c.unpaired == ["only_a", "only_b"]


@pytest.mark.parametrize(("a_wins", "b_wins", "p_value"), [(0, 0, 1.0), (0, 1, 1.0), (0, 6, 0.03125), (1, 6, 0.125)])
def test_exact_mcnemar_p_value_on_discordant_pairs(a_wins, b_wins, p_value):
    a = _rows({**{f"a{i}": True for i in range(a_wins)}, **{f"b{i}": False for i in range(b_wins)}})
    b = _rows({**{f"a{i}": False for i in range(a_wins)}, **{f"b{i}": True for i in range(b_wins)}})
    assert compare_runs(a, b).p_value == pytest.approx(p_value)


def test_load_results_reads_task_results_jsonl_from_a_run_directory(tmp_path):
    results = tmp_path / "run" / "results"
    results.mkdir(parents=True)
    (results / "task_results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in _rows({"t1": True})))
    assert load_results(tmp_path / "run")[0]["instance_id"] == "t1"


def test_runs_without_shared_tasks_report_zero_pairs_instead_of_crashing():
    comparison = compare_runs(_rows({"t1": True}), _rows({"t2": True}))

    report = comparison.format()

    assert "paired tasks: 0" in report and comparison.p_value == 1.0
