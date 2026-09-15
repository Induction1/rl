#!/usr/bin/env bash
set -euo pipefail

NAME="${1:?usage: runner/resume.sh <run-name> [--hours H]}"
shift
source "$(dirname "$0")/lib.sh"
require_env
RUN="$ROOT/runs/$NAME"
[ -d "$RUN" ] || { echo "no such run: $RUN"; exit 1; }

manifest() {
  python3 -c "import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])" "$RUN/manifest.json" "$1"
}

HOURS=$(manifest hours)
while [ $# -gt 0 ]; do
  case "$1" in
    --hours) HOURS="$2"; shift 2 ;;
    *) echo "unknown arg $1"; exit 1 ;;
  esac
done
MODEL=$(manifest model)
START=$(python3 -c "import datetime, sys; print(int(datetime.datetime.fromisoformat(sys.argv[1]).timestamp()))" "$(manifest started)")
DEADLINE=$(python3 -c "print(int($START + $HOURS * 3600))")
SESSION=$(latest_session "$RUN/transcript.jsonl")
[ -n "$SESSION" ] || { echo "no session id in transcript"; exit 1; }
dc ps --status running --services 2>/dev/null | grep -q task || { echo "the box is not running; cannot resume"; exit 1; }
dc up -d oracle >/dev/null 2>&1

"$ROOT/runner/checkpoint.sh" "$RUN" "$COMPOSE" 300 "$START" &
KPID=$!
SESSIONS=$(grep -c '^-- session' "$RUN/sessions.log" || echo 0)
SHORT=0
RC=0
echo "== resuming $NAME: session $SESSION, $(( (DEADLINE - $(date +%s)) / 60 )) min left" | tee -a "$RUN/sessions.log"
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  SESSIONS=$((SESSIONS + 1))
  LEFT=$((DEADLINE - $(date +%s)))
  T0=$(date +%s)
  echo "-- session $SESSIONS ($((LEFT / 60)) min left) resuming $SESSION" | tee -a "$RUN/sessions.log"
  run_session "Time remains. Continue." "$LEFT" --resume "$SESSION"
  SESSION_SECS=$(( $(date +%s) - T0 ))
  echo "   session $SESSIONS ended rc=$RC after $SESSION_SECS s" | tee -a "$RUN/sessions.log"
  if [ "$RC" -eq 143 ] || [ "$RC" -eq 137 ]; then break; fi
  if [ "$RC" -ne 0 ]; then
    echo "   non-zero exit (rate limit?); waiting 120 s before retrying" | tee -a "$RUN/sessions.log"
    sleep 120
    continue
  fi
  if [ "$SESSION_SECS" -lt 60 ]; then SHORT=$((SHORT + 1)); else SHORT=0; fi
  if [ "$SHORT" -ge 3 ]; then
    echo "== candidate declared done: three consecutive sessions under 60 s; ending early" | tee -a "$RUN/sessions.log"
    break
  fi
  sleep 5
done
kill "$KPID" 2>/dev/null
wait "$KPID" 2>/dev/null || true

finish
echo "== filed under runs/$NAME"
