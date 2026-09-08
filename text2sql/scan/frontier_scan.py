"""Frontier zero-shot scan over BIRD dev databases (the database-selection measurement).
Usage:  python scan/frontier_scan.py --dbs financial,card_games --n 60 --model claude-opus-5
Writes runs/scan/<model>__<db>__<ev|noev>.jsonl (one line per question, resumable) and prints
per-database execution accuracy with Wilson 95% intervals."""
from __future__ import annotations
import argparse, asyncio, json, os, random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import t2s
from anthropic import AsyncAnthropic

def load_key():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    p = Path.home() / ".secrets" / "apis"
    for line in p.read_text().splitlines():
        if line.startswith("ANTHROPIC_API_KEY="):
            os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")

async def ask(client, model, prompt, sem, effort):
    async with sem:
        kw = dict(model=model, max_tokens=4000, system=t2s.SYSTEM,
                  messages=[{"role": "user", "content": prompt}])
        if effort:
            kw["output_config"] = {"effort": effort}
        r = await client.messages.create(**kw)
        text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        return text, r.usage.input_tokens, r.usage.output_tokens

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dbs", required=True, help="comma-separated db_ids, or 'all'")
    ap.add_argument("--n", type=int, default=60, help="questions per db (random, seeded)")
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--effort", default=None, help="low|medium|high|xhigh|max (default: API default)")
    ap.add_argument("--no-evidence", action="store_true", help="withhold BIRD's evidence hint")
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    load_key()
    dev = t2s.load_dev()
    dbs = sorted({r["db_id"] for r in dev}) if a.dbs == "all" else a.dbs.split(",")
    out_dir = t2s.HERE / "runs" / "scan"; out_dir.mkdir(parents=True, exist_ok=True)
    client = AsyncAnthropic(); sem = asyncio.Semaphore(a.concurrency)
    tot_in = tot_out = 0
    print(f"{'db':24}{'n':>5}{'EX':>7}{'95% CI':>16}{'exec_err':>10}")
    for db in dbs:
        qs = [r for r in dev if r["db_id"] == db]
        random.Random(a.seed).shuffle(qs); qs = qs[:a.n]
        tag = "noev" if a.no_evidence else "ev"
        path = out_dir / f"{a.model}__{db}__{tag}.jsonl"
        done = {}
        if path.exists():
            for line in path.read_text().splitlines():
                d = json.loads(line); done[d["question_id"]] = d
        schema = t2s.schema_prompt(qs[0]["db_path"])
        todo = [q for q in qs if q["question_id"] not in done]
        async def one(q):
            prompt = t2s.build_prompt(schema, q["question"], None if a.no_evidence else q.get("evidence"))
            t0 = time.time()
            try:
                text, ti, to = await ask(client, a.model, prompt, sem, a.effort)
            except Exception as e:
                return {**{k: q[k] for k in ("question_id", "db_id", "question", "difficulty")},
                        "error": f"api: {e}", "match": False}
            pred = t2s.extract_sql(text)
            prow, perr = t2s.execute(q["db_path"], pred)
            grow, gerr = t2s.execute(q["db_path"], q["SQL"])
            return {**{k: q[k] for k in ("question_id", "db_id", "question", "difficulty")},
                    "gold": q["SQL"], "pred": pred, "pred_err": perr, "gold_err": gerr,
                    "match": t2s.ex_match(prow, grow), "in_tok": ti, "out_tok": to,
                    "secs": round(time.time() - t0, 1)}
        results = await asyncio.gather(*(one(q) for q in todo))
        with path.open("a") as f:
            for r in results:
                f.write(json.dumps(r) + "\n"); done[r["question_id"]] = r
        rs = list(done.values()); k = sum(r["match"] for r in rs); n = len(rs)
        tot_in += sum(r.get("in_tok", 0) for r in results); tot_out += sum(r.get("out_tok", 0) for r in results)
        p, lo, hi = t2s.wilson(k, n)
        err = sum(1 for r in rs if r.get("pred_err"))
        print(f"{db:24}{n:>5}{p:>7.2f}{f'[{lo:.2f}, {hi:.2f}]':>16}{err:>10}")
    print(f"\nnew tokens this run: in={tot_in:,} out={tot_out:,}")

if __name__ == "__main__":
    asyncio.run(main())
