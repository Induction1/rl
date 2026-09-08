#!/usr/bin/env bash
# Pod-side bootstrap for the 3B scan. Assumes a fresh RunPod PyTorch 2.x pod (CUDA 12.8), run as root.
# Environment assumption: no uv, no tmux on a fresh pod; network access to bird-bench + HF.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq tmux unzip >/dev/null
curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1; export PATH="$HOME/.local/bin:$PATH"
mkdir -p /workspace/text2sql && cd /workspace/text2sql
# data: pull from source (346 MB zip + nested databases zip), not from the Mac
if [ ! -d data/dev_20240627/dev_databases ]; then
  mkdir -p data && cd data
  [ -f dev.zip ] || curl -L -sS -o dev.zip https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip
  unzip -q -o dev.zip && (cd dev_20240627 && unzip -q -o dev_databases.zip) && cd ..
fi
# python env with vllm (pinned to a recent stable), no torch reinstall fights: fresh venv
uv venv .venv --python 3.12 -q && . .venv/bin/activate
# RUN-VERIFIED 2026-09-05: plain install pulls a CUDA-13 torch; RunPod driver is 12.8 → pin the torch backend
# vLLM >=0.2x ships only cu129/cu13 wheels; 0.11.0 is the last PyPI build against CUDA 12.8 (run-verified 9/5)
# --no-cache: a 30 GB container fills up with the uv cache + one torch reinstall
uv pip install -q --no-cache --torch-backend=cu128 "vllm==0.11.0" "transformers<5"   # transformers 5 removed all_special_tokens_extended (run-verified 9/5)
python -c "import vllm, torch; print('vllm', vllm.__version__, '| cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0))"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo SETUP_OK
