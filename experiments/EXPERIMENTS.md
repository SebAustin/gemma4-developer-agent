# Experiment log

## Reference-fix ceilings (gold patch applied through the real harness)
| environment | full | dev30 | file | main causes of reference-fix failures |
|---|---|---|---|---|
| local Docker + per-task wheels | 105/129 | 25/30 | `oracle_local.json` | offline sandbox (requests), version-sensitive rich rendering |
| Kaggle notebook (subprocess sandbox) | 73/129 | 18/30 | `oracle_kaggle.json` | missing test deps: `inline_snapshot` 27, `dirty_equals` 7, other 1; version differences 13; network 8 (per-task reasons in the file) |

Every run is identified by its bundle hash (`g4 package` prints it) and a frozen split from `splits.json`. Compare variants only on the same split, with the same concurrency.

| date | run | bundle hash | split | conc. | resolved | rate | eval time | notes |
|---|---|---|---|---|---|---|---|---|
| | sample_submission (baseline) | | dev30 | 4 | | | | official sample, 1 min / 10 calls |
| | v1_scaffold | | dev30 | 4 | | | | swe skill + workflow prompt, 5 min / 40 calls |

## Leaderboard submissions
| date | bundle hash | public LB | notes |
|---|---|---|---|
