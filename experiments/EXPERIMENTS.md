# Experiment log

## Reference-fix ceilings (gold patch applied through the real harness)
| environment | full | dev30 | file | main causes of reference-fix failures |
|---|---|---|---|---|
| local Docker + per-task wheels | 105/129 | 25/30 | `oracle_local.json` | offline sandbox (requests), version-sensitive rich rendering |
| Kaggle notebook (subprocess sandbox) | 73/129 | 18/30 | `oracle_kaggle.json` | missing test deps: `inline_snapshot` 27, `dirty_equals` 7, other 1; version differences 13; network 8 (per-task reasons in the file) |

Dev runs below used concurrency 4 and `dev30`; they are not comparable with serial `sound40` runs (ADR 0004). Every run is identified by its bundle hash (`g4 package` prints it) and a frozen split from `splits.json`. Compare variants only on the same split, with the same concurrency.

| date | run | bundle hash | split | conc. | resolved | rate | eval time | notes |
|---|---|---|---|---|---|---|---|---|
| 2026-10-03 | sample_baseline | b092c13256c8 | dev30 | 4 | 0/30 | 0.00 | 532 s | official sample, 1 min / 10 calls; all 30 timed out, 4 patches |
| 2026-10-03 | v1_scaffold (run 3) | 9c208aa2c19a | dev30 | 4 | 5/30 | 0.17 | 2295 s | swe skill + workflow prompt, 5 min / 40 calls; 14 patches, 22 timeouts |
| 2026-10-03 | v2_fast | 0028c7312dfe | dev30 | 4 | 6/30 | 0.20 | 2339 s | v1 + edit by 6th call; 19 patches, 19 timeouts; resolves all v1 tasks + rich_3278 |

All three runs: Kaggle env (ceiling 18/30), scorer memory config (0.80), no server hang. Concurrency 4 slows every turn, which penalizes short budgets much more than the scorer does: the sample scores ~0.12 on the LB but 0/30 here. Compare variants with equal budgets only.

### Failure breakdown of v2_fast on dev30 (from trajectories; 30 tasks)
| outcome | n | causes |
|---|---|---|
| resolved | 6 | first edit at median call 9, ~120 s |
| patch, test-patch conflict | 3 | agent edited lines the hidden test patch changes; harness never reverts them (docs/diagnosis/test-patch-conflicts.md) → `v3_guard` |
| patch, Kaggle-env gap | 1 | fastapi_14349: missing `inline_snapshot`; not an agent failure, absent at the scorer |
| patch, missing public name | 2 | test imports a name the issue never states (fastapi_15030), or a variant the agent skipped (`router.frontend`, fastapi_15800) |
| patch, wrong behaviour | 2 | rich rendering assertions (3296, 3535) |
| patch, scratch files only | 3 | only `repro.py` in the patch (rich_3470, rich_4076, fastapi_14246) → `v3_guard` deletes them, but the source edit was never made |
| patch, other | 2 | requests_6592 (no test output), requests_7505 (timeout) |
| no patch | 11 | 9 never edited (still exploring at the 5-min wall) |

## Leaderboard submissions
LB noise is about ±0.03–0.06: our identical resubmission of v4_guard_budget scored 0.13 then 0.10, and a public notebook's unchanged archive scored 0.12 / 0.10 / 0.06. So a single submission cannot rank variants, and variants are compared on serial dev runs instead (ADR 0004).

Read with that caveat:
- Both skill bundles trail the sample (0.08, 0.06).
- `v2_noskill`, the same prompt without the skill, scored 0.13 (ADR 0005).

The one-factor-per-day LB ablation plan of 2026-10-05 is superseded.

Reading as of 2026-11-07: v2_noskill 0.13 / 0.12 (second on harness 0.2.11), v3_guard 0.10, v4_guard_budget 0.13 / 0.10. The leaderboard shows **no detectable effect** of the guard. The mechanism stays confirmed by the Docker replay (docs/diagnosis/test-patch-conflicts.md); its size on the hidden repos is unknown.

### Leaderboard score vs submission count (public LB snapshot 2026-11-07 12:00 UTC, 5,003 teams)
The leaderboard shows each team's **best** public score, so a team that submits more draws more often from the ±0.03–0.06 noise.

