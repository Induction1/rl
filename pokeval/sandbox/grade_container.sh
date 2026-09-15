#!/usr/bin/env bash
set -euo pipefail

NAME="${1:?usage: sandbox/grade_container.sh <candidate-name> [/task/engine.py]}"
SRC="${2:-/task/engine.py}"
: "${POKEVAL_TEST_SET:?set POKEVAL_TEST_SET to the path of the test set}"
TEST_SET="$(cd "$(dirname "$POKEVAL_TEST_SET")" && pwd)/$(basename "$POKEVAL_TEST_SET")"
cd "$(dirname "$0")"
docker compose stop oracle >/dev/null
mkdir -p ../candidates
docker compose cp "task:${SRC}" "../candidates/${NAME}.py"
echo "kept a copy: candidates/${NAME}.py ; oracle stopped, log in sandbox/oracle_logs/"
cd .. && python3 harness/grade.py "$TEST_SET" \
  "${NAME}=docker compose -f sandbox/docker-compose.yml exec -T -e ORACLE_URL=http://127.0.0.1:9 task python3 ${SRC}"
