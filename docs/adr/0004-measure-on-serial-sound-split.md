# Variants are compared on serial dev runs over sound tasks, not on the leaderboard

The leaderboard moves by about ±0.06 (±3–4 of ~58 tasks) between identical submissions. A public notebook resubmitted one unchanged archive and got 0.12, 0.10 and 0.06. One submission a day therefore cannot separate variants.

Dev runs now use:
- the `sound40` split: tasks whose reference fix resolves in the Kaggle environment (`experiments/oracle_kaggle.json`), so a miss is the agent's;
- concurrency 1, because the scorer runs tasks one after another and concurrency 4 slows every turn;
- `g4 compare`: a paired per-task comparison with an exact McNemar p-value.

The leaderboard only confirms large dev gains (≥ +4 of 40), plus an occasional resubmission of the best bundle.

## Consequences
- A serial run of 40 tasks costs ~3.5–5 GPU-h of the 45 h weekly quota, so about 5 variants a week.
- `sound40` is rich-heavy (22 rich, 17 fastapi, 1 requests), because the Kaggle environment breaks many fastapi reference fixes. The hidden set comes from other repositories anyway, so rank variants on it; don't treat it as a score estimate.
- Dev runs at concurrency 4 (all runs before 2026-10-06) are not comparable with serial ones.
