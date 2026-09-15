#!/usr/bin/env bash
set -euo pipefail

USAGE="usage: runner/run.sh <run-name> [--hours H] [--model M] [--refill TURNS/MIN] [--bucket TURNS] [--checkpoint-min MIN]"
NAME="${1:?$USAGE}"
shift
HOURS=2
MODEL="claude-opus-5[1m]"
REFILL=3000
BUCKET=5000
CHECKPOINT_MIN=5
while [ $# -gt 0 ]; do
  case "$1" in
    --hours) HOURS="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --refill) REFILL="$2"; shift 2 ;;
    --bucket) BUCKET="$2"; shift 2 ;;
    --checkpoint-min) CHECKPOINT_MIN="$2"; shift 2 ;;
    *) echo "unknown arg $1"; exit 1 ;;
  esac
done

source "$(dirname "$0")/lib.sh"
require_env
RUN="$ROOT/runs/$NAME"
[ -e "$RUN" ] && { echo "run '$NAME' already exists: $RUN"; exit 1; }
mkdir -p "$RUN"

echo "== fresh box ($REFILL turns/min, bucket $BUCKET)"
(
  cd "$ROOT/sandbox" && docker compose down -v >/dev/null 2>&1
  ORACLE_REFILL="$REFILL" ORACLE_BUCKET="$BUCKET" docker compose up -d --build >/dev/null 2>&1
)
rm -f "$ROOT/sandbox/oracle_logs/oracle_queries.jsonl"
for i in $(seq 1 30); do
  dc exec -T task oracle --budget 2>/dev/null && break
  [ "$i" -eq 30 ] && { echo "oracle never came up"; exit 1; }
  sleep 1
done

python3 - "$RUN" "$NAME" "$MODEL" "$HOURS" "$REFILL" "$BUCKET" "$ROOT" "$POKEVAL_TEST_SET" <<'PY'
import datetime
import hashlib
import json
import subprocess
import sys

run, name, model, hours, refill, bucket, root, test_set = sys.argv[1:]


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:16]


showdown = subprocess.run(['node', '-p', 'require("pokemon-showdown/package.json").version'],
                          cwd=root, capture_output=True, text=True).stdout.strip()
manifest = {
    'name': name,
    'model': model,
    'hours': float(hours),
    'agent': 'claude code inside the task container',
    'oracle_refill_per_minute': int(refill),
    'oracle_bucket': int(bucket),
    'started': datetime.datetime.now().isoformat(timespec='seconds'),
    'showdown': showdown,
    'task_sha': sha(f'{root}/task/TASK.md'),
    'spec_sha': sha(f'{root}/task/SPEC.md'),
    'docs_sha': sha(f'{root}/docs/README.md'),
    'corpus_sha': sha(test_set),
    'corpus_n': sum(1 for _ in open(test_set)),
}
json.dump(manifest, open(f'{run}/manifest.json', 'w'), indent=1)
PY

SECS=$(python3 -c "print(int($HOURS * 3600))")
echo "== candidate: $MODEL inside the box, $HOURS h, transcript -> runs/$NAME/transcript.jsonl"
START=$(date +%s)
DEADLINE=$((START + SECS))
"$ROOT/runner/checkpoint.sh" "$RUN" "$COMPOSE" "$(python3 -c "print(int($CHECKPOINT_MIN * 60))")" "$START" &
KPID=$!
SESSION=""
SESSIONS=0
RC=0
SHORT=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  SESSIONS=$((SESSIONS + 1))
  LEFT=$((DEADLINE - $(date +%s)))
  T0=$(date +%s)
  echo "-- session $SESSIONS ($((LEFT / 60)) min left)$([ -n "$SESSION" ] && echo " resuming $SESSION")" | tee -a "$RUN/sessions.log"
  if [ -z "$SESSION" ]; then
    run_session "Read /task/TASK.md and begin." "$LEFT"
  else
    run_session "Time remains. Continue." "$LEFT" --resume "$SESSION"
  fi
  SESSION=$(latest_session "$RUN/transcript.jsonl")
  SESSION_SECS=$(( $(date +%s) - T0 ))
  echo "   session $SESSIONS ended rc=$RC after $(( $(date +%s) - START )) s total ($SESSION_SECS s this session)" | tee -a "$RUN/sessions.log"
  if [ "$(date +%s)" -ge "$DEADLINE" ]; then break; fi
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
END=$(date +%s)
echo "== $SESSIONS session(s), $((END - START)) s of $SECS"

finish
python3 - "$RUN" "$RC" "$((END - START))" <<'PY'
import json
import sys

run, rc, secs = sys.argv[1:]
manifest = json.load(open(f'{run}/manifest.json'))
manifest.update(last_rc=int(rc), wall_seconds=int(secs))
json.dump(manifest, open(f'{run}/manifest.json', 'w'), indent=1)
PY
echo "== filed under runs/$NAME"
