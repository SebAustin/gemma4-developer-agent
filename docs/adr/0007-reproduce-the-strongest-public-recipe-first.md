# Reproduce the strongest public recipe before tuning our own (amends 0004 and 0005)

On 2026-11-07 our best bundles scored 0.12–0.13, while about twenty teams sat at 0.22–0.24 and one at 0.29, most of them forks of public notebooks. A claimed gap of about 0.11 is roughly 6 public tasks, twice the leaderboard noise, so one submission can confirm or refute it. We therefore:

- fork the strongest public recipe (Apache 2.0 Kaggle notebooks) as our new base, crediting its author in the bundle and the repository;
- spend the first new submission slot on a **reproduction**: the recipe unchanged, only repackaged through `g4 package` so its bundle hash is logged;
- keep the ADR 0004 dev gate (paired serial run on the sound split, ≥ +4 of 40) for every change we make on top of the reproduced base.

The goal is ≥ 0.24 first, then gains measured on dev. Public rank 1 is not a measurable goal: the public set is ~58 tasks and the final ranking uses the private tasks.

## Consequences
- Our v1–v4 bundles stay in the repository as the paper's evidence; they are no longer the base for new variants.
- The daily rotation of old bundles ends once `v3_guard` (58091025) scores.
- The paper keeps its numbers as of 2026-11-09 and states the gap with public bundles in its Limitations section.

## Considered options
- Keep improving our own line: rejected, because nothing in v2–v4 left the 0.06–0.13 band and the dev gate allows about five variants a week.
- Submit public recipes and our changes in the same slot: rejected, because a change on top of an unreproduced base cannot be attributed.
