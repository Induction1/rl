"""Hop / date-phrasing / output-convention families (added 2026-09-06 after the run-1 failure read).

Why: 47 of the 106 held-out questions were never solved in run 1. Reading them: the pool had ZERO rows on
BIRD's canonical path client -> disp -> account -> trans (and none joining disp with trans at all), so the
model invented columns (trans.client_id, disp.district_id, account.balance). GRPO only learns from groups
with mixed outcomes, and shapes the model never produces stay at 0/8 forever. These families are derived
from the SCHEMA GRAPH (every foreign-key path at 1, 2, 3 hops, plain lookups, one filter, no aggregate) —
not from the held-out questions. Also: date phrasings with BIRD's year semantics ("after 1996" = year > 1996),
and output conventions ("which district" -> the name A2; "who" -> client_id).
Contract as templates.py: gen(db, rng) -> (sql, canonical_question, tags)."""
from __future__ import annotations
from semantics import DISTRICT, VALUES
from templates import _meaning, _yr, tie_free

FREQ = list(VALUES[("account", "frequency")]); STATUS = list(VALUES[("loan", "status")]); CARD = list(VALUES[("card", "type")])
OPS = list(VALUES[("trans", "operation")]); TKS = [k for k in VALUES[("trans", "k_symbol")]]; OKS = list(VALUES[("order", "k_symbol")])
def _f(v): return _meaning("account", "frequency", v)
def _g(v): return _meaning("client", "gender", v)
def _op(v): return _meaning("trans", "operation", v)

_CACHE = {}
def _ids(db, sql, k=40):
    """Cached: the disp×trans GROUP BY scans ~1M rows; run it once per (sql) and sample from the cached list."""
    if sql not in _CACHE:
        _CACHE[sql] = [r[0] for r in db.con.execute(sql + " ORDER BY RANDOM() LIMIT 400")]
    return _CACHE[sql]

# clients whose accounts have a moderate number of transactions (keeps results under the row cap)
def _client_with_trans(db, rng, lo=3, hi=120):
    return rng.choice(_ids(db, f"SELECT T1.client_id FROM disp AS T1 INNER JOIN trans AS T2 ON T1.account_id = T2.account_id GROUP BY T1.client_id HAVING COUNT(*) BETWEEN {lo} AND {hi}"))
def _client_with_loan(db, rng):
    return rng.choice(_ids(db, "SELECT DISTINCT T1.client_id FROM disp AS T1 INNER JOIN loan AS T2 ON T1.account_id = T2.account_id"))
def _client_with_order(db, rng):
    return rng.choice(_ids(db, 'SELECT DISTINCT T1.client_id FROM disp AS T1 INNER JOIN "order" AS T2 ON T1.account_id = T2.account_id'))
def _account_with_trans(db, rng, lo=3, hi=150):
    return rng.choice(_ids(db, f"SELECT account_id FROM trans GROUP BY account_id HAVING COUNT(*) BETWEEN {lo} AND {hi}"))

