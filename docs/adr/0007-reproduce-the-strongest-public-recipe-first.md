# Build on the public Budget-Fit recipe; rank bundles by mean of draws (amends 0004 and 0005)

On 2026-11-07 our best bundles scored 0.12–0.13 while about 77 teams showed ≥ 0.22. The public leaderboard shows each team's **best** submission, and that score rises with the number of submissions (Spearman 0.59 over 5,003 teams; the ≥ 0.22 teams have a median of 19 submissions, the 0.12–0.13 teams a median of 3; `experiments/EXPERIMENTS.md`). All ten strongest public notebooks are one single-agent recipe whose identical files score 7–13 of 58 tasks across draws. Its best-measured form, Budget-Fit, averages about 10/58 (0.17) over 10 draws (its author's census); our four draws average 7.25/58 (0.125). The real gap is about 3 tasks, not 7, and one draw (±2 tasks) cannot confirm it.

We therefore:
- take Budget-Fit, unchanged, as the new base (`submissions/v5_budgetfit`, attribution in `submissions/ATTRIBUTION.md`). It is the only public recipe with a mean over many draws; its descendants (SuperAgent, flexonafft, "Baseline LB 0.24") claim single best draws and average about 8.7/58 in the same census. Their prompt ideas become candidate changes;
- keep the ADR 0004 dev gate (paired serial run on the sound split, ≥ +4 of 40) for every change on top of the base;
- spend every daily submission slot on the bundle with the best evidence so far, repeats included, and log each draw. Bundles are ranked by the mean of their draws plus their paired dev result, never by their best draw;
- select the final submissions for the private leaderboard by that same evidence, not by public score.

## Consequences
- Our v1–v4 bundles stay in the repository as the paper's evidence; they are no longer the base for new variants.
- The daily rotation of old bundles ends once `v3_guard` (58091025) scores.
- Our public leaderboard score will rise with the number of draws whatever the bundle does. That rise is not progress and is never reported as such.
- The paper reports the best-of-N effect in Section 3.1 as a measurement finding.

## Considered options
- Keep improving our own line: rejected. Nothing in v2–v4 left the 0.06–0.13 band, and the recipe's budgets alone (`v4_guard_budget`) did not close the gap, so the difference sits in sampling and prompt.
- Base on the bundle with the highest claimed score (0.24): rejected, because that claim is a best draw and its file family averages below Budget-Fit.
- Confirm the base with one reproduction submission: rejected as a test (a single draw is as wide as the gap); the base still gets submitted, as the first of many logged draws.
