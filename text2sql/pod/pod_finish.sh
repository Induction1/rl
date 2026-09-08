#!/usr/bin/env bash
# End-of-run: copy every saved adapter + metrics + eval traces to the Mac; push the final adapter to HF.
# Run from the Mac: bash pod_finish.sh   (needs HF_TOKEN in ~/.secrets/apis; pod alias t2strain)
set -euo pipefail
RUN="${RUN:-t2s-v2}"   # run name (outputs/<RUN>, HF repo suffix); RUN=t2s-v1 reproduces the run-1 pull
D="${OUT:-./runs}/$RUN"; mkdir -p $D/ckpts $D/evals
HF=$(grep "^HF_TOKEN=" ~/.secrets/apis | cut -d= -f2- | tr -d '"'"'")
ssh -o BatchMode=yes t2strain 'cd /root/adapters && tar czf - $(ls -d step_*)' | tar xzf - -C $D/ckpts   # run 2: adapters saved by adapter_saver.sh every 25 steps
ssh -o BatchMode=yes t2strain "cd /workspace/prime-rl/outputs/$RUN && tar czf - metrics.jsonl logs/latest rollouts/step_*/eval configs/resolved" | tar xzf - -C $D
FINAL=$(ls $D/ckpts | grep step_ | sed 's/step_//' | sort -n | tail -1); echo "final adapter step: $FINAL"; cp -r $D/ckpts/step_$FINAL $D/ckpts/final_$FINAL
ssh -o BatchMode=yes t2strain "export PATH=\$HOME/.local/bin:\$PATH; cd /workspace/prime-rl && HF_TOKEN=$HF RUN=$RUN uv run --no-sync python - <<'PY'
from huggingface_hub import HfApi; import os
api=HfApi(token=os.environ['HF_TOKEN']); repo='Induction/qwen2.5-coder-3b-'+os.environ['RUN']+'-lora'
api.create_repo(repo, private=True, exist_ok=True)
steps=sorted((d for d in os.listdir('/root/adapters') if d.startswith('step_')), key=lambda d:int(d.split('_')[1]))
api.upload_folder(folder_path=f'/root/adapters/{steps[-1]}', repo_id=repo, path_in_repo='final')
for d in steps: api.upload_folder(folder_path=f'/root/adapters/{d}', repo_id=repo, path_in_repo=d)
print('pushed to', repo)
PY"
du -sh $D; echo "FINISH_OK — pod may be terminated after verifying the HF repo"
