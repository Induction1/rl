#!/usr/bin/env bash
# Pod-side end-of-run push (2026-09-07): waits for Step 250, lets adapter_saver do its final sweep, then uploads
# /root/adapters (per-25-step LoRA adapters), metrics.jsonl, resolved configs, and all eval traces to HF.
# Start: HF_TOKEN=… setsid nohup bash /workspace/pod_autopush.sh > /workspace/autopush.log 2>&1 < /dev/null &
export PATH=$HOME/.local/bin:$PATH
T=/workspace/prime-rl/outputs/t2s-v2/logs/latest/trainer.log
until grep -qsE 'Step 250 ' $T; do sleep 120; done
echo "$(date -u +%FT%TZ) step 250 seen; waiting for adapter_saver final sweep"
until grep -qs 'final sweep done' /workspace/adapter_saver.log; do sleep 30; done
cd /root/outputs/t2s-v2 && tar czf /root/t2s-v2_evals.tgz metrics.jsonl configs rollouts/step_*/eval logs/*/orchestrator.log logs/*/trainer.log 2>/dev/null
ls /root/adapters; du -sh /root/adapters /root/t2s-v2_evals.tgz
cd /workspace/prime-rl && uv run --no-sync python - <<'PY'
import os
from huggingface_hub import HfApi
api=HfApi(token=os.environ['HF_TOKEN']); repo='Induction/qwen2.5-coder-3b-t2s-v2-lora'
api.create_repo(repo, private=True, exist_ok=True)
steps=sorted((d for d in os.listdir('/root/adapters') if d.startswith('step_')), key=lambda d:int(d.split('_')[1]))
api.upload_folder(folder_path=f'/root/adapters/{steps[-1]}', repo_id=repo, path_in_repo='final')
for d in steps: api.upload_folder(folder_path=f'/root/adapters/{d}', repo_id=repo, path_in_repo=d)
api.upload_file(path_or_fileobj='/root/t2s-v2_evals.tgz', path_in_repo='t2s-v2_evals.tgz', repo_id=repo)
print('PUSHED', repo, steps)
PY
echo "$(date -u +%FT%TZ) AUTOPUSH_DONE — safe to terminate the pod"
