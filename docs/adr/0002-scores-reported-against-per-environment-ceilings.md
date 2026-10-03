# Scores are reported against the reference-fix ceiling of their environment

The local, Kaggle and scoring environments resolve different subsets of tasks even with the known-correct patch: 105, 73 and an unknown number out of 129. The Kaggle image lacks test packages such as `inline_snapshot`. So a raw dev-run score mixes agent quality with environment gaps.

Every dev-run score is therefore logged alongside the ceiling of the environment it ran in (`experiments/oracle_*.json`), and variants are compared only within one environment and one dev split. We chose this over "fixing" the Kaggle environment by installing extra packages, which would drift further from the unknown scoring environment.

## Consequences
Leaderboard scores can't be predicted from dev runs in absolute terms, only directionally.
