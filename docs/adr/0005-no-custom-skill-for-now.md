# Bundles ship without the swe skill (supersedes 0003, provisionally)

Both skill bundles scored below the sample on the leaderboard (`v1_scaffold` 0.08, `v2_fast` 0.06). `v2_noskill` keeps the `v2_fast` prompt but uses only shell commands, and scored 0.13. Given the ±0.06 leaderboard noise, this is suggestive, not proven. Candidates therefore start from `v2_noskill`.

## Consequences
- The prompt teaches the shell recipes (`grep`, `pytest`, `git diff`) in a small table.
- Skill calls no longer escape the tool-call cap. Every action counts against `max_tool_calls`.
- To settle the question, run `v2_fast` against `v2_noskill` on `sound40` and compare them paired (ADR 0004). If the skill wins there, the gap was leaderboard noise or a scorer-environment difference, and it needs diagnosis before the skill returns.
