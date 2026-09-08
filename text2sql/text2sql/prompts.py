"""Every piece of text the model sees, in one place.

v1 (run 1, 2026-09-05): schema (CREATE TABLE + 3 sample rows per table) + question. NO legend, NO join
graph, NO value lists. SQL-only output. Kept verbatim so run 1 stays reproducible.

v2 (run 2, 2026-09-06, his decisions after the run-1 failure read): the standard BIRD input —
  1. column legend for district's coded columns + every coded value (from gen/semantics.py),
  2. the join graph in prose (one line per foreign key; "client reaches account only through disp"),
  3. the distinct values of every low-cardinality text column, exact casing (kills the 'North Bohemia' trap),
  4. system line "only output the information that is asked" (SLM-SQL's line; targets output-column errors),
  5. optional think-then-SQL format (reasoning inside <think>…</think>, then ONE ```sql block).
The think variant is gated: base-model pass@8 with and without it decides (scan/gate_scan.py)."""
from __future__ import annotations
import sqlite3, sys
from pathlib import Path

# ----------------------------------------------------------------------------- v1 (run 1, frozen)
SYSTEM_PROMPT = (
    "You are an expert SQLite analyst for a bank's database. Given the database schema and a question, "
    "write ONE SQLite query that answers the question exactly: the requested columns and no others, the "
    "requested ordering and limit if any. Return only the query inside a single ```sql fenced block."
)

def user_message(schema: str, question: str) -> str:
    return f"Database schema:\n\n{schema}\n\nQuestion: {question.strip()}\n\nAnswer with a single SQLite query in a ```sql block."

# ----------------------------------------------------------------------------- v2
SYSTEM_PROMPT_V2 = (
    "You are an expert SQLite analyst for a Czech bank's database. Given the database schema, a legend of "
    "its coded columns and values, the join graph, and a question, write ONE SQLite query that answers the "
    "question. Only output the information that is asked: the requested columns and no others, the requested "
    "ordering and limit if any. String comparisons are case-sensitive: use the stored values exactly as listed. "
    "Return only the query inside a single ```sql fenced block."
)

SYSTEM_PROMPT_THINK = (
    "You are an expert SQLite analyst for a Czech bank's database. Given the database schema, a legend of "
    "its coded columns and values, the join graph, and a question, write ONE SQLite query that answers the "
    "question. Only output the information that is asked: the requested columns and no others, the requested "
    "ordering and limit if any. String comparisons are case-sensitive: use the stored values exactly as listed. "
    "First reason briefly inside <think> and </think> tags: which tables are needed, the join path between "
    "them, the filters, and the output columns. Then return the query inside a single ```sql fenced block "
    "after the closing </think> tag. No SQL fences inside the think section."
)

JOIN_GRAPH = """Join graph (how the tables connect; there are no other links):
  account.district_id -> district.district_id   (the district where the ACCOUNT is held)
  client.district_id  -> district.district_id   (the district where the CLIENT lives; can differ from the account's)
  disp.client_id -> client.client_id  and  disp.account_id -> account.account_id
      (disp links clients to accounts; client and account are connected ONLY through disp; disp.type = OWNER or DISPONENT)
  card.disp_id -> disp.disp_id   (a card belongs to a disposition, so to one client on one account)
  loan.account_id  -> account.account_id
  trans.account_id -> account.account_id   (transactions belong to accounts, not to clients; balance lives in trans)
  order.account_id -> account.account_id   (table name must be quoted: "order")
  Typical paths: client -> disp -> account -> {loan | trans | order | district};  card -> disp -> {client | account}.
Dates are TEXT in 'YYYY-MM-DD' form. Compare years with STRFTIME('%Y', col): "in 1996" = STRFTIME('%Y', col) = '1996',
"after 1996" = STRFTIME('%Y', col) > '1996', "before 1996" = < '1996', "between 1995 and 1997" = BETWEEN '1995' AND '1997'."""

# low-cardinality TEXT columns whose exact stored values matter (profiled 2026-09-06 on financial_work.sqlite)
VALUE_COLUMNS = [("district", "A3"), ("account", "frequency"), ("disp", "type"), ("card", "type"), ("loan", "status"),
                 ("client", "gender"), ("trans", "type"), ("trans", "operation"), ("trans", "k_symbol"), ("order", "k_symbol"),
                 ("trans", "bank"), ("order", "bank_to")]

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "gen"))

def legend_text() -> str:
    """The coded-column / coded-value legend from gen/semantics.py (the run-1 'withheld' knowledge)."""
    from semantics import DISTRICT, VALUES, TABLES
    out = ["Tables:"] + [f"  {t}: {m}" for t, m in TABLES.items()]
    out += ["District columns (coded):"] + [f"  {c} = {m}" for c, m in DISTRICT.items()]
    out += ["  A4–A7 are stored as TEXT; CAST them to INTEGER before comparing or sorting."]
    out += ["Coded values:"]
    for (t, c), m in VALUES.items():
        out.append(f"  {t}.{c}: " + "; ".join(f"'{k}' = {v}" for k, v in m.items()))
    return "\n".join(out)

def value_lists(db_path: str) -> str:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True); con.text_factory = lambda b: b.decode("utf-8", "replace")
    out = ["Distinct stored values of the categorical text columns (exact spelling and case):"]
    for t, c in VALUE_COLUMNS:
        vals = [r[0] for r in con.execute(f'SELECT DISTINCT "{c}" FROM "{t}" WHERE "{c}" IS NOT NULL AND TRIM("{c}") != \'\' ORDER BY 1')]
        out.append(f"  {t}.{c}: " + ", ".join(f"'{v}'" for v in vals))
    con.close(); return "\n".join(out)

def context_block(db_path: str) -> str:
    """Everything v2 adds to the prompt besides the schema. Built once per taskset load."""
    return legend_text() + "\n\n" + JOIN_GRAPH + "\n\n" + value_lists(db_path)

def user_message_v2(schema: str, question: str, context: str, think: bool = False) -> str:
    tail = ("Reason inside <think>…</think> first, then answer with a single SQLite query in a ```sql block."
            if think else "Answer with a single SQLite query in a ```sql block.")
    return f"Database schema:\n\n{schema}\n\n{context}\n\nQuestion: {question.strip()}\n\n{tail}"

def system_prompt(version: int = 1, think: bool = False) -> str:
    if version == 1: return SYSTEM_PROMPT
    return SYSTEM_PROMPT_THINK if think else SYSTEM_PROMPT_V2
