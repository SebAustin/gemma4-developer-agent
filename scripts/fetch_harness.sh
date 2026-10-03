#!/usr/bin/env bash
# Fetch the competition harness wheels (not on PyPI) into vendor/wheelhouse/.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p vendor/wheelhouse
for f in swegemma-0.2.7-py3-none-any.whl adk_submission-0.2.12-py3-none-any.whl adk_eval_core-0.1.0-py3-none-any.whl; do
  # always re-download: the organizers republish wheels under the same version (e.g. 2026-09-30)
  rm -f "vendor/wheelhouse/$f"; kaggle datasets download metric/gemma-4-developer-agent-wheelhouse -f "$f" -p vendor/wheelhouse -q
done
