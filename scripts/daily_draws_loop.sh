#!/usr/bin/env bash
# Runs scripts/daily_draws.sh every 30 minutes from a terminal-started shell. This is used
# instead of the LaunchAgent because macOS privacy protection (TCC) blocks launchd jobs
# from reading ~/Documents. It survives closing the terminal but not a reboot. Start it with:
#   nohup scripts/daily_draws_loop.sh >> ~/Library/Logs/g4-daily-draws.log 2>&1 & disown
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
while :; do
  bash "$ROOT/scripts/daily_draws.sh" || echo "$(date -u +%FT%TZ) daily_draws.sh exited $?"
  [[ "$(date -u +%F)" > "2026-12-01" ]] && exit 0
  sleep 1800
done
