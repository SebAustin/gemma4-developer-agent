# Audit the Pipeline Before Tuning the Agent
### Measuring a declarative Gemma 4 coding agent under a noisy, hidden leaderboard

<!-- Kaggle Writeup for gemma-4-developer-agent-paper. Limit: 3,000 words, references excluded. -->

## Abstract

The Gemma 4 Developer Agent competition scores a declarative agent bundle (prompts, skills, sampling and budgets for Gemma 4 31B) by how many hidden Python issues it resolves. It does so in a single 12-hour run over private repositories, with one submission a day. We report what one small team learned while trying to improve such an agent. Most of it concerns measurement, not the agent.

1. Resubmitting an identical bundle moved its public score by 0.03 (0.13 → 0.10). A public bundle moved by up to 0.06. That is 2–4 of the ~58 public tasks, larger than every effect we tried to measure.
2. The fraction of public tasks that the *reference fix itself* passes depends on the environment: 105/129 in Docker with per-task dependencies, 73/129 in Kaggle notebooks. Raw dev scores are uninterpretable without this ceiling.
3. Reading agent trajectories, not scores, exposed a harness bug. Test-file edits by the agent were never reverted before grading, which made correct fixes fail. We replayed it in the scorer's Docker sandbox. The organizers fixed it independently six days later.
4. A custom navigation skill that looked neutral-to-positive on early dev tasks coincided with our worst leaderboard scores. A serial, paired run on 40 sound tasks agreed in direction (20 vs 15 resolved, 6 vs 1 discordant, p = 0.125).
5. Half of all dev failures were agents that never made a source edit, not wrong edits.

We release the toolkit that produced these results. It contains a bundle validator that encodes scorer pitfalls, per-environment reference-fix ceilings, a "sound" dev split, and a paired comparison tool.

## 1. Introduction

Agent competitions with hidden test sets invite a familiar loop: change the prompt, submit, read the score, repeat. That loop assumes the score is a reliable signal. In this competition, three properties break the assumption:
- **The test repositories are private.** Public tasks come from four open-source repositories (fastapi, rich, requests, httpx). The ~120 scored tasks come from others.
- **The public leaderboard sees about half of them.** Each submission is a 12-hour GPU run, and teams get one a day.
- **The harness is a moving target.** It is a set of wheels the organizers republished twice during the competition, sometimes under the same version number.

We set out to improve the agent through prompts, custom tools and budget tuning, but our scores never left the 0.06–0.13 band. The measurement work we built to explain them produced findings that transfer to any team building agents against a hidden benchmark.

**Contributions.**
1. A noise model of the public leaderboard, from repeated submissions of identical bundles.
2. Per-environment reference-fix ceilings, and the "sound split" they enable.
3. A harness-audit method, reading trajectories against harness source, that found a scoring bug with a reproducible replay.
4. Single-factor agent ablations, read against that noise.
5. An open toolkit (Section 6).

## 2. Setting

**Bundle.** A submission is a zip containing:
- `agent.yaml`: one ADK `LlmAgent` bound to `gemma-4-31b-it-qat-w4a16-ct`, plus optional sub-agents;
- prompts;
- optional skills (instructions plus Python scripts run inside the task sandbox);
- sampling settings;
- optional LoRA adapters;
- `eval_config.yaml`, with per-task limits on time, tool calls, turns and command timeout.

There is no agent code. The harness (`swegemma`/`adk_submission`) compiles the YAML into an ADK agent with fixed tools: `run_command`, `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`, and three code-graph tools.

**Scoring.** vLLM serves the model on 4×L4 with a 32k context. Tasks run **sequentially** (host-confirmed). The hidden tests of each task run against the agent's diff. Exceeding 12 hours errors the whole submission. The score is the fraction of resolved tasks.

**Our compute.** Kaggle only: 45 GPU-hours a week on 4×L4 notebooks, which our other projects also draw on. Local work used an M1 Mac with Docker.

**Bundles in this paper.**

| bundle | description |
|---|---|
| `sample` | the official sample: 1 min / 10 tool calls |
| `v1_scaffold` | `swe` navigation skill + red/green workflow prompt, 5 min / 40 calls |
| `v2_fast` | v1 with "first edit by your 6th call" |
| `v2_noskill` | v2_fast's prompt with shell commands instead of the skill |
| `v3_guard` | v2_noskill + a pre-submit step that reverts test/config edits and deletes scratch files |
| `v4_guard_budget` | v3_guard + 8 min / 28 calls / 240 s |

## 3. Measuring under noise

### 3.1 The leaderboard noise floor

