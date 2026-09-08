"""Tiered SQL templates over BIRD `financial`. Each generator returns (sql, canonical_question, tags).
Gold SQL is correct BY CONSTRUCTION (the canonical question is rendered from the same choices),
so the label can't be wrong; Haiku later rewrites the canonical question into natural English.

Tiers (the curriculum ladder, easy -> hard):
  1  one table: filter / count / min-max-avg / top-k
  2  one join, filter on one side, output or aggregate from the other
  3  two or three joins with GROUP BY / HAVING / ORDER BY ... LIMIT
  4  subqueries vs aggregates, set operations, date arithmetic, conditional aggregation, coded
     district semantics with two hops
Values are sampled from the live database so filters are non-empty."""
from __future__ import annotations
import random, sqlite3
from semantics import DISTRICT, NUMERIC_DISTRICT, VALUES

class DB:
    def __init__(self, path):
        self.con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    def col_values(self, table, col, k=30):
        q = f'SELECT DISTINCT "{col}" FROM "{table}" WHERE "{col}" IS NOT NULL AND "{col}" != "" ORDER BY RANDOM() LIMIT {k}'
        return [r[0] for r in self.con.execute(q)]
    def num_quantiles(self, table, col):
        expr = f'CAST("{col}" AS INTEGER)' if col in ("A4", "A5", "A6", "A7") else f'"{col}"'
        vals = [r[0] for r in self.con.execute(f'SELECT {expr} FROM "{table}" WHERE "{col}" IS NOT NULL ORDER BY {expr}')]
        return [self._nice(vals[int(len(vals) * q)]) for q in (0.2, 0.4, 0.6, 0.8)]
    @staticmethod
    def _nice(v):
        """Round a data-derived threshold to a number a person would say (2 significant figures)."""
        if v is None: return v
        if isinstance(v, float) and abs(v) < 100: return int(round(v)) if abs(v) >= 2 else round(v, 1)
        v = float(v); mag = 10 ** (len(str(int(abs(v)))) - 2) if abs(v) >= 10 else 1
        return int(round(v / mag) * mag)

TEXT_NUMERIC = {"A4", "A5", "A6", "A7"}  # declared TEXT in BIRD's financial.sqlite; sort/compare via CAST
def num(c):
    """Cast TEXT-typed numeric district columns; accepts bare or table-qualified names (T2.A4)."""
    return f"CAST({c} AS INTEGER)" if c.split(".")[-1] in TEXT_NUMERIC else c

def tie_free(db, key_sql_no_limit, k):
    """True iff the k-th and (k+1)-th ordering keys differ, so a top-k gold is unambiguous."""
    rows = db.con.execute(key_sql_no_limit + f" LIMIT {k + 1}").fetchall()
    return len(rows) <= k or rows[k - 1][-1] != rows[k][-1]


def min_count_threshold(db, count_sql, rng, choices):
    """Pick N from choices such that HAVING COUNT(*) >= N excludes at least one group and keeps at least 3."""
    counts = sorted(r[0] for r in db.con.execute(count_sql))
    ok = [n for n in choices if sum(c >= n for c in counts) >= 3 and sum(c < n for c in counts) >= 1]
    return rng.choice(ok) if ok else None


def month_range(y, m1, m2):
    """Inclusive month range as a half-open date predicate with valid dates only."""
    y2, mn = (y + 1, 1) if m2 == 12 else (y, m2 + 1)
    return f"date >= '{y}-{m1:02d}-01' AND date < '{y2}-{mn:02d}-01'"

def _yr(rng): return rng.choice(range(1993, 1999))
def _meaning(t, c, v): return VALUES[(t, c)][v]

