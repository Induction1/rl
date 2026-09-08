"""Stage 2: question synthesis, using OmniSQL's published prompt template (RUCKBReasoning/OmniSQL,
data_synthesis/question_synthesis, fetched 2026-09-05) filled with our legend as the column info.
Deviation from OmniSQL, on purpose: we add a "Reference phrasing" line (the template's canonical
question) so the model rephrases a correct sentence rather than inferring meaning from SQL alone.
Optional --roundtrip adds a Haiku-solves-it tag (difficulty info only; NOT a filter).
Usage: python gen/write_questions.py --in data/pool/pool_stage1.jsonl --out data/pool/pool_stage2.jsonl [--limit N] [--roundtrip]"""
from __future__ import annotations
import argparse, asyncio, json, os, random, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scan"))
import t2s
from semantics import legend
from anthropic import AsyncAnthropic

MODEL = "claude-haiku-4-5"

STYLES = {  # verbatim from OmniSQL generate_question_synthesis_prompts.py (six of nine; Vague/Metaphorical/Multi-turn skipped for v1)
"Formal": """**Formal Style**
   - Uses standard grammar and vocabulary.
   - Example: Find all students older than 18 years and return their home addresses.""",
"Colloquial": """**Colloquial Style**
   - Employs informal vocabulary and expressions.
   - Example: Hey! Could you help me find all the students who are over 18? I'd love to know their names and where they live.""",
"Imperative": """**Imperative Style**
   - Uses command or directive sentences.
   - Example: Could you please gather all the students who are older than 18? I really need to know their names and where they live!""",
"Interrogative": """**Interrogative Style**
   - Uses question forms.
   - Example: Could you tell me which students are older than 18 and what their home addresses are?""",
"Descriptive": """**Descriptive Style**
   - Uses detailed descriptions with contextual information.
   - Example: I want to know the names and home addresses of all students older than 18.""",
"Concise": """**Concise Style**
   - Use short and concise expressions.
   - Example: Students older than 18, return their names and addresses.""",
}

TEMPLATE = """**Task Overview**
Your task is to create a high-quality natural language question based on a given SQL query and other information.

**Style**
The natural language question should follow this style:
{style_desc}

**Database Engine**
SQLite

**Column Information**
Below are column names and their corresponding descriptions:
{column_info}

**SQL Query**
Given SQL query:
```sql
{sql}
```

**Reference phrasing**
A correct but plain statement of what the query asks: {canonical}

**Reasoning Steps**
1. **Explain the SQL Query:** Provide a detailed explanation of what the query does.
2. **Generate a Question:** Formulate a natural language question based on the SQL query and explanation.

**Guidelines**
1. Clearly describe the columns being selected by the SQL query. For example:
   - "SELECT * ... FROM ..." means "Find all ...";
   - "SELECT f.check_date, f.status, f.remarks, c.year, c.year_min, c.year_max, c.year_average, c.data_quality_score FROM ..." means "Return the check dates, statuses, remarks, years, minimum years, maximum years, average years, and quality scores for ...".
2. Ensure the natural language question accurately captures the semantics of the SQL query, including conditions such as predicates, `ORDER BY`, and `LIMIT` clauses.
3. Refer to coded columns and coded values by their descriptions (e.g. say "average salary", never "A11"; say "monthly statement issuance", never "POPLATEK MESICNE"). Do not ask for rounding or formatting the query does not perform.

**Output Format**
Please structure your response as follows:
[EXPLANATION-START]
(SQL Explanation)
[EXPLANATION-END]
[QUESTION-START]
(Natural Language Question)
[QUESTION-END]
- **SQL Explanation**: Provide a clear and detailed explanation of the SQL query, enclosed within [EXPLANATION-START] and [EXPLANATION-END].
- **Natural Language Question**: Translate the SQL query into a natural language question, enclosed within [QUESTION-START] and [QUESTION-END].

**Insturction**
Based on the above information, follow the reasoning steps to generate the explanation and the question corresponding to the SQL query."""

def load_key():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        for line in (Path.home() / ".secrets" / "apis").read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")

def output_columns(db_path, sql):
    import sqlite3
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try: return [d[0] for d in con.execute(sql).description]
    finally: con.close()

def parse_question(text):
    m = re.search(r"\[QUESTION-START\](.*?)\[QUESTION-(?:END|START)\]", text, re.S)
    if not m:  # last resort: text after the last [QUESTION-START]
        tail = text.split("[QUESTION-START]")[-1]
        m = None; q = tail
    else:
        q = m.group(1)
    q = q.strip().strip('"')
    return q if "[EXPLANATION" not in q else ""

async def synthesize(client, sem, row, style, column_info):
    prompt = TEMPLATE.format(style_desc=STYLES[style], column_info=column_info, sql=row["sql"], canonical=row["canonical_question"])
    async with sem:
        r = await client.messages.create(model=MODEL, max_tokens=800, messages=[{"role": "user", "content": prompt}])
    return parse_question("".join(b.text for b in r.content if b.type == "text"))

async def roundtrip(client, sem, question, schema, lg):
    prompt = t2s.build_prompt(schema + "\n\n/* legend */\n" + lg, question, None)
    async with sem:
        r = await client.messages.create(model=MODEL, max_tokens=600, system=t2s.SYSTEM, messages=[{"role": "user", "content": prompt}])
    return t2s.extract_sql("".join(b.text for b in r.content if b.type == "text"))

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--roundtrip", action="store_true")
    a = ap.parse_args(); load_key()
    dev = t2s.load_dev(); db_path = next(r["db_path"] for r in dev if r["db_id"] == "financial")
    schema = t2s.schema_prompt(db_path); lg = legend()
    rows = [json.loads(l) for l in open(a.inp)]
    if a.limit:
        rng = random.Random(a.seed); by = {}
        for r in rows: by.setdefault(r["tier"], []).append(r)
        rows = [r for t in sorted(by) for r in rng.sample(by[t], min(a.limit, len(by[t])))]
    done = {}
    if Path(a.out).exists():
        for l in open(a.out): d = json.loads(l); done[d["id"]] = d
    todo = [r for r in rows if r["id"] not in done]
    client = AsyncAnthropic(); sem = asyncio.Semaphore(a.concurrency); rng = random.Random(a.seed)
    styles = list(STYLES)
    async def one(row):
        style = rng.choice(styles)
        row = {**row, "out_cols": output_columns(db_path, row["sql"])}
        q = await synthesize(client, sem, row, style, lg)
        rec = {**row, "question": q, "style": style}
        if a.roundtrip:
            rt_sql = await roundtrip(client, sem, q, schema, lg)
            gold_rows, _ = t2s.execute(db_path, row["sql"]); rt_rows, _ = t2s.execute(db_path, rt_sql)
            rec["haiku_solvable_with_legend"] = t2s.ex_match(rt_rows, gold_rows)
        return rec
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
    print(f"wrote {len(results)} new; {len(allr)} total -> {a.out}")
    if a.roundtrip:
        for t in sorted({r['tier'] for r in allr}):
            rs = [r for r in allr if r["tier"] == t]
            print(f"  tier {t}: haiku-solvable-with-legend {sum(r.get('haiku_solvable_with_legend', False) for r in rs)}/{len(rs)}")

if __name__ == "__main__":
    asyncio.run(main())
