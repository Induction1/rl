"""Extra tier-2 and tier-3 patterns (added 2026-09-05 after the audits showed 6–9 shapes per tier
was too thin). Same contract as templates.py: (sql, canonical_question, tags), gold correct by
construction, values sampled from the live database, ties rejected via tie_free, TEXT-numeric
district columns cast via num(). Tier 2 = exactly one join, no GROUP BY. Tier 3 = 2–3 joins and/or
GROUP BY with HAVING / ORDER BY LIMIT."""
from __future__ import annotations
from semantics import DISTRICT, NUMERIC_DISTRICT, VALUES
from templates import num, tie_free, _meaning, _yr, min_count_threshold

FREQ = list(VALUES[("account", "frequency")]); STATUS = list(VALUES[("loan", "status")])
CARD = list(VALUES[("card", "type")]); OKS = list(VALUES[("order", "k_symbol")])
def _f(v): return _meaning("account", "frequency", v)
def _s(v): return _meaning("loan", "status", v)
def _c(v): return _meaning("card", "type", v)
def _o(v): return _meaning("order", "k_symbol", v)
def _g(v): return _meaning("client", "gender", v)

# --------------------------------------------------------------------------- tier 2 extras
def t2x(db, rng):
    kind = rng.choice(["loans_status_freq", "avg_loan_by_freq_filter", "orders_ks_in_district_id", "order_total_freq",
                       "clients_born_region", "oldest_client_in_district", "accounts_opened_year_region",
                       "cards_type_disponent", "loans_year_district_id", "loan_ids_status_freq", "salary_of_client",
                       "clients_gender_region", "max_loan_in_region", "cards_issued_year_owner", "accounts_freq_district_name"])
    if kind == "loans_status_freq":
        st, fq = rng.choice(STATUS), rng.choice(FREQ)
        return (f"SELECT COUNT(*) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.status = '{st}' AND T2.frequency = '{fq}'",
                f"How many loans with status {_s(st)} are on accounts with {_f(fq)}?", ["join", "count"])
    if kind == "avg_loan_by_freq_filter":
        fq = rng.choice(FREQ); f = rng.choice(["AVG", "MAX", "MIN", "SUM"]); w = {"AVG": "average", "MAX": "largest", "MIN": "smallest", "SUM": "total"}[f]
        return (f"SELECT {f}(T1.amount) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T2.frequency = '{fq}'",
                f"What is the {w} loan amount among accounts with {_f(fq)}?", ["join", "aggregate"])
    if kind == "orders_ks_in_district_id":
        ks = rng.choice(OKS); did = rng.choice(db.col_values("account", "district_id"))
        return (f"SELECT COUNT(*) FROM \"order\" AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.k_symbol = '{ks}' AND T2.district_id = {did}",
                f"How many permanent orders for {_o(ks)} are on accounts in district id {did}?", ["join", "count", "reserved_word"])
    if kind == "order_total_freq":
        fq = rng.choice(FREQ); ks = rng.choice(OKS)
        return (f"SELECT SUM(T1.amount) FROM \"order\" AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T2.frequency = '{fq}' AND T1.k_symbol = '{ks}'",
                f"What is the total amount of permanent orders for {_o(ks)} on accounts with {_f(fq)}?", ["join", "aggregate", "reserved_word"])
    if kind == "clients_born_region":
        region = rng.choice(db.col_values("district", "A3")); y = rng.choice(range(1940, 1985, 5)); op = rng.choice(["<", ">="])
        return (f"SELECT COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A3 = '{region}' AND STRFTIME('%Y', T1.birth_date) {op} '{y}'",
                f"How many clients in the region '{region}' were born {'before' if op == '<' else 'in or after'} {y}?", ["join", "count", "date"])
    if kind == "oldest_client_in_district":
        name = rng.choice(db.col_values("district", "A2")); d = rng.choice(["ASC", "DESC"])
        key = f"SELECT T1.client_id, T1.birth_date FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A2 = '{name}' ORDER BY T1.birth_date {d}"
        if not tie_free(db, key, 1): return t2x(db, rng)
        return (f"SELECT T1.client_id FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A2 = '{name}' ORDER BY T1.birth_date {d} LIMIT 1",
                f"What is the client id of the {'oldest' if d == 'ASC' else 'youngest'} client living in the district '{name}'?", ["join", "order_limit", "date"])
    if kind == "accounts_opened_year_region":
        region = rng.choice(db.col_values("district", "A3")); y = _yr(rng)
        return (f"SELECT COUNT(*) FROM account AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A3 = '{region}' AND STRFTIME('%Y', T1.date) = '{y}'",
                f"How many accounts in the region '{region}' were opened in {y}?", ["join", "count", "date"])
    if kind == "cards_type_disponent":
        ct = rng.choice(CARD)
        return (f"SELECT COUNT(*) FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id WHERE T1.type = '{ct}' AND T2.type = 'DISPONENT'",
                f"How many {_c(ct)}s are held by authorized users (disponents) rather than owners?", ["join", "count"])
    if kind == "loans_year_district_id":
        did = rng.choice(db.col_values("account", "district_id")); y = rng.choice(range(1994, 1999))
        return (f"SELECT COUNT(*) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T2.district_id = {did} AND STRFTIME('%Y', T1.date) = '{y}'",
                f"How many loans were granted in {y} on accounts in district id {did}?", ["join", "count", "date"])
    if kind == "loan_ids_status_freq":
        st, fq = rng.choice(STATUS), rng.choice(FREQ)
        return (f"SELECT T1.loan_id FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T1.status = '{st}' AND T2.frequency = '{fq}'",
                f"List the loan ids of loans with status {_s(st)} on accounts with {_f(fq)}.", ["join", "list"])
    if kind == "salary_of_client":
        cid = rng.choice(db.col_values("client", "client_id")); c = rng.choice(["A11", "A2", "A3", "A13"])
        return (f"SELECT T2.{c} FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T1.client_id = {cid}",
                f"What is the {DISTRICT[c]} of the district where client id {cid} lives?", ["join", "lookup", "coded"])
    if kind == "clients_gender_region":
        region = rng.choice(db.col_values("district", "A3")); g = rng.choice(["M", "F"])
        return (f"SELECT COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A3 = '{region}' AND T1.gender = '{g}'",
                f"How many {_g(g)} clients live in the region '{region}'?", ["join", "count"])
    if kind == "max_loan_in_region":
        # two joins would be tier 3; use account.district_id directly against a district id
        did = rng.choice(db.col_values("account", "district_id")); f = rng.choice(["MAX", "AVG", "COUNT"])
        w = {"MAX": "largest loan amount", "AVG": "average loan amount", "COUNT": "number of loans"}[f]
        return (f"SELECT {f}(T1.amount) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T2.district_id = {did}",
                f"What is the {w} on accounts in district id {did}?", ["join", "aggregate"])
    if kind == "cards_issued_year_owner":
        y = rng.choice(range(1994, 1999)); role = rng.choice(["OWNER", "DISPONENT"])
        return (f"SELECT COUNT(*) FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id WHERE STRFTIME('%Y', T1.issued) = '{y}' AND T2.type = '{role}'",
                f"How many cards were issued in {y} to {_meaning('disp','type',role)}s?", ["join", "count", "date"])
    name = rng.choice(db.col_values("district", "A2")); fq = rng.choice(FREQ)
    return (f"SELECT COUNT(*) FROM account AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A2 = '{name}' AND T1.frequency = '{fq}'",
            f"How many accounts in the district '{name}' have {_f(fq)}?", ["join", "count"])

