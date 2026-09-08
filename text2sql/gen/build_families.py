"""Family-aware pool builder: per-tier, per-family targets; same filters as build_pool (execute, non-empty,
row cap, checker, dedupe by skeleton+result, repeat cap). Writes data/pool/pool_stage1.jsonl with a
`family` field. Usage: python gen/build_families.py --plan default [--scale 0.1] [--seed 0]
--scale 0.1 = a smoke run at 10 % of every target."""
from __future__ import annotations
import argparse, hashlib, json, random, sqlite3, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scan"))
import t2s
from templates import DB, t1, t2, t3, t4
from templates_extra import t2x, t3x
from build_pool import skeleton
from check_pool import check_row, hard
import families_t4, families_t3, families_bird, families_hops
try:
    import families_t2, families_t1
except ImportError:
    families_t2 = families_t1 = None

def plan_default():
    """(tier, family_name, generator, target). Existing generators count as families too."""
    P = [(1, "t1_base", t1, 300)]
    if families_t1: P += [(1, n, f, 90) for n, f in families_t1.FAMILIES]
    P += [(2, "t2_base", t2, 250), (2, "t2_extra", t2x, 400)]
    if families_t2: P += [(2, n, f, 100) for n, f in families_t2.FAMILIES]
    P += [(3, "t3_base", t3, 150), (3, "t3_extra", t3x, 300)]
    P += [(3, n, f, {"ratios": 200, "date_groups": 150, "multi_group": 150, "distinct_groups": 100, "trans_agg": 250}[n]) for n, f in families_t3.FAMILIES]
    P += [(4, "t4_base", t4, 350)]
    P += [(4, n, f, {"correlated": 200, "setops": 200, "antijoin": 150, "cond_having": 150, "nested_agg": 150, "date_arith": 150, "trans_hard": 250}[n]) for n, f in families_t4.FAMILIES]
    P += [(t, n, f, k) for t, n, f, k in families_bird.FAMILIES]
    P += [(t, n, f, k) for t, n, f, k in families_hops.FAMILIES]   # 2026-09-06: schema-graph hop / date / output-convention families
    return P

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-rows", type=int, default=300); ap.add_argument("--max-per-skeleton", type=int, default=30)
    ap.add_argument("--out", default=str(HERE.parent / "data" / "pool" / "pool_stage1.jsonl"))
    ap.add_argument("--only", default="", help="comma-separated family names to (re)generate; others skipped")
    a = ap.parse_args()
    dev = t2s.load_dev(); db_path = next(r["db_path"] for r in dev if r["db_id"] == "financial")
    db = DB(db_path); rng = random.Random(a.seed); con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    kept, seen, per_skel = [], set(), {}
    print(f"{'tier':>4} {'family':16}{'target':>7}{'kept':>6}{'tried':>7}{'dup':>6}{'empty':>6}{'big':>5}{'flag':>5}{'s':>6}")
    only = set(a.only.split(",")) if a.only else None
    for tier, fam, gen, target in plan_default():
        if only and fam not in only: continue
        target = max(3, int(round(target * a.scale))); n = tries = dup = empty = big = flagged = 0; t0 = time.time()
        while n < target and tries < target * 6:
            tries += 1
            try: sql, q, tags = gen(db, rng)
            except RecursionError: continue
            rows, e = t2s.execute(db_path, sql, timeout_s=20)
            if e or not rows or all(v is None for r in rows for v in r): empty += 1; continue
            if len(rows) > a.max_rows: big += 1; continue
            if hard(check_row(con, sql, rows)): flagged += 1; continue
            sig = hashlib.md5(json.dumps(sorted(map(str, rows)))[:4000].encode()).hexdigest()
            key = (skeleton(sql), sig); sk = (tier, skeleton(sql))
            if key in seen or per_skel.get(sk, 0) >= a.max_per_skeleton: dup += 1; continue
            seen.add(key); per_skel[sk] = per_skel.get(sk, 0) + 1; n += 1
            kept.append({"id": f"t{tier}_{fam}_{n:04d}", "tier": tier, "family": fam, "tags": tags, "sql": sql,
                         "canonical_question": q, "n_rows": len(rows), "result_sig": sig})
        print(f"{tier:>4} {fam:16}{target:>7}{n:>6}{tries:>7}{dup:>6}{empty:>6}{big:>5}{flagged:>5}{time.time()-t0:>6.0f}", flush=True)
        Path(a.out).write_text("".join(json.dumps(r) + "\n" for r in kept))  # incremental: a kill never loses finished families
    Path(a.out).write_text("".join(json.dumps(r) + "\n" for r in kept))
    by = {}
    for r in kept: by[r["tier"]] = by.get(r["tier"], 0) + 1
    print(f"\nwrote {len(kept)} rows -> {a.out}   per tier: {by}")

if __name__ == "__main__":
    main()
