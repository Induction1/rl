"""Tier-2 families (exactly one join, no GROUP BY): text matching through a join · date ranges through a
join · multi-condition through a join · EXISTS/NOT EXISTS lookups · distinct counts through a join ·
arithmetic through a join. Contract as templates.py."""
from __future__ import annotations
from semantics import DISTRICT, VALUES
from templates import num, tie_free, _meaning, _yr, month_range

STATUS = list(VALUES[("loan", "status")]); FREQ = list(VALUES[("account", "frequency")]); CARD = list(VALUES[("card", "type")])
OKS = list(VALUES[("order", "k_symbol")])
def _s(v): return _meaning("loan", "status", v)
def _f(v): return _meaning("account", "frequency", v)
def _g(v): return _meaning("client", "gender", v)
def _prefix(db, rng):
    names = db.col_values("district", "A2", k=77); p = rng.choice(names)[:rng.choice([1, 2])]
    return p if sum(n.startswith(p) for n in names) >= 2 else _prefix(db, rng)

def f_text_join(db, rng):
    kind = rng.choice(["clients_prefix", "accounts_contains", "loans_prefix_count", "cards_region_like"])
    if kind == "clients_prefix":
        p = _prefix(db, rng); g = rng.choice(["M", "F"])
        return (f"SELECT COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A2 LIKE '{p}%' AND T1.gender = '{g}'",
                f"How many {_g(g)} clients live in districts whose name starts with '{p}'?", ["like", "join", "count"])
    if kind == "accounts_contains":
        sub = rng.choice(["ov", "ice", "in", "Praha", "nad"]); fq = rng.choice(FREQ)
        return (f"SELECT COUNT(*) FROM account AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A2 LIKE '%{sub}%' AND T1.frequency = '{fq}'",
                f"How many accounts with {_f(fq)} are in districts whose name contains '{sub}'?", ["like", "join", "count"])
    if kind == "loans_prefix_count":
        p = _prefix(db, rng); st = rng.choice(STATUS)
        return (f"SELECT COUNT(*) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.status = '{st}' AND T2.district_id IN (SELECT district_id FROM district WHERE A2 LIKE '{p}%')",
                f"How many loans with status {_s(st)} are on accounts in districts whose name starts with '{p}'?", ["like", "join", "subquery", "count"])
    sub = rng.choice(["Bohemia", "Moravia"]); ct = rng.choice(CARD)
    return (f"SELECT COUNT(*) FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id WHERE T1.type = '{ct}' AND T2.account_id IN (SELECT T3.account_id FROM account AS T3 INNER JOIN district AS T4 ON T3.district_id = T4.district_id WHERE T4.A3 LIKE '%{sub}%')",
            f"How many {_meaning('card','type',ct)}s are on accounts in regions whose name contains '{sub}'?", ["like", "join", "subquery", "count"])

def f_date_join(db, rng):
    kind = rng.choice(["loans_between_region", "accounts_quarter_region", "cards_year_range_type", "clients_birth_range_district"])
    if kind == "loans_between_region":
        y = rng.choice(range(1994, 1999)); m1, m2 = sorted(rng.sample(range(1, 13), 2)); region = rng.choice(db.col_values("district", "A3"))
        return (f"SELECT COUNT(*) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE {month_range(y, m1, m2).replace('date', 'T1.date')} AND T2.district_id IN (SELECT district_id FROM district WHERE A3 = '{region}')",
                f"How many loans were granted between the start of month {m1} and the end of month {m2} of {y} on accounts in the region '{region}'?", ["date_range", "join", "count"])
    if kind == "accounts_quarter_region":
        y = _yr(rng); q = rng.choice([1, 2, 3, 4]); region = rng.choice(db.col_values("district", "A3")); m1 = 3 * q - 2; m2 = 3 * q
        return (f"SELECT COUNT(*) FROM account AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A3 = '{region}' AND {month_range(y, m1, m2).replace('date', 'T1.date')}",
                f"How many accounts in the region '{region}' were opened in quarter {q} of {y}?", ["date_range", "join", "count"])
    if kind == "cards_year_range_type":
        y1 = rng.choice(range(1994, 1998)); y2 = y1 + 1; role = rng.choice(["OWNER", "DISPONENT"])
        return (f"SELECT COUNT(*) FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id WHERE T2.type = '{role}' AND STRFTIME('%Y', T1.issued) BETWEEN '{y1}' AND '{y2}'",
                f"How many cards were issued to {_meaning('disp','type',role)}s in {y1} or {y2}?", ["date_range", "join", "count"])
    name = rng.choice(db.col_values("district", "A2")); y1 = rng.choice(range(1940, 1980, 10)); y2 = y1 + 9
    return (f"SELECT COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A2 = '{name}' AND STRFTIME('%Y', T1.birth_date) BETWEEN '{y1}' AND '{y2}'",
            f"How many clients living in the district '{name}' were born between {y1} and {y2} inclusive?", ["date_range", "join", "count"])

