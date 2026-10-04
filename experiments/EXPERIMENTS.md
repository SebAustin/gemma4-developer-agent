# Experiment log

## Reference-fix ceilings (gold patch applied through the real harness)
| environment | full | dev30 | file | main causes of reference-fix failures |
|---|---|---|---|---|
| local Docker + per-task wheels | 105/129 | 25/30 | `oracle_local.json` | offline sandbox (requests), version-sensitive rich rendering |
| Kaggle notebook (subprocess sandbox) | 73/129 | 18/30 | `oracle_kaggle.json` | missing test deps: `inline_snapshot` 27, `dirty_equals` 7, other 1; version differences 13; network 8 (per-task reasons in the file) |

Every run is identified by its bundle hash (`g4 package` prints it) and a frozen split from `splits.json`. Compare variants only on the same split, with the same concurrency.

| date | run | bundle hash | split | conc. | resolved | rate | eval time | notes |
|---|---|---|---|---|---|---|---|---|
| 2026-10-03 | sample_baseline | b092c13256c8 | dev30 | 4 | 0/30 | 0.00 | 532 s | official sample, 1 min / 10 calls; all 30 timed out, 4 patches |
| 2026-10-03 | v1_scaffold (run 3) | 9c208aa2c19a | dev30 | 4 | 5/30 | 0.17 | 2295 s | swe skill + workflow prompt, 5 min / 40 calls; 14 patches, 22 timeouts |
| 2026-10-03 | v2_fast | 0028c7312dfe | dev30 | 4 | 6/30 | 0.20 | 2339 s | v1 + edit by 6th call; 19 patches, 19 timeouts; resolves all v1 tasks + rich_3278 |

All three runs: Kaggle env (ceiling 18/30), scorer memory config (0.80), no server hang. Concurrency 4 slows every turn, which penalizes short budgets much more than the scorer does: the sample scores ~0.12 on the LB but 0/30 here. Compare variants with equal budgets only.

## Leaderboard submissions
Code competition: the zip must be a kernel output. Run `g4 submission-kernel <bundle>`, push it, then `kaggle competitions submit gemma-4-developer-agent -k sebmontreal/g4-submission -f submission.zip -v <N>`.

| date | ref | bundle hash | public LB | notes |
|---|---|---|---|---|
| 2026-10-02 | 56783164 | 9c208aa2c19a | **0.08** | v1_scaffold: swe skill + red/green workflow, 5 min / 40 calls; below sample (~0.12), see docs/diagnosis/v1-regression.md |