# ----------------------------------------------------------------------------- one hop (tier 2)
def f_hop1(db, rng):
    kind = rng.choice(["client_accounts", "client_account_freq", "account_owner", "account_district", "client_district_region",
                       "card_holder", "loan_account_freq", "account_trans_op", "order_account_district"])
    if kind == "client_accounts":
        cid = rng.choice(db.col_values("disp", "client_id")); role = rng.choice(["OWNER", "DISPONENT", None])
        if role:
            return (f"SELECT account_id FROM disp WHERE client_id = {cid} AND type = '{role}'",
                    f"Which accounts is client {cid} the {_meaning('disp','type',role)} of? Give the account ids.", ["hop1", "disp", "lookup"])
        return (f"SELECT account_id FROM disp WHERE client_id = {cid}", f"List the account ids linked to client {cid}.", ["hop1", "disp", "lookup"])
    if kind == "client_account_freq":
        cid = rng.choice(db.col_values("disp", "client_id"))
        return (f"SELECT T2.account_id, T2.frequency FROM disp AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.client_id = {cid}",
                f"For each account linked to client {cid}, give the account id and its statement frequency code.", ["hop1", "disp", "join", "lookup"])
    if kind == "account_owner":
        aid = rng.choice(db.col_values("account", "account_id"))
        return (f"SELECT client_id FROM disp WHERE account_id = {aid} AND type = 'OWNER'",
                f"Who is the owner of account {aid}? Give the client id.", ["hop1", "disp", "owner", "who"])
    if kind == "account_district":
        aid = rng.choice(db.col_values("account", "account_id")); out = rng.choice(["A2", "A3", "A2, T2.A3"])
        what = {"A2": "district name", "A3": "region", "A2, T2.A3": "district name and region"}[out]
        cols = ", ".join("T2." + c.strip().replace("T2.", "") for c in out.split(","))
        return (f"SELECT {cols} FROM account AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T1.account_id = {aid}",
                f"In which {what} is account {aid} held?", ["hop1", "join", "district", "lookup"])
    if kind == "client_district_region":
        cid = rng.choice(db.col_values("client", "client_id")); out = rng.choice(["A2", "A3"])
        return (f"SELECT T2.{out} FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T1.client_id = {cid}",
                f"In which {'district' if out=='A2' else 'region'} does client {cid} live? Give the {'district name' if out=='A2' else 'region name'}.", ["hop1", "join", "district", "lookup"])
    if kind == "card_holder":
        cid = rng.choice(db.col_values("card", "card_id"))
        return (f"SELECT T2.client_id FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id WHERE T1.card_id = {cid}",
                f"Who holds card {cid}? Give the client id.", ["hop1", "card", "disp", "who"])
    if kind == "loan_account_freq":
        lid = rng.choice(db.col_values("loan", "loan_id"))
        return (f"SELECT T2.frequency FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.loan_id = {lid}",
                f"What is the statement frequency code of the account that holds loan {lid}?", ["hop1", "loan", "join", "lookup"])
    if kind == "account_trans_op":
        aid = _account_with_trans(db, rng); op = rng.choice([o for o in OPS if o])
        return (f"SELECT trans_id FROM trans WHERE account_id = {aid} AND operation = '{op}'",
                f"List the transaction ids of the {_op(op)} transactions on account {aid}.", ["hop1", "trans", "coded", "lookup"])
    oid = rng.choice(db.col_values("order", "order_id"))
    return (f"SELECT T3.A2 FROM \"order\" AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T1.order_id = {oid}",
            f"Which district is the account of permanent order {oid} held in? Give the district name.", ["hop1", "order", "reserved_word", "district"])

