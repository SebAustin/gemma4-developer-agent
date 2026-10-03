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
