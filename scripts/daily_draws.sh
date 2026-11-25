#!/usr/bin/env bash
# One attempt at today's Daily slot (see CONTEXT.md). launchd runs this every 30 minutes.
# It submits only when `g4 draws next` exits 0 AND no stamp for today exists, so reruns,
# pending draws, an already used slot, a lagging Kaggle listing or a submit whose CLI call
# timed out are all no-ops. Standing user approval for daily draws: 2026-11-15, until
# 2026-12-01. The rotation lives in experiments/slot.yaml. DRY_RUN=1 never submits.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export KAGGLE_BIN="${KAGGLE_BIN:-uvx --from kaggle==2.2.3 kaggle}"
STATE="${G4_STATE_DIR:-$HOME/Library/Application Support/g4}"
LAST_DAY="2026-12-01"
log() { echo "$(date -u +%FT%TZ) $*"; }

mkdir -p "$STATE"
LOCK="$STATE/daily_draws.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  holder="$(cat "$LOCK/pid" 2>/dev/null || true)"
  if [[ -n "$holder" ]] && kill -0 "$holder" 2>/dev/null; then
    log "another run (pid $holder) holds $LOCK; skipping"; exit 0
  fi
  log "WARNING: clearing stale lock $LOCK (holder ${holder:-unknown} is gone)"
  rm -rf "$LOCK"; mkdir "$LOCK"
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

today="$(date -u +%F)"
if [[ "$today" > "$LAST_DAY" ]]; then
  log "past $LAST_DAY: daily draws are over"; exit 0
fi
STAMP="$STATE/submitted-$today"
if [[ -e "$STAMP" ]]; then
  log "already submitted on $today ($(cat "$STAMP")); never resubmitting the same UTC day"; exit 0
fi

uv run --quiet g4 draws sync >/dev/null
set +e
decision="$(uv run --quiet g4 draws next --shell)"
code=$?
set -e

# Only well-formed KEY='value' lines from g4 are evaluated.
if grep -qvE "^(DRAW|KERNEL_VERSION|MESSAGE|REASON|COMPETITION|KERNEL)=" <<<"$decision"; then
  log "unexpected output from g4 draws next (exit $code); not submitting"; exit 1
fi
eval "$decision"

case "$code" in
  0) ;;
  3|4|5) log "no submit (exit $code): $REASON"; exit 0 ;;
  *) log "g4 draws next failed (exit $code)"; exit "$code" ;;
esac

log "submit draw $DRAW (kernel v$KERNEL_VERSION)"
if [[ "${DRY_RUN:-0}" == 1 ]]; then
  log "DRY_RUN: would run: $KAGGLE_BIN competitions submit $COMPETITION -k $KERNEL -f submission.zip -v $KERNEL_VERSION -m \"$MESSAGE\""
  exit 0
fi

# The stamp goes down BEFORE the submit: if the CLI times out after Kaggle accepted it,
# no later run today can submit again. It is never removed automatically.
( set -o noclobber; echo "draw $DRAW kernel v$KERNEL_VERSION at $(date -u +%T)Z" > "$STAMP" ) || {
  log "stamp $STAMP appeared concurrently; not submitting"; exit 0; }

# shellcheck disable=SC2086  # KAGGLE_BIN is a command line on purpose
$KAGGLE_BIN competitions submit "$COMPETITION" -k "$KERNEL" \
  -f submission.zip -v "$KERNEL_VERSION" -m "$MESSAGE" || log "submit command returned non-zero (stamp kept)"

uv run --quiet g4 draws sync >/dev/null || log "post-submit sync failed"
if awk -F, -v d="$DRAW" 'NR>1 && $3==d {found=1} END {exit !found}' experiments/draws.csv; then
  log "confirmed: draw $DRAW is on Kaggle"
else
  log "draw $DRAW not visible yet; the stamp blocks any resubmit today. Check the listing by hand."
fi
