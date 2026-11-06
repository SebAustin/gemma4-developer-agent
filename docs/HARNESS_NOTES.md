# Harness notes (verified by reading the source)

> **Current harness: swegemma 0.2.11 / adk_submission 0.2.13** (wheelhouse republished 2026-10-12, no changelog). What changed from 0.2.7:
> - Test and config edits are stripped from the agent patch, and the test-file reset works. The test-reset bug below is fixed.
> - The scoring pytest run has its own `verification_timeout_seconds` (300). The bundle's `timeout_seconds` now caps agent commands only.
> - `include_thoughts: false` no longer disables reasoning. Thoughts are still generated, but stripped from history.
> - `validate_single_declared_model` and `setup_gemma_model_registry` were removed. Use `adk_submission.discovery.discover_declared_models`.
> - Tool exceptions return to the model as `{'status': 'error'}` instead of crashing. Sandbox errors keep the patch graded.
> - The workspace tree in the prompt prunes `tests/` and `docs/` and is capped at 200 lines.
> - Tool names, signatures and output caps are unchanged.
>
> Sections below describe 0.2.7 unless stated otherwise.

Source: `swegemma 0.2.7`, `adk_submission 0.2.11`, `adk_eval_core 0.1.0` and `google-adk 1.36.1`, all from the Kaggle dataset `metric/gemma-4-developer-agent-wheelhouse`. Run `scripts/fetch_harness.sh`, then read `.venv/lib/python3.12/site-packages/`.

## Skills (`skills:` on an LlmAgent)
- `resolve_skills` turns the list into an ADK `SkillToolset`. That adds the tools `load_skill`, `load_skill_resource` and `run_skill_script`, and appends a default skill system instruction plus an XML list of skills (name and description) to every request.
- `run_skill_script(skill_name, file_path, args)`: `args` can be a list of strings (passed verbatim as argv) or a dict (turned into `--key value`).
- Execution (`_SkillScriptCodeExecutor`) is a self-extracting wrapper. It writes **all** of the skill's files to a `tempfile.TemporaryDirectory`, `chdir`s there, and runs the script via `runpy`. swegemma's `AdkSandboxCodeExecutor` writes that wrapper to `<workspace>/.adk_exec_<id>.py`, runs `python3` on it with cwd set to the workspace, then deletes it.
  - A script's cwd is **not** the repo. Discover the root via `sys.path[0]`, `PYTHONPATH`, `PWD` or `/workspace` (see `skills/swe/scripts/_common.py`).
  - In the subprocess sandbox the repo is **not** at `/workspace`. Path rewriting only applies to shell command strings, not file contents.
  - While a script runs, `.adk_exec_*.py` is an untracked file in the repo, so ignore it in `git status` checks.
- Skill tools are **not** swegemma `@budget_gated` tools, so they don't count toward `max_tool_calls`. They are still subject to the time budget (the executor checks `budget_check_fn` and the remaining time) and to `max_turns`.
- Skill output is not truncated by the harness (the 5k-char cap only applies to `run_command`). Scripts must cap their own output.

## Instruction templating
- ADK's `inject_session_state` replaces every `{+[^{}]*}+` match whose content is an identifier (optionally with a `?` suffix or an `app:`/`user:`/`temp:` prefix).
- If the key is missing from session state, it raises `KeyError`, which kills the task.
- Session state holds `problem_description`, plus `hints` only when a task has hints. No training task has hints, so use `{hints?}`.
- Non-identifier braces such as `{"a": 1}` are left untouched. `g4 validate` enforces all of this.

## Scoring flow facts
- **Host-confirmed (forum, Ryan Holbrook):** tasks run **sequentially**. The scorer reads exactly `timeout_seconds`, `max_tool_calls`, `max_time_minutes` and `max_turns`; an omitted field means no limit. One 12 h run covers all ~120 tasks, public and private together. **Exceeding 12 h errors the whole submission.** A planned "score unfinished tasks as 0" fix was being reconsidered on 2026-10-07, so `max_time_minutes` is the only failsafe.
- 2026-10-06: a wave of submissions (ours 56885293 included) ran 15–17 h, then ended in "A system error…", among them 4.5–5 min/task bundles that had fit 12 h before. So scorer speed varies from day to day; keep a wide margin under 12 h.
- The scorer runs ~120 tasks **one after another** (organizer-confirmed, per public notebooks). The 12 h include sandbox setup, not grading. 4×L4 serve one model with tensor parallelism; they are not four task workers. `Evaluator.run(concurrency=...)` exists, but the scorer does not use it.
- **Verification timeout:** the bundle's `timeout_seconds` becomes `harness.command_timeout_seconds` (`swegemma/config.py:179`). That value caps every agent command **and** the scoring pytest run over the hidden test files (`harness/verification.py:502`), which runs whole files on a 2-vCPU sandbox. Default 300 s; `g4 validate` warns below 240 s as cheap insurance. Measured 2026-10-06 (local reference-fix run, all 129 tasks, amd64 emulation): scoring pytest took ≤ 9.2 s, mean 1.0 s (`results/oracle-v1_scaffold-full/test_outputs`). The "requests takes ~100 s" claim from a public notebook does not reproduce offline, so expect little gain from raising the timeout on repos like these.
- vLLM serves `max_model_len` 32,768 and rejects any request whose prompt plus `max_output_tokens` exceeds it. Long tasks then die mid-run, so keep `max_output_tokens` ≤ 8192.
- `thinking_config.include_thoughts: false` disables reasoning in the ADK→vLLM bridge, even with a positive `thinking_budget` (reported by the "Measure before you tune" notebook).
- When the time or call budget runs out, the working tree is still diffed and graded.
- **Test edits are never reverted.** The harness's pre-grading reset (`git checkout HEAD -- … sitecustomize.py …`) always aborts on pathspecs that are not in the repo. An agent edit to lines that the hidden test patch changes therefore fails the task, even with a correct fix. Bundles must revert test and config edits themselves; see `docs/diagnosis/test-patch-conflicts.md`.
- Kaggle notebooks use `sandbox='subprocess'` because there is no Docker.
- The docker sandbox is only for local runs (`swebench-sandbox:latest`).
- `setup_gemma_model_registry(served_model=...)` routes all Gemma aliases to one served model. That lets us smoke-test with a small local model while keeping the competition model name in `agent.yaml`.

