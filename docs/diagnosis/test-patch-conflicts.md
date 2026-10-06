# Correct fixes fail with "Failed to apply test_patch"

## Symptom
In the dev30 runs, 3/30 tasks (v2_fast) and 2/30 (v1) failed with `Failed to apply test_patch`. One of them, `fastapi_14077`, changed exactly the three files of the reference patch. Every failing patch also edited a test file that the hidden test patch changes.

## Cause (verified in source and in the local Docker sandbox, 2026-10-06)
`swegemma/harness/verification.py` tries to reset test and config files before it applies the test patch:
```
git checkout HEAD -- <test files> <agent-touched test/config files> conftest.py pytest.ini sitecustomize.py usercustomize.py _swegemma_stubs.py 2>/dev/null || true
```
`sitecustomize.py`, `usercustomize.py` and `_swegemma_stubs.py` live in site-packages, not in the repository. Git rejects the whole checkout when any pathspec is unknown ("pathspec did not match"). It does this in the sandbox image's git 2.47 too, so nothing is reset. The test patch is then applied on top of the agent's test edits:
- If the edits touch lines the test patch also changes, the patch fails to apply and the task fails.
- If they don't overlap, the `git apply -3` fallback merges them, and the edit survives into grading.

## Proof
`fastapi_14077` was replayed through the real harness (Docker sandbox, scripted model):
- (a) the reference fix plus the agent's real test edit from the Kaggle run: not resolved, `Failed to apply test_patch`;
- (b) the same edits, then the ship check: resolved.

## Fix
Bundle `v3_guard`, a prompt-only change:
- It drops the false claim that the grader resets test files.
- It states that test and config edits make the hidden tests fail to apply.
- Its Ship step runs a ship-check command that reverts test and config edits, and has the agent delete untracked scratch files. In v2_fast, 3 of 19 patches were scratch files only.

`tests/test_ship_check.py` runs the prompt's command on a scratch repository.