| submissions | teams | mean | median | p90 | share ≥ 0.22 |
|---|---|---|---|---|---|
| 1 | 927 | 0.089 | 0.10 | 0.17 | 0.0% |
| 2 | 691 | 0.109 | 0.12 | 0.17 | 0.3% |
| 3–4 | 934 | 0.128 | 0.15 | 0.18 | 0.2% |
| 5–9 | 1114 | 0.148 | 0.17 | 0.18 | 0.4% |
| 10–19 | 918 | 0.167 | 0.17 | 0.20 | 3.4% |
| 20–49 | 419 | 0.183 | 0.18 | 0.20 | 8.8% |

Spearman(score, submissions) = 0.59. The 77 teams at ≥ 0.22 have a median of 19 submissions; the 782 teams at 0.12–0.13 have a median of 3 (we have 7). Effort confounds this (teams that iterate more also submit more), but it matches the public census: every top public notebook is the same single-agent recipe (240 s / 28 calls / 8 min / 80 turns, T 0.2, no top_k, out 8192, thinking 4096), and identical files score 7–13 of 58 tasks across draws, mean ≈ 10/58 (0.17) for Budget-Fit over 10 draws (author's census). Our four scored draws average 7.25/58 (0.125). The real gap is about 3 tasks, not 7.

### Public evidence (2026-10-06, read from notebooks; not reproduced by us)
| source | config | reported |
|---|---|---|
| "Budget-Fit Single Agent" (author at 0.18 on the LB) | sample prompt + pacing (edit by call 12), 8 min / 28 calls / 80 turns, timeout 240, temp 0.2, thinking 4096, out 8192 | no edit by call 12 → 87% fail; ~half of eventual fixes land after 4 min |
| "Measure before you tune" | identical archive resubmitted | 0.12 / 0.10 / 0.06 |
| strongest public bundles | temp 0.2, top_k 40 or unset, out 8192, thinking 4096 or off | 0.10–0.13 |

### Serial dev runs on harness 0.2.11 (pushed 2026-11-06)
`v2_noskill` and `v2_fast` on `sound40`, concurrency 1, in parallel (kernels `g4-eval-v2-noskill-sound40-h0211`, `g4-eval-v2-fast-sound40-h0211`). They test paper claims 3 (skill vs shell) and 6 (does serial dev track the LB). The 2026-10-06 attempt crashed on the removed `swegemma.models.discovery`.

Results (completed 2026-11-06 23:43 UTC; outputs in `results/kaggle/g4-eval-*-sound40-h0211-1106-2344/`). Ceiling is 40/40, because every `sound40` task passes with the reference fix on Kaggle.

| bundle | hash | resolved | fastapi / rich / requests | session timeouts | median s / calls | eval time |
|---|---|---|---|---|---|---|
| `v2_noskill` | 64e7add9e296 | **20/40** | 12/17, 7/22, 1/1 | 14 | 286 / 24 | 2.8 h |
| `v2_fast` | (swe skill) | 15/40 | 8/17, 6/22, 1/1 | 17 | 295 / 27 | 3.0 h |

`g4 compare`: both 14, noskill only 6 (fastapi_11194, fastapi_14419, fastapi_14851, fastapi_15589, rich_3521, rich_3777), fast only 1 (rich_4079), neither 19. Exact McNemar **p = 0.125**. The direction agrees with the LB (0.13 vs 0.06), so claim 6 holds in direction, but the result is not significant.

**Unsound task found:** `fastapi_14851` passes with an **empty patch** (noskill made 0 edits and called submit; the hidden tests ran 9 passed, exit 0). `v2_fast` timed out on it, so the tests never ran (exit -1). Excluding it: 19 vs 15, discordant 5 vs 1, p = 0.22. A sound split must also check that the empty patch fails. Empty-patch replay over all of `sound40` (local Docker, `python -m g4agent.oracle_run --split sound40 --plan empty`, 2026-11-07): **2/40 pass with no edit**, `fastapi_14851` (test patch only adds coverage tests for existing behaviour) and `fastapi_14077` (test patch only swaps `status.HTTP_422_UNPROCESSABLE_ENTITY` for `422`). Excluding both: noskill 18/38, fast 14/38, discordant 5 vs 1, p = 0.22. Over all 129 public tasks (`--split full --plan empty`, `experiments/empty_local.json`), these are the **only two**. `fastapi_14077` is the task of the test-reset Docker replay: the agent's test edit turned a free task into a failure.

Outcome breakdown (patch file contents):

| outcome | noskill | fast |
|---|---|---|
| resolved | 20 | 15 |
| no patch (10 / 11 of them timed out) | 11 | 12 |
| scratch or test files only | 1 | 3 |
| source patch, hidden tests fail (3 / 4 timed out) | 8 | 10 |

Harness 0.2.11 observations:
- A timed-out task that has a patch is still graded (exit 1); one without a patch gets exit -1. None of the 8 timed-out patches resolved.
- `v2_fast` `rich_3772` took 604.65 s, about 2× the 5-min cap, while its scoring pytest timed out (exit 124). So a single task can exceed `max_time_minutes` by the verification timeout (300 s), and the 12 h projection should add that worst case.

### Serial dev plan on `sound40` (concurrency 1; compare with `g4 compare`)
| order | bundle | single change vs v2_noskill | question |
|---|---|---|---|
| 1 | `v2_noskill` | baseline | does serial dev rank like the LB? |
| 2 | `v3_budget` | timeout 240, 8 min / 28 calls / 80 turns | does the measured budget envelope help? (the timeout part should be neutral: scoring pytest takes ≤ 9.2 s on all 129 public tasks) |
| 3 | `v3_sampling` | temp 0.2, no top_k, thinking 4096, out 8192 | does longer thinking pay for its time? |
| 4 | `v3_edit12` | localize ≤10 calls, first edit by call 12, no exploration after 20 | is "edit by call 6" too aggressive? |
| 1b | `v3_guard` | prompt: no test/config edits, ship check reverts them and removes scratch files | how many tasks did test-patch conflicts and scratch-only patches cost? (in v2_fast dev30: 3 conflicts + 3 scratch-only of 19 patches) |
| 5 (optional) | `v2_fast` | swe skill | is the skill effect real (paper)? |

Winners stack into `v4`. Submit only when dev shows ≥ +4 of 40 over the current best.

Notes:
- `v3_budget` leaves the prompt unchanged: its pace rule is relative ("less than a quarter of the time or calls left").
- `g4 validate` warns that `v3_budget` takes 18 h in the worst case. Budget-Fit reports that the 28-call cap ends most tasks well before 8 min. The serial dev run measures mean task time; project 120 × that before any submission.

Code competition: the zip must be a kernel output. Run `g4 submission-kernel <bundle>`, push it, then `kaggle competitions submit gemma-4-developer-agent -k sebmontreal/g4-submission -f submission.zip -v <N>`. Wait for version N's own run to finish (the status call may still show the previous version's COMPLETE), and check that its log prints the expected bundle hash.

