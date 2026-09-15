ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="$ROOT/sandbox/docker-compose.yml"

dc() { docker compose -f "$COMPOSE" "$@"; }

require_env() {
  : "${CLAUDE_CODE_OAUTH_TOKEN:?set CLAUDE_CODE_OAUTH_TOKEN (create one with: claude setup-token)}"
  : "${POKEVAL_TEST_SET:?set POKEVAL_TEST_SET to the path of the test set}"
  [ -f "$POKEVAL_TEST_SET" ] || { echo "no test set at $POKEVAL_TEST_SET"; exit 1; }
  POKEVAL_TEST_SET="$(cd "$(dirname "$POKEVAL_TEST_SET")" && pwd)/$(basename "$POKEVAL_TEST_SET")"
  export CLAUDE_CODE_OAUTH_TOKEN POKEVAL_TEST_SET
}

latest_session() {
  python3 - "$1" <<'PY'
import json
import sys

session = ''
for line in open(sys.argv[1]):
    try:
        event = json.loads(line)
    except ValueError:
        continue
    session = event.get('session_id') or session
print(session)
PY
}

run_session() {
  local prompt="$1" left="$2" cpid wpid
  shift 2
  set +e
  dc exec -T -e CLAUDE_CODE_OAUTH_TOKEN -e HOME=/home/agent -w /task task \
    claude -p "$prompt" "$@" --model "$MODEL" --dangerously-skip-permissions \
    --output-format stream-json --verbose < /dev/null >> "$RUN/transcript.jsonl" 2>> "$RUN/candidate.stderr" &
  cpid=$!
  (
    sleep "$left"
    dc exec -T task pkill -TERM claude 2>/dev/null
    sleep 30
    dc exec -T task pkill -KILL claude 2>/dev/null
    kill -KILL "$cpid" 2>/dev/null
  ) &
  wpid=$!
  wait "$cpid"
  RC=$?
  kill "$wpid" 2>/dev/null
  wait "$wpid" 2>/dev/null || true
  set -e
}

finish() {
  echo "== grade"
  ( cd "$ROOT/sandbox" && ./grade_container.sh "$NAME" ) | tee "$RUN/score.txt" || true
  cp "$ROOT/sandbox/oracle_logs/oracle_queries.jsonl" "$RUN/oracle_queries.jsonl" 2>/dev/null || echo "(no oracle queries)"
  cp "$ROOT/candidates/$NAME.py" "$RUN/engine.py" 2>/dev/null || echo "(no engine.py was left in /task)"
  python3 "$ROOT/runner/summary.py" "$RUN/transcript.jsonl" | tee "$RUN/summary.txt"
  python3 "$ROOT/runner/render_transcript.py" "$RUN/transcript.jsonl" > "$RUN/transcript.md"
  echo "== trajectory (grading $(ls "$RUN/checkpoints" 2>/dev/null | wc -l | tr -d ' ') checkpoints)"
  python3 "$ROOT/runner/trajectory.py" "$RUN" | tee "$RUN/trajectory.txt"
}
