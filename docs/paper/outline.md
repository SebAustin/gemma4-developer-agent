# Paper outline (paper track `gemma-4-developer-agent-paper`, Kaggle Writeup ≤ 3,000 words, due 2026-11-12 23:59 UTC)

Decided 2026-11-06:
- Target Overall Best Paper, with a "Released resources" section.
- Solo author (Sebastien Henry); AI assistance acknowledged.
- Kaggle Writeup only; arXiv optional later.
- Repository public at submission (ADR 0006).
- Required sections: abstract, introduction, research description, related work.

Working title: **Measuring a declarative coding agent under a noisy, hidden leaderboard: audit the evaluation pipeline before tuning the agent**

Thesis: with ±0.03–0.06 leaderboard noise, hidden repositories and one submission a day, most apparent gains from prompt or tool changes are noise. A team learns more by auditing the evaluation pipeline than by tuning prompts. The pipeline audit covers per-environment reference-fix ceilings, a harness test-reset bug, sound-task splits and paired comparisons.

## Claims → evidence → still needed
| # | claim | evidence now | still needed |
|---|---|---|---|
| 1 | The public leaderboard can't rank variants: identical bundles move ±0.03–0.06 | ours: v4_guard_budget 0.13 / 0.10; public: 0.12 / 0.10 / 0.06 | more identical pairs from daily resubmissions |
| 2 | The harness never reverts agent test edits, and edits overlapping the hidden test patch fail correct fixes | source trace + git pathspec repro + Docker replay of fastapi_14077 (docs/diagnosis/test-patch-conflicts.md); 3/30 dev tasks (v2_fast), 2/30 (v1) | paired sound40 run, v3_guard vs v2_noskill. LB: no detectable effect (0.10 vs 0.13, within noise) |
| 3 | A custom navigation skill hurt on hidden repos, though it helped (slightly) on public dev | LB: skill 0.08 / 0.06 vs no-skill 0.13; dev30: v2_fast 6/30 > v1 5/30 | paired sound40: v2_fast vs v2_noskill |
| 4 | Time-to-first-edit, not patch quality, is the main loss | v2_fast dev30: 14/30 tasks never made a source edit; only 4/30 patches wrong in behaviour or naming (EXPERIMENTS.md failure breakdown) | the same breakdown on serial sound40 runs |
| 5 | Environment ceilings differ (local 105/129, Kaggle 73/129), so scores must be read against per-environment ceilings | `experiments/oracle_*.json` | — |
| 6 | Serial dev runs on sound tasks with paired tests are a cheap, faithful proxy | design (ADR 0004) | serial v2_noskill on sound40 vs its LB 0.13; Spearman across ≥ 4 variants |

## Sections
1. Setup: competition, harness, bundle constraints, compute (4×L4, 12 h, 1 submission/day).
2. Measurement: environments and ceilings, LB noise, the sound split, paired McNemar.
3. Harness effects: test-patch conflicts, scratch files, verification timeout (null result: ≤ 9.2 s on all 129 public tasks).
4. Agent design ablations: skill vs shell, budget envelope, sampling, edit deadline.
5. Failure taxonomy from trajectories.
6. Limits: public-repo dev vs private-repo test; single-seed runs.

## Figures
- Failure breakdown bar chart (claim 4).
- Paired win/loss matrix per ablation (claims 2–3).
- Ceiling vs agent score per environment (claim 5).