# --------------------------------------------------------------------------- tier 1
def t1(db, rng):
    kind = rng.choice(["count_filter", "agg_col", "topk", "count_district", "list_filter"])
    if kind == "count_filter":
        t, c = rng.choice([("account", "frequency"), ("disp", "type"), ("card", "type"), ("loan", "status"),
                           ("client", "gender"), ("trans", "operation"), ("order", "k_symbol")])
        v = rng.choice(list(VALUES[(t, c)]))
        noun = {"account": "accounts", "disp": "dispositions", "card": "cards", "loan": "loans",
                "client": "clients", "trans": "transactions", "order": "permanent orders"}[t]
        return (f'SELECT COUNT(*) FROM "{t}" WHERE {c} = \'{v}\'',
                f"How many {noun} have {c} = {_meaning(t, c, v)}?", ["count", "filter"])
    if kind == "agg_col":
        t, c, noun = rng.choice([("loan", "amount", "loan amount"), ("loan", "duration", "loan duration"),
                                 ("loan", "payments", "monthly loan payment"), ("order", "amount", "permanent order amount")])
        f = rng.choice(["AVG", "MAX", "MIN", "SUM"])
        word = {"AVG": "average", "MAX": "largest", "MIN": "smallest", "SUM": "total"}[f]
        return (f'SELECT {f}({c}) FROM "{t}"', f"What is the {word} {noun}?", ["aggregate"])
    if kind == "topk":
        c = rng.choice(NUMERIC_DISTRICT); k = rng.choice([1, 3, 5]); d = rng.choice(["DESC", "ASC"])
        word = "highest" if d == "DESC" else "lowest"
        if not tie_free(db, f"SELECT A2, {num(c)} FROM district WHERE {c} IS NOT NULL ORDER BY {num(c)} {d}", k):
            return t1(db, rng)
        return (f'SELECT A2 FROM district WHERE {c} IS NOT NULL ORDER BY {num(c)} {d} LIMIT {k}',
                f"Which {k} district{'s' if k > 1 else ''} {'have' if k > 1 else 'has'} the {word} {DISTRICT[c]}? Give the district name{'s' if k > 1 else ''}.",
                ["district", "order_limit"])
    if kind == "count_district":
        region = rng.choice(db.col_values("district", "A3"))
        return (f'SELECT COUNT(*) FROM district WHERE A3 = \'{region}\'',
                f"How many districts are in the region '{region}'?", ["district", "count"])
    # list_filter
    c = rng.choice(NUMERIC_DISTRICT); thr = rng.choice(db.num_quantiles("district", c)); op = rng.choice([">", "<"])
    return (f'SELECT A2 FROM district WHERE {num(c)} {op} {thr}',
            f"List the names of districts whose {DISTRICT[c]} is {'greater' if op == '>' else 'less'} than {thr}.",
            ["district", "filter"])

# --------------------------------------------------------------------------- tier 2
def t2(db, rng):
    kind = rng.choice(["clients_in_district", "accounts_freq_region", "loans_status_district",
                       "cards_type_owner", "avg_salary_of_loan_clients", "clients_gender_district_count"])
    if kind == "clients_in_district":
        name = rng.choice(db.col_values("district", "A2")); g = rng.choice(["M", "F"])
        return (f"SELECT COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A2 = '{name}' AND T1.gender = '{g}'",
                f"How many {_meaning('client','gender',g)} clients live in the district named '{name}'?", ["join", "count"])
    if kind == "accounts_freq_region":
        region = rng.choice(db.col_values("district", "A3")); fq = rng.choice(list(VALUES[("account", "frequency")]))
        return (f"SELECT COUNT(*) FROM account AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A3 = '{region}' AND T1.frequency = '{fq}'",
                f"How many accounts in the region '{region}' have {_meaning('account','frequency',fq)}?", ["join", "count"])
    if kind == "loans_status_district":
        st = rng.choice(list(VALUES[("loan", "status")])); c = rng.choice(["A2", "A3"])
        return (f"SELECT DISTINCT T3.{c} FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T1.status = '{st}'",
                f"List the distinct {DISTRICT[c]}s of the accounts that have a loan with status {_meaning('loan','status',st)}.", ["join", "distinct"])
    if kind == "cards_type_owner":
        ct = rng.choice(list(VALUES[("card", "type")]))
        return (f"SELECT COUNT(*) FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id WHERE T1.type = '{ct}' AND T2.type = 'OWNER'",
                f"How many {_meaning('card','type',ct)}s are held by account owners (not disponents)?", ["join", "count"])
    if kind == "avg_salary_of_loan_clients":
        st = rng.choice(list(VALUES[("loan", "status")]))
        return (f"SELECT AVG(A11) FROM district WHERE district_id IN (SELECT T2.district_id FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.status = '{st}')",
                f"Across the districts that have at least one loan with status {_meaning('loan','status',st)}, what is the average of the districts' average salaries?", ["subquery", "aggregate", "coded"])
    g = rng.choice(["M", "F"]); c = rng.choice(["A11", "A13", "A4"]); thr = rng.choice(db.num_quantiles("district", c))
    return (f"SELECT COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T1.gender = '{g}' AND {num('T2.'+c)} > {thr}",
            f"How many {_meaning('client','gender',g)} clients live in districts whose {DISTRICT[c]} is above {thr}?", ["join", "count", "coded"])

