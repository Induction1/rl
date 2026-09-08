"""Tier-3 families: ratios of aggregates per group · date-bucket grouping · grouping with multi-condition
filters · distinct counts per group · transactions aggregates (indexed copy). Contract as templates.py."""
from __future__ import annotations
from semantics import DISTRICT, VALUES
from templates import num, tie_free, _meaning, _yr, min_count_threshold

STATUS = list(VALUES[("loan", "status")]); FREQ = list(VALUES[("account", "frequency")]); CARD = list(VALUES[("card", "type")])
def _s(v): return _meaning("loan", "status", v)
def _f(v): return _meaning("account", "frequency", v)
J_LAD = "FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id"

def f_ratios(db, rng):
    kind = rng.choice(["default_share_region", "cards_per_100_accounts", "avg_loan_per_client_region", "female_share_region_topk", "weekly_share_district_topk"])
    if kind == "default_share_region":
        st = rng.choice(STATUS)
        return (f"SELECT T3.A3, CAST(SUM(CASE WHEN T1.status = '{st}' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) {J_LAD} GROUP BY T3.A3",
                f"For each region, what percentage of its loans have status {_s(st)}? Give the region and the percentage.", ["ratio", "conditional_agg", "join3", "coded"])
    if kind == "cards_per_100_accounts":
        k = rng.choice([3, 5]); d = rng.choice(["DESC", "ASC"])
        n_min = min_count_threshold(db, "SELECT COUNT(*) FROM account GROUP BY district_id", rng, [30, 40, 50, 60, 80])
        if n_min is None: return f_ratios(db, rng)
        key = f"SELECT T1.A2, CAST((SELECT COUNT(*) FROM card AS C INNER JOIN disp AS D ON C.disp_id = D.disp_id INNER JOIN account AS A ON D.account_id = A.account_id WHERE A.district_id = T1.district_id) AS REAL) * 100 / (SELECT COUNT(*) FROM account AS A2 WHERE A2.district_id = T1.district_id) AS r FROM district AS T1 WHERE (SELECT COUNT(*) FROM account AS A3 WHERE A3.district_id = T1.district_id) >= {n_min} ORDER BY r {d}"
        if not tie_free(db, key, k): return f_ratios(db, rng)
        return (key + f" LIMIT {k}", f"Among districts with at least {n_min} accounts, which {k} have the {'highest' if d=='DESC' else 'lowest'} number of cards per 100 accounts? Give the district name and the ratio.", ["ratio", "correlated", "order_limit"])
    if kind == "avg_loan_per_client_region":
        return ("SELECT T3.A3, CAST(SUM(T1.amount) AS REAL) / (SELECT COUNT(*) FROM client AS C INNER JOIN district AS D ON C.district_id = D.district_id WHERE D.A3 = T3.A3) " + J_LAD + " GROUP BY T3.A3",
                "For each region, what is the total loan amount divided by the number of clients living in the region? Give the region and the value.", ["ratio", "correlated", "join3"])
    if kind == "female_share_region_topk":
        k = rng.choice([1, 3]); d = rng.choice(["DESC", "ASC"])
        key = f"SELECT T2.A3, CAST(SUM(CASE WHEN T1.gender = 'F' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) AS r FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id GROUP BY T2.A3 ORDER BY r {d}"
        if not tie_free(db, key, k): return f_ratios(db, rng)
        return (key + f" LIMIT {k}", f"Which {k} region{'s' if k>1 else ''} {'have' if k>1 else 'has'} the {'highest' if d=='DESC' else 'lowest'} percentage of female clients? Give the region and the percentage.", ["ratio", "conditional_agg", "order_limit"])
    k = rng.choice([3, 5]); fq = rng.choice(FREQ)
    n_min = min_count_threshold(db, "SELECT COUNT(*) FROM account GROUP BY district_id", rng, [40, 50, 60, 80])
    if n_min is None: return f_ratios(db, rng)
    key = f"SELECT T2.A2, CAST(SUM(CASE WHEN T1.frequency = '{fq}' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) AS r FROM account AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id GROUP BY T2.A2 HAVING COUNT(*) >= {n_min} ORDER BY r DESC"
    if not tie_free(db, key, k): return f_ratios(db, rng)
    return (key + f" LIMIT {k}", f"Among districts with at least {n_min} accounts, which {k} have the highest share of accounts with {_f(fq)}? Give the district name and the percentage.", ["ratio", "conditional_agg", "having", "order_limit"])

