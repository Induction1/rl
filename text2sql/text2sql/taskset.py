"""text2sql — verifiers v1 environment (single-turn). One task = one question about BIRD `financial`.

Sources: `split = "train"` reads the generated pool (data/pool/pool_run1.jsonl or pool_run2.jsonl, kept rows only:
Haiku-written English, reading-check passed); `split = "bird_dev"` reads the 106 held-out human questions
(hints withheld unless with_hints=True). Rewards: correct (w 1.0) = execution match per verify.py;
format (w 0.0 by default — his call was pure binary; set format_weight > 0 to enable). Metrics:
executed, tier, family. The prompt never includes the legend or BIRD's evidence hints."""
from __future__ import annotations
import json, random
from collections.abc import Iterator
from pathlib import Path

import verifiers.v1 as vf

from text2sql import prompts, verify

ROOT = Path(__file__).resolve().parent.parent          # .../rl/text2sql
DATA = ROOT / "data"
ORDER_TAGS = {"order_limit", "order", "nth"}

def _schema(db_path: str, sample_rows: int = 3) -> str:
    import sqlite3
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True); con.text_factory = lambda b: b.decode("utf-8", "replace")
    cur = con.cursor(); out = []
    for name, ddl in cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
        out.append(ddl.strip() + ";")
        rows = cur.execute(f'SELECT * FROM "{name}" LIMIT {sample_rows}').fetchall(); cols = [d[0] for d in cur.description]
        out.append(f"/* {sample_rows} sample rows from {name}:\n" + " | ".join(cols) + "\n" + "\n".join(" | ".join(str(v)[:40] for v in r) for r in rows) + "\n*/\n")
    con.close(); return "\n".join(out)

def _db_path() -> str:
    work = DATA / "financial_work.sqlite"
    if work.exists(): return str(work)
    return str(DATA / "dev_20240627" / "dev_databases" / "financial" / "financial.sqlite")


class T2SQLTaskConfig(vf.TaskConfig):
    pass


class T2SQLConfig(vf.TasksetConfig):
    split: str = "train"
    """'train' = generated pool · 'bird_dev' = the 106 held-out human questions."""
    pool_path: str = str(DATA / "pool" / "pool_run2.jsonl")   # run 2 pool; configs/rl_v1.toml points at pool_run1.jsonl
    with_hints: bool = False
    """bird_dev only: include BIRD's evidence hint in the question (secondary eval condition)."""
    corrected: bool = False
    """bird_dev only: use Wretblad et al. (ACL 2024) corrected questions+gold (data/corrected/financial_corrected.json)."""
    prompt_version: int = 1
    """1 = run-1 prompt (schema only) · 2 = legend + join graph + value lists + 'only output what is asked' (2026-09-06)."""
    think: bool = False
    """v2 only: think-then-SQL format (reasoning in <think>…</think>, then one ```sql block)."""
    tiers: str = "1,2,3,4"
    """train only: which difficulty tiers to include."""
    seed: int = 0
    shuffle: bool = True
    format_weight: float = 0.0
    task: T2SQLTaskConfig = T2SQLTaskConfig()


class T2SQLData(vf.TaskData):
    info: dict
    """{'gold_sql', 'order_sensitive', 'tier', 'family', 'db_path'}"""


class T2SQLTask(vf.Task[T2SQLData, vf.State, T2SQLTaskConfig]):
    pass   # rewards are recorded in T2SQLEnv.run() via trace.record_reward (a @vf.reward reading trace.info scored 0 under prime-rl: different trace object)


class T2SQLEnvConfig(vf.EnvConfig):
    agent: vf.AgentConfig = vf.AgentConfig()


class T2SQLEnv(vf.Env[T2SQLEnvConfig]):
    async def run(self, task, agents):
        info = task.data.info
        async with agents.agent.interaction(task) as ix:
            seg = await ix.turn()                     # single turn: the prompt is the question
        trace = ix.trace
        reply = seg.last_reply if hasattr(seg, "last_reply") else (trace.assistant_messages[-1].content if trace.assistant_messages else "")
        res = verify.score(info["db_path"], reply or "", info["gold_sql"], bool(info["order_sensitive"]))
        trace.record_reward("correct", float(res["correct"]), 1.0)
        trace.info["correct"] = res["correct"]
        trace.record_metric("executed", res["executed"])
        trace.record_metric("format", res["format"])
        trace.record_metric("tier", float(info.get("tier", 0)))
        trace.info["pred_sql"] = res["pred_sql"]; trace.info["error"] = res["error"]; trace.info["family"] = info.get("family")


class T2SQLTaskset(vf.Taskset[T2SQLTask, T2SQLConfig]):
    INFINITE = False

    def _rows(self):
        c = self.config; db = _db_path()
        if c.split == "bird_dev":
            if c.corrected:
                rows = json.loads((DATA / "corrected" / "financial_corrected.json").read_text())
            else:
                root = next(DATA.rglob("dev.json")).parent
                rows = [r for r in json.loads((root / "dev.json").read_text()) if r["db_id"] == "financial"]
            for r in rows:
                q = r["question"] + (f"\nHint: {r['evidence']}" if c.with_hints and r.get("evidence", "").strip() else "")
                yield {"id": f"bird_{r['question_id']}", "question": q, "gold_sql": r["SQL"], "order_sensitive": "ORDER BY" in r["SQL"].upper() and "LIMIT" in r["SQL"].upper(),
                       "tier": {"simple": 1, "moderate": 2, "challenging": 4}.get(r.get("difficulty"), 0), "family": "bird", "db_path": db}
            return
        tiers = {int(t) for t in c.tiers.split(",")}
        rows = [json.loads(l) for l in open(c.pool_path) if l.strip()]
        rows = [r for r in rows if r.get("keep", True) and r["tier"] in tiers]
        if c.shuffle: random.Random(c.seed).shuffle(rows)
        for r in rows:
            yield {"id": r["id"], "question": r.get("question") or r["canonical_question"], "gold_sql": r["sql"],
                   "order_sensitive": bool(set(r.get("tags", [])) & ORDER_TAGS), "tier": r["tier"], "family": r.get("family", "?"), "db_path": db}

    def load(self) -> Iterator[T2SQLTask]:
        c = self.config; schema = _schema(_db_path())
        if c.prompt_version == 1:
            build = lambda q: prompts.user_message(schema, q)
        else:
            ctx = prompts.context_block(_db_path())
            build = lambda q: prompts.user_message_v2(schema, q, ctx, think=c.think)
        system = prompts.system_prompt(c.prompt_version, c.think)
        for i, r in enumerate(self._rows()):
            yield T2SQLTask(
                T2SQLData(idx=i, name=r["id"], prompt=build(r["question"]), system_prompt=system,
                          info={k: r[k] for k in ("gold_sql", "order_sensitive", "tier", "family", "db_path")}),
                self.config.task,
            )
