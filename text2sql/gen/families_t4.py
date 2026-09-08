"""Tier-4 families (2026-09-05 proposal): correlated subqueries vs group averages · set ops incl. UNION ·
anti-joins (NOT EXISTS) · conditional aggregation with HAVING · nested aggregates · date arithmetic ·
transactions hard cases (needs the indexed working copy). Contract as templates.py. Each function is
one family; FAMILIES lists (name, fn). Gold correct by construction; ties/NULLs guarded."""
from __future__ import annotations
from semantics import DISTRICT, VALUES
from templates import num, tie_free, _meaning, _yr, min_count_threshold

STATUS = list(VALUES[("loan", "status")]); FREQ = list(VALUES[("account", "frequency")])
OKS = list(VALUES[("order", "k_symbol")]); TKS = [k for k in VALUES[("trans", "k_symbol")]]
def _s(v): return _meaning("loan", "status", v)
def _o(v): return _meaning("order", "k_symbol", v)
def _tk(v): return _meaning("trans", "k_symbol", v)
J_LAD = "FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id"

def f_correlated(db, rng):
    kind = rng.choice(["loan_vs_region_avg", "order_vs_account_avg", "district_vs_region_salary", "client_age_vs_district"])
    if kind == "loan_vs_region_avg":
        op = rng.choice([">", "<"]); col = rng.choice(["amount", "payments"]); region = rng.choice(db.col_values("district", "A3")); as_count = rng.random() < 0.6
        sel, ask = ("COUNT(*)", "how many loans have") if as_count else ("T1.loan_id", "which loans have")
        return (f"SELECT {sel} {J_LAD} WHERE T3.A3 = '{region}' AND T1.{col} {op} (SELECT AVG(T4.{col}) FROM loan AS T4 INNER JOIN account AS T5 ON T4.account_id = T5.account_id INNER JOIN district AS T6 ON T5.district_id = T6.district_id WHERE T6.A2 = T3.A2)",
                f"In the region '{region}', {ask} a {'higher' if op=='>' else 'lower'} {'amount' if col=='amount' else 'monthly payment'} than the average for loans in their own district?" + ("" if as_count else " Give the loan ids."), ["correlated", "join3"] + (["count"] if as_count else []))
    if kind == "order_vs_account_avg":
        ks = rng.choice(OKS); as_count = rng.random() < 0.6; op = rng.choice([">", "<"])
        sel, ask = ("COUNT(*)", "How many permanent orders") if as_count else ("T1.order_id", "Which permanent orders")
        return (f"SELECT {sel} FROM \"order\" AS T1 WHERE T1.k_symbol = '{ks}' AND T1.amount {op} (SELECT AVG(T2.amount) FROM \"order\" AS T2 WHERE T2.k_symbol = T1.k_symbol)",
                f"{ask} for {_o(ks)} have an amount {'above' if op=='>' else 'below'} the average amount of all permanent orders for {_o(ks)}?" + ("" if as_count else " Give the order ids."), ["correlated", "reserved_word"] + (["count"] if as_count else []))
    if kind == "district_vs_region_salary":
        c = rng.choice(["A11", "A13", "A10"]); op = rng.choice([">", "<"])
        return (f"SELECT T1.A2 FROM district AS T1 WHERE T1.{c} {op} (SELECT AVG(T2.{c}) FROM district AS T2 WHERE T2.A3 = T1.A3)",
                f"Which districts have a {DISTRICT[c]} {'above' if op=='>' else 'below'} the average of the districts in their own region? Give the district names.", ["correlated", "coded"])
    y = rng.choice(range(1960, 1985, 5)); op = rng.choice(["<", ">"])
    return (f"SELECT T1.client_id FROM client AS T1 WHERE STRFTIME('%Y', T1.birth_date) {op} (SELECT STRFTIME('%Y', MIN(T2.birth_date)) FROM client AS T2 WHERE T2.district_id = T1.district_id AND STRFTIME('%Y', T2.birth_date) >= '{y}') AND STRFTIME('%Y', T1.birth_date) >= '{y}'",
            f"Among clients born in or after {y}, which ones were born {'before' if op=='<' else 'after'} the earliest such birth year in their own district? Give the client ids.", ["correlated", "date"])

