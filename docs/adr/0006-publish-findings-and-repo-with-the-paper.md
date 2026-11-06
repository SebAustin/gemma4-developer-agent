# Harness findings and the repository go public with the paper, before the main track ends

The paper track (`gemma-4-developer-agent-paper`, due 2026-11-12) closes three weeks before the main competition (2026-12-02), and Writeups become visible after its deadline. We publish everything in full at paper submission:
- the test-reset bug, with its mechanism, the Docker replay and the cleanup step before submitting;
- the repository: tooling, docs, experiment logs and bundles.

## Why
- **The bug is our most novel and most verifiable finding.** Novelty and Verifiability are two of the paper's five equally weighted criteria.
- **Disclosure costs us little on the leaderboard.** The guard's effect wasn't detectable there (v2_noskill 0.13, v3_guard 0.10, v4_guard_budget 0.13 / 0.10, with ±0.03–0.06 leaderboard noise). Our bundles also score at or below public notebooks.
- **The bug degrades the benchmark for every team.** Publishing it is the fair choice.

## Considered
- **Hold code and details until Dec 2,** which the host allows. Rejected: lower Verifiability, for an edge we couldn't measure.

## Consequences
- Before the repository goes public, check it for secrets, Kaggle credentials and private-data paths.
- Competitors may adopt the cleanup step before Dec 2.

## Note (2026-11-06)
The harness republished on 2026-10-12 (swegemma 0.2.11) fixes the test-reset bug, so disclosing it no longer gives competitors anything. The paper presents it as independently found (2026-10-06) and confirmed by the upstream fix, without claiming credit for the fix.
