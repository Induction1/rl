#!/usr/bin/env bash
# Hangup-proof launcher + watchdog for t2s-v2 (2026-09-07). Usage: HF_TOKEN=… WANDB_API_KEY=… setsid nohup bash /workspace/watchdog.sh > /workspace/watchdog.log 2>&1 &
# Relaunches the resume (from the latest checkpoint) if the trainer dies before Step 250, at most MAX_ATTEMPTS times.
export PATH=$HOME/.local/bin:$PATH HF_HOME=/root/hf
CFG=/workspace/text2sql/configs/rl_v2_resume.toml; LOGDIR=/workspace/prime-rl/outputs/t2s-v2/logs; MAX_ATTEMPTS=3; n=0
done_yet() { grep -qsE 'Step 250 ' $LOGDIR/latest/trainer.log; }
alive() { pgrep -f 'prime_rl.*(trainer|orchestrator)' >/dev/null; }
while ! done_yet && [ $n -lt $MAX_ATTEMPTS ]; do
  n=$((n+1)); echo "$(date -u +%FT%TZ) launch attempt $n"
  (cd /workspace/prime-rl && setsid nohup uv run --no-sync rl @ $CFG > /workspace/rl_resume_$n.log 2>&1) &
  sleep 240
  while alive; do
    # prune train rollouts older than 5 steps (evals kept); ckpts are 14 GB each on the 80 GB container disk
    ls -d /root/outputs/t2s-v2/rollouts/step_* 2>/dev/null | sort -t_ -k2 -n | head -n -5 | while read d; do rm -rf "$d/train"; done
    sleep 120
  done
  echo "$(date -u +%FT%TZ) processes gone after attempt $n; done_yet=$(done_yet && echo yes || echo no)"
  sleep 30
done
echo "$(date -u +%FT%TZ) watchdog exit (done=$(done_yet && echo yes || echo no), attempts=$n)"
