# Gemma 4 Developer Agent: competition workspace

This is our entry for the Kaggle [Gemma 4 Developer Agent](https://www.kaggle.com/competitions/gemma-4-developer-agent) competition. A declarative ADK bundle drives `gemma-4-31b-it-qat-w4a16-ct` to fix Python issues. The score is the fraction of hidden tests passed.

## Layout
| Path | What |
|---|---|
| `submissions/<variant>/` | Agent bundles: `agent.yaml`, prompts, `skills/`, `eval_config.yaml`, optional `adapters/` |
| `src/g4agent/` | Tooling: `validate` (real harness compile + lints), `package` (deterministic zip), `splits`, `kaggle_ops` (eval kernels), `skill_runner` |
| `kaggle/eval_kernel/run_eval.py` | Template for the Kaggle GPU eval run (vLLM + official `Evaluator`) |
| `experiments/` | Frozen dev splits (`splits.json`) and the experiment log (`EXPERIMENTS.md`) |
| `docs/HARNESS_NOTES.md` | Non-obvious harness behaviour, verified from its source |
| `data/`, `vendor/` | Competition data and harness wheels (gitignored, downloaded with the Kaggle CLI) |

## Setup
```bash
scripts/fetch_harness.sh                                         # harness wheels (not on PyPI)
uv sync
kaggle competitions download gemma-4-developer-agent -p data     # 20 GB; unzip in data/
```

## Everyday loop
```bash
uv run pytest                                          # tooling and skill-script tests
uv run g4 validate submissions/v1_scaffold             # compile with the real harness, lint prompts/skills
uv run g4 kernel submissions/v1_scaffold --split dev30 # render a Kaggle eval kernel
kaggle kernels push -p kaggle/runs/<slug>              # run it on Kaggle L4x4 (spends GPU quota)
uv run g4 package submissions/v1_scaffold              # dist/v1_scaffold.zip for submission
```