| date | ref | bundle hash | public LB | notes |
|---|---|---|---|---|
| 2026-11-07 | 58091025 | adce53d47bc8 | pending | v3_guard identical resubmission (0.10 on 0.2.7), **harness swegemma 0.2.11** |
| 2026-11-06 | 58068665 | 64e7add9e296 | **0.12** | v2_noskill identical resubmission (0.13 on 0.2.7), **harness swegemma 0.2.11**; within the noise floor (rows below were scored on 0.2.7 unless noted) |
| 2026-10-08 | 56958315 | 689a8fb46e18 | **0.10** | v4_guard_budget, identical resubmission: 0.13 then 0.10, so our own leaderboard noise is ±0.03 (2 tasks of ~58) |
| 2026-10-07 | 56893672 | 689a8fb46e18 | **0.13** | v4_guard_budget: v3_guard + 240 s, 8 min / 28 calls / 80 turns; finished inside 12 h; ties v2_noskill (within the ±0.06 noise) |
| 2026-10-06 | 56885293 | adce53d47bc8 | **0.10** (rerun by the host after the 2026-10-06 Kaggle error wave; requested in discussion 743683) | v3_guard: v2_noskill + ship check (reverts test/config edits, removes scratch files); docs/diagnosis/test-patch-conflicts.md |
| 2026-10-05 | 56836396 | 64e7add9e296 | **0.13** | v2_noskill: v2_fast prompt, shell commands instead of the swe skill; our best |
| 2026-10-03 | 56810022 | 0028c7312dfe | **0.06** | v2_fast: edit by 6th call, 5 min / 40 calls; dev30 6/30 vs v1 5/30 |
| 2026-10-02 | 56783164 | 9c208aa2c19a | **0.08** | v1_scaffold: swe skill + red/green workflow, 5 min / 40 calls; below sample (~0.12), see docs/diagnosis/v1-regression.md |