def f_multi_join(db, rng):
    kind = rng.choice(["gender_region_decade", "loan_status_amount_freq", "order_amount_ks_freq", "card_type_owner_region"])
    if kind == "gender_region_decade":
        region = rng.choice(db.col_values("district", "A3")); g = rng.choice(["M", "F"]); dec = rng.choice([1950, 1960, 1970])
        return (f"SELECT COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A3 = '{region}' AND T1.gender = '{g}' AND STRFTIME('%Y', T1.birth_date) BETWEEN '{dec}' AND '{dec+9}'",
                f"How many {_g(g)} clients in the region '{region}' were born in the {dec}s?", ["multi_filter", "join", "count"])
    if kind == "loan_status_amount_freq":
        st = rng.choice(STATUS); thr = rng.choice([50000, 100000, 200000]); fq = rng.choice(FREQ); op = rng.choice([">", "<"])
        return (f"SELECT COUNT(*) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.status = '{st}' AND T1.amount {op} {thr} AND T2.frequency = '{fq}'",
                f"How many loans have status {_s(st)}, an amount {'above' if op=='>' else 'below'} {thr}, and are on accounts with {_f(fq)}?", ["multi_filter", "join", "count"])
    if kind == "order_amount_ks_freq":
        ks = rng.choice(OKS); thr = rng.choice([1000, 2000, 5000]); fq = rng.choice(FREQ)
        return (f"SELECT COUNT(*) FROM \"order\" AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.k_symbol = '{ks}' AND T1.amount > {thr} AND T2.frequency = '{fq}'",
                f"How many permanent orders for {_meaning('order','k_symbol',ks)} above {thr} are on accounts with {_f(fq)}?", ["multi_filter", "join", "count", "reserved_word"])
    ct = rng.choice(CARD); role = rng.choice(["OWNER", "DISPONENT"]); y = rng.choice(range(1995, 1999))
    return (f"SELECT COUNT(*) FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id WHERE T1.type = '{ct}' AND T2.type = '{role}' AND STRFTIME('%Y', T1.issued) = '{y}'",
            f"How many {_meaning('card','type',ct)}s were issued in {y} to {_meaning('disp','type',role)}s?", ["multi_filter", "join", "count", "date"])

def f_exists(db, rng):
    kind = rng.choice(["accounts_with_card_region", "clients_without_loan_district", "districts_with_gold", "accounts_with_order_ks"])
    if kind == "accounts_with_card_region":
        region = rng.choice(db.col_values("district", "A3"))
        return (f"SELECT COUNT(*) FROM account AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A3 = '{region}' AND EXISTS (SELECT 1 FROM disp AS T3 INNER JOIN card AS T4 ON T3.disp_id = T4.disp_id WHERE T3.account_id = T1.account_id)",
                f"How many accounts in the region '{region}' have at least one card issued on them?", ["exists", "join", "count"])
    if kind == "clients_without_loan_district":
        name = rng.choice(db.col_values("district", "A2"))
        return (f"SELECT COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A2 = '{name}' AND NOT EXISTS (SELECT 1 FROM disp AS T3 INNER JOIN loan AS T4 ON T3.account_id = T4.account_id WHERE T3.client_id = T1.client_id)",
                f"How many clients living in the district '{name}' are not linked to any account with a loan?", ["not_exists", "join", "count"])
    if kind == "districts_with_gold":
        ct = rng.choice(CARD); region = rng.choice(db.col_values("district", "A3"))
        return (f"SELECT T1.A2 FROM district AS T1 WHERE T1.A3 = '{region}' AND EXISTS (SELECT 1 FROM account AS T2 INNER JOIN disp AS T3 ON T2.account_id = T3.account_id INNER JOIN card AS T4 ON T3.disp_id = T4.disp_id WHERE T2.district_id = T1.district_id AND T4.type = '{ct}')",
                f"Which districts in the region '{region}' have at least one {_meaning('card','type',ct)} issued on their accounts? Give the district names.", ["exists", "join"])
    ks = rng.choice(OKS); fq = rng.choice(FREQ)
    return (f"SELECT COUNT(*) FROM account AS T1 WHERE T1.frequency = '{fq}' AND EXISTS (SELECT 1 FROM \"order\" AS T2 WHERE T2.account_id = T1.account_id AND T2.k_symbol = '{ks}')",
            f"How many accounts with {_f(fq)} have at least one permanent order for {_meaning('order','k_symbol',ks)}?", ["exists", "count", "reserved_word"])

