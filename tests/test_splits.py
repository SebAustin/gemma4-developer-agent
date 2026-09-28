import json

import pytest

from g4agent.splits import make_splits, patch_churn, size_bucket, stratified_sample, write_splits


def _task(i: int, repo: str, churn: int) -> dict:
    patch = "--- a/x.py\n+++ b/x.py\n" + "+line\n" * churn
    return {"instance_id": f"{repo.split('/')[1]}_{i}", "repo": repo, "patch": patch}


@pytest.fixture
def tasks():
    out = [_task(i, "org/big", 3 + i) for i in range(60)]
    out += [_task(i, "org/mid", 50) for i in range(30)]
    out += [_task(i, "org/small", 200) for i in range(10)]
    return out


def test_patch_churn_ignores_headers():
    assert patch_churn("--- a/f\n+++ b/f\n@@ -1 +1 @@\n-a\n+b\n c\n") == 2


def test_size_bucket_edges():
    assert [size_bucket(c) for c in (0, 5, 6, 20, 21, 80, 81)] == ["xs", "xs", "s", "s", "m", "m", "l"]


def test_sample_has_exact_size_and_is_proportional(tasks):
    picked = stratified_sample(tasks, 20)
    assert len(picked) == len(set(picked)) == 20
    by_repo = {r: sum(1 for p in picked if p.startswith(r)) for r in ("big", "mid", "small")}
    assert by_repo == {"big": 12, "mid": 6, "small": 2}


def test_sample_is_independent_of_input_order(tasks):
    assert stratified_sample(tasks, 20) == stratified_sample(list(reversed(tasks)), 20)


def test_smoke_is_not_required_to_be_subset_but_splits_are_valid(tasks):
    splits = make_splits(tasks)
    ids = {t["instance_id"] for t in tasks}
    for name, split in splits.items():
        assert set(split) <= ids, name


def test_write_splits_refuses_silent_change(tasks, tmp_path):
    tasks_path = tmp_path / "tasks.jsonl"
    tasks_path.write_text("\n".join(json.dumps(t) for t in tasks))
    out = tmp_path / "splits.json"
    write_splits(tasks_path, out)
    write_splits(tasks_path, out)  # identical -> fine
    tasks_path.write_text("\n".join(json.dumps(t) for t in tasks[:50]))
    with pytest.raises(RuntimeError):
        write_splits(tasks_path, out)