# --------------------------------------------------------------------------- tier 3
def t3(db, rng):
    kind = rng.choice(["loans_per_district_top", "avg_loan_by_status", "clients_per_region_having",
                       "orders_per_account_top", "card_types_per_district", "trans_sum_by_ksymbol_year"])
    if kind == "loans_per_district_top":
        k = rng.choice([1, 3, 5]); d = rng.choice(["DESC", "ASC"])
        key = f"SELECT T3.A2, COUNT(*) AS n FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id GROUP BY T3.A2 ORDER BY n {d}"
        if not tie_free(db, key, k): return t3(db, rng)
        return (f"SELECT T3.A2, COUNT(*) AS n FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id GROUP BY T3.A2 ORDER BY n {d} LIMIT {k}",
                f"Which {k} district{'s' if k>1 else ''} {'have' if k>1 else 'has'} the {'most' if d=='DESC' else 'fewest'} loans? Give the district name and the number of loans.", ["group", "order_limit", "join"])
    if kind == "avg_loan_by_status":
        return ("SELECT status, AVG(amount) FROM loan GROUP BY status",
                "For each loan status, what is the average loan amount?", ["group", "aggregate"])
    if kind == "clients_per_region_having":
        counts = sorted(r[0] for r in db.con.execute("SELECT COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id GROUP BY T2.A3"))
        thr = rng.choice([500, 600, 700, 800, 900]); thr = thr if counts[0] < thr < counts[-1] else 700
        return (f"SELECT T2.A3, COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id GROUP BY T2.A3 HAVING COUNT(*) > {thr}",
                f"Which regions have more than {thr} clients? Give the region and the client count.", ["group", "having", "join"])
    if kind == "orders_per_account_top":
        ks = rng.choice([k for k in VALUES[("order", "k_symbol")]])
        if not tie_free(db, f"SELECT account_id, SUM(amount) AS total FROM \"order\" WHERE k_symbol = '{ks}' GROUP BY account_id ORDER BY total DESC", 5): return t3(db, rng)
        return (f"SELECT account_id, SUM(amount) AS total FROM \"order\" WHERE k_symbol = '{ks}' GROUP BY account_id ORDER BY total DESC LIMIT 5",
                f"Which 5 accounts have the largest total permanent-order amount for {_meaning('order','k_symbol',ks)}? Give the account id and the total.", ["group", "order_limit", "reserved_word"])
    if kind == "card_types_per_district":
        name = rng.choice(db.col_values("district", "A2"))
        return (f"SELECT T1.type, COUNT(*) FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id INNER JOIN account AS T3 ON T2.account_id = T3.account_id INNER JOIN district AS T4 ON T3.district_id = T4.district_id WHERE T4.A2 = '{name}' GROUP BY T1.type",
                f"For accounts held in the district '{name}', how many cards of each type were issued? Give card type and count.", ["group", "join3"])
    ks = rng.choice(["SIPO", "UVER", "POJISTNE", "DUCHOD"]); y = _yr(rng)
    return (f"SELECT SUM(amount) FROM trans WHERE k_symbol = '{ks}' AND STRFTIME('%Y', date) = '{y}'",
            f"What is the total amount of transactions for {_meaning('trans','k_symbol',ks)} in {y}?", ["date", "aggregate", "trans"])

