# Per-task wheel sets for local verification

The harness installs the newest version of every wheel it is given. With the public wheel set, that breaks local verification in two ways: the benchmark repos' own released packages shadow the patched working copy, and newer dependencies violate older snapshots' pins (starlette 1.x vs old fastapi). The reference fix passed on only 51/129 tasks.

We therefore build a wheel set per task, without the repo's own distribution and filtered to the snapshot's declared version constraints, instead of patching the harness or using one global pinned set. Result: 105/129.

## Considered Options
- **Patch the harness's install logic:** rejected, because the bundle must keep working against the unmodified harness the scorer runs.
- **One hand-pinned global wheel set:** rejected, because snapshots span incompatible starlette and pydantic versions.

## Consequences
Local reference-fix ceilings are only comparable when computed with this mechanism. Changing it requires recomputing `experiments/oracle_local.json`.
