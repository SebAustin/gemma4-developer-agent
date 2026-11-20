agency-mission: active

# Mission: enhance the bundle to beat the leader

- **Tier:** standard. **Profile:** ml (competition). **Started:** 2026-11-20.
- **Oracle:** Kaggle scorer (1 submission/UTC day, 13–18 h to score, 1 pending at a time). Local proxy: `sound71` dev split on Kaggle GPU (gated: spends the shared weekly quota).
- **Risk signals:** none in code. Gated actions: Kaggle kernel pushes, extra submissions, new datasets.
- **Pass bar:** a bundle whose leaderboard mean beats `v5` (0.173 over 7 sound draws) beyond noise. **Stretch:** beat the leader (0.29 best draw).
- **Verification owed:** headroom analysis (running); GPU go-ahead for any dev run.

## State
- Baseline `v5_budgetfit`: sound draws 0.17, 0.17, 0.12, 0.22, 0.18, 0.17, 0.18 (mean 0.173), 1 failed draw (0.01).
- `v8_temp1`: 0.17, 0.15; draw 11 pending.
- Dev levers tested on `sound71`, all tied with `v5` within ±3 tasks: v6, v7 ×2, v8, v9.
- Deadline: 2026-12-02. Daily draw job alternates v8_temp1 / v5.

## Round log
- R0 (2026-11-20): headroom analysis over existing dev runs dispatched (no GPU).
