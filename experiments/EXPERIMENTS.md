# Experiment log

## Reference-fix ceilings (gold patch applied through the real harness)
| environment | full | dev30 | file |
|---|---|---|---|
| local Docker + per-task wheels | 105/129 | 25/30 | `oracle_local.json` |
| Kaggle notebook (subprocess sandbox) | not yet run | | `g4 oracle-kernel` |

Every run is identified by its bundle hash (`g4 package` prints it) and a frozen split from `splits.json`. Compare variants only on the same split, with the same concurrency.

| date | run | bundle hash | split | conc. | resolved | rate | eval time | notes |
|---|---|---|---|---|---|---|---|---|
| | sample_submission (baseline) | | dev30 | 4 | | | | official sample, 1 min / 10 calls |
| | v1_scaffold | | dev30 | 4 | | | | swe skill + workflow prompt, 5 min / 40 calls |

## Leaderboard submissions
| date | bundle hash | public LB | notes |
|---|---|---|---|
