#!/usr/bin/env bash
# Copies the LoRA adapter (broadcasts/step_N, ~230 MB) to /root/adapters/step_N at every 25th step — the run-1 style
# per-25-step weights. Independent of the watchdog. Start: setsid nohup bash /workspace/adapter_saver.sh > /workspace/adapter_saver.log 2>&1 < /dev/null &
B=/root/outputs/t2s-v2/broadcasts; A=/root/adapters; mkdir -p $A
while true; do
  for d in $(ls -d $B/step_* 2>/dev/null); do
    n=${d##*_}
    if [ $((n % 25)) -eq 0 ] && [ ! -f $A/step_$n/adapter_model.safetensors ] && [ -f $d/adapter_model.safetensors ]; then
      cp -r $d $A/step_$n.tmp && mv $A/step_$n.tmp $A/step_$n && echo "$(date -u +%FT%TZ) saved step_$n"
    fi
  done
  grep -qsE 'Step 250 ' /workspace/prime-rl/outputs/t2s-v2/logs/latest/trainer.log && { sleep 180; ls $B; for d in $(ls -d $B/step_* 2>/dev/null); do n=${d##*_}; [ -f $A/step_$n/adapter_model.safetensors ] || cp -r $d $A/step_$n; done; echo "$(date -u +%FT%TZ) final sweep done"; exit 0; }
  sleep 120
done