def f_date_groups(db, rng):
    kind = rng.choice(["loans_per_year_region", "accounts_per_quarter_year", "cards_per_year_type", "loan_amount_per_year", "orders_none_years"])
    if kind == "loans_per_year_region":
        region = rng.choice(db.col_values("district", "A3"))
        return (f"SELECT STRFTIME('%Y', T1.date), COUNT(*) {J_LAD} WHERE T3.A3 = '{region}' GROUP BY STRFTIME('%Y', T1.date)",
                f"In the region '{region}', how many loans were granted in each year? Give the year and the count.", ["date_group", "join3"])
    if kind == "accounts_per_quarter_year":
        y = _yr(rng)
        return (f"SELECT (CAST(STRFTIME('%m', date) AS INTEGER) + 2) / 3, COUNT(*) FROM account WHERE STRFTIME('%Y', date) = '{y}' GROUP BY (CAST(STRFTIME('%m', date) AS INTEGER) + 2) / 3",
                f"How many accounts were opened in each quarter of {y}? Give the quarter number (1 to 4) and the count.", ["date_group"])
    if kind == "cards_per_year_type":
        ct = rng.choice(CARD)
        return (f"SELECT STRFTIME('%Y', issued), COUNT(*) FROM card WHERE type = '{ct}' GROUP BY STRFTIME('%Y', issued)",
                f"How many {_meaning('card','type',ct)}s were issued in each year? Give the year and the count.", ["date_group"])
    if kind == "loan_amount_per_year":
        f = rng.choice(["SUM", "AVG", "MAX"]); w = {"SUM": "total", "AVG": "average", "MAX": "largest"}[f]
        return (f"SELECT STRFTIME('%Y', date), {f}(amount) FROM loan GROUP BY STRFTIME('%Y', date)",
                f"For each year, what was the {w} loan amount granted? Give the year and the value.", ["date_group", "aggregate"])
    st = rng.choice(STATUS)
    return (f"SELECT STRFTIME('%Y', T1.date), COUNT(*) FROM loan AS T1 WHERE T1.status = '{st}' GROUP BY STRFTIME('%Y', T1.date)",
            f"For loans with status {_s(st)}, how many were granted in each year? Give the year and the count.", ["date_group", "coded"])

def f_multi_group(db, rng):
    kind = rng.choice(["gender_region_decade", "status_by_freq", "cards_by_type_gender", "loans_by_region_status_filter"])
    if kind == "gender_region_decade":
        region = rng.choice(db.col_values("district", "A3")); dec = rng.choice([1950, 1960, 1970])
        return (f"SELECT T1.gender, COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A3 = '{region}' AND STRFTIME('%Y', T1.birth_date) BETWEEN '{dec}' AND '{dec+9}' GROUP BY T1.gender",
                f"Among clients in the region '{region}' born in the {dec}s, how many are there of each gender? Give the gender code and the count.", ["multi_filter", "group", "join", "date"])
    if kind == "status_by_freq":
        thr = rng.choice([100000, 200000])
        return (f"SELECT T2.frequency, T1.status, COUNT(*) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.amount > {thr} GROUP BY T2.frequency, T1.status",
                f"For loans above {thr}, how many are there for each combination of statement frequency and loan status? Give the frequency code, the status code and the count.", ["multi_filter", "group", "join", "coded"])
    if kind == "cards_by_type_gender":
        y = rng.choice(range(1995, 1999))
        return (f"SELECT T1.type, T3.gender, COUNT(*) FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id INNER JOIN client AS T3 ON T2.client_id = T3.client_id WHERE STRFTIME('%Y', T1.issued) = '{y}' GROUP BY T1.type, T3.gender",
                f"For cards issued in {y}, how many were issued per card type and client gender? Give the card type, the gender code and the count.", ["multi_filter", "group", "join3", "date"])
    st = rng.choice(STATUS); thr = rng.choice([100000, 150000])
    return (f"SELECT T3.A3, COUNT(*) {J_LAD} WHERE T1.status = '{st}' AND T1.amount < {thr} GROUP BY T3.A3",
            f"For loans with status {_s(st)} and amount below {thr}, how many are there per region? Give the region and the count.", ["multi_filter", "group", "join3", "coded"])

