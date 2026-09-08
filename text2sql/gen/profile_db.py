"""Profile the database BEFORE writing query templates: declared vs actual type, NULLs, distinct,
min/max, and top-k tie risk per column. Writes data/pool/profile.json; templates consult it."""
import json, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scan")); import t2s
dev = t2s.load_dev(); db = next(r["db_path"] for r in dev if r["db_id"] == "financial")
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True); prof = {}
for (t,) in con.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
    n = con.execute(f'select count(*) from "{t}"').fetchone()[0]; prof[t] = {"rows": n, "cols": {}}
    for _, c, decl, *_ in con.execute(f'pragma table_info("{t}")'):
        q = lambda s: con.execute(s).fetchone()
        nulls = q(f'select count(*) from "{t}" where "{c}" is null')[0]
        types = [r[0] for r in con.execute(f'select distinct typeof("{c}") from "{t}" where "{c}" is not null')]
        distinct = q(f'select count(distinct "{c}") from "{t}"')[0]
        numeric_text = decl.upper() == "TEXT" and all(r[0] for r in con.execute(f'select "{c}" glob "*[0-9]*" and not "{c}" glob "*[a-zA-Z]*" from "{t}" where "{c}" is not null limit 50'))
        expr = f'CAST("{c}" AS REAL)' if numeric_text else f'"{c}"'
        mn, mx = q(f'select min({expr}), max({expr}) from "{t}" where "{c}" is not null')
        # tie risk: does the top-5 / bottom-5 boundary tie?
        tie = {}
        if (types and types[0] in ("integer", "real")) or numeric_text:
            for k in (1, 3, 5):
                for d in ("DESC", "ASC"):
                    rows = con.execute(f'select {expr} from "{t}" where "{c}" is not null order by {expr} {d} limit {k+1}').fetchall()
                    tie[f"{d}{k}"] = len(rows) > k and rows[k-1][0] == rows[k][0]
        prof[t]["cols"][c] = {"declared": decl, "stored": types, "nulls": nulls, "distinct": distinct,
                              "numeric_text": numeric_text, "min": mn, "max": mx, "tie_at_boundary": tie}
Path("data/pool").mkdir(parents=True, exist_ok=True)
json.dump(prof, open("data/pool/profile.json", "w"), indent=1, default=str)
print("WARNINGS:")
for t, p in prof.items():
    for c, i in p["cols"].items():
        flags = []
        if i["numeric_text"]: flags.append("NUMERIC STORED AS TEXT")
        if i["nulls"]: flags.append(f"{i['nulls']} NULLs")
        if any(i["tie_at_boundary"].values()): flags.append("ties at top-k: " + ",".join(k for k, v in i["tie_at_boundary"].items() if v))
        if i["distinct"] <= 1: flags.append("constant column")
        if flags: print(f"  {t}.{c:12} {' | '.join(flags)}")