def f_distinct_join(db, rng):
    kind = rng.choice(["districts_with_status", "regions_with_card_type", "clients_with_loans_region", "ks_in_district"])
    if kind == "districts_with_status":
        st = rng.choice(STATUS)
        return (f"SELECT COUNT(DISTINCT T2.district_id) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.status = '{st}'",
                f"How many distinct districts have at least one loan with status {_s(st)}?", ["distinct", "join", "count"])
    if kind == "regions_with_card_type":
        ct = rng.choice(CARD)
        return (f"SELECT COUNT(DISTINCT T2.account_id) FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id WHERE T1.type = '{ct}'",
                f"How many distinct accounts have at least one {_meaning('card','type',ct)}?", ["distinct", "join", "count"])
    if kind == "clients_with_loans_region":
        region = rng.choice(db.col_values("district", "A3"))
        return (f"SELECT COUNT(DISTINCT T1.client_id) FROM disp AS T1 INNER JOIN loan AS T2 ON T1.account_id = T2.account_id WHERE T1.account_id IN (SELECT T3.account_id FROM account AS T3 INNER JOIN district AS T4 ON T3.district_id = T4.district_id WHERE T4.A3 = '{region}')",
                f"How many distinct clients are linked to an account with a loan in the region '{region}'?", ["distinct", "join", "subquery", "count"])
    name = rng.choice(db.col_values("district", "A2"))
    return (f"SELECT COUNT(DISTINCT T1.k_symbol) FROM \"order\" AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T2.district_id = (SELECT district_id FROM district WHERE A2 = '{name}') AND T1.k_symbol != ''",
            f"How many distinct permanent-order purposes appear on accounts in the district '{name}' (ignoring orders with no recorded purpose)?", ["distinct", "join", "count", "reserved_word"])

def f_arith_join(db, rng):
    kind = rng.choice(["total_repayment_freq", "avg_monthly_payment_region", "loan_per_inhabitant_district", "order_share_of_loan"])
    if kind == "total_repayment_freq":
        fq = rng.choice(FREQ); f = rng.choice(["SUM", "AVG", "MAX"]); w = {"SUM": "total", "AVG": "average", "MAX": "largest"}[f]
        return (f"SELECT {f}(T1.payments * T1.duration) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T2.frequency = '{fq}'",
                f"For loans on accounts with {_f(fq)}, what is the {w} total scheduled repayment, computed as monthly payment times duration in months?", ["arithmetic", "join", "aggregate"])
    if kind == "avg_monthly_payment_region":
        region = rng.choice(db.col_values("district", "A3"))
        return (f"SELECT AVG(T1.amount / T1.duration) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T2.district_id IN (SELECT district_id FROM district WHERE A3 = '{region}')",
                f"For loans on accounts in the region '{region}', what is the average of loan amount divided by duration in months (integer division as stored)?", ["arithmetic", "join", "aggregate"])
    if kind == "loan_per_inhabitant_district":
        name = rng.choice(db.col_values("district", "A2"))
        return (f"SELECT SUM(T1.amount) * 1.0 / CAST(T2.A4 AS INTEGER) FROM loan AS T1 INNER JOIN account AS T3 ON T1.account_id = T3.account_id INNER JOIN district AS T2 ON T3.district_id = T2.district_id WHERE T2.A2 = '{name}' GROUP BY T2.A4",
                f"For the district '{name}', what is the total loan amount per inhabitant (total loan amount divided by the district's number of inhabitants)?", ["arithmetic", "join3", "coded"])
    thr = rng.choice([0.05, 0.1])
    return (f"SELECT COUNT(*) FROM \"order\" AS T1 INNER JOIN loan AS T2 ON T1.account_id = T2.account_id WHERE T1.k_symbol = 'UVER' AND T1.amount * 1.0 / T2.payments > {1 + thr}",
            f"How many loan-payment permanent orders exceed the loan's monthly payment by more than {int(thr*100)} percent?", ["arithmetic", "join", "count", "reserved_word"])

FAMILIES = [("text_join", f_text_join), ("date_join", f_date_join), ("multi_join", f_multi_join),
            ("exists", f_exists), ("distinct_join", f_distinct_join), ("arith_join", f_arith_join)]
