"""Run-2 pool: run-1 pool (pool_run1, keep=True) + hop/date/outconv rows after the English pass + reading check.
For date_phrase and outconv, HALF the rows keep the terse canonical question (BIRD phrasing is terse; the OmniSQL
styles expand it). Dedupe by (skeleton, result_sig). Usage: python gen/merge_v2.py"""
import json, random, sys, collections
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scan"))
from build_pool import skeleton
P = HERE.parent / "data" / "pool"
base = [json.loads(l) for l in open(P / "pool_run1.jsonl") if l.strip()]
hops = [json.loads(l) for l in open(P / "pool_hops_stage3.jsonl") if l.strip()]
topup = [json.loads(l) for l in open(P / "pool_topup_stage2.jsonl") if l.strip()] if (P / "pool_topup_stage2.jsonl").exists() else []
rank = [json.loads(l) for l in open(P / "pool_rank_stage2.jsonl") if l.strip()] if (P / "pool_rank_stage2.jsonl").exists() else []
for r in topup + rank: r["question"] = r["canonical_question"]; r["style"] = "canonical"   # no API pass: template English (2026-09-06, no console credits)
rng = random.Random(0); seen = set(); out = []
for r in base + hops + topup + rank:
    if not r.get("keep", True): continue
    k = (skeleton(r["sql"]), r["result_sig"])
    if k in seen: continue
    seen.add(k)
    if r["family"] in ("date_phrase", "outconv") and rng.random() < 0.5:
        r = dict(r); r["question"] = r["canonical_question"]; r["style"] = "canonical"
    out.append(r)
(P / "pool_run2.jsonl").write_text("".join(json.dumps(r) + "\n" for r in out))
print(f"pool_run2: {len(out)} rows (base kept {sum(1 for r in base if r.get('keep', True))}, hops kept {sum(1 for r in hops if r.get('keep', True))}, topup {len(topup)}, rank {len(rank)})")
print("per tier:", dict(sorted(collections.Counter(r["tier"] for r in out).items())))
for f, n in sorted(collections.Counter(r["family"] for r in out).items()): print(f"  {f:14}{n:>5}")
