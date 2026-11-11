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
| resolved | 6 | first source edit at median call 12, ~135 s (call 9, ~120 s if scratch-file writes count; corrected 2026-11-07) |
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

Spearman(score, submissions) = 0.59. The 77 teams at ≥ 0.22 have a median of 19 submissions; the 782 teams at 0.12–0.13 have a median of 3 (we have 7). Effort confounds this (teams that iterate more also submit more), but it matches the public census: every top public notebook is the same single-agent recipe (240 s / 28 calls / 8 min / 80 turns, T 0.2, no top_k, out 8192, thinking 4096), and identical files score across draws as follows: mean 0.166 (0.13–0.18), about 10/58, for Budget-Fit over 10 draws (Dariush Afshar's census, quoted in public notebooks; not ours); the budget-aware files scored 7, 7, 9, 11, 13 of 58 (reported in Dmitrii Gluzdov's "Public Agent Ideas and Evidence"). Our four scored draws average 7.25/58 (0.125). The real gap is about 3 tasks, not 7.

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
| `v2_noskill` | 64e7add9e296 | **20/40** | 12/17, 7/22, 1/1 | 18 (4 still resolved) | 286 / 24 | 2.8 h |
| `v2_fast` | (swe skill) | 15/40 | 8/17, 6/22, 1/1 | 18 (1 still resolved) | 295 / 27 | 3.0 h |

Timeouts are counted from the harness log (`agent timed out`), corrected on 2026-11-07. `task_results.jsonl` leaves `error` empty when a timed-out task resolves through the working-tree fallback, so the first count (14 / 17) missed fastapi_5624, 14419, 13537, 11194 (noskill) and fastapi_5624 (fast).

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
- A timed-out task that has an edit is still graded: the harness diffs the working tree (`agent_runner.py` ~1048-1078); one without an edit gets exit -1. Five timed-out tasks resolved this way (4 noskill, 1 fast); the earlier note that none did came from the incomplete `error` field.
- `v2_fast` `rich_3772` took 604.65 s, about 2× the 5-min cap, while its scoring pytest timed out (exit 124). So a single task can exceed `max_time_minutes` by the verification timeout (300 s), and the 12 h projection should add that worst case.

### Base and first candidate on `sound71` (pushed 2026-11-07, ADR 0007 and 0008)
`sound71`: every task whose reference fix passes on Kaggle and whose empty patch fails (41 rich, 29 fastapi, 1 requests; it contains 38 of `sound40`). Serial, concurrency 1, harness 0.2.11.
Caveat (found 2026-11-08 by the paper fact-check): the empty-patch replay ran in local Docker (`empty_local.json`), and for 4 `sound71` tasks the reference fix also fails locally (`requests_6644`, `rich_3472`, `rich_3782`, `rich_4079`; all 4 are in `sound40` too). For them "the empty patch fails" is uninformative: an empty patch could still pass on Kaggle. Not checked on Kaggle.

| bundle | hash | change vs base | kernel | resolved |
|---|---|---|---|---|
| `v5_budgetfit` | a975adbcd250 | public Budget-Fit recipe, unchanged (attribution in `submissions/ATTRIBUTION.md`) | `g4-eval-v5-budgetfit-sound71` v1 | **29/71** |
| `v6_issue_recovery` | e0883c598cf0 | prompt only: issue copied into the system prompt + `git diff` recovery after history compaction; malformed `edit_file` recovery via `run_command`; "Baseline LB 0.24" edits (protect `pytest.ini`/`conftest.py`, change every sync/async variant, `git status --short && git diff` before submit), scratch scripts under `/tmp` | `g4-eval-v6-issue-recovery-sound71` v1 | **28/71** |