## Test-dependency environment (important for interpreting dev scores)
- **Docker sandbox** (`install_test_dependencies`): streams unpacked wheels from the wheels dir into site-packages, **deduplicated to the highest version per package**. `sandbox/setup.py --fast-path` only writes a `.pth` file and the pytest config; it does not pin versions.
  - Older fastapi commits then get starlette 1.x and fail with `Router.__init__() got an unexpected keyword argument 'on_startup'`, even with the reference patch.
- **Subprocess sandbox** (Kaggle notebooks) skips dependency installation entirely and uses the host image's packages.
- The real scorer references a private `metric/gemma-4-developer-agent-metric-data` dataset (a sandbox and wheels of its own) and "secret bundle" hydration in `Evaluator`. **Neither local nor notebook environments are guaranteed to match it.**
- So measure the **oracle ceiling** per environment (`python -m g4agent.oracle_run --split full`, which applies the gold patch through the real harness). Report agent scores as resolved / oracle-resolvable as well as raw.
- The public wheels lack several fastapi test deps: `typing_inspection`, `inline_snapshot`, `dirty_equals`, `pyjwt`, `pwdlib`, `python-multipart`, and others. Local runs use `data/wheels_local` (official wheels hard-linked together with `data/wheels_extra`, downloaded with `--no-deps` so no pinned package gets upgraded).
- **Package shadowing:** the public wheel set contains the benchmark repos themselves (rich, requests, httpx, fastapi). Injected into site-packages, they shadow the patched `/workspace` copy, so tests import the *released* package and the patch is ignored. The hidden test repos are private, so this can't happen at scoring time.
- `g4agent.local_env` builds a per-task wheel set: it drops the repo's own distribution and keeps only versions satisfying the snapshot's declared pins (fixing the starlette clash). It also gives each set its own `tempfile` dir, because the harness caches unpacked wheels under a fixed name. Result: the oracle went from 1/5 to 5/5 on smoke5.
- Apple Silicon: build the sandbox image with `--platform linux/amd64`, because the wheels are x86_64.

## vLLM memory with LoRA (Kaggle eval kernel)
- With `VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1` (set by the official notebook), `gpu_memory_utilization=0.80` behaves like about 0.62. Enabling LoRA (`max_loras=8`, `max_lora_rank=128`) then leaves a negative KV-cache budget on 4x L4: "No available memory for the cache blocks", seen 2026-09-28 with the sample bundle.
- The eval kernel therefore copies the official notebook (0.90). That leaves roughly 1.8 GiB of KV cache per GPU.
- **Risk:** HARNESS_README says the scorer uses 0.80 with the same LoRA settings. The sample (LoRA) bundle does score on the leaderboard, so the scorer evidently starts. Still, before submitting our own LoRA bundle, verify it on a scorer-identical config, and keep adapter rank small.

## Harness republished 2026-09-30 (same swegemma 0.2.7 version, adk_submission 0.2.12)
- Tools now return dicts at the ADK boundary. `VllmConfig` gained `reasoning_config`: for the `gemma4` parser it defaults to Gemma 4 channel tokens, which **enables vLLM's thinking-token budget**, so `thinking_budget` is now enforced.
- New default `scheduler_reserve_full_isl=False` (Gemma 4 requests no longer stall in the waiting queue). LoRA defaults are now `max_loras=1` with the rank inferred from the adapters.
- `scripts/fetch_harness.sh` always re-downloads, because wheels get republished under the same version.
- 2026-10-03: Kaggle's default Docker image moved to Python 3.13, which breaks the cp312 wheelhouse. Kernels pin the official notebook's image (`kaggle_ops.KAGGLE_DOCKER_IMAGE`).
