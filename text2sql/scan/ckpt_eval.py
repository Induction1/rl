"""Post-run checkpoint sweep (2026-09-07): every saved t2s-v2 adapter (+ the base model) on every held-out set, k samples
at T=1, scored with the training verifier. vLLM loads the base once and hot-swaps LoRA adapters.

Pod-side (4090 after scan/pod_setup.sh; needs data/financial_work.sqlite, data/corrected/*.json, gen/, text2sql/):
  HF_TOKEN=… python scan/ckpt_eval.py --repo Induction/qwen2.5-coder-3b-t2s-v2-lora --k 8
Sets: orig_nohint · orig_hint · wretblad (106, corrected questions+gold) · arcwise (30, VLDB'26 full fix) ·
      arcwise_sqlonly (30, gold fixed, question untouched). Writes runs/ckpt_eval/<set>__<ckpt>.jsonl + summary.json."""
from __future__ import annotations
import argparse, importlib.util, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import t2s

def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
verify = _load("verify", "text2sql/verify.py"); prompts = _load("prompts", "text2sql/prompts.py")

def rows_from(json_rows, hints=False):
    out = []
    for r in json_rows:
        if r.get("db_id") != "financial": continue
        q = r["question"] + (f"\nHint: {r['evidence']}" if hints and str(r.get("evidence", "")).strip() else "")
        out.append({"id": f"bird_{r['question_id']}", "question": q, "gold": r["SQL"],
                    "order_sensitive": "ORDER BY" in r["SQL"].upper() and "LIMIT" in r["SQL"].upper()})
    return out

def sets():
    orig = [r for r in t2s.load_dev() if r["db_id"] == "financial"]
    C = ROOT / "data" / "corrected"
    wret = json.loads((C / "financial_corrected.json").read_text())
    arc = json.loads((C / "arcwise_plat_full_with_diff.json").read_text())
    arcs = json.loads((C / "arcwise_plat_sql_only_with_diff.json").read_text())
    return {"orig_nohint": rows_from(orig), "orig_hint": rows_from(orig, True), "wretblad": rows_from(wret),
            "arcwise": rows_from(arc), "arcwise_sqlonly": rows_from(arcs)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="Induction/qwen2.5-coder-3b-t2s-v2-lora"); ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-3B-Instruct")
    ap.add_argument("--k", type=int, default=8); ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--ckpts", default="all", help="comma list like step_100,step_250 or 'all'"); ap.add_argument("--sets", default="all")
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--gpu-mem", type=float, default=0.85)
    a = ap.parse_args()
    from huggingface_hub import snapshot_download
    from vllm import LLM, SamplingParams
    from vllm.lora.request import LoRARequest
    local = snapshot_download(a.repo, token=os.environ.get("HF_TOKEN"))
    ck = sorted([d for d in os.listdir(local) if d.startswith("step_") and os.path.isfile(f"{local}/{d}/adapter_model.safetensors")], key=lambda d: int(d.split("_")[1]))
    if a.ckpts != "all": ck = [c for c in ck if c in a.ckpts.split(",")]
    ck = ["base"] + ck
    S = sets()
    if a.sets != "all": S = {k: v for k, v in S.items() if k in a.sets.split(",")}
    db = str(ROOT / "data" / "financial_work.sqlite"); schema = t2s.schema_prompt(db); ctx = prompts.context_block(db)
    llm = LLM(model=a.model, dtype="bfloat16", gpu_memory_utilization=a.gpu_mem, max_model_len=4096, enable_lora=True, max_lora_rank=32, seed=a.seed)
    tok = llm.get_tokenizer(); sp = SamplingParams(n=a.k, temperature=a.temperature, max_tokens=256, seed=a.seed)
    out_dir = ROOT / "runs" / "ckpt_eval"; out_dir.mkdir(parents=True, exist_ok=True)
    summary = {}
    print(f"{'ckpt':10}" + "".join(f"{s:>18}" for s in S) + "   (mean EX / pass@k)")
    for i, c in enumerate(ck):
        lora = None if c == "base" else LoRARequest(c, i, f"{local}/{c}")
        line = f"{c:10}"; summary[c] = {}
        for sname, rows in S.items():
            reqs = [tok.apply_chat_template([{"role": "system", "content": prompts.system_prompt(2)}, {"role": "user", "content": prompts.user_message_v2(schema, r["question"], ctx)}], tokenize=False, add_generation_prompt=True) for r in rows]
            t0 = time.time(); outs = llm.generate(reqs, sp, lora_request=lora)
            recs = []
            for r, o in zip(rows, outs):
                res = [verify.score(db, x.text, r["gold"], r["order_sensitive"]) for x in o.outputs]
                sr = sum(x["correct"] for x in res) / len(res)
                recs.append({**r, "solve_rate": sr, "samples": [{"pred": x["pred_sql"], "correct": x["correct"], "error": x["error"]} for x in res]})
            (out_dir / f"{sname}__{c}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in recs))
            ex = sum(x["solve_rate"] for x in recs) / len(recs); pk = sum(x["solve_rate"] > 0 for x in recs) / len(recs)
            summary[c][sname] = {"ex": ex, "pass_k": pk, "n": len(recs)}
            line += f"{ex*100:>8.1f} / {pk*100:<7.1f}"
        print(line, flush=True)
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))

if __name__ == "__main__":
    main()
