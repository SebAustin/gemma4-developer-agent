# Agent guide: Gemma 4 Developer Agent competition

We build declarative ADK bundles (`submissions/<variant>/`) that drive `gemma-4-31b-it-qat-w4a16-ct` to fix Python issues. Commands live in `README.md` and `uv run g4 --help`.

## Before changing a bundle
Read `docs/HARNESS_NOTES.md` when you touch prompts, skills, eval kernels or dependency setup. It records harness behaviour verified from source, which no config file shows: brace templating, how skill scripts are materialized, and wheel shadowing.

## Rules that are easy to break
- Prompts use braces only for `{problem_description}` or `{hints?}`. Any other `{word}` crashes the task at the first model call. `g4 validate` catches it.
- Skill scripts locate the repo through `_common.find_workspace()`. Their cwd is a temp dir, and in the Kaggle subprocess sandbox the repo is not at `/workspace`.
- A bundle is ready when `uv run pytest` and `uv run g4 validate <bundle>` both pass.
- Measure on the frozen splits in `experiments/splits.json`. Read every score against the reference-fix ceiling of its environment (`experiments/oracle_*.json`), and log it in `experiments/EXPERIMENTS.md`.

## Actions that need the user's go-ahead
Kaggle kernel pushes (they spend the weekly GPU quota), competition submissions (1 per day) and new Kaggle datasets.
