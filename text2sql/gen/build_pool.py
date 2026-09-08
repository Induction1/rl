"""Stage 1 of data generation: templates -> SQL -> execute -> filter -> pool.jsonl (no API, no GPU).
Usage: python gen/build_pool.py --per-tier 1200 [--show 3]
Keeps a query iff it executes, returns 1..50 rows, has a non-null value, and its (sql skeleton,
result signature) is new. Writes data/pool/pool_stage1.jsonl with tier, tags, sql, canonical question."""
from __future__ import annotations
import argparse, hashlib, json, random, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scan"))
import t2s
from templates import DB, TIERS
import sqlite3
from check_pool import check_row, hard

def skeleton(sql: str) -> str:
    s = re.sub(r"'[^']*'", "'?'", sql); s = re.sub(r"\b\d+(\.\d+)?\b", "?", s)
    s = re.sub(r"(?i)^select (?:t\d+\.)?(?:a2|district_id)\b", "SELECT ?", s)  # names vs ids = same shape
    return re.sub(r"\s+", " ", s).strip().lower()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-tier", type=int, default=1200); ap.add_argument("--show", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--max-rows", type=int, default=150)
    ap.add_argument("--max-per-skeleton", type=int, default=12, help="diversity cap: rows sharing one SQL skeleton per tier")
    a = ap.parse_args()
    dev = t2s.load_dev(); db_path = next(r["db_path"] for r in dev if r["db_id"] == "financial")
    db = DB(db_path); rng = random.Random(a.seed)
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    out_dir = HERE.parent / "data" / "pool"; out_dir.mkdir(parents=True, exist_ok=True)
    kept, seen, stats = [], set(), {}; per_skel = {}
    for tier, gen in TIERS.items():
        n_ok = n_try = 0; dup = err = empty = big = 0; flagged = {}
        while n_ok < a.per_tier and n_try < a.per_tier * 12:
            n_try += 1
            sql, q, tags = gen(db, rng)
            rows, e = t2s.execute(db_path, sql, timeout_s=20)
            if e: err += 1; continue
            if not rows or all(v is None for r in rows for v in r): empty += 1; continue
            if len(rows) > a.max_rows: big += 1; continue
            fl = hard(check_row(con, sql, rows))
            if fl:
                for x in fl: flagged[x] = flagged.get(x, 0) + 1
                continue
            sig = hashlib.md5(json.dumps(sorted(map(str, rows)))[:4000].encode()).hexdigest()
            key = (skeleton(sql), sig)
            if key in seen: dup += 1; continue
            sk = (tier, skeleton(sql))
            if per_skel.get(sk, 0) >= a.max_per_skeleton: dup += 1; continue
            per_skel[sk] = per_skel.get(sk, 0) + 1
            seen.add(key); n_ok += 1
            kept.append({"id": f"t{tier}_{n_ok:05d}", "tier": tier, "tags": tags, "sql": sql,
                         "canonical_question": q, "n_rows": len(rows), "result_sig": sig})
        stats[tier] = dict(kept=n_ok, tried=n_try, dup=dup, err=err, empty=empty, too_big=big, checker_rejected=flagged)
    path = out_dir / "pool_stage1.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in kept))
    print(f"wrote {len(kept)} rows -> {path}")
    for t, s in stats.items(): print(f"  tier {t}: {s}")
    if a.show:
        for t in TIERS:
            print(f"\n=== tier {t} samples")
            for r in rng.sample([r for r in kept if r["tier"] == t], min(a.show, sum(r['tier']==t for r in kept))):
                print(f"Q: {r['canonical_question']}\n   {r['sql']}\n   -> {r['n_rows']} rows  tags={r['tags']}")

if __name__ == "__main__":
    main()
