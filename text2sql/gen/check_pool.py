"""Mechanical checker: every gold-bug class the 9/5 agent audits found, as a deterministic test that
runs on every generated row. Hard flags reject the row; soft flags are reported. Used by build_pool
(reject at generation time) and as a CLI over any pool file:
    python gen/check_pool.py data/pool/pool_stage1.jsonl
Classes (from the audits): text_affinity · tie_at_limit · null_in_result · noop_filter ·
single_group · unquoted_order · empty/oversize (already filtered upstream, re-checked here)."""
from __future__ import annotations
import json, re, sqlite3, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scan"))
import t2s

TEXT_NUMERIC = ("A4", "A5", "A6", "A7")
HARD = {"text_affinity", "tie_at_limit", "null_in_result", "unquoted_order", "empty", "oversize", "error", "noop_filter", "unordered_limit", "nondeterministic"}
SOFT = {"single_group", "unchecked_limit"}

def _text_affinity(sql: str) -> bool:
    """A4–A7 used in a comparison or ORDER BY without CAST(... ) wrapping it."""
    for c in TEXT_NUMERIC:
        for m in re.finditer(rf"(?<![A-Za-z0-9_])(?:T\d+\.)?{c}\b", sql):
            before = sql[max(0, m.start() - 6):m.start()].upper()
            after = sql[m.end():m.end() + 12]
            if "CAST(" in before:                      # CAST(T2.A4 AS ...) — safe
                continue
            if re.match(r"\s*(>=|<=|>|<|=|!=|\+|-)", after) or re.search(rf"ORDER BY\s+(?:T\d+\.)?{c}\b", sql, re.I):
                return True
            # also: literal on the left side (thr > A4)
            if re.search(rf"(>=|<=|>|<|=)\s*(?:T\d+\.)?{c}\b", sql):
                return True
    return False

def _unquoted_order(sql: str) -> bool:
    return re.search(r"(?i)\b(from|join)\s+order\b", sql) is not None

_LIMIT = re.compile(r"(?is)^(?P<body>.*?)\bORDER BY\s+(?P<key>.+?)\s*(?P<dir>ASC|DESC)?\s*LIMIT\s+(?P<k>\d+)\s*$")
def _tie_at_limit(con, sql: str):
    """Rebuild the query with the ORDER BY key projected, fetch k+1 rows, compare the k-th and (k+1)-th keys.
    Returns True (tie), False (no tie), or None (could not check)."""
    m = _LIMIT.match(sql.strip())
    if not m:
        return None if re.search(r"(?i)\bLIMIT\b", sql) else False
    body, key, d, k = m.group("body"), m.group("key").strip(), (m.group("dir") or "ASC").upper(), int(m.group("k"))
    if re.search(r"(?i)\b(INTERSECT|EXCEPT|UNION)\b", body):
        return None
    # if key is a positional or alias reference, resolve against the select list
    sel = re.match(r"(?is)^\s*SELECT\s+(DISTINCT\s+)?(?P<list>.+?)\s+FROM\b", body)
    if not sel:
        return None
    cols = [c.strip() for c in re.split(r",(?![^()]*\))", sel.group("list"))]
    if key.isdigit():
        key_expr = re.sub(r"(?i)\s+AS\s+\w+$", "", cols[int(key) - 1])
    else:
        alias_hit = [c for c in cols if re.search(rf"(?i)\bAS\s+{re.escape(key)}$", c)]
        key_expr = re.sub(r"(?i)\s+AS\s+\w+$", "", alias_hit[0]) if alias_hit else key
    probe = re.sub(r"(?is)^\s*SELECT\s+(DISTINCT\s+)?", lambda mm: mm.group(0) + f"({key_expr}) AS __key, ", body, count=1)
    probe = f"{probe} ORDER BY __key {d} LIMIT {k + 1}"
    try:
        rows = con.execute(probe).fetchall()
    except sqlite3.Error:
        return None
    return len(rows) > k and rows[k - 1][0] == rows[k][0]

def _noop_filter(con, sql: str, n_rows: int):
    """A HAVING or a single top-level numeric WHERE that excludes nothing."""
    m = re.search(r"(?is)\bHAVING\b(.+?)(\bORDER BY\b|\bLIMIT\b|$)", sql)
    if m:
        stripped = sql[:m.start()] + sql[m.end(1):]
        try:
            return len(con.execute(stripped).fetchall()) == n_rows
        except sqlite3.Error:
            return None
    m = re.search(r"(?is)\bWHERE\s+((?:CAST\()?[\w\.]+(?:\s+AS\s+\w+\))?\s*(>=|<=|>|<)\s*[\d\.]+)\s*(\bGROUP\b|\bORDER\b|\bLIMIT\b|$)", sql)
    if m and " AND " not in sql.upper() and " OR " not in sql.upper():
        stripped = sql[:m.start()] + sql[m.end(1):]
        try:
            return len(con.execute(stripped).fetchall()) == n_rows
        except sqlite3.Error:
            return None
    return False

def check_row(con, sql: str, rows) -> list[str]:
    flags = []
    if rows is None: return ["error"]
    if not rows: return ["empty"]
    if len(rows) > 300: flags.append("oversize")
    if any(v is None for r in rows for v in r): flags.append("null_in_result")
    if _text_affinity(sql): flags.append("text_affinity")
    if _unquoted_order(sql): flags.append("unquoted_order")
    if re.search(r"(?i)\bLIMIT\s+\d+", sql) and not re.search(r"(?i)\bORDER BY\b", sql): flags.append("unordered_limit")
    if re.search(r"(?i)CURRENT_DATE|CURRENT_TIMESTAMP|\bnow\b|RANDOM\(", sql): flags.append("nondeterministic")
    tie = _tie_at_limit(con, sql)
    if tie: flags.append("tie_at_limit")
    elif tie is None: flags.append("unchecked_limit")
    if re.search(r"(?i)\bGROUP BY\b", sql) and len(rows) == 1: flags.append("single_group")
    noop = _noop_filter(con, sql, len(rows))
    if noop: flags.append("noop_filter")
    return flags

def hard(flags): return [f for f in flags if f in HARD]

if __name__ == "__main__":
    path = sys.argv[1]
    dev = t2s.load_dev(); db = next(r["db_path"] for r in dev if r["db_id"] == "financial")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    import collections; cnt = collections.Counter(); bad = 0
    for line in open(path):
        r = json.loads(line); rows, e = t2s.execute(db, r["sql"])
        f = check_row(con, r["sql"], None if e else rows)
        for x in f: cnt[(r["tier"], x)] += 1
        if hard(f):
            bad += 1; print(f"[t{r['tier']} {r['id']}] {hard(f)} :: {r['sql'][:130]}")
    print(f"\nrows with HARD flags: {bad}\nall flags (tier, class): {dict(sorted(cnt.items()))}")