# ----------------------------------------------------------------------------- two hops through disp (tier 3)
def f_hop2(db, rng):
    kind = rng.choice(["client_trans_op", "client_trans_count", "client_trans_big", "client_loans", "client_orders", "trans_owner_gender",
                       "loan_owner", "account_owner_birth", "card_account_district", "client_account_district"])
    if kind == "client_trans_op":
        cid = _client_with_trans(db, rng); op = rng.choice([o for o in OPS if o])
        return (f"SELECT T2.trans_id FROM disp AS T1 INNER JOIN trans AS T2 ON T1.account_id = T2.account_id WHERE T1.client_id = {cid} AND T2.operation = '{op}'",
                f"List the transaction ids of the {_op(op)} transactions made on the accounts of client {cid}.", ["hop2", "disp", "trans", "coded"])
    if kind == "client_trans_count":
        cid = _client_with_trans(db, rng, 3, 2000); ty = rng.choice([t for t in VALUES[("trans", "type")] if t != "VYBER"])   # audit 9/6: 'VYBER' collides with operation='VYBER' (superset); ambiguous in English
        return (f"SELECT COUNT(*) FROM disp AS T1 INNER JOIN trans AS T2 ON T1.account_id = T2.account_id WHERE T1.client_id = {cid} AND T2.type = '{ty}'",
                f"How many {_meaning('trans','type',ty)} transactions are there on the accounts of client {cid}?", ["hop2", "disp", "trans", "count", "coded"])
    if kind == "client_trans_big":
        cid = _client_with_trans(db, rng, 3, 2000); thr = rng.choice([5000, 10000, 20000, 30000])
        return (f"SELECT T2.trans_id, T2.amount FROM disp AS T1 INNER JOIN trans AS T2 ON T1.account_id = T2.account_id WHERE T1.client_id = {cid} AND T2.amount > {thr}",
                f"Which transactions on the accounts of client {cid} have an amount above {thr}? Give the transaction id and the amount.", ["hop2", "disp", "trans"])
    if kind == "client_loans":
        cid = _client_with_loan(db, rng); out = rng.choice(["T2.loan_id, T2.amount", "T2.amount, T2.status", "T2.loan_id"])
        what = {"T2.loan_id, T2.amount": "loan id and amount", "T2.amount, T2.status": "amount and status code", "T2.loan_id": "loan id"}[out]
        return (f"SELECT {out} FROM disp AS T1 INNER JOIN loan AS T2 ON T1.account_id = T2.account_id WHERE T1.client_id = {cid}",
                f"What loans are on the accounts of client {cid}? Give the {what}.", ["hop2", "disp", "loan"])
    if kind == "client_orders":
        cid = _client_with_order(db, rng)
        return (f"SELECT T2.order_id, T2.amount FROM disp AS T1 INNER JOIN \"order\" AS T2 ON T1.account_id = T2.account_id WHERE T1.client_id = {cid}",
                f"List the permanent orders on the accounts of client {cid}, with the order id and the amount.", ["hop2", "disp", "order", "reserved_word"])
    if kind == "trans_owner_gender":
        tid = rng.choice(_ids(db, "SELECT trans_id FROM trans"))
        return (f"SELECT T3.gender FROM trans AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id INNER JOIN client AS T3 ON T2.client_id = T3.client_id WHERE T1.trans_id = {tid} AND T2.type = 'OWNER'",
                f"What is the gender of the owner of the account on which transaction {tid} was made?", ["hop2", "trans", "disp", "client", "owner"])
    if kind == "loan_owner":
        lid = rng.choice(db.col_values("loan", "loan_id"))
        return (f"SELECT T2.client_id FROM loan AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id WHERE T1.loan_id = {lid} AND T2.type = 'OWNER'",
                f"Who owns the account that loan {lid} was granted on? Give the client id.", ["hop2", "loan", "disp", "who"])
    if kind == "account_owner_birth":
        aid = rng.choice(db.col_values("account", "account_id"))
        return (f"SELECT T2.birth_date FROM disp AS T1 INNER JOIN client AS T2 ON T1.client_id = T2.client_id WHERE T1.account_id = {aid} AND T1.type = 'OWNER'",
                f"What is the birth date of the owner of account {aid}?", ["hop2", "disp", "client", "owner"])
    if kind == "card_account_district":
        cid = rng.choice(db.col_values("card", "card_id"))
        return (f"SELECT T4.A2 FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id INNER JOIN account AS T3 ON T2.account_id = T3.account_id INNER JOIN district AS T4 ON T3.district_id = T4.district_id WHERE T1.card_id = {cid}",
                f"Which district is the account that card {cid} was issued on held in? Give the district name.", ["hop2", "card", "disp", "account", "district"])
    cid = rng.choice(db.col_values("disp", "client_id"))
    return (f"SELECT T3.A2 FROM disp AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T1.client_id = {cid}",
            f"In which districts are the accounts of client {cid} held? Give the district names.", ["hop2", "disp", "account", "district"])

