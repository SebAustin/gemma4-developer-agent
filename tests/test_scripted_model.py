from types import SimpleNamespace

from g4agent.scripted_model import empty_plan, oracle_plan

TASK = SimpleNamespace(patch="diff --git a/x.py b/x.py\n", problem_statement="Fix x.")


def test_empty_plan_submits_without_touching_the_repository():
    plan = empty_plan(TASK)

    assert plan == [("submit_patch", {})]


def test_oracle_plan_applies_the_reference_fix_before_submitting():
    plan = oracle_plan(TASK)

    names = [name for name, _ in plan]
    assert names[-1] == "submit_patch"
    assert any(TASK.patch in args.get("command", "") for _, args in plan)
