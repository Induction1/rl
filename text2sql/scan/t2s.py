"""Shared pieces for the text2sql project: BIRD loading, schema prompts, SQLite execution,
and the BIRD execution-accuracy (EX) matcher. Used by the frontier scan, the local-model scan,
and later by the verifiers environment."""
from __future__ import annotations
import json, re, sqlite3, threading
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent          # .../text2sql
DATA = HERE / "data"

def find_dev_root() -> Path:
    """dev.zip unpacks as dev_YYYYMMDD/ (sometimes with a nested folder). Find dev.json."""
    hits = sorted(DATA.rglob("dev.json"))
    if not hits:
        raise FileNotFoundError("dev.json not found under data/ — is dev.zip unpacked?")
    return hits[0].parent

def load_dev() -> list[dict]:
    root = find_dev_root()
    rows = json.loads((root / "dev.json").read_text())
    work = DATA / "financial_work.sqlite"   # indexed working copy (same data; trans indexes for speed)
    for r in rows:
        r["db_path"] = str(root / "dev_databases" / r["db_id"] / f"{r['db_id']}.sqlite")
        if r["db_id"] == "financial" and work.exists():
            r["db_path"] = str(work)
    return rows

def schema_prompt(db_path: str, sample_rows: int = 3) -> str:
    """CREATE TABLE statements plus a few sample rows per table — the standard BIRD prompt shape."""
    con = sqlite3.connect(db_path)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    cur = con.cursor()
    out = []
    tables = cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL "
                         "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    for name, ddl in tables:  # fetchall first: reusing `cur` inside the loop would reset the iteration
        out.append(ddl.strip() + ";")
        if sample_rows:
            try:
                rows = cur.execute(f'SELECT * FROM "{name}" LIMIT {sample_rows}').fetchall()
                cols = [d[0] for d in cur.description]
                out.append(f"/* {sample_rows} sample rows from {name}:\n" + " | ".join(cols) + "\n" +
                           "\n".join(" | ".join(str(v)[:40] for v in r) for r in rows) + "\n*/")
            except sqlite3.Error as e:
                out.append(f"/* sample rows unavailable: {e} */")
        out.append("")
    con.close()
    return "\n".join(out)

SYSTEM = ("You are an expert SQLite analyst. Given a database schema and a question, write ONE SQLite "
          "query that answers the question. Return only the query inside a ```sql fenced block.")

def build_prompt(schema: str, question: str, evidence: str | None) -> str:
    parts = ["Database schema:\n", schema, "\nQuestion: " + question.strip()]
    if evidence:
        parts.append("Hint: " + evidence.strip())
    parts.append("\nAnswer with a single SQLite query in a ```sql block.")
    return "\n".join(parts)

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.S | re.I)
def extract_sql(text: str) -> str:
    m = _FENCE.findall(text)
    sql = (m[-1] if m else text).strip()
    return sql.rstrip(";").strip() if sql else ""

def execute(db_path: str, sql: str, timeout_s: float = 30.0):
    """Run read-only; returns (rows, None) or (None, error_string). Interrupts after timeout_s."""
    if not sql:
        return None, "empty"
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    timer = threading.Timer(timeout_s, con.interrupt)
    timer.start()
    try:
        rows = con.execute(sql).fetchall()
        return rows, None
    except sqlite3.Error as e:
        return None, f"{type(e).__name__}: {e}"
    finally:
        timer.cancel(); con.close()

def ex_match(pred_rows, gold_rows) -> bool:
    """BIRD's official metric: set equality of result rows (order-insensitive, duplicates collapsed)."""
    if pred_rows is None or gold_rows is None:
        return False
    return set(map(tuple, pred_rows)) == set(map(tuple, gold_rows))

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Accuracy with a 95% Wilson interval — for the per-database scan table."""
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n; d = 1 + z*z/n; c = p + z*z/(2*n); h = z * ((p*(1-p)/n + z*z/(4*n*n)) ** 0.5)
    return p, (c - h)/d, (c + h)/d