# ----------------------------------------------------------------------------- three hops with a filter (tier 3/4)
def f_hop3(db, rng):
    kind = rng.choice(["region_owner_trans_count", "district_owners_loan_status", "gender_trans_op_count", "card_type_trans_count", "freq_owner_trans_ks"])
    if kind == "region_owner_trans_count":
        region = rng.choice(db.col_values("district", "A3")); op = rng.choice([o for o in OPS if o])
        return (f"SELECT COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id INNER JOIN disp AS T3 ON T1.client_id = T3.client_id INNER JOIN trans AS T4 ON T3.account_id = T4.account_id WHERE T2.A3 = '{region}' AND T3.type = 'OWNER' AND T4.operation = '{op}'",
                f"How many {_op(op)} transactions were made on accounts owned by clients living in the region '{region}'?", ["hop3", "trans", "disp", "district", "count", "coded"])
    if kind == "district_owners_loan_status":
        name = rng.choice(db.col_values("district", "A2")); st = rng.choice(STATUS)
        return (f"SELECT T3.client_id FROM account AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id INNER JOIN disp AS T3 ON T1.account_id = T3.account_id INNER JOIN loan AS T4 ON T1.account_id = T4.account_id WHERE T2.A2 = '{name}' AND T3.type = 'OWNER' AND T4.status = '{st}'",
                f"Which clients own an account held in the district '{name}' that has a loan with status {_meaning('loan','status',st)}? Give the client ids.", ["hop3", "loan", "disp", "district", "who", "coded"])
    if kind == "gender_trans_op_count":
        g = rng.choice(["M", "F"]); op = rng.choice([o for o in OPS if o]); y = _yr(rng)
        return (f"SELECT COUNT(*) FROM client AS T1 INNER JOIN disp AS T2 ON T1.client_id = T2.client_id INNER JOIN trans AS T3 ON T2.account_id = T3.account_id WHERE T1.gender = '{g}' AND T2.type = 'OWNER' AND T3.operation = '{op}' AND STRFTIME('%Y', T3.date) = '{y}'",
                f"How many {_op(op)} transactions in {y} were made on accounts owned by {_g(g)} clients?", ["hop3", "trans", "disp", "count", "date", "coded"])
    if kind == "card_type_trans_count":
        ct = rng.choice(CARD); op = rng.choice([o for o in OPS if o])
        return (f"SELECT COUNT(*) FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id INNER JOIN trans AS T3 ON T2.account_id = T3.account_id WHERE T1.type = '{ct}' AND T3.operation = '{op}'",
                f"How many {_op(op)} transactions were made on accounts that have a {_meaning('card','type',ct)}?", ["hop3", "card", "disp", "trans", "count", "coded"])
    fq = rng.choice(FREQ); ks = rng.choice([k for k in TKS if k])
    return (f"SELECT COUNT(DISTINCT T2.client_id) FROM account AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id INNER JOIN trans AS T3 ON T1.account_id = T3.account_id WHERE T1.frequency = '{fq}' AND T2.type = 'OWNER' AND T3.k_symbol = '{ks}'",
            f"How many distinct clients own an account with {_f(fq)} that has a transaction for {_meaning('trans','k_symbol',ks)}?", ["hop3", "trans", "disp", "count", "distinct", "coded"])

# ----------------------------------------------------------------------------- date phrasings (tier 2) — BIRD's year semantics
def f_dates(db, rng):
    tbl, col, noun = rng.choice([("account", "date", "accounts opened"), ("loan", "date", "loans granted"), ("card", "issued", "cards issued"), ("client", "birth_date", "clients born")])
    kind = rng.choice(["after", "before", "in", "since", "between"])
    y = rng.choice(range(1930, 1980)) if tbl == "client" else _yr(rng)
    region = rng.choice(db.col_values("district", "A3")) if tbl in ("account", "client") else None
    if tbl in ("account", "client"):
        base = f"FROM {tbl} AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A3 = '{region}' AND "
        where_tail = f" in the region '{region}'"
    else:
        base = f"FROM {tbl} AS T1 WHERE "; where_tail = ""
    yr = f"STRFTIME('%Y', T1.{col})"
    if kind == "after":
        return (f"SELECT COUNT(*) {base}{yr} > '{y}'", f"How many {noun} after {y}{where_tail}?", ["date", "after", "year"])
    if kind == "before":
        return (f"SELECT COUNT(*) {base}{yr} < '{y}'", f"How many {noun} before {y}{where_tail}?", ["date", "before", "year"])
    if kind == "in":
        return (f"SELECT COUNT(*) {base}{yr} = '{y}'", f"How many {noun} in {y}{where_tail}?", ["date", "in", "year"])
    if kind == "since":
        return (f"SELECT COUNT(*) {base}{yr} >= '{y}'", f"How many {noun} in {y} or later{where_tail}?", ["date", "since", "year"])
    y2 = y + rng.choice([1, 2, 3])
    return (f"SELECT COUNT(*) {base}{yr} BETWEEN '{y}' AND '{y2}'", f"How many {noun} between {y} and {y2}{where_tail}?", ["date", "between", "year"])

