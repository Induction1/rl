#!/usr/bin/env bash
# Training-pod bootstrap for text2sql RL (2-GPU RunPod, CUDA 12.8 driver). REUSES the 2026-08-28 recipe
# (rl/IMPLEMENTATION.md § prime-rl on a fresh pod) — do not "improve" it with a fresh install.
# Environment assumption: fresh RunPod PyTorch pod, run as root, network OK. Mac side ships the env + data
# with (run 2, 2026-09-06): `tar czf - text2sql gen pyproject.toml rl_v2.toml data/financial_work.sqlite data/dev_20240627/dev.json
# data/pool/pool_run2.jsonl data/corrected | ssh <pod> 'mkdir -p /workspace/text2sql && tar xzf - -C /workspace/text2sql'`
# (gen/ is needed: prompts v2 imports gen/semantics.py for the legend).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq tmux rsync >/dev/null
command -v uv >/dev/null || (curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1); export PATH="$HOME/.local/bin:$PATH"
cd /workspace
git config --global url."https://github.com/".insteadOf "git@github.com:"   # submodules use SSH URLs
if [ ! -d prime-rl ]; then git clone https://github.com/PrimeIntellect-ai/prime-rl; fi
cd prime-rl
PIN="${PRIME_RL_REF:-v0.9.0}"   # the release used on 2026-08-28; override with PRIME_RL_REF=
if [ -n "$PIN" ]; then git checkout -q "$PIN"; fi
git submodule update --init --recursive || (git submodule deinit -f . && rm -rf .git/modules/* && git submodule update --init --recursive --force)
uv sync --all-extras                        # torch/vLLM = the `gpu` extra; plain sync has no torch
uv pip install -e /workspace/text2sql       # our env (verifiers v1 taskset `text2sql`)
# smoke: taskset loads + gold executes, no model needed
cd /workspace/text2sql && PYTHONPATH=. /workspace/prime-rl/.venv/bin/python -c "
from text2sql.taskset import T2SQLTaskset, T2SQLConfig
n=sum(1 for _ in T2SQLTaskset(T2SQLConfig(split='train', prompt_version=2, pool_path='/workspace/text2sql/data/pool/pool_run2.jsonl')).load()); b=sum(1 for _ in T2SQLTaskset(T2SQLConfig(split='bird_dev', prompt_version=2, corrected=True)).load())
print('train tasks (v2 pool)', n, '| bird_dev corrected tasks', b)"
cd /workspace/prime-rl && uv run --no-sync validate text2sql -n 5 --runtime.type subprocess 2>&1 | tail -3
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo SETUP_OK
# Launch (after the config surface is re-checked against THIS checkout — see rl_v1.toml header):
#   tmux new -d -s rl "cd /workspace/prime-rl && HF_TOKEN=... WANDB_API_KEY=... uv run --no-sync rl @ /workspace/text2sql/configs/rl_v2.toml --run.name t2s-v2 2>&1 | tee /workspace/rl.log"
