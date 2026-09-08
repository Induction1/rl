"""Open-model zero-shot scan with vLLM — same prompts, same questions (seeded), same scorer as
frontier_scan.py, so the numbers are comparable. Runs on any CUDA box (Bouchet gpu_devel or a
RunPod pod). Usage:
  python scan/local_scan.py --dbs financial,card_games --n 40 --model Qwen/Qwen2.5-Coder-3B-Instruct
  add --no-evidence to withhold the hint. Writes runs/scan/<model-tail>__<db>__<ev|noev>.jsonl"""
from __future__ import annotations
import argparse, json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import t2s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dbs", required=True); ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-3B-Instruct")
    ap.add_argument("--no-evidence", action="store_true"); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=512); ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--k", type=int, default=1, help="samples per question (k>1 → also report pass@k and per-question solve rate)")
    ap.add_argument("--gpu-mem", type=float, default=0.85)
    a = ap.parse_args()
    from vllm import LLM, SamplingParams
    dev = t2s.load_dev()
    dbs = sorted({r["db_id"] for r in dev}) if a.dbs == "all" else a.dbs.split(",")
    llm = LLM(model=a.model, dtype="bfloat16", gpu_memory_utilization=a.gpu_mem, max_model_len=8192)
    tok = llm.get_tokenizer()
    sp = SamplingParams(n=a.k, temperature=a.temperature if a.k == 1 else max(a.temperature, 0.7),
                        max_tokens=a.max_tokens)
    out_dir = t2s.HERE / "runs" / "scan"; out_dir.mkdir(parents=True, exist_ok=True)
    tail = a.model.rstrip("/").split("/")[-1]; tag = "noev" if a.no_evidence else "ev"
    print(f"{'db':24}{'n':>5}{'EX@1':>7}{'95% CI':>16}{'pass@k':>8}{'exec_err':>10}")
    for db in dbs:
        qs = [r for r in dev if r["db_id"] == db]; random.Random(a.seed).shuffle(qs); qs = qs[:a.n]
        schema = t2s.schema_prompt(qs[0]["db_path"])
        prompts = []
        for q in qs:
            msgs = [{"role": "system", "content": t2s.SYSTEM},
                    {"role": "user", "content": t2s.build_prompt(schema, q["question"], None if a.no_evidence else q.get("evidence"))}]
            prompts.append(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True))
        outs = llm.generate(prompts, sp)
        recs = []
        for q, o in zip(qs, outs):
            grow, gerr = t2s.execute(q["db_path"], q["SQL"])
            samples = []
            for c in o.outputs:
                pred = t2s.extract_sql(c.text); prow, perr = t2s.execute(q["db_path"], pred)
                samples.append({"pred": pred, "pred_err": perr, "match": t2s.ex_match(prow, grow)})
            recs.append({**{k: q[k] for k in ("question_id", "db_id", "question", "difficulty")}, "gold": q["SQL"],
                         "gold_err": gerr, "samples": samples, "match": samples[0]["match"],
                         "solve_rate": sum(s["match"] for s in samples) / len(samples)})
        path = out_dir / f"{tail}__{db}__{tag}.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in recs))
        n = len(recs); k1 = sum(r["match"] for r in recs); pk = sum(r["solve_rate"] > 0 for r in recs)
        p, lo, hi = t2s.wilson(k1, n); err = sum(1 for r in recs if r["samples"][0]["pred_err"])
        print(f"{db:24}{n:>5}{p:>7.2f}{f'[{lo:.2f}, {hi:.2f}]':>16}{pk/n:>8.2f}{err:>10}")
        if a.k > 1:
            mixed = sum(0 < r["solve_rate"] < 1 for r in recs)
            print(f"{'':24}   groups with mixed rewards (GRPO signal): {mixed}/{n}")

if __name__ == "__main__":
    main()
