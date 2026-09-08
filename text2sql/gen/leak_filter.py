"""A3 leak audit: drop any training row whose ANSWER (result signature) equals the answer of one of the
106 held-out BIRD financial questions, and any row whose SQL skeleton equals a BIRD gold skeleton.
Conservative on purpose: coincidental matches are removed too. Usage: python gen/leak_filter.py IN OUT"""
import json, sys, hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scan"))
import t2s
from build_pool import skeleton
src, dst = sys.argv[1], sys.argv[2]
dev = t2s.load_dev(); fin = [r for r in dev if r["db_id"] == "financial"]; db = fin[0]["db_path"]
bird_sigs, bird_skel = set(), set()
for r in fin:
    rows, e = t2s.execute(db, r["SQL"])
    if not e and rows: bird_sigs.add(hashlib.md5(json.dumps(sorted(map(str, rows)))[:4000].encode()).hexdigest())
    bird_skel.add(skeleton(r["SQL"]))
kept, dropped = [], []
for line in open(src):
    r = json.loads(line)
    if r["result_sig"] in bird_sigs or skeleton(r["sql"]) in bird_skel: dropped.append(r)
    else: kept.append(r)
Path(dst).write_text("".join(json.dumps(r) + "\n" for r in kept))
print(f"leak filter: kept {len(kept)}, dropped {len(dropped)} (answer or shape shared with a held-out BIRD question) -> {dst}")
