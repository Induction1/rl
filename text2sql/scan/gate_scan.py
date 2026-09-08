"""Run-2 gate (2026-09-06): base-model pass@8 under the candidate prompts, BEFORE any pod training.
Decides (a) the new step-0 baseline, (b) whether the hop families carry GRPO signal (mixed groups > 0),
(c) whether the think-then-SQL format starts at or above SQL-only. Scores with text2sql/verify.py (the
training reward, rule 8 lifted) so numbers are the run's numbers, not the scan's.

Pod-side (4090, after scan/pod_setup.sh; needs data/financial_work.sqlite, data/corrected/, data/pool/pool_hops_stage2.jsonl):
  python scan/gate_scan.py --k 8 --conds all
Writes runs/gate/<cond>.jsonl and prints one table. Conditions:
  v1_nohint     106, run-1 prompt (replicates run-1 step 0; sanity)
  v2_nohint     106, v2 prompt (legend + join graph + value lists)      ← new baseline
  v2_hint       106, v2 + BIRD evidence
  v2_corr       106 corrected (Wretblad), v2
  v2t_nohint    106, v2 + think format
  hops_v2       hop/date/outconv families (canonical questions), v2
  hops_v2t      same, think format"""
from __future__ import annotations
import argparse, importlib.util, json, random, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import t2s

def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
verify = _load("verify", "text2sql/verify.py"); prompts = _load("prompts", "text2sql/prompts.py")
ORDER_TAGS = {"order_limit", "order", "nth"}

def bird_rows(corrected=False):
    if corrected:
        rows = json.loads((ROOT / "data" / "corrected" / "financial_corrected.json").read_text())
    else:
        rows = [r for r in t2s.load_dev() if r["db_id"] == "financial"]
    return [{"id": f"bird_{r['question_id']}", "question": r["question"], "evidence": r.get("evidence", ""), "gold": r["SQL"],
             "order_sensitive": "ORDER BY" in r["SQL"].upper() and "LIMIT" in r["SQL"].upper(), "tier": r.get("difficulty", "?"), "family": "bird"} for r in rows]

def hop_rows(path, n, seed):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    random.Random(seed).shuffle(rows)
    return [{"id": r["id"], "question": r["canonical_question"], "evidence": "", "gold": r["sql"],
             "order_sensitive": bool(set(r.get("tags", [])) & ORDER_TAGS), "tier": r["tier"], "family": r["family"]} for r in rows[:n]]

COND = {  # name -> (rows_fn, version, think, hints)
    "v1_nohint":  (lambda a: bird_rows(), 1, False, False),
    "v2_nohint":  (lambda a: bird_rows(), 2, False, False),
    "v2_hint":    (lambda a: bird_rows(), 2, False, True),
    "v2_corr":    (lambda a: bird_rows(True), 2, False, False),
    "v2t_nohint": (lambda a: bird_rows(), 2, True, False),
    "hops_v2":    (lambda a: hop_rows(a.hops, a.hops_n, a.seed), 2, False, False),
    "hops_v2t":   (lambda a: hop_rows(a.hops, a.hops_n, a.seed), 2, True, False),
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-3B-Instruct")
    ap.add_argument("--conds", default="all"); ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--temperature", type=float, default=1.0, help="1.0 = the training temperature")
    ap.add_argument("--max-tokens-sql", type=int, default=256); ap.add_argument("--max-tokens-think", type=int, default=768)
    ap.add_argument("--hops", default=str(ROOT / "data" / "pool" / "pool_hops_stage2.jsonl")); ap.add_argument("--hops-n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--gpu-mem", type=float, default=0.85)
    a = ap.parse_args()
    conds = list(COND) if a.conds == "all" else a.conds.split(",")
    db = str(ROOT / "data" / "financial_work.sqlite")
    schema = t2s.schema_prompt(db); ctx = prompts.context_block(db)
    from vllm import LLM, SamplingParams
    llm = LLM(model=a.model, dtype="bfloat16", gpu_memory_utilization=a.gpu_mem, max_model_len=6144, seed=a.seed)
    tok = llm.get_tokenizer()
    out_dir = ROOT / "runs" / "gate"; out_dir.mkdir(parents=True, exist_ok=True)
    print(f"{'cond':12}{'n':>5}{'EX@1':>7}{'pass@k':>8}{'mixed':>7}{'exec_err':>9}{'fmt_err':>8}{'tok':>6}{'s':>6}")
    for cond in conds:
        rows_fn, ver, think, hints = COND[cond]; rows = rows_fn(a)
        reqs = []
        for r in rows:
            q = r["question"] + (f"\nHint: {r['evidence']}" if hints and r["evidence"].strip() else "")
            user = prompts.user_message(schema, q) if ver == 1 else prompts.user_message_v2(schema, q, ctx, think=think)
            msgs = [{"role": "system", "content": prompts.system_prompt(ver, think)}, {"role": "user", "content": user}]
            reqs.append(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True))
        sp = SamplingParams(n=a.k, temperature=a.temperature, max_tokens=a.max_tokens_think if think else a.max_tokens_sql, seed=a.seed)
        t0 = time.time(); outs = llm.generate(reqs, sp)
        recs = []
        for r, o in zip(rows, outs):
            samples = []
            for c in o.outputs:
                res = verify.score(db, c.text, r["gold"], r["order_sensitive"])
                samples.append({"text": c.text, "pred": res["pred_sql"], "correct": res["correct"], "executed": res["executed"], "format": res["format"], "error": res["error"], "tokens": len(c.token_ids)})
            sr = sum(s["correct"] for s in samples) / len(samples)
            recs.append({**{k: r[k] for k in ("id", "question", "gold", "tier", "family")}, "solve_rate": sr, "samples": samples})
        (out_dir / f"{cond}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in recs))
        n = len(recs); ex1 = sum(x["solve_rate"] for x in recs) / n; pk = sum(x["solve_rate"] > 0 for x in recs) / n
        mixed = sum(0 < x["solve_rate"] < 1 for x in recs) / n
        allS = [s for x in recs for s in x["samples"]]
        ee = sum(1 for s in allS if s["format"] and not s["executed"]) / len(allS); fe = sum(1 for s in allS if not s["format"]) / len(allS)
        tk = sum(s["tokens"] for s in allS) / len(allS)
        print(f"{cond:12}{n:>5}{ex1:>7.3f}{pk:>8.2f}{mixed:>7.2f}{ee:>9.2f}{fe:>8.2f}{tk:>6.0f}{time.time()-t0:>6.0f}", flush=True)
        if cond.startswith("hops"):
            by = {}
            for x in recs: by.setdefault(x["family"], []).append(x["solve_rate"])
            for f, v in sorted(by.items()):
                print(f"    {f:12} n={len(v):3d} EX@1={sum(v)/len(v):.2f} pass@k={sum(s>0 for s in v)/len(v):.2f} mixed={sum(0<s<1 for s in v)/len(v):.2f}")

if __name__ == "__main__":
    main()
