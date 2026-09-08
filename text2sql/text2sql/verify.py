"""The reward. Implements VERIFIER.md (2026-09-05): execute the model's query read-only on the financial
database and compare to the gold result set.
  1  row order: ignored unless the task is tagged order-sensitive (ranking / top-k) → list compare
  2  duplicates: collapsed (set compare), as BIRD EX
  3  column count must match; extra columns fail
  4  column order is positional (tuples)
  5  floats: exact equality (his default; ints and floats compare numerically, 1 == 1.0)
  6  empty result never scores
  7  errors / timeouts (30 s) → 0
  8  (LIFTED 2026-09-06, his decision: 5 held-out golds return >1000 rows and could never score; BIRD EX has no cap)
  9  all-NULL result never scores
 11  format: exactly one ```sql block, else 0 (no partial credit)
 12  read-only connection; any write / PRAGMA / ATTACH fails at the engine
Returns a dict of reward components + metrics so the taskset can record them."""
from __future__ import annotations
import re, sqlite3, threading

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.S | re.I)
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_FORBIDDEN = re.compile(r"(?i)\b(ATTACH|PRAGMA|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|VACUUM)\b")

def extract_sql(text: str):
    """Exactly one fenced block → its SQL; zero or several → None (rule 11)."""
    text = _THINK.sub("", text or "")          # v2 think format: reasoning is not the answer (2026-09-06)
    if "<think>" in text.lower():              # unclosed think section → no answer
        return None
    blocks = _FENCE.findall(text)
    if len(blocks) != 1:
        return None
    sql = blocks[0].strip().rstrip(";").strip()
    return sql or None

def execute(db_path: str, sql: str, timeout_s: float = 30.0):
    if not sql or _FORBIDDEN.search(sql):
        return None, "forbidden_or_empty"
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    timer = threading.Timer(timeout_s, con.interrupt); timer.start()
    try:
        return con.execute(sql).fetchall(), None
    except sqlite3.Error as e:
        return None, f"{type(e).__name__}: {e}"
    finally:
        timer.cancel(); con.close()

def _norm(v):
    if isinstance(v, bool): return int(v)
    if isinstance(v, (int, float)): return float(v)
    return v

def _rows(rows):
    return [tuple(_norm(v) for v in r) for r in rows]

def compare(pred_rows, gold_rows, order_sensitive: bool) -> bool:
    if pred_rows is None or gold_rows is None: return False
    if not pred_rows or not gold_rows: return False                     # rule 6
    # rule 8 (row cap) lifted 2026-09-06 — see header
    if all(v is None for r in pred_rows for v in r): return False       # rule 9
    if len(pred_rows[0]) != len(gold_rows[0]): return False              # rule 3
    p, g = _rows(pred_rows), _rows(gold_rows)
    if order_sensitive:
        # dedupe while preserving order, then compare as lists (rule 1)
        def dedupe(xs):
            seen, out = set(), []
            for x in xs:
                if x not in seen: seen.add(x); out.append(x)
            return out
        return dedupe(p) == dedupe(g)
    return set(p) == set(g)                                              # rule 2

def score(db_path: str, completion_text: str, gold_sql: str, order_sensitive: bool) -> dict:
    sql = extract_sql(completion_text)
    out = {"format": 1.0 if sql else 0.0, "correct": 0.0, "executed": 0.0, "error": None, "pred_sql": sql}
    if not sql:
        return out
    pred, perr = execute(db_path, sql)
    if perr:
        out["error"] = perr; return out
    out["executed"] = 1.0
    gold, gerr = execute(db_path, gold_sql)
    out["correct"] = 1.0 if compare(pred, gold, order_sensitive) else 0.0
    return out
