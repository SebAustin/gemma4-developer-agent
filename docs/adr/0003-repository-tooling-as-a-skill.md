# Repository tooling ships as a skill, not as prompt instructions

Submissions can't contain agent code, but a skill's scripts run inside the task sandbox. We put navigation, targeted testing and the pre-submit patch check into the `swe` skill, instead of only teaching shell recipes (`grep`, `find`, `pytest`) in the prompt. The reasons:
- Skill calls are not counted against `max_tool_calls`.
- Their output is ranked and size-capped.
- They are unit-tested.

## Consequences
- Every model request carries the skill instruction and list, a fixed context cost.
- Scripts must discover the repository root themselves (in the Kaggle sandbox it is not at `/workspace`) and must never write inside it.
- Whether the skill helps more than it costs is still unproven: `v1_scaffold` scored 0.08 vs about 0.12 for the sample. See `docs/diagnosis/v1-regression.md`.