def f_distinct_groups(db, rng):
    kind = rng.choice(["clients_with_cards_per_region", "districts_with_loans_per_region", "accounts_with_orders_per_district_topk", "distinct_ks_per_region"])
    if kind == "clients_with_cards_per_region":
        ct = rng.choice(CARD)
        return (f"SELECT T4.A3, COUNT(DISTINCT T2.client_id) FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id INNER JOIN client AS T3 ON T2.client_id = T3.client_id INNER JOIN district AS T4 ON T3.district_id = T4.district_id WHERE T1.type = '{ct}' GROUP BY T4.A3",
                f"For each region, how many distinct clients hold a {_meaning('card','type',ct)}? Give the region and the count.", ["distinct", "group", "join3"])
    if kind == "districts_with_loans_per_region":
        st = rng.choice(STATUS)
        return (f"SELECT T3.A3, COUNT(DISTINCT T3.district_id) {J_LAD} WHERE T1.status = '{st}' GROUP BY T3.A3",
                f"For each region, how many distinct districts have at least one loan with status {_s(st)}? Give the region and the count.", ["distinct", "group", "join3", "coded"])
    if kind == "accounts_with_orders_per_district_topk":
        k = rng.choice([3, 5])
        key = "SELECT T3.A2, COUNT(DISTINCT T1.account_id) AS n FROM \"order\" AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id GROUP BY T3.A2 ORDER BY n DESC"
        if not tie_free(db, key, k): return f_distinct_groups(db, rng)
        return (key + f" LIMIT {k}", f"Which {k} districts have the most distinct accounts with at least one permanent order? Give the district name and the count.", ["distinct", "group", "order_limit", "join3", "reserved_word"])
    return ("SELECT T3.A3, COUNT(DISTINCT T1.k_symbol) FROM \"order\" AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T1.k_symbol != '' GROUP BY T3.A3",
            "For each region, how many distinct permanent-order purposes appear (ignoring orders with no recorded purpose)? Give the region and the count.", ["distinct", "group", "join3", "reserved_word"])

def f_trans_agg(db, rng):
    kind = rng.choice(["monthly_total_account", "per_account_type_totals", "region_year_type_total", "ks_count_per_year", "avg_balance_top_district"])
    if kind == "monthly_total_account":
        aid = rng.choice(db.col_values("loan", "account_id")); y = rng.choice(range(1995, 1999)); tp = rng.choice(["PRIJEM", "VYDAJ"])
        return (f"SELECT STRFTIME('%m', date), SUM(amount) FROM trans WHERE account_id = {aid} AND STRFTIME('%Y', date) = '{y}' AND type = '{tp}' GROUP BY STRFTIME('%m', date)",
                f"For account id {aid} in {y}, what is the monthly total of {_meaning('trans','type',tp)} transactions? Give the month and the total.", ["trans", "date_group"])
    if kind == "per_account_type_totals":
        aid = rng.choice(db.col_values("loan", "account_id"))
        return (f"SELECT type, SUM(amount) FROM trans WHERE account_id = {aid} GROUP BY type",
                f"For account id {aid}, what is the total transaction amount per transaction type? Give the type code and the total.", ["trans", "group", "coded"])
    if kind == "region_year_type_total":
        region = rng.choice(db.col_values("district", "A3")); y = rng.choice(range(1995, 1999)); ks = rng.choice(["SIPO", "UVER", "POJISTNE", "DUCHOD"])
        return (f"SELECT SUM(T1.amount) FROM trans AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T3.A3 = '{region}' AND STRFTIME('%Y', T1.date) = '{y}' AND T1.k_symbol = '{ks}'",
                f"What was the total amount of {_meaning('trans','k_symbol',ks)} transactions in {y} for accounts in the region '{region}'?", ["trans", "join3", "date"])
    if kind == "ks_count_per_year":
        ks = rng.choice(["SIPO", "UVER", "POJISTNE", "DUCHOD", "UROK"])
        return (f"SELECT STRFTIME('%Y', date), COUNT(*) FROM trans WHERE k_symbol = '{ks}' GROUP BY STRFTIME('%Y', date)",
                f"How many {_meaning('trans','k_symbol',ks)} transactions were there in each year? Give the year and the count.", ["trans", "date_group"])
    k = rng.choice([3, 5]); name = rng.choice(db.col_values("district", "A2"))
    key = f"SELECT T1.account_id, AVG(T1.balance) AS b FROM trans AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T3.A2 = '{name}' GROUP BY T1.account_id ORDER BY b DESC"
    if not tie_free(db, key, k): return f_trans_agg(db, rng)
    return (key + f" LIMIT {k}", f"Among accounts in the district '{name}', which {k} have the highest average balance across their transactions? Give the account id and the average balance.", ["trans", "order_limit", "join3"])

FAMILIES = [("ratios", f_ratios), ("date_groups", f_date_groups), ("multi_group", f_multi_group),
            ("distinct_groups", f_distinct_groups), ("trans_agg", f_trans_agg)]