# ----------------------------------------------------------------------------- output conventions (tier 2/3)
def f_outconv(db, rng):
    kind = rng.choice(["which_district_most", "which_region_most", "who_largest", "list_accounts_district", "which_district_of_client"])
    if kind == "which_district_most":
        ent = rng.choice([("account", "accounts"), ("client", "clients")])
        key = f"SELECT T2.A2, COUNT(*) AS c FROM {ent[0]} AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id GROUP BY T2.A2 ORDER BY c DESC"
        if not tie_free(db, key, 1): return f_outconv(db, rng)
        return (f"SELECT T2.A2 FROM {ent[0]} AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id GROUP BY T2.A2 ORDER BY COUNT(*) DESC LIMIT 1",
                f"Which district has the most {ent[1]}?", ["outconv", "which_district", "group", "order_limit"])
    if kind == "which_region_most":
        st = rng.choice(STATUS)
        key = f"SELECT T3.A3, COUNT(*) AS c FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T1.status = '{st}' GROUP BY T3.A3 ORDER BY c DESC"
        if not tie_free(db, key, 1): return f_outconv(db, rng)
        return (f"SELECT T3.A3 FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T1.status = '{st}' GROUP BY T3.A3 ORDER BY COUNT(*) DESC LIMIT 1",
                f"Which region has the most loans with status {_meaning('loan','status',st)}?", ["outconv", "which_region", "group", "order_limit", "coded"])
    if kind == "who_largest":
        what = rng.choice([("loan", "amount", "largest loan"), ("loan", "payments", "highest monthly loan payment")])
        key = f"SELECT loan_id, {what[1]} FROM loan ORDER BY {what[1]} DESC"
        if not tie_free(db, key, 1): return f_outconv(db, rng)
        return (f"SELECT T2.client_id FROM loan AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id WHERE T2.type = 'OWNER' ORDER BY T1.{what[1]} DESC LIMIT 1",
                f"Who owns the account with the {what[2]}?", ["outconv", "who", "order_limit", "disp"])
    if kind == "list_accounts_district":
        name = rng.choice(db.col_values("district", "A2")); fq = rng.choice(FREQ)
        return (f"SELECT T1.account_id FROM account AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A2 = '{name}' AND T1.frequency = '{fq}'",
                f"List the accounts in {name} with {_f(fq)}.", ["outconv", "list_accounts", "join", "coded"])
    cid = rng.choice(db.col_values("client", "client_id"))
    return (f"SELECT T2.A2 FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T1.client_id = {cid}",
            f"Which district does client {cid} live in?", ["outconv", "which_district", "join"])

FAMILIES = [(2, "hop1", f_hop1, 220), (3, "hop2", f_hop2, 260), (3, "hop3", f_hop3, 140), (2, "date_phrase", f_dates, 120), (2, "outconv", f_outconv, 100)]

