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


def test_sound_split_only_uses_tasks_the_reference_fix_resolves(tasks):
    resolvable = {t["instance_id"] for t in tasks if not t["instance_id"].endswith(("0", "5"))}
    sound = make_splits(tasks, resolvable=resolvable)["sound40"]
    assert len(sound) == 40 and set(sound) <= resolvable
    assert sound == make_splits(list(reversed(tasks)), resolvable=resolvable)["sound40"]


def test_write_splits_adds_a_new_split_but_keeps_frozen_ones(tasks, tmp_path):
    tasks_path = tmp_path / "tasks.jsonl"
    tasks_path.write_text("\n".join(json.dumps(t) for t in tasks))
    out = tmp_path / "splits.json"
    frozen = write_splits(tasks_path, out)
    oracle = tmp_path / "oracle.json"
    oracle.write_text(json.dumps({"resolvable": [t["instance_id"] for t in tasks[:70]]}))

    splits = write_splits(tasks_path, out, oracle_path=oracle)

    assert {k: splits[k] for k in frozen} == frozen and len(splits["sound40"]) == 40
    assert json.loads(out.read_text()) == splits


def test_sound_split_keeps_the_repo_mix_of_the_resolvable_tasks(tasks):
    resolvable = {t["instance_id"] for t in tasks if t["repo"] != "org/small"}  # big 60, mid 30

    sound = make_splits(tasks, resolvable=resolvable)["sound40"]

    assert sum(i.startswith("big") for i in sound) == 27 and sum(i.startswith("mid") for i in sound) == 13


def test_full_sound_split_drops_tasks_that_pass_with_an_empty_patch(tasks):
    resolvable = {t["instance_id"] for t in tasks[:70]}
    empty_pass = {tasks[0]["instance_id"], tasks[5]["instance_id"]}

    splits = make_splits(tasks, resolvable=resolvable, empty_pass=empty_pass)

    assert splits["sound68"] == sorted(resolvable - empty_pass)


def test_no_full_sound_split_without_the_empty_patch_check(tasks):
    resolvable = {t["instance_id"] for t in tasks[:70]}

    splits = make_splits(tasks, resolvable=resolvable)

    assert not any(name.startswith("sound") and name != "sound40" for name in splits)


def test_write_splits_adds_the_full_sound_split_from_the_empty_patch_file(tasks, tmp_path):
    tasks_path = tmp_path / "tasks.jsonl"
    tasks_path.write_text("\n".join(json.dumps(t) for t in tasks))
    out = tmp_path / "splits.json"
    oracle = tmp_path / "oracle.json"
    oracle.write_text(json.dumps({"resolvable": [t["instance_id"] for t in tasks[:70]]}))
    frozen = write_splits(tasks_path, out, oracle_path=oracle)
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"passes_with_empty_patch": [tasks[1]["instance_id"]]}))

    splits = write_splits(tasks_path, out, oracle_path=oracle, empty_path=empty)

    assert {k: splits[k] for k in frozen} == frozen
    assert len(splits["sound69"]) == 69 and tasks[1]["instance_id"] not in splits["sound69"]