| bundle | public scores |
|---|---|
| public bundle (another team, unchanged archive) | 0.12, 0.10, 0.06 |
| `v4_guard_budget` (ours, identical resubmission) | 0.13, 0.10 |
| `v2_noskill` (ours) | 0.13, TODO(LB 58068665, harness 0.2.11) |

With ~58 public tasks, one task is worth 0.017. A spread of 0.03–0.06 is therefore 2–4 tasks. Sampling at temperature 0.2–0.3 and early-branching trajectories make this unsurprising, but easy to forget when each data point costs a day.

All our between-bundle differences fall inside this spread, except the two skill bundles against the rest (Section 5.1). We adopted a rule: a single leaderboard comparison is never evidence. Leaderboard slots serve to confirm large dev effects and to estimate noise.

### 3.2 Reference-fix ceilings per environment

Before measuring any agent, we ran every public task through the *real harness* with a scripted model. The scripted model applies the gold patch through `run_command` and calls `submit_patch`. Any task this "oracle" fails is unsolvable in that environment, whatever the agent does.

| environment | resolved by the reference fix | main causes of failure |
|---|---|---|
| Docker sandbox, per-task dependency set | 105/129 | requests tests need network; rich rendering is version-sensitive |
| Kaggle notebook (subprocess sandbox) | 73/129 | missing test dependencies (35: `inline_snapshot` 27, `dirty_equals` 7, other 1), version differences (13), network (8) |

The Docker number needed two local fixes first:
- **Package shadowing.** The public wheels include the benchmark repositories themselves. Installed into site-packages, they make tests import the *released* package instead of the patched copy, so a correct patch is ignored.
- **Highest-version selection.** The harness keeps the highest version of each wheel, which pulls an incompatible starlette into older fastapi commits.

Per-task wheel sets that drop the repository's own package and respect its pins raised the oracle from 1/5 to 5/5 on a smoke split.

Our first dev runs scored 5–6 of 30 tasks. That reads as 17–20%, but only 18 of those 30 tasks are solvable in the Kaggle environment, so the agent actually resolved a third of what it could. We therefore defined the **sound split** `sound40`: 40 tasks, stratified by repository and patch size, drawn only from tasks the reference fix resolves in the Kaggle environment. Every miss on `sound40` is the agent's.

### 3.3 Paired comparison and serial runs

Two variants run on the same tasks agree on most of them; only *discordant* tasks carry information. We compare runs task by task with an exact McNemar (binomial) test. Our earlier comparison, v1 against v2_fast on 30 tasks, shows why this matters:
- v2_fast resolved every task v1 did, plus one;
- headline: 6 vs 5;
- p = 1.0.

We also learned that dev runs must match the scorer's **sequential** execution. At concurrency 4, every turn is slower. That penalised the official sample's 1-minute budget so much that it scored 0/30 on dev, against ~0.12 on the leaderboard.

We then ran `v2_noskill` and `v2_fast` serially on `sound40` with the scorer's budget (5 min, 40 calls), on harness 0.2.11:

| | `v2_fast` resolved | `v2_fast` failed |
|---|---|---|
| **`v2_noskill` resolved** | 14 | 6 |
| **`v2_noskill` failed** | 1 | 19 |

`v2_noskill` resolved 20/40 and `v2_fast` 15/40. The two runs disagree on 7 tasks, 6 of them in `v2_noskill`'s favour (exact McNemar p = 0.125). The direction matches the leaderboard (0.13 vs 0.06), but even a 5-task gap on 40 tasks is not significant.

The run exposed one more way a split can be unsound. `v2_noskill` "resolved" `fastapi_14851` without editing any file: the hidden tests pass on the unmodified repository. `v2_fast` timed out there, so it counted as a loss. Replaying an empty patch over all 129 public tasks found one more, `fastapi_14077`, whose hidden test patch only swaps a status constant for its literal value. Both are in `sound40`. A sound task needs two checks: the reference fix passes *and* the empty patch fails. Without both tasks: 18 vs 14 of 38, 5 vs 1 discordant (p = 0.22).

## 4. Auditing the harness

The most valuable hour of the project came from reading failed trajectories next to the harness source, not from scores.

### 4.1 Test edits made correct fixes fail

In v2_fast's dev run, 3 of 30 tasks failed with `Failed to apply test_patch`. In one of them (`fastapi_14077`), the agent's patch changed *exactly* the three files of the reference fix. It also changed an assertion in a test file, a test that the hidden test patch rewrites.

The harness intended to prevent this. Before applying the test patch, it resets test and configuration files:

```
git checkout HEAD -- <test files> <agent-touched test/config files> conftest.py pytest.ini sitecustomize.py usercustomize.py _swegemma_stubs.py 2>/dev/null || true
```

The three last paths live in site-packages, never in the repository. Git rejects the *entire* checkout when any pathspec is unknown, and `|| true` hides the error. So the reset never ran.