# ----------------------------------------------------------------------------- ranking through a join (tier 3) — BIRD has ORDER BY … LIMIT in 20 % of questions, pool had 10 %
def f_rank(db, rng):
    kind = rng.choice(["district_most_entity", "region_total_loans", "client_most_accounts", "district_metric_in_region", "oldest_client_district", "top3_districts_metric", "largest_loan_in_district", "district_most_cards"])
    d = rng.choice(["DESC", "ASC"]); word = "most" if d == "DESC" else "fewest"; hi = "highest" if d == "DESC" else "lowest"
    if kind == "district_most_entity":
        ent, noun = rng.choice([("account", "accounts"), ("client", "clients"), ("loan", "loans")])
        base = (f"FROM {ent} AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id" if ent != "loan" else
                "FROM loan AS T1 INNER JOIN account AS T3 ON T1.account_id = T3.account_id INNER JOIN district AS T2 ON T3.district_id = T2.district_id")
        key = f"SELECT T2.A2, COUNT(*) AS c {base} GROUP BY T2.A2 ORDER BY c {d}"
        if not tie_free(db, key, 1): return f_rank(db, rng)
        return (f"SELECT T2.A2 {base} GROUP BY T2.A2 ORDER BY COUNT(*) {d} LIMIT 1", f"Which district has the {word} {noun}?", ["rank", "group", "order_limit", "join"])
    if kind == "region_total_loans":
        agg, what = rng.choice([("SUM(T1.amount)", "total loan amount"), ("AVG(T1.amount)", "average loan amount"), ("COUNT(*)", "number of loans")])
        base = "FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id"
        key = f"SELECT T3.A3, {agg} AS v {base} GROUP BY T3.A3 ORDER BY v {d}"
        if not tie_free(db, key, 1): return f_rank(db, rng)
        return (f"SELECT T3.A3 {base} GROUP BY T3.A3 ORDER BY {agg} {d} LIMIT 1", f"Which region has the {hi} {what}?", ["rank", "group", "order_limit", "join3"])
    if kind == "client_most_accounts":
        key = "SELECT client_id, COUNT(*) AS c FROM disp GROUP BY client_id ORDER BY c DESC"
        if not tie_free(db, key, 1): return f_rank(db, rng)
        return ("SELECT client_id FROM disp GROUP BY client_id ORDER BY COUNT(*) DESC LIMIT 1", "Which client is linked to the most accounts? Give the client id.", ["rank", "group", "order_limit", "disp"])
    if kind == "district_metric_in_region":
        c = rng.choice(["A11", "A13", "A12", "A15", "A16", "A10", "A4"]); region = rng.choice(db.col_values("district", "A3"))
        from templates import num
        key = f"SELECT A2, {num(c)} AS v FROM district WHERE A3 = '{region}' AND {c} IS NOT NULL ORDER BY v {d}"
        if not tie_free(db, key, 1): return f_rank(db, rng)
        return (f"SELECT A2 FROM district WHERE A3 = '{region}' AND {c} IS NOT NULL ORDER BY {num(c)} {d} LIMIT 1", f"Which district in the region '{region}' has the {hi} {DISTRICT[c]}?", ["rank", "order_limit", "coded"])
    if kind == "oldest_client_district":
        name = rng.choice(db.col_values("district", "A2")); g = rng.choice(["M", "F", None]); age = "oldest" if d == "ASC" else "youngest"
        gf = f" AND T1.gender = '{g}'" if g else ""
        key = f"SELECT T1.client_id, T1.birth_date FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A2 = '{name}'{gf} ORDER BY T1.birth_date {d}"
        if not tie_free(db, key, 1): return f_rank(db, rng)
        return (f"SELECT T1.client_id FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A2 = '{name}'{gf} ORDER BY T1.birth_date {d} LIMIT 1",
                f"Who is the {age} {_g(g) + ' ' if g else ''}client living in the district '{name}'? Give the client id.", ["rank", "order_limit", "join", "who"])
    if kind == "top3_districts_metric":
        c = rng.choice(["A11", "A13", "A15", "A16", "A14"]); k = rng.choice([3, 5])
        from templates import num
        key = f"SELECT A2, {num(c)} AS v FROM district WHERE {c} IS NOT NULL ORDER BY v {d}"
        if not tie_free(db, key, k): return f_rank(db, rng)
        return (f"SELECT A2 FROM district WHERE {c} IS NOT NULL ORDER BY {num(c)} {d} LIMIT {k}", f"Which {k} districts have the {hi} {DISTRICT[c]}? Give the district names.", ["rank", "order_limit", "coded", "topk"])
    if kind == "largest_loan_in_district":
        name = rng.choice(db.col_values("district", "A2")); col, what = rng.choice([("amount", "largest" if d == "DESC" else "smallest"), ("duration", "longest" if d == "DESC" else "shortest")])
        key = f"SELECT T1.loan_id, T1.{col} FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T3.A2 = '{name}' ORDER BY T1.{col} {d}"
        if not tie_free(db, key, 1): return f_rank(db, rng)
        return (f"SELECT T1.loan_id FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T3.A2 = '{name}' ORDER BY T1.{col} {d} LIMIT 1",
                f"Which loan on an account in the district '{name}' has the {what} {'amount' if col=='amount' else 'duration'}? Give the loan id.", ["rank", "order_limit", "join3"])
    ct = rng.choice(CARD)
    base = f"FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id INNER JOIN account AS T3 ON T2.account_id = T3.account_id INNER JOIN district AS T4 ON T3.district_id = T4.district_id WHERE T1.type = '{ct}'"
    key = f"SELECT T4.A2, COUNT(*) AS c {base} GROUP BY T4.A2 ORDER BY c {d}"
    if not tie_free(db, key, 1): return f_rank(db, rng)
    return (f"SELECT T4.A2 {base} GROUP BY T4.A2 ORDER BY COUNT(*) {d} LIMIT 1", f"Which district has the {word} {_meaning('card','type',ct)}s issued on its accounts?", ["rank", "group", "order_limit", "join3", "card"])

FAMILIES.append((3, "rank", f_rank, 260))