def f_setops(db, rng):
    kind = rng.choice(["union_ids", "intersect_status", "except_region", "intersect_card_loan", "union_districts"])
    if kind == "union_ids":
        ks = rng.choice(OKS); st = rng.choice(STATUS)
        return (f"SELECT account_id FROM \"order\" WHERE k_symbol = '{ks}' UNION SELECT account_id FROM loan WHERE status = '{st}'",
                f"List the account ids that have a permanent order for {_o(ks)} or a loan with status {_s(st)} (each id once).", ["set_op", "union"])
    if kind == "intersect_status":
        s1, s2 = rng.sample(STATUS, 2)
        return (f"SELECT T2.district_id {J_LAD.replace('INNER JOIN district AS T3 ON T2.district_id = T3.district_id','')} WHERE T1.status = '{s1}' INTERSECT SELECT T2.district_id FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.status = '{s2}'",
                f"Which district ids have both a loan with status {_s(s1)} and a loan with status {_s(s2)}?", ["set_op", "intersect"])
    if kind == "except_region":
        region = rng.choice(db.col_values("district", "A3")); st = rng.choice(STATUS)
        return (f"SELECT T3.district_id {J_LAD} WHERE T3.A3 = '{region}' EXCEPT SELECT T3.district_id {J_LAD} WHERE T3.A3 = '{region}' AND T1.status = '{st}'",
                f"In the region '{region}', which district ids have loans but none with status {_s(st)}?", ["set_op", "except"])
    if kind == "intersect_card_loan":
        ct = rng.choice(list(VALUES[("card", "type")]))
        return (f"SELECT T2.account_id FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id WHERE T1.type = '{ct}' INTERSECT SELECT account_id FROM loan",
                f"Which account ids have both a {_meaning('card','type',ct)} and a loan?", ["set_op", "intersect"])
    c1, c2 = rng.sample(["A11", "A13", "A14", "A10"], 2); t1 = db.num_quantiles("district", c1)[2]; t2 = db.num_quantiles("district", c2)[2]
    return (f"SELECT A2 FROM district WHERE {c1} > {t1} UNION SELECT A2 FROM district WHERE {c2} > {t2}",
            f"List the names of districts whose {DISTRICT[c1]} is above {t1} or whose {DISTRICT[c2]} is above {t2} (each name once).", ["set_op", "union", "coded"])