What happens next depends on the overlap:
- **Test edits on lines the hidden test patch also changes:** the patch fails to apply and the task fails, however correct the fix.
- **Non-overlapping edits:** these merged through the harness's `git apply -3` fallback and stayed in the tree under grading.

We reproduced it in the Docker sandbox the scorer uses, by replaying `fastapi_14077` with a scripted model:
- the reference fix plus the agent's real test edit: **failed** (`Failed to apply test_patch`);
- the same edits followed by a revert of test and config files: **resolved**.

This task later turned out to pass even with an empty patch (Section 3.3). The agent's test edit had turned a free point into a loss.

Our prompt had made things worse. Copying a common belief, it told the model that "the grader resets test files". The same audit found a second mechanical loss: 3 of v2_fast's 19 patches contained only a scratch `repro.py` and no source edit.

We built `v3_guard`. It drops the false claim and adds a ship check, a regex-filtered `git checkout` that reverts test/config edits, before `submit_patch`. A unit test runs the prompt's exact command on a scratch repository.

On the leaderboard, `v3_guard` scored 0.10 and its successor 0.13 / 0.10: inside the noise floor. The harness republished on 2026-10-12 (swegemma 0.2.11) fixes the bug upstream. Its reset passes only tracked paths, and protected files are stripped from the agent's patch before scoring. We had documented it independently on 2026-10-06 (repository commit `0dc6bed`).

### 4.2 Other pitfalls a validator can catch

Each of these cost us or other teams a run, and each is now a check in our validator:
- **Templating.** ADK treats any `{identifier}` in an instruction as a session-state key. A missing key raises `KeyError` at the first model call and fails the task. Only `{problem_description}` and `{hints?}` exist.
- **The 32k request limit.** vLLM rejects prompt + `max_output_tokens` > 32,768, killing long tasks. Keep output at ≤ 8,192 (first noted publicly).
- **The 12-hour cliff.** Exceeding 12 hours errors the whole submission rather than zeroing unfinished tasks. Our check projects 120 × (cap + 1 min setup) and warns.
- **Verification timeout (a null result).** Before 0.2.11, the bundle's `timeout_seconds` also bounded the scoring pytest run, and a public notebook warned it could fail correct patches. Measured over all 129 public tasks, scoring pytest took at most 9.2 s (mean 1.0 s), so this was not a real risk on these repositories. Version 0.2.11 decouples the two.

## 5. Agent design under noise

### 5.1 A navigation skill that looked fine on dev

Skills are the only way to ship custom tools in a declarative bundle. Our `swe` skill ranked files for an issue (BM25 plus definition and path bonuses), printed symbol definitions and outlines, ran targeted tests, and checked the patch before submitting. It had unit tests, capped its output, and its calls didn't count against the tool budget.

| bundle | dev30 (Kaggle env, ceiling 18) | public leaderboard |
|---|---|---|
| sample | 0/30* | ~0.12 (public reports) |
| v1_scaffold (skill) | 5/30 | 0.08 |
| v2_fast (skill) | 6/30 | 0.06 |
| v2_noskill (same prompt, shell only) | — | 0.13 |

\* run at concurrency 4, which penalises the 1-minute budget (Section 3.3).

The two skill bundles are our two lowest scores. Removing the skill while keeping the prompt gave our best. This is the only gap that survives the noise floor (0.06–0.08 vs 0.13), and even it rests on single submissions.

We have hypotheses, but no proof:
- Skill calls don't count against the call cap, yet they consume wall-clock time.
- The skill's instruction block adds context to every request.
- The scripts' heuristics were tuned on four public repositories.

On serial `sound40` (Section 3.3), the skill-free bundle won 6 tasks and lost 1 (20 vs 15, p = 0.125). Dev and leaderboard agree in direction; neither proves it alone. Together they are our best-supported design result: on these budgets, the custom tool layer cost more than it saved. The skill run also timed out more often (17 vs 14 tasks).

### 5.2 Where the points go

We classified all 30 v2_fast dev trajectories:

| outcome | tasks |
|---|---|
| resolved | 6 |
| never made a source edit (still exploring at the 5-min limit) | 11 |
| patch with scratch files only | 3 |
| patch blocked by the test-reset bug | 3 |
| patch, environment gap (missing `inline_snapshot`) | 1 |
| patch, missing public name (one never stated in the issue; one variant skipped) | 2 |
| patch, wrong behaviour | 2 |
| other (no test output; timeout) | 2 |

Fourteen of 30 tasks ended without any source edit. Only four failures were "the model wrote the wrong fix". The resolved tasks made their first edit at a median of call 9, about 120 s into the run. The prompt asked for an edit by call 6, and the model did not comply.