# --------------------------------------------------------------------------- tier 4
def t4(db, rng):
    kind = rng.choice(["above_avg_col", "both_years", "except_pair", "share_by_group", "vs_own_district_avg",
                       "change_between_years", "age_at_loan", "having_case", "no_orders"])
    if kind == "above_avg_col":
        c = rng.choice(NUMERIC_DISTRICT); op = rng.choice([">", "<"]); out = rng.choice(["A2", "district_id"])
        return (f"SELECT {out} FROM district WHERE {num(c)} {op} (SELECT AVG({num(c)}) FROM district)",
                f"Which districts have a {DISTRICT[c]} {'above' if op=='>' else 'below'} the average across all districts? Give the district {'names' if out=='A2' else 'ids'}.",
                ["subquery", "coded"])
    if kind == "both_years":
        y1 = rng.choice(range(1993, 1998)); y2 = y1 + rng.choice([1, 2]); y2 = min(y2, 1998)
        unit, sql_unit = rng.choice([("district ids", "T2.district_id"), ("account ids", "T1.account_id")])
        src, dcol = rng.choice([("loan", "T1.date"), ("account", None)])
        if src == "loan":
            base = "FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE STRFTIME('%Y', T1.date) = '{y}'"
            return (f"SELECT {sql_unit} {base.format(y=y1)} INTERSECT SELECT {sql_unit} {base.format(y=y2)}",
                    f"Which {unit} had loans granted in both {y1} and {y2}?", ["set_op", "date", "both_years"])
        base = "FROM \"order\" AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.k_symbol = '{k}'"
        k1, k2 = rng.sample(["SIPO", "UVER", "POJISTNE", "LEASING"], 2)
        return (f"SELECT {sql_unit} {base.format(k=k1)} INTERSECT SELECT {sql_unit} {base.format(k=k2)}",
                f"Which {unit} have permanent orders for both {_meaning('order','k_symbol',k1)} and {_meaning('order','k_symbol',k2)}?", ["set_op", "both"])
    if kind == "except_pair":
        trip = rng.choice([
            ("SELECT account_id FROM loan", "SELECT T2.account_id FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id",
             "List the account ids that have a loan but no card issued to any of their dispositions."),
            ("SELECT T2.account_id FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id", "SELECT account_id FROM loan",
             "List the account ids that have at least one card but no loan."),
            ("SELECT account_id FROM loan WHERE status = 'D'", "SELECT account_id FROM \"order\"",
             "List the account ids of loans that are running with the client in debt and that have no permanent orders."),
            ("SELECT district_id FROM client WHERE gender = 'F'", "SELECT T2.district_id FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id",
             "List the district ids that have female clients but no loans at all."),
        ])
        return (f"{trip[0]} EXCEPT {trip[1]}", trip[2], ["set_op", "except"])
    if kind == "share_by_group":
        grp, gname = rng.choice([("T2.A3", "region"), ("T2.A2", "district")]); g = rng.choice(["F", "M"])
        k = rng.choice([0, 3, 5])
        tail = f" ORDER BY 2 DESC LIMIT {k}" if k else ""
        if k and not tie_free(db, f"SELECT {grp}, CAST(SUM(CASE WHEN T1.gender = '{g}' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id GROUP BY {grp} ORDER BY 2 DESC", k):
            return t4(db, rng)
        return (f"SELECT {grp}, CAST(SUM(CASE WHEN T1.gender = '{g}' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id GROUP BY {grp}{tail}",
                (f"For each {gname}, what percentage of clients are {_meaning('client','gender',g)}? Give the {gname} and the percentage." if not k else
                 f"Which {k} {gname}s have the highest percentage of {_meaning('client','gender',g)} clients? Give the {gname} and the percentage."),
                ["conditional_agg", "group", "join"] + (["order_limit"] if k else []))
    if kind == "vs_own_district_avg":
        op = rng.choice([">", "<"]); col = rng.choice(["amount", "duration", "payments"])
        return (f"SELECT T1.loan_id FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.{col} {op} (SELECT AVG(T3.{col}) FROM loan AS T3 INNER JOIN account AS T4 ON T3.account_id = T4.account_id WHERE T4.district_id = T2.district_id)",
                f"Which loans have a {'larger' if op=='>' else 'smaller'} {col} than the average loan {col} of their own district? Give loan ids.", ["correlated_subquery", "join"])
    if kind == "change_between_years":
        a, b, what = rng.choice([("A12", "A13", "unemployment rate"), ("A15", "A16", "number of committed crimes")])
        k = rng.choice([1, 3]); d = rng.choice(["DESC", "ASC"])
        if not tie_free(db, f"SELECT A2, {b} - {a} FROM district WHERE {a} IS NOT NULL AND {b} IS NOT NULL ORDER BY {b} - {a} {d}", k): return t4(db, rng)
        # NULLs excluded (one district has NULL A12/A15); ASC = smallest change, phrased as such (not "decrease")
        return (f"SELECT A2, {b} - {a} FROM district WHERE {a} IS NOT NULL AND {b} IS NOT NULL ORDER BY {b} - {a} {d} LIMIT {k}",
                f"Among districts with data for both years, which {k} district{'s' if k>1 else ''} had the {'highest (most positive)' if d=='DESC' else 'lowest (most negative)'} change in {what} from 1995 to 1996? Give the name and the change (1996 minus 1995).",
                ["coded", "arithmetic", "order_limit"])
    if kind == "age_at_loan":
        thr = rng.choice([100000, 200000, 400000]); role = rng.choice(["OWNER", "DISPONENT"])
        return (f"SELECT T1.loan_id, CAST(STRFTIME('%Y', T1.date) AS INTEGER) - CAST(STRFTIME('%Y', T3.birth_date) AS INTEGER) FROM loan AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id INNER JOIN client AS T3 ON T2.client_id = T3.client_id WHERE T2.type = '{role}' AND T1.amount > {thr}",
                f"For loans above {thr} on accounts that have a {_meaning('disp','type',role)}, how old (year difference) was that {_meaning('disp','type',role)} when the loan was granted? Give loan id and age.", ["date", "join3", "arithmetic"])
    if kind == "having_case":
        g1, g2 = rng.choice([("F", "M"), ("M", "F")])
        return (f"SELECT T2.A2 FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id GROUP BY T2.A2 HAVING SUM(CASE WHEN T1.gender = '{g1}' THEN 1 ELSE 0 END) > SUM(CASE WHEN T1.gender = '{g2}' THEN 1 ELSE 0 END)",
                f"Which districts have more {_meaning('client','gender',g1)} clients than {_meaning('client','gender',g2)} clients? Give district names.", ["conditional_agg", "having", "join"])
    if kind == "owner_vs_disponent":
        f = rng.choice(["AVG", "MAX", "COUNT"])
        return (f"SELECT T2.type, {f}(T1.amount) FROM loan AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id GROUP BY T2.type",
                f"Grouped by disposition type (owner vs disponent), what is the {'average' if f=='AVG' else 'largest' if f=='MAX' else 'number'} of loan amounts? Give the type and the value.", ["group", "join", "coded"])
    fq = rng.choice(list(VALUES[("account", "frequency")]))
    return (f"SELECT account_id FROM account WHERE frequency = '{fq}' AND account_id NOT IN (SELECT account_id FROM \"order\")",
            f"Which accounts with {_meaning('account','frequency',fq)} have no permanent orders? Give account ids.", ["subquery", "not_in", "reserved_word"])

def _mix(a, b, wb):
    """Combine an original tier generator with its extras; wb = probability of drawing from the extras."""
    def gen(db, rng): return (b if rng.random() < wb else a)(db, rng)
    return gen

from templates_extra import t2x, t3x
TIERS = {1: t1, 2: _mix(t2, t2x, 0.7), 3: _mix(t3, t3x, 0.7), 4: t4}