def f_antijoin(db, rng):
    kind = rng.choice(["accounts_no_card", "clients_no_card", "districts_no_default", "accounts_no_trans_ks", "owners_no_loan"])
    if kind == "accounts_no_card":
        fq = rng.choice(FREQ); as_count = rng.random() < 0.6
        return (f"SELECT {'COUNT(*)' if as_count else 'T1.account_id'} FROM account AS T1 WHERE T1.frequency = '{fq}' AND NOT EXISTS (SELECT 1 FROM disp AS T2 INNER JOIN card AS T3 ON T2.disp_id = T3.disp_id WHERE T2.account_id = T1.account_id) AND EXISTS (SELECT 1 FROM loan AS T4 WHERE T4.account_id = T1.account_id)",
                (f"How many accounts with {_meaning('account','frequency',fq)} have a loan but no card on any of their dispositions?" if as_count else f"Which accounts with {_meaning('account','frequency',fq)} have a loan but no card on any of their dispositions? Give the account ids."), ["anti_join", "exists"] + (["count"] if as_count else []))
    if kind == "clients_no_card":
        region = rng.choice(db.col_values("district", "A3")); g = rng.choice(["M", "F"])
        return (f"SELECT COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A3 = '{region}' AND T1.gender = '{g}' AND NOT EXISTS (SELECT 1 FROM disp AS T3 INNER JOIN card AS T4 ON T3.disp_id = T4.disp_id WHERE T3.client_id = T1.client_id)",
                f"How many {_meaning('client','gender',g)} clients in the region '{region}' have no card at all?", ["anti_join", "count"])
    if kind == "districts_no_default":
        return ("SELECT T1.A2 FROM district AS T1 WHERE EXISTS (SELECT 1 FROM account AS T2 INNER JOIN loan AS T3 ON T2.account_id = T3.account_id WHERE T2.district_id = T1.district_id) AND NOT EXISTS (SELECT 1 FROM account AS T2 INNER JOIN loan AS T3 ON T2.account_id = T3.account_id WHERE T2.district_id = T1.district_id AND T3.status = 'D')",
                "Which districts have at least one loan but no loan that is running with the client in debt? Give the district names.", ["anti_join", "exists", "coded"])
    if kind == "accounts_no_trans_ks":
        ks = rng.choice(["POJISTNE", "SIPO", "DUCHOD"]); region = rng.choice(db.col_values("district", "A3")); as_count = rng.random() < 0.7
        return (f"SELECT {'COUNT(*)' if as_count else 'T1.account_id'} FROM account AS T1 INNER JOIN district AS T3 ON T1.district_id = T3.district_id WHERE T3.A3 = '{region}' AND NOT EXISTS (SELECT 1 FROM trans AS T2 WHERE T2.account_id = T1.account_id AND T2.k_symbol = '{ks}')",
                (f"How many accounts in the region '{region}' have never had a transaction for {_tk(ks)}?" if as_count else f"Which accounts in the region '{region}' have never had a transaction for {_tk(ks)}? Give the account ids."), ["anti_join", "trans"] + (["count"] if as_count else []))
    return ("SELECT T1.client_id FROM client AS T1 WHERE EXISTS (SELECT 1 FROM disp AS T2 WHERE T2.client_id = T1.client_id AND T2.type = 'OWNER') AND NOT EXISTS (SELECT 1 FROM disp AS T2 INNER JOIN loan AS T3 ON T2.account_id = T3.account_id WHERE T2.client_id = T1.client_id) AND T1.gender = '" + rng.choice(["M", "F"]) + "' AND STRFTIME('%Y', T1.birth_date) < '1950'",
            "Which clients born before 1950 own an account but have no loan on any account they are linked to? Give the client ids. (Use the gender filter in the query.)", ["anti_join", "exists"])

def f_cond_having(db, rng):
    kind = rng.choice(["female_share_districts", "default_share_regions", "gold_share_districts", "weekly_share_regions"])
    if kind == "female_share_districts":
        pct = rng.choice([50, 52, 55]); op = rng.choice([">", "<"])
        return (f"SELECT T2.A2 FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id GROUP BY T2.A2 HAVING CAST(SUM(CASE WHEN T1.gender = 'F' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) {op} {pct}",
                f"Which districts have {'more' if op=='>' else 'less'} than {pct} percent female clients? Give the district names.", ["conditional_agg", "having"])
    if kind == "default_share_regions":
        pct = rng.choice([5, 8, 10])
        return (f"SELECT T3.A3, CAST(SUM(CASE WHEN T1.status = 'D' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) {J_LAD} GROUP BY T3.A3 HAVING CAST(SUM(CASE WHEN T1.status = 'D' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) > {pct}",
                f"Which regions have more than {pct} percent of their loans running with the client in debt? Give the region and the percentage.", ["conditional_agg", "having", "join3", "coded"])
    if kind == "gold_share_districts":
        return ("SELECT T4.A2 FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id INNER JOIN account AS T3 ON T2.account_id = T3.account_id INNER JOIN district AS T4 ON T3.district_id = T4.district_id GROUP BY T4.A2 HAVING SUM(CASE WHEN T1.type = 'gold' THEN 1 ELSE 0 END) >= 2",
                "Which districts have at least two gold cards issued on their accounts? Give the district names.", ["conditional_agg", "having", "join3"])
    pct = rng.choice([5, 8, 10])
    return (f"SELECT T2.A3 FROM account AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id GROUP BY T2.A3 HAVING CAST(SUM(CASE WHEN T1.frequency = 'POPLATEK TYDNE' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) > {pct}",
            f"Which regions have more than {pct} percent of their accounts on weekly statement issuance? Give the region names.", ["conditional_agg", "having", "coded"])

