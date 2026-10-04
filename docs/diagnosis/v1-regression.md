# Diagnosis: v1_scaffold scores 0.08 vs ~0.12 for the official sample

## Symptom
Public LB 0.08 for bundle `9c208aa2c19a` (submission 56783164, 2026-10-02). Sample-like bundles (1 min / 10 calls per task) score 0.12–0.13.

## Feedback loop
A differential run of `sample_baseline` vs `v1_scaffold` on `dev30` with Kaggle L4x4 (`kaggle/runs/g4-eval-{baseline,v1}-dev30`). It reads each run's `run_meta.json` plus per-task traces/logs. It is slow (about 1 h), but it is the only loop that exercises Gemma; no local GPU.

## Falsified
- **Skill scripts fail in Kaggle's sandbox.** In the CPU oracle kernel's logs (Kaggle subprocess sandbox), all 129 `locate.py` and 258 `check_patch.py` calls returned normal stdout with no errors.

## Ranked hypotheses (each with a falsifiable prediction)
1. **The 12 h wall clock runs out before all tasks run.** The scorer is likely serial, and per-task sandbox setup counts toward the 12 h but not toward `max_time_minutes`. 120 × (5 min + setup) can exceed 12 h, so the last tasks get no patch.
   - *Prediction:* the dev-run task durations plus per-task setup, extrapolated to 120 tasks, exceed 12 h. The 1-minute sample stays well under.
2. **Slow turns: the agent rarely reaches an edit within 5 minutes.** A 1536-token thinking budget, a multi-step workflow and a separate reproduction step make each turn slow.
   - *Prediction:* many v1 tasks end with an empty or tiny patch at the time limit, and the time to the first `edit_file` is large compared with the baseline.
3. **Skill overhead.** The ADK default skill instruction ("MUST use load_skill") makes Gemma spend turns on `load_skill`/`list_skills` before working.
   - *Prediction:* traces show `load_skill` within the first turns of most tasks, and removing `skills:` (or the default instruction) cuts the turns to first edit.
4. **Malformed skill calls.** Gemma passes `args` as a string or puts options in the wrong field, so `run_skill_script` returns errors and gets retried.
   - *Prediction:* v1 traces contain `run_skill_script` responses with `error_code`.
5. **Patch hygiene.** Edits land in test, config or scratch files, which the grader discards.
   - *Prediction:* v1 patches touch protected paths more often than baseline patches.

## Loop result 1 (2026-10-03, dev30, conc. 4, gpu_mem 0.90 + VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1)
- baseline 0/30, v1 0/30, and **every task hit the session timeout** in both runs.
- v1: the first 8 tasks (two waves of 4) acted normally, at 15–40 s per turn and 60–345k prompt tokens per task. **From about 600 s into serving, all 22 later tasks got zero model responses** (`total_prompt_tokens: 0`), with no API errors or retries in the kernel log.
- The baseline's whole evaluation took 517 s, under that point. Its 1-minute budget still timed out every task (about 4–10 agent steps each).
- Reading: the inference server stops answering after about 10 minutes of v1-sized load, so the dev numbers are invalid past that point.
- This does not yet explain LB 0.08, because the scorer runs its own server, presumably at 0.80.
- Next probe: keep the vLLM log (`vllm_server.log`) and run the scorer-documented memory config (0.80, no profiler env var).

## Loop result 2 (2026-10-03, dev30, conc. 4, scorer config: gpu_mem 0.80, no profiler env var)
- v1 resolved 1/30 (fastapi_14301). KV cache usage stayed at 10–17%, so **KV memory is falsified as the cause**.
- Same failure shape as before, just later. Three waves (12 tasks) worked, then from about 900 s every task got zero responses.
- `vllm_server.log` stops at 19:41:51 mid-flight (Running: 4 reqs), with no error and no shutdown. In run 1 the process was still alive at the end ("did not terminate within 10.0s"), so this is a **silent engine hang**, not a crash.
- New top hypothesis: **host-RAM pressure.** Sandboxes run pytest and repo code beside vLLM; the OOM killer takes one tensor-parallel worker and the others block forever.
  - *Prediction:* free memory goes to ~0 and a vLLM worker disappears just before the hang.
- If true, this also explains part of LB 0.08: a scorer server that hangs mid-run leaves the remaining tasks without patches, and v1's longer, test-running tasks reach it sooner.
- The working tasks also show the progress problem (hypothesis 2): 8–35 steps in 5 minutes, often without an edit.
- Probe 3: a `[DEBUG-mon]` monitor thread logging `free -m`, vLLM processes, GPU memory, `/health` and dmesg OOM lines every 20 s.

## Loop result 3 (2026-10-03, same config as run 2, plus `[DEBUG-mon]`)
- **No hang:** all 30 tasks got responses, `/health` was 200 in all 115 samples, and free host RAM never dropped below about 171 GB.
- **Host OOM is falsified**, so the hang is intermittent (2 of 3 runs). Remaining suspect: an agent command in the subprocess sandbox (which shares the host with vLLM) killing vLLM's processes, e.g. `pkill python` to stop a server it started.
  - Run 3 logs contain no kill commands. The run 1–2 outputs were overwritten (Kaggle serves only the latest version's output), so that can't be checked yet.
- **The scorer runs Docker sandboxes** (HARNESS_README 3.1: 4 GiB / 2 vCPU per container), so this hang most likely affects only our dev kernel, not LB scoring.
- **v1 resolved 5/30** (ceiling 18). The baseline's only hang-free run resolved 0/30.
- On the LB, 0.08 vs 0.12 on ~60 tasks is about 5 vs 7 resolved, within noise. **The "regression" is not established.**
- Next: the watchdog flags hangs in `run_meta.json` (`server_hang_at`). Re-run the baseline and v2_fast under run 3's config, keeping each run's outputs in timestamped folders.

## Conclusion (2026-10-03)
- **The "v1 regression" is not supported.** Under identical dev conditions the sample resolves 0/30, v1 5/30 and v2_fast 6/30. LB 0.08 vs 0.12 is ±2 tasks on ~60, and the sample's 1-minute budget does much better when turns are faster, as on the scorer.
- **Real defects found and fixed along the way:**
  - The kernel memory config, plus the harness's LoRA defaults.
  - An unpinned Docker image.
  - A silent vLLM hang (2 of 3 early runs). The harness's 2026-09-30 scheduler fix (`scheduler_reserve_full_isl=False`) is the likely cause. The watchdog now reports any recurrence.
  - Progress speed: edit-early (v2_fast) raises the patch rate from 14 to 19 of 30.
- The `[DEBUG-mon]` instrumentation became a permanent, documented watchdog; there are no tagged debug logs left (`grep DEBUG- kaggle/` returns nothing).
