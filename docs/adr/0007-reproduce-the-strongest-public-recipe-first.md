# Build on the public Budget-Fit recipe; rank bundles by mean of draws (amends 0004 and 0005)

On 2026-11-07 our best bundles scored 0.12–0.13 while about 77 teams showed ≥ 0.22. The public leaderboard shows each team's **best** submission, and that score rises with the number of submissions (Spearman 0.59 over 5,003 teams; the ≥ 0.22 teams have a median of 19 submissions, the 0.12–0.13 teams a median of 3; `experiments/EXPERIMENTS.md`). All ten strongest public notebooks are one single-agent recipe; one of its file sets scored 7–13 of 58 tasks over five draws. Its best-measured form, Budget-Fit, averages 0.166 (about 10/58) over 10 draws (Dariush Afshar's census of public notebooks); our four draws average 7.25/58 (0.125). The real gap is about 3 tasks, not 7, and one draw (±2 tasks) cannot confirm it.

We therefore:
- take Budget-Fit, unchanged, as the new base (`submissions/v5_budgetfit`, attribution in `submissions/ATTRIBUTION.md`). It is the only public recipe with a mean over many draws; its descendants (SuperAgent, flexonafft, "Baseline LB 0.24") claim single best draws and average about 8.7/58 in the same census. Their prompt ideas become candidate changes;
- keep the ADR 0004 dev gate (paired serial run on the sound split, ≥ +4 of 40) for every change on top of the base;
- spend every daily submission slot on the bundle with the best evidence so far, repeats included, and log each draw. Bundles are ranked by the mean of their draws plus their paired dev result, never by their best draw;
- select the final submissions for the private leaderboard (the rules allow up to two) by that same evidence, not by public score.

## Consequences
- Our v1–v4 bundles stay in the repository as the paper's evidence; they are no longer the base for new variants.
- The daily rotation of old bundles ends once `v3_guard` (58091025) scores.
- Our public leaderboard score will rise with the number of draws whatever the bundle does. That rise is not progress and is never reported as such.
- The paper reports the best-of-N effect in Section 3.1 as a measurement finding.

## Considered options
- Keep improving our own line: rejected. Nothing in v2–v4 left the 0.06–0.13 band, and the recipe's budgets alone (`v4_guard_budget`) did not close the gap, so the difference sits in sampling and prompt.
- Base on the bundle with the highest claimed score (0.24): rejected, because that claim is a best draw and its file family averages below Budget-Fit.
- Confirm the base with one reproduction submission: rejected as a test (a single draw is as wide as the gap); the base still gets submitted, as the first of many logged draws.

## Note (2026-11-10)
The user set the goal for the last 22 days: the final private-leaderboard ranking, not the public number. Every daily slot until 2026-12-01 goes to a draw of the bundle with the best evidence (`v5_budgetfit` for now; the slot follows dev per ADR 0008). Two draws so far scored 0.17 and 0.17. Before spending GPU quota, the public notebooks published after the census are read (not run) and compared with `v5`; only the most promising one gets a paired `sound71` run, with the user's go-ahead.

## Note (2026-11-14): leader comparison
The leader (Yurnero, 0.29) has published no method; the 0.24 tie is single best draws of Budget-Fit relatives (Idris v24: one 0.24 draw, siblings 0.15–0.17; his local run of a bundle identical to `v5` tied his own prompt, 18 vs 19 of 46). Decided with the user:
- Bundle-level changes only (prompt, sampling, budgets, skills). No LoRA: public adapters scored 0.06–0.15, cost about 29% more time per task (≈ 11.7 h projected) and silenced the thinking channel.
- The target is the expected private score (mean of draws), with the public 0.29 as a reference only.
- Failed draws (CONTEXT.md) leave the mean but count in a failure rate.
- GPU cap for this competition: one more paired `sound71` run in the week of 2026-11-14 and three the week after.
- Next candidate: `v9_complete` (`v5` + Idris v30's completeness step), temperature set by the `v8_temp1` result, pushed only after that result and the user's go-ahead.
- Final selection: two different bundles with similar means, so one failure mode cannot sink both private submissions.