def f_nested_agg(db, rng):
    kind = rng.choice(["max_of_counts", "region_top_avg_salary_min_loans", "district_most_loans_in_region", "avg_of_per_account_totals"])
    if kind == "max_of_counts":
        return ("SELECT MAX(n) FROM (SELECT COUNT(*) AS n FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id GROUP BY T2.district_id)",
                "What is the largest number of loans held by any single district?", ["nested_agg"])
    if kind == "region_top_avg_salary_min_loans":
        thr = min_count_threshold(db, f"SELECT COUNT(*) {J_LAD} GROUP BY T3.A3", rng, [60, 70, 80, 90, 100, 120])
        if thr is None: return f_nested_agg(db, rng)
        key = f"SELECT T3.A3, AVG(T3.A11) AS a FROM (SELECT T1.district_id FROM district AS T1) AS D INNER JOIN district AS T3 ON D.district_id = T3.district_id GROUP BY T3.A3 HAVING (SELECT COUNT(*) {J_LAD.replace('T1','L1').replace('T2','L2').replace('T3','L3')} WHERE L3.A3 = T3.A3) >= {thr} ORDER BY a DESC"
        if not tie_free(db, key, 1): return f_nested_agg(db, rng)
        return (key + " LIMIT 1",
                f"Among regions with at least {thr} loans, which region has the highest average district salary? Give the region and that average.", ["nested_agg", "having", "coded"])
    if kind == "district_most_loans_in_region":
        region = rng.choice(db.col_values("district", "A3"))
        key = f"SELECT T3.A2, COUNT(*) AS n {J_LAD} WHERE T3.A3 = '{region}' GROUP BY T3.A2 ORDER BY n DESC"
        if not tie_free(db, key, 1): return f_nested_agg(db, rng)
        return (key + " LIMIT 1", f"Within the region '{region}', which district has the most loans? Give the district name and the number of loans.", ["nested_agg", "order_limit", "join3"])
    ks = rng.choice(OKS)
    return (f"SELECT AVG(t) FROM (SELECT SUM(amount) AS t FROM \"order\" WHERE k_symbol = '{ks}' GROUP BY account_id)",
            f"Across accounts that have permanent orders for {_o(ks)}, what is the average per-account total amount of those orders?", ["nested_agg", "reserved_word"])

def f_date_arith(db, rng):
    kind = rng.choice(["months_account_to_loan", "loan_end_year", "age_at_card", "loans_within_year_of_opening"])
    if kind == "months_account_to_loan":
        thr = rng.choice([12, 24, 36]); op = rng.choice(["<", ">"])
        return (f"SELECT T1.loan_id FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE (CAST(STRFTIME('%Y', T1.date) AS INTEGER) - CAST(STRFTIME('%Y', T2.date) AS INTEGER)) * 12 + (CAST(STRFTIME('%m', T1.date) AS INTEGER) - CAST(STRFTIME('%m', T2.date) AS INTEGER)) {op} {thr}",
                f"Which loans were granted {'less' if op=='<' else 'more'} than {thr} months after the account was opened (month difference)? Give the loan ids.", ["date", "arithmetic"])
    if kind == "loan_end_year":
        y = rng.choice(range(1996, 2004))
        return (f"SELECT COUNT(*) FROM loan WHERE CAST(STRFTIME('%Y', date) AS INTEGER) + (duration / 12) = {y}",
                f"How many loans are scheduled to end in {y}, taking the end year as the grant year plus the duration in whole years (duration in months divided by 12, integer division)?", ["date", "arithmetic"])
    if kind == "age_at_card":
        ct = rng.choice(list(VALUES[("card", "type")])); thr = rng.choice([25, 30, 40]); op = rng.choice(["<", ">="])
        return (f"SELECT COUNT(*) FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id INNER JOIN client AS T3 ON T2.client_id = T3.client_id WHERE T1.type = '{ct}' AND CAST(STRFTIME('%Y', T1.issued) AS INTEGER) - CAST(STRFTIME('%Y', T3.birth_date) AS INTEGER) {op} {thr}",
                f"How many {_meaning('card','type',ct)}s were issued to clients who were {'younger than' if op=='<' else 'at least'} {thr} (year difference) at issue time?", ["date", "arithmetic", "join3"])
    return ("SELECT COUNT(*) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE STRFTIME('%Y', T1.date) = STRFTIME('%Y', T2.date)",
            "How many loans were granted in the same calendar year the account was opened?", ["date"])

