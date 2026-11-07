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
A folder of instructions and scripts shipped inside a bundle that the agent can run inside the task sandbox. Only the older variants ship one (`swe`); see ADR 0005.
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

**Leaderboard noise**:
The spread of public leaderboard scores between submissions of the same bundle. Measured at ±0.03 (our two runs of one bundle) to ±0.06 (a public bundle run three times), that is 2–4 of the ~58 public tasks. Score gaps smaller than this say nothing about which variant is better.
_Avoid_: variance, randomness, luck

**Environment**:
Where a task's tests execute, defined by the packages they can import. There are three, and they differ: the **local environment** (our Docker sandbox), the **Kaggle environment** (a Kaggle notebook's sandbox) and the **scoring environment** (the scorer's).
_Avoid_: setup, platform

**Reference-fix ceiling**:
How many tasks resolve in a given environment when the agent applies the known-correct patch. It caps any agent's score in that environment.
_Avoid_: oracle score, upper bound, max score

**Sound task**:
A task whose reference fix resolves in the Kaggle environment *and* whose empty patch fails. A miss on it is then the agent's fault, not the environment's, and a pass is the agent's credit, not the task's. The `sound40` split was built with the first check only. It contains at least one task that passes with an empty patch (`fastapi_14851`).
_Avoid_: valid task, clean task

**Verification timeout**:
The limit on the scoring pytest run over a task's hidden test files. Since harness 0.2.11, it is the harness's own 300 s, separate from the bundle's `timeout_seconds` (which now caps agent commands only). Before 0.2.11, the two were the same value.
_Avoid_: test timeout, command timeout (when the scoring run is meant)

**Dev split**:
A frozen subset of the public tasks used to compare variants; scores are only comparable within one split.
_Avoid_: dev set, validation set, sample

**Dev run**:
Evaluating one variant on one dev split, on Kaggle GPUs. Since ADR 0004, dev runs are serial (concurrency 1), like the scorer.
_Avoid_: experiment, benchmark run, eval

**Paired comparison**:
Comparing two dev runs task by task on the same split. Only the tasks one variant resolves and the other does not carry signal (`g4 compare`, exact McNemar test).
_Avoid_: A/B test, diff of scores

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
