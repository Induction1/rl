"""Stage 3: the READING check (no solving). Built from OmniSQL's two GPT_evaluation prompts
(adherence.txt = does the SQL align with the question; input_quality.txt = is the question itself
good), fetched 2026-09-05 and merged into one call. The judge sees schema, legend, question, SQL,
output columns and the first result rows. It never writes SQL, so nothing is capped by what it
can solve. Verdicts are LOGGED on every row; a row is 'kept' iff all four gating criteria are
Excellent or Good. Usage: python gen/reading_check.py --in pool_stage2.jsonl --out pool_stage3.jsonl [--model claude-haiku-4-5]"""
from __future__ import annotations
import argparse, asyncio, json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scan"))
import t2s
from semantics import legend
from write_questions import load_key
from anthropic import AsyncAnthropic

PROMPT = """Task Overview:
You are a data science expert evaluating a text-to-SQL training example: a natural language question, an SQL query meant to answer it, and the first rows the query returns on the real database. Using the provided database schema and column legend, assess (a) how accurately the query follows the question and (b) the quality of the question itself. Address each criterion below.

Evaluation Criteria:
1. Result Alignment: Does the SQL query return exactly the columns requested in the question, without including any extraneous or unnecessary columns, and without the question asking for columns, rounding, or formatting the query does not produce?
2. Structural Alignment: Does the structure of the SQL query accurately reflect the logic and intent of the natural language question (predicates, grouping, ORDER BY, LIMIT, set operations)?
3. Answer Adherence: Is the SQL query both acceptable and correct as a solution to the posed question, fully addressing its requirements?
4. Unambiguous Phrasing: Is the question clearly worded, such that a competent analyst would write a query with the same result?
5. Real-world Relevance: Would a bank analyst or manager plausibly ask this question? (Questions that merely describe a query shape, e.g. "top 15 combinations of X and Y by average Z", are Poor.)
6. Proper Grammar: Is the question grammatically correct, with clear syntax and no spelling errors?

Leveling Criteria:
Excellent: meets the requirement fully and flawlessly.
Good: meets most of the requirements with minor issues that do not affect the outcome.
Average: partially meets the requirements with mistakes that impact the result.
Poor: fails to meet key requirements.

Database Engine: SQLite

Database Schema:
{schema}

Column Legend (coded columns and coded values):
{legend}

Question:
{question}

SQL Query:
```sql
{sql}
```

Output columns: {out_cols}
First rows returned ({n_rows} total):
{rows}

Output Format:
Think through the process step by step, then give your final decision in this JSON format:
```json
{{
  "Result Alignment": ["level", "explanation"],
  "Structural Alignment": ["level", "explanation"],
  "Answer Adherence": ["level", "explanation"],
  "Unambiguous Phrasing": ["level", "explanation"],
  "Real-world Relevance": ["level", "explanation"],
  "Proper Grammar": ["level", "explanation"]
}}
```
"level" must be one of: "Excellent", "Good", "Average", "Poor"."""

GATES = ["Result Alignment", "Structural Alignment", "Answer Adherence", "Unambiguous Phrasing", "Real-world Relevance"]

def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    try: return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError: return None

async def judge(client, sem, model, prompt):
    async with sem:
        r = await client.messages.create(model=model, max_tokens=1500, messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in r.content if b.type == "text")

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="claude-haiku-4-5"); ap.add_argument("--concurrency", type=int, default=8)
    a = ap.parse_args(); load_key()
    dev = t2s.load_dev(); db_path = next(r["db_path"] for r in dev if r["db_id"] == "financial")
    schema = t2s.schema_prompt(db_path, sample_rows=0); lg = legend()
    rows = [json.loads(l) for l in open(a.inp)]
    done = {}
    if Path(a.out).exists():
        for l in open(a.out): d = json.loads(l); done[d["id"]] = d
    todo = [r for r in rows if r["id"] not in done]
    client = AsyncAnthropic(); sem = asyncio.Semaphore(a.concurrency)
    async def one(row):
        res, _ = t2s.execute(db_path, row["sql"])
        shown = "\n".join(" | ".join(str(v) for v in r) for r in (res or [])[:5])
        prompt = PROMPT.format(schema=schema, legend=lg, question=row["question"], sql=row["sql"],
                               out_cols=row.get("out_cols"), n_rows=len(res or []), rows=shown)
        text = await judge(client, sem, a.model, prompt)
        v = parse(text) or {}
        levels = {k: (v.get(k) or ["?", ""])[0] for k in GATES + ["Proper Grammar"]}
        keep = all(levels.get(k) in ("Excellent", "Good") for k in GATES)
        return {**row, "check_model": a.model, "check": v, "check_levels": levels, "keep": keep}
    lock = asyncio.Lock(); out_f = open(a.out, "a")
    async def one_and_write(r):
        try: rec = await one(r)
        except Exception as e:
            print("row failed:", r["id"], str(e)[:120]); return None
        async with lock:
            out_f.write(json.dumps(rec) + "\n"); out_f.flush(); done[rec["id"]] = rec
        return rec
    results = [x for x in await asyncio.gather(*(one_and_write(r) for r in todo)) if x]
    out_f.close()
    allr = list(done.values())
    print(f"{'tier':>5}{'n':>5}{'kept':>6}{'  worst criterion (count of non-Good)'}")
    for t in sorted({r['tier'] for r in allr}):
        rs = [r for r in allr if r["tier"] == t]
        bad = {k: sum(1 for r in rs if r["check_levels"].get(k) not in ("Excellent", "Good")) for k in GATES}
        worst = max(bad, key=bad.get)
        print(f"{t:>5}{len(rs):>5}{sum(r['keep'] for r in rs):>6}  {worst}={bad[worst]}")

if __name__ == "__main__":
    asyncio.run(main())