def f_trans_hard(db, rng):
    kind = rng.choice(["negative_balance_accounts", "withdrawals_exceed_credits", "first_trans_year", "largest_withdrawal_per_account_top", "accounts_no_trans_in_year"])
    if kind == "negative_balance_accounts":
        region = rng.choice(db.col_values("district", "A3"))
        return (f"SELECT DISTINCT T1.account_id FROM trans AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T3.A3 = '{region}' AND T1.balance < 0",
                f"Which accounts in the region '{region}' have had a negative balance after some transaction? Give the account ids.", ["trans", "join3"])
    if kind == "withdrawals_exceed_credits":
        y = rng.choice(range(1995, 1999)); name = rng.choice(db.col_values("district", "A2"))
        return (f"SELECT T1.account_id FROM trans AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T3.A2 = '{name}' AND STRFTIME('%Y', T1.date) = '{y}' GROUP BY T1.account_id HAVING SUM(CASE WHEN T1.type IN ('VYDAJ', 'VYBER') THEN T1.amount ELSE 0 END) > SUM(CASE WHEN T1.type = 'PRIJEM' THEN T1.amount ELSE 0 END)",
                f"For accounts in the district '{name}', which ones withdrew more than they received in {y}? Give the account ids.", ["trans", "conditional_agg", "having", "date"])
    if kind == "first_trans_year":
        y = _yr(rng); fq = rng.choice(FREQ)
        return (f"SELECT COUNT(*) FROM account AS T1 WHERE T1.frequency = '{fq}' AND (SELECT MIN(STRFTIME('%Y', T2.date)) FROM trans AS T2 WHERE T2.account_id = T1.account_id) = '{y}'",
                f"How many accounts with {_meaning('account','frequency',fq)} had their first transaction in {y}?", ["trans", "correlated", "date"])
    if kind == "largest_withdrawal_per_account_top":
        did = rng.choice(db.col_values("account", "district_id"))
        key = f"SELECT T1.account_id, MAX(T1.amount) AS m FROM trans AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T2.district_id = {did} AND T1.type IN ('VYDAJ', 'VYBER') GROUP BY T1.account_id ORDER BY m DESC"
        if not tie_free(db, key, 3): return f_trans_hard(db, rng)
        return (key + " LIMIT 3", f"Among accounts in district id {did}, which 3 accounts had the largest single withdrawal? Give the account id and that withdrawal amount.", ["trans", "order_limit", "join"])
    y = _yr(rng); did = rng.choice(db.col_values("account", "district_id"))
    return (f"SELECT T1.account_id FROM account AS T1 WHERE T1.district_id = {did} AND STRFTIME('%Y', T1.date) < '{y}' AND NOT EXISTS (SELECT 1 FROM trans AS T2 WHERE T2.account_id = T1.account_id AND STRFTIME('%Y', T2.date) = '{y}')",
            f"Which accounts in district id {did} that were opened before {y} had no transactions at all during {y}? Give the account ids.", ["trans", "anti_join", "date"])

FAMILIES = [("correlated", f_correlated), ("setops", f_setops), ("antijoin", f_antijoin), ("cond_having", f_cond_having),
            ("nested_agg", f_nested_agg), ("date_arith", f_date_arith), ("trans_hard", f_trans_hard)]
