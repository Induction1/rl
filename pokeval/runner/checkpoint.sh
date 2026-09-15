#!/usr/bin/env bash
set -euo pipefail

RUN="${1:?usage: runner/checkpoint.sh <run-dir> <compose-file> <interval-seconds> <start-epoch>}"
COMPOSE="$2"
INTERVAL="$3"
START="$4"
mkdir -p "$RUN/checkpoints"
while sleep "$INTERVAL"; do
  T=$(( $(date +%s) - START ))
  DIR="$RUN/checkpoints/$(printf '%06d' "$T")"
  mkdir -p "$DIR"
  docker compose -f "$COMPOSE" cp task:/task "$DIR/" >/dev/null 2>&1 || { rmdir "$DIR" 2>/dev/null; continue; }
  wc -c < "$RUN/transcript.jsonl" > "$DIR/transcript_bytes" 2>/dev/null || echo 0 > "$DIR/transcript_bytes"
done