Results (2026-11-07; outputs in `results/kaggle/g4-eval-v{5-budgetfit,6-issue-recovery}-sound71-h0211-1107`):
- **`v6` vs `v5`:** both 26, `v5` only 3 (fastapi_15589, fastapi_9555, rich_3278), `v6` only 2 (fastapi_14419, fastapi_5624), neither 40; exact McNemar p = 1.0. `v5` keeps the slot (ADR 0008). `v6` is rejected as a bundle.
- **What `v6` cost:** eval 5.70 h vs 5.37 h (mean 289 s vs 272 s per task). The issue copy enlarges every request, so compaction fired in 56/71 tasks (median first at agent step 14) against 47/71 (step 16). Its rules did run: `git status --short` after a compaction in 11/56 tasks, and malformed-`edit_file` replies fell from 76 (9 tasks) to 29 (11 tasks). The malformed-edit rule is worth keeping without the issue copy.
- **The call cap binds more than the time cap:** 20/71 `v5` tasks used all 28 calls (2 resolved), 27/71 in `v6` (4 resolved). Duration ≥ 8 min: 10 in `v5` (1 resolved), 12 in `v6` (2 resolved).
- **`v5` vs `v2_noskill` on the 38 shared tasks** (runs a day apart, different budgets: noskill 5 min / 40 calls / thinking 1536 / T 0.3): `v2_noskill` 18, `v5` 14; noskill only 5 (fastapi_14419, fastapi_14873, fastapi_5624, rich_3521, rich_3777), `v5` only 1 (rich_3278); p = 0.22. Three of the five hit `v5`'s 28-call cap; noskill solved them in 23–27 calls. `v5` vs `v2_fast`: 14 vs 14. This runs against the leaderboard (Budget-Fit census mean 0.166 over 10 draws, ours 0.12–0.13), so dev and LB disagree on this pair; our own `v5` draws decide it.
- **Scorer time:** 120 tasks × mean task time = 9.1 h (`v5`), 9.6 h (`v6`), 8.4 h (`v2_noskill`), before setup and slow-scorer days.
- **Earlier thinking is replayed every turn:** with `include_thoughts: true` the next prompt grows by a median 1.12× the previous completion (`v5`, completions > 300 tokens); generated tokens make about 40% of prompt growth before the first compaction. On 0.2.11 `include_thoughts: false` keeps reasoning but strips it from history, so it should slow prompt growth and delay compaction. Its sign on resolves is still unknown.
- Compaction counter used here (prompt tokens fall > 30% after reaching 14,336) finds 30/40 on `v2_noskill`, where the earlier count found 31/40. Script: `scripts/trace_stats.py <results dir>`. Resolved 2026-11-08: 33/40 tasks reach 14,336 tokens, but 3 (`rich_3180`, `rich_3506`, `rich_3894`) reach it only on their last model call, so no compaction ever affects them; no task shows a smaller drop. 30/40 (median first at call 19.5) is the count of observed compactions and the one the paper uses (Sections 4.2 and 5.3 now share this counter). The earlier 31 matches neither rule and is retired.

Next candidates on `sound71` (both pushed 2026-11-07 19:03 UTC as v1, user go-ahead; about 5.5 GPU-h each; embedded bundles decoded and diffed against `submissions/` before the push):

| bundle | hash | change vs `v5` | why | kernel dir |
|---|---|---|---|---|
| `v7_no_thoughts` | 513241012bc3 | `include_thoughts: false` | earlier thinking makes ~25% of prompt growth (40% generated × ~60% thinking); stripping it should delay compaction and shorten prefill | `kaggle/runs/g4-eval-v7-no-thoughts-sound71` |
| `v7_calls40` | c2a7ea4b9328 | 40 calls (prompt text matches), thinking 1536 | the 28-call cap ends 28% of tasks (2/20 resolved); `v2_noskill`'s budget won 5–1 on the shared tasks. Thinking 1536 pays for the extra calls: 40 calls at 4096 would project ~10.3 h, too close to 12 h | `kaggle/runs/g4-eval-v7-calls40-sound71` |

Results (2026-11-08; outputs in `results/kaggle/g4-eval-v7-{no-thoughts,calls40}-sound71-h0211-1108`; `scripts/budget_stats.py` and `scripts/trace_stats.py`):

| bundle | resolved | vs `v5` (only / only) | McNemar p | eval time | 120-task projection | tasks ≥ 8 min | at call cap |
|---|---|---|---|---|---|---|---|
| `v5_budgetfit` | 29/71 | — | — | 5.37 h | 9.1 h | 10 (1 resolved) | 20 at 28 (2 resolved) |
| `v7_no_thoughts` | 24/71 | 4 / 9 | 0.27 | 6.28 h | 10.6 h | 19 (1 resolved) | 10 at 28 (1 resolved) |
| `v7_calls40` | 29/71 | 5 / 5 | 1.0 | 6.01 h | 10.2 h | 15 (1 resolved) | 13 at 40 (0 resolved) |

