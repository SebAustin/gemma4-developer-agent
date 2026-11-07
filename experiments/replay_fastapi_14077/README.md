# Test-reset replay of `fastapi_14077` (2026-10-06, harness swegemma 0.2.7, local Docker sandbox)

Two runs of the real harness with a scripted model (`src/g4agent/scripted_model.py`), reconstructed in each trajectory's tool calls:

- `a_test_edit/`: the reference fix, then the agent's real test edit from the `v2_fast` dev run, then `submit_patch`. Result: not resolved, `Failed to apply test_patch` (see `task_results.jsonl`).
- `b_with_guard/`: the same two patches, then the `v3_guard` ship check (a regex-filtered `git checkout` of test and config files), then `submit_patch`. Result: resolved.

Harness 0.2.11 fixes the reset upstream, so replaying these steps on 0.2.11 resolves in both cases. Diagnosis: `docs/diagnosis/test-patch-conflicts.md`.
