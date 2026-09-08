# text2sql

RL post training of Qwen2.5-Coder-3B-Instruct to write SQL for one real database, BIRD `financial`, with execution
match against gold as the only reward. Two runs on prime-rl with GRPO and LoRA. Test accuracy on the 106 human written
questions went from 27 percent (untrained, with the final prompt) to 52 percent, matching Claude Sonnet 5 zero shot.

Read more at https://induction1.github.io/research/text2sql-rl/

## Layout

| Folder | What is in it |
|---|---|
| `text2sql/` | the environment: prompt builders (run 1 and run 2 versions), the verifier, the verifiers v1 taskset |
| `gen/` | the training data pipeline: legend, templates for four tiers, the hop and rank families, pool builder, mechanical checker, English rewrite, reading check, leak filter, merge |
| `scan/` | measurement: frontier scan, untrained model scan, the pre training gate, the post run checkpoint sweep |
| `configs/` | prime-rl configs for run 1, run 2, and the run 2 resume |
| `pod/` | RunPod bootstrap for the scan and training pods, the run 2 watchdog, adapter saver, HF auto push, and the pull script |
| `analysis/` | the failure reads behind the post mortem tables, the difficulty breakdown, and the figures |
| `data/` | the two training pools (2,252 and 3,246 rows) and the two corrected versions of the test questions |
| `results/` | test accuracy and training reward by step for both runs, the gate results, the checkpoint sweep, the scan outputs |

The database and BIRD's dev split are downloads; `pod/pod_scan_setup.sh` fetches them. The adapters from every 25 steps
of run 2 and the run 2 eval traces are on Hugging Face at `Induction/qwen2.5-coder-3b-t2s-v2-lora`.

## Reproducing

1. Scan pod (one 24 GB GPU): `bash pod/pod_scan_setup.sh`, then `python scan/gate_scan.py --k 8` for the gate or
   `python scan/ckpt_eval.py --repo Induction/qwen2.5-coder-3b-t2s-v2-lora` for the checkpoint sweep.
2. Data: `python gen/build_families.py` then `gen/write_questions.py`, `gen/reading_check.py`, `gen/leak_filter.py`,
   `gen/merge_v2.py`. The rewrite and reading check call Claude Haiku and need `ANTHROPIC_API_KEY`.
3. Training pod (two 80 GB GPUs): `bash pod/pod_train_setup.sh`, then
   `uv run --no-sync rl @ /workspace/text2sql/configs/rl_v2.toml` from the prime-rl checkout. `VERIFIER.md` is the
   reward specification.

Built on [prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) v0.9.0 and
[verifiers](https://github.com/PrimeIntellect-ai/verifiers) v1.