The pattern held on the sound split under harness 0.2.11, where environment gaps and the test-reset bug no longer apply:

| outcome on `sound40` | `v2_noskill` | `v2_fast` |
|---|---|---|
| resolved | 20 | 15 |
| no patch at all | 11 | 12 |
| scratch or test files only | 1 | 3 |
| source patch, hidden tests fail | 8 | 10 |

In both runs, about half the failures produced no patch; nearly all of those timed out while still exploring.

This supports spending budget on *getting to an edit* rather than on verification. It matches a public finding that runs without a source edit by call 12 fail 87% of the time. Our 8-minute variant (`v4_guard_budget`) did not separate from the 5-minute one on the leaderboard; we did not test it on dev.

## 6. Released resources

The repository (Apache-2.0) contains:
- `g4 validate`: compiles a bundle with the real harness and adds the checks of Section 4.2.
- `g4 compare`: paired per-task comparison with an exact McNemar p-value.
- `g4 splits`: frozen, stratified dev splits, including `sound40`.
- `experiments/oracle_kaggle.json`, `oracle_local.json`, `empty_local.json`: per-task reference-fix outcomes (with failure reasons) and empty-patch outcomes.
- A Kaggle eval-kernel generator that embeds the bundle and split for reproducible GPU runs, plus a CPU oracle kernel.
- Harness notes verified against source: templating, skill execution, wheel shadowing, scorer facts. Also the trajectory-based failure breakdown and the replay script for the test-reset bug.
- All bundles of Section 2 and the experiment log with bundle hashes.

## 7. Related work

- **SWE-bench** [1] established issue resolution against hidden tests. SWE-bench Verified [5] found many tasks underspecified or unfairly tested. SWE-Bench+ [6] found that a large share of patches counted as resolved leaked the solution or passed weak tests. Our reference-fix ceilings are the environment-side analogue: tasks that are unsolvable *in a given runtime*.
- **Agent design.** SWE-agent [2] argued that the agent-computer interface matters. Agentless [3] showed that simple localisation and repair pipelines compete with complex agents. OpenHands [4] provides an open agent platform. Our skill result is a cautionary data point for interface design that is tuned on visible repositories.
- **Evaluation noise.** Kapoor et al. [8] call for cost-aware, reproducible agent evaluation. Madaan et al. [9] quantify how much benchmark scores vary, including across models trained with different seeds. Blum and Hardt [7] analyse adaptive overfitting to competition leaderboards. Paired tests for comparing classifiers go back to Dietterich [10].

## 8. Limitations

- **Tiny samples.** Our leaderboard evidence is single or double submissions on ~58 tasks, and our dev evidence is 30–40 tasks with one seed.
- **`sound40` was filtered on the reference fix only.** Two of its tasks pass with an empty patch (Section 3.3). We found them after the runs and report results with and without them.
- **Public repositories differ from the hidden ones.** The public tasks come from four well-known open-source repositories, and the hidden tasks from private ones.
- **The harness changed under us** (0.2.7 → 0.2.11), so leaderboard scores before and after 2026-10-12 aren't strictly comparable.
- **Partly qualitative.** The test-reset finding is exact, but its effect on the hidden set was too small to see on the leaderboard.

## Acknowledgements

The tooling, experiments and analysis were developed with the help of an AI coding assistant (Claude). Public notebooks by other participants ("Budget-Fit Single Agent", "Measure Before You Tune") contributed the 32k-limit and leaderboard-noise observations, credited where used.

## References

[1] C. E. Jimenez et al. SWE-bench: Can Language Models Resolve Real-World GitHub Issues? ICLR 2024.
[2] J. Yang et al. SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering. NeurIPS 2024.
[3] C. S. Xia et al. Agentless: Demystifying LLM-based Software Engineering Agents. arXiv:2407.01489, 2024.
[4] X. Wang et al. OpenHands: An Open Platform for AI Software Developers as Generalist Agents. ICLR 2025. arXiv:2407.16741.
[5] N. Chowdhury et al. Introducing SWE-bench Verified. OpenAI, 2024.
[6] R. Aleithan et al. SWE-Bench+: Enhanced Coding Benchmark for LLMs. arXiv:2410.06992, 2024.
[7] A. Blum, M. Hardt. The Ladder: A Reliable Leaderboard for Machine Learning Competitions. ICML 2015.
[8] S. Kapoor et al. AI Agents That Matter. arXiv:2407.01502, 2024.
[9] L. Madaan et al. Quantifying Variance in Evaluation Benchmarks. arXiv:2406.10229, 2024.
[10] T. G. Dietterich. Approximate Statistical Tests for Comparing Supervised Classification Learning Algorithms. Neural Computation 10(7):1895–1923, 1998.