# --------------------------------------------------------------------------- tier 3 extras
def t3x(db, rng):
    kind = rng.choice(["loans_per_region", "avg_loan_per_region_top", "clients_per_district_topk", "cards_per_region_type",
                       "order_total_per_ks_region", "status_dist_in_district", "districts_having_loans", "regions_by_loan_amount",
                       "avg_duration_by_status_region", "accounts_many_orders", "clients_many_accounts", "loans_per_year",
                       "top_districts_avg_loan_min5", "gender_of_owners_region", "freq_dist_in_region"])
    J_LAD = "FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id"
    if kind == "loans_per_region":
        return (f"SELECT T3.A3, COUNT(*) {J_LAD} GROUP BY T3.A3",
                "For each region, how many loans have been granted? Give the region and the count.", ["group", "join3"])
    if kind == "avg_loan_per_region_top":
        k = rng.choice([1, 3]); d = rng.choice(["DESC", "ASC"])
        key = f"SELECT T3.A3, AVG(T1.amount) AS a {J_LAD} GROUP BY T3.A3 ORDER BY a {d}"
        if not tie_free(db, key, k): return t3x(db, rng)
        return (f"SELECT T3.A3, AVG(T1.amount) AS a {J_LAD} GROUP BY T3.A3 ORDER BY a {d} LIMIT {k}",
                f"Which {k} region{'s' if k>1 else ''} {'have' if k>1 else 'has'} the {'highest' if d=='DESC' else 'lowest'} average loan amount? Give the region and the average.", ["group", "order_limit", "join3"])
    if kind == "clients_per_district_topk":
        k = rng.choice([1, 3, 5]); d = rng.choice(["DESC", "ASC"])
        key = f"SELECT T2.A2, COUNT(*) AS n FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id GROUP BY T2.A2 ORDER BY n {d}"
        if not tie_free(db, key, k): return t3x(db, rng)
        return (f"SELECT T2.A2, COUNT(*) AS n FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id GROUP BY T2.A2 ORDER BY n {d} LIMIT {k}",
                f"Which {k} district{'s' if k>1 else ''} {'have' if k>1 else 'has'} the {'most' if d=='DESC' else 'fewest'} clients? Give the district name and the number of clients.", ["group", "order_limit", "join"])
    if kind == "cards_per_region_type":
        region = rng.choice(db.col_values("district", "A3"))
        return (f"SELECT T1.type, COUNT(*) FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id INNER JOIN account AS T3 ON T2.account_id = T3.account_id INNER JOIN district AS T4 ON T3.district_id = T4.district_id WHERE T4.A3 = '{region}' GROUP BY T1.type",
                f"In the region '{region}', how many cards of each type were issued? Give the card type and the count.", ["group", "join3"])
    if kind == "order_total_per_ks_region":
        region = rng.choice(db.col_values("district", "A3"))
        return (f"SELECT T1.k_symbol, SUM(T1.amount) FROM \"order\" AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T3.A3 = '{region}' AND T1.k_symbol != '' GROUP BY T1.k_symbol",
                f"For accounts in the region '{region}', what is the total permanent-order amount per purpose (excluding orders with no recorded purpose)? Give the purpose code and the total.", ["group", "join3", "reserved_word"])
    if kind == "status_dist_in_district":
        name = rng.choice(db.col_values("district", "A2"))
        return (f"SELECT T1.status, COUNT(*) {J_LAD} WHERE T3.A2 = '{name}' GROUP BY T1.status",
                f"For loans on accounts in the district '{name}', how many loans are there per status? Give the status code and the count.", ["group", "join3", "coded"])
    if kind == "districts_having_loans":
        counts = sorted(r[0] for r in db.con.execute(f"SELECT COUNT(*) {J_LAD} GROUP BY T3.A2"))
        thr = rng.choice([10, 12, 15, 20]); thr = thr if counts[0] < thr < counts[-1] else 12
        return (f"SELECT T3.A2 {J_LAD} GROUP BY T3.A2 HAVING COUNT(*) > {thr}",
                f"Which districts have more than {thr} loans? Give the district names.", ["group", "having", "join3"])
    if kind == "regions_by_loan_amount":
        d = rng.choice(["DESC", "ASC"])
        return (f"SELECT T3.A3, SUM(T1.amount) AS s {J_LAD} GROUP BY T3.A3 ORDER BY s {d}",
                f"Rank the regions by total loan amount from {'highest' if d=='DESC' else 'lowest'} to {'lowest' if d=='DESC' else 'highest'}. Give the region and the total.", ["group", "order", "join3"])
    if kind == "avg_duration_by_status_region":
        region = rng.choice(db.col_values("district", "A3"))
        return (f"SELECT T1.status, AVG(T1.duration) {J_LAD} WHERE T3.A3 = '{region}' GROUP BY T1.status",
                f"For loans on accounts in the region '{region}', what is the average loan duration per status? Give the status code and the average duration.", ["group", "join3", "coded"])
    if kind == "accounts_many_orders":
        thr = rng.choice([3, 4])
        return (f"SELECT account_id FROM \"order\" GROUP BY account_id HAVING COUNT(*) > {thr}",
                f"Which accounts have more than {thr} permanent orders? Give the account ids.", ["group", "having", "reserved_word"])
    if kind == "clients_many_accounts":
        return ("SELECT client_id FROM disp GROUP BY client_id HAVING COUNT(*) > 1",
                "Which clients are linked to more than one account (via dispositions)? Give the client ids.", ["group", "having"])
    if kind == "loans_per_year":
        return ("SELECT STRFTIME('%Y', date), COUNT(*) FROM loan GROUP BY STRFTIME('%Y', date)",
                "How many loans were granted in each year? Give the year and the count.", ["group", "date"])
    if kind == "top_districts_avg_loan_min5":
        k = rng.choice([3, 5]); d = rng.choice(["DESC", "ASC"])
        n_min = min_count_threshold(db, f"SELECT COUNT(*) {J_LAD} GROUP BY T3.A2", rng, [6, 8, 10, 12, 15])
        if n_min is None: return t3x(db, rng)
        key = f"SELECT T3.A2, AVG(T1.amount) AS a {J_LAD} GROUP BY T3.A2 HAVING COUNT(*) >= {n_min} ORDER BY a {d}"
        if not tie_free(db, key, k): return t3x(db, rng)
        return (f"SELECT T3.A2, AVG(T1.amount) AS a {J_LAD} GROUP BY T3.A2 HAVING COUNT(*) >= {n_min} ORDER BY a {d} LIMIT {k}",
                f"Among districts with at least {n_min} loans, which {k} have the {'highest' if d=='DESC' else 'lowest'} average loan amount? Give the district name and the average.", ["group", "having", "order_limit", "join3"])
    if kind == "gender_of_owners_region":
        region = rng.choice(db.col_values("district", "A3"))
        return (f"SELECT T1.gender, COUNT(*) FROM client AS T1 INNER JOIN disp AS T2 ON T1.client_id = T2.client_id INNER JOIN district AS T3 ON T1.district_id = T3.district_id WHERE T2.type = 'OWNER' AND T3.A3 = '{region}' GROUP BY T1.gender",
                f"Among account owners living in the region '{region}', how many are male and how many are female? Give the gender code and the count.", ["group", "join3"])
    region = rng.choice(db.col_values("district", "A3"))
    return (f"SELECT T1.frequency, COUNT(*) FROM account AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A3 = '{region}' GROUP BY T1.frequency",
            f"In the region '{region}', how many accounts have each statement issuance frequency? Give the frequency code and the count.", ["group", "join", "coded"])
