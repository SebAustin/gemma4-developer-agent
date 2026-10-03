# Gemma 4 Developer Agent

Our entry for the Kaggle competition in which a declarative agent configuration drives Gemma 4 to fix issues in Python repositories, graded by hidden tests.

## Submissions

**Bundle**:
A complete declarative agent configuration (agent definition, prompts, skills, budgets, optional adapters) that the competition harness compiles and runs. Each variant lives in its own directory and is identified by its bundle hash.
_Avoid_: submission (that is the act of sending a bundle), config, agent

**Variant**:
One named bundle under comparison, e.g. `sample_baseline`, `v1_scaffold`, `v2_fast`.
_Avoid_: version, model

**Skill**:
A folder of instructions and scripts shipped inside a bundle that the agent can run inside the task sandbox. Our bundles ship one, `swe`.
_Avoid_: tool (reserved for the harness's built-in tools such as `edit_file`)

**Submission**:
Sending one bundle to the competition for scoring. Limited to one per day.
_Avoid_: upload, entry

## Evaluation

**Task**:
One issue to fix in one repository snapshot, with hidden tests that decide whether it is resolved.
_Avoid_: instance, problem, sample

**Resolved**:
A task whose hidden tests all pass after the agent's patch is applied.
_Avoid_: solved, passed, fixed

**Scorer**:
The competition's private evaluation run, which produces the leaderboard score. We cannot inspect it.
_Avoid_: grader, metric, evaluator

**Environment**:
Where a task's tests execute, defined by the packages they can import. There are three, and they differ: the **local environment** (our Docker sandbox), the **Kaggle environment** (a Kaggle notebook's sandbox) and the **scoring environment** (the scorer's).
_Avoid_: setup, platform

**Reference-fix ceiling**:
How many tasks resolve in a given environment when the agent applies the known-correct patch. It caps any agent's score in that environment.
_Avoid_: oracle score, upper bound, max score

**Dev split**:
A frozen subset of the public tasks used to compare variants; scores are only comparable within one split.
_Avoid_: dev set, validation set, sample

**Dev run**:
Evaluating one variant on one dev split, on Kaggle GPUs.
_Avoid_: experiment, benchmark run, eval

## Kaggle machinery

**Eval kernel**:
A Kaggle GPU job that serves Gemma and evaluates one variant on one dev split.
_Avoid_: notebook, eval script

**Oracle kernel**:
A Kaggle CPU job that measures the reference-fix ceiling of the Kaggle environment.

**Submission kernel**:
A Kaggle CPU job whose only output is the bundle archive. The competition accepts submissions only as kernel outputs.

## Local verification

**Wheel set**:
The collection of package wheels a task's tests may install from in the local environment, chosen per task.
_Avoid_: dependencies, wheels dir

**Shadowing**:
When an installed copy of the repository under test is imported instead of the patched working copy, so the patch is silently ignored.
_Avoid_: import conflict