- **`v7_no_thoughts` is rejected.** Stripping thinking from history did delay compaction (26/71 tasks against 47/71), but replies polarized rather than all getting longer: the median model call stayed at 119 tokens, near-empty calls (≤ 50 tokens) rose from 17.5% to 36.2%, and calls of 1,000+ tokens from 7.0% to 12.1% (61% of completion tokens against 46%). Mean completion 434 tokens per model call against 317. The extra decode time pushed 19 tasks past 8 min against 10, and resolves fell 29 → 24 (p = 0.27, not significant). This settles the "unknown sign" lever below: negative on time, not significant on resolves. (Corrected 2026-11-08 after the paper fact-check: this note first said the model "thinks longer on every call"; `budget_stats.py` now prints the distribution.)
- **`v7_calls40` is rejected.** It ties `v5` and costs 1.1 h more of scorer time, so the 12 h limit would hold only about 1.8 h of headroom before setup. Of the 20 tasks that hit `v5`'s 28-call cap, it resolved 5, but only `rich_3777` (35 calls) needed more than 28 calls; the other four finished in 12–26 calls, so they came from run-to-run variation, not the budget. The 13 tasks that used all 40 calls resolved none. The call cap is not where tasks are lost: tasks that exhaust it are almost always stuck.
- **Dev run-to-run noise:** both `v7` runs resolved the same three tasks that `v5` missed (`fastapi_14873`, `fastapi_5624`, `rich_3676`), at 18–37 calls. `v7_calls40` changes three things (call cap 28 → 40, thinking 4096 → 1536, the prompt's budget lines), so its 5 / 5 tie with `v5` is not a pure noise estimate, and no identical-config rerun exists on `sound71`. Still, a variant that ties differs on 10 of 71 tasks, so one paired 71-task run cannot detect a lever worth +1 or +2. (Corrected 2026-11-08: this note first called the two configs "near-identical".)
- **`v5` keeps the slot** (Q14: ties go to the incumbent).

Queued for the 2026-11-14 quota reset (user go-ahead 2026-11-10 and 2026-11-11): `v8_temp1` (`v5` + temperature 1.0, top_k 64; kernel `g4-eval-v8-temp1-sound71`) and an **identical `v5` rerun** (`g4-eval-v5-budgetfit-sound71-rerun`, embedded bundle verified file-for-file against the original kernel). The rerun gives the first same-config dev noise estimate on `sound71`; `v8` is judged against both `v5` runs.

Lever analysis behind `v6` (2026-11-07, harness source + all 80 `sound40` traces, each lever checked by a skeptic):
- **History compaction** (scorer config, ADK `EventsCompactionConfig`): at 14,336 prompt tokens all but the last 5 events are summarized, text only, ~25 s per summary. Fired in 30/40 noskill tasks at a median of call 19.5 (corrected 2026-11-08 from 31/40 at call 19, see the counter note above); exact-repeat tool calls rose from 8% to 17% after it. Estimated 0 to +2.
- **Malformed `edit_file` loops**: 86 failed calls (85 with a stray backtick closing a string), resent unchanged, ~670 s per run; they cost turns but not counted calls. 0 to +1.
- **Time**: model decoding is 96% of task time, thinking ~60% of the 5 minutes, 35 tok/s single stream. Thinking 4096 at a 5-min cap would cost 1–3 tasks; fine at 8 min.
- **Refuted**: an earlier call cap to move the harness's budget warning (the model does not react to it). **About 0**: graph tools, batched lookups, max_output_tokens 4096, thinking 768–1024. **Unknown sign (−3 to +3)**: `include_thoughts: false` (measured 2026-11-08 as `v7_no_thoughts`: −5, see above).
- Six `sound40` tasks need names the issue never states (fastapi_15661, 15280, 14479, 14487, 15800, rich_3938); practical ceiling about 34/40.

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
- The team may have only one pending submission. A submit sent while another is still scoring fails with a bare `400 Bad Request` from the CLI; the server's message reads "Your team already has 1 pending submissions" (seen 2026-11-08, while `v3_guard` was scoring). A submit sent after the day's slot is used gets the same bare `400` (seen 2026-11-08 20:19 UTC, nothing pending; the slot counts UTC days, so 18:00 CST is the reset). A rejected submit does not use the day's slot. A run scores for up to 12 h (58144231 took about 13 h 5 min from submit to score, so queueing can add an hour), so a submission sent after about 12:00 UTC can still be pending when the next slot opens at 00:00 UTC and delay it. Submit before 12:00 UTC to keep the next day's slot free.

| date | ref | bundle hash | public LB | notes |
|---|---|---|---|---|
| 2026-11-11 | 58222745 | a975adbcd250 | **0.01** | v5_budgetfit draw 3 (same files that scored 0.17 twice; about 0–1 of ~58 tasks, so most likely a broken scoring run, e.g. a model-server hang, not the recipe; the scorer log is not visible to us), identical resubmission of kernel v8, **harness swegemma 0.2.11**; submitted 02:57 UTC (user go-ahead 2026-11-10 for daily draws until Dec 1; later draws are submitted at 00:01 UTC by the daily slot job) |
| 2026-11-09 | 58144231 | a975adbcd250 | **0.17** | v5_budgetfit identical resubmission of kernel g4-submission v8 (zip sha256 aa9d6f89f529): second draw of the public Budget-Fit recipe, **harness swegemma 0.2.11**; same score as 58109075, both draws inside the census range 0.13–0.18; submitted 00:01:55 UTC by the scheduled slot job, scored between 13:05 and 13:11 UTC, about 13 h 5 min after submission, so submit-to-score can exceed 12 h |
| 2026-11-08 | 58109075 | a975adbcd250 | **0.17** | v5_budgetfit: public Budget-Fit recipe unchanged (census draws 0.13–0.18, mean 0.166); our first own draw, 0.17 ≈ 10 of ~58 tasks, inside the census range and about 3 tasks above our own bundles' mean (7.25); the team's best, but not our design; finished inside 12 h on 0.2.11; **harness swegemma 0.2.11**; kernel g4-submission v8, zip sha256 aa9d6f89f529; the 00:00 UTC submit was refused while 58091025 was still pending |
| 2026-11-07 | 58091025 | adce53d47bc8 | **0.12** | v3_guard identical resubmission (0.10 on 0.2.7), **harness swegemma 0.2.11**; ties v2_noskill's 0.12 on 0.2.11, which ends the old-bundle rotation |
| 2026-11-06 | 58068665 | 64e7add9e296 | **0.12** | v2_noskill identical resubmission (0.13 on 0.2.7), **harness swegemma 0.2.11**; within the noise floor (rows below were scored on 0.2.7 unless noted) |
| 2026-10-08 | 56958315 | 689a8fb46e18 | **0.10** | v4_guard_budget, identical resubmission: 0.13 then 0.10, so our own leaderboard noise is ±0.03 (2 tasks of ~58) |
| 2026-10-07 | 56893672 | 689a8fb46e18 | **0.13** | v4_guard_budget: v3_guard + 240 s, 8 min / 28 calls / 80 turns; finished inside 12 h; ties v2_noskill (within the ±0.06 noise) |
| 2026-10-06 | 56885293 | adce53d47bc8 | **0.10** (rerun by the host after the 2026-10-06 Kaggle error wave; requested in discussion 743683) | v3_guard: v2_noskill + ship check (reverts test/config edits, removes scratch files); docs/diagnosis/test-patch-conflicts.md |
| 2026-10-05 | 56836396 | 64e7add9e296 | **0.13** | v2_noskill: v2_fast prompt, shell commands instead of the swe skill; our best |
| 2026-10-03 | 56810022 | 0028c7312dfe | **0.06** | v2_fast: edit by 6th call, 5 min / 40 calls; dev30 6/30 vs v1 5/30 |
| 2026-10-02 | 56783164 | 9c208aa2c19a | **0.08** | v1_scaffold: swe skill + red/green workflow, 5 min / 40 calls; below sample (~0.12), see docs/diagnosis/v1-regression.md |
