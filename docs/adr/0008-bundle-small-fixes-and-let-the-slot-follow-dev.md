# Test small fixes as one bundle; the daily slot follows the dev point estimate (amends 0004)

The lever analysis of 2026-11-07 (harness source plus all 80 `sound40` trajectories, each claim checked by a skeptic) found no single change worth more than about +2 of 40 tasks. A paired run on 40 tasks cannot see +1, so the ADR 0004 bar (≥ +4 of 40) is out of reach for any one fix, and testing them one at a time would spend the GPU quota on null results.

We therefore:
- group the changes that are low-risk and mechanistically verified into one candidate (`v6_issue_recovery` = `v5_budgetfit` + the issue copied into the system prompt with a recovery rule for history compaction, a recovery rule for malformed `edit_file` calls, and the three prompt edits of the public "Baseline LB 0.24" notebook) and compare it paired against its base;
- test risky changes with an unknown sign (`include_thoughts: false`, thinking-budget changes) on their own, after the base's traces show how often they matter;
- run dev comparisons on `sound71`, every task whose reference fix passes on Kaggle and whose empty patch fails, for about twice the discordant tasks of `sound40`;
- give the daily submission slot to whichever bundle resolves more tasks in the paired dev run, ties going to the incumbent. A slot is one draw either way, so following the point estimate costs nothing.

The ≥ +4 bar still applies to what we claim in writing.

## Consequences
- A bundle's dev gain cannot be attributed to one of its parts. When a bundle wins, its parts can be ablated later if the quota allows.
- `sound71` results are not comparable with `sound40` results.
