"""BIRD-style families (added 2026-09-05 after comparing feature mixes): the held-out 106 lean on
(a) entity-chain lookups through 3–4 joins ending in a single fact, (b) "what percentage of X ... Y"
phrasings, (c) nth-highest rankings. These cover those KINDS of question with our own entities and
phrasings — not BIRD's questions. Leak filter still removes any answer/shape collision."""
from __future__ import annotations
from semantics import DISTRICT, VALUES
from templates import num, tie_free, _meaning, _yr

STATUS = list(VALUES[("loan", "status")]); FREQ = list(VALUES[("account", "frequency")]); CARD = list(VALUES[("card", "type")])
OKS = list(VALUES[("order", "k_symbol")])
CHAIN = ("FROM client AS T1 INNER JOIN disp AS T2 ON T1.client_id = T2.client_id INNER JOIN account AS T3 ON T2.account_id = T3.account_id "
         "INNER JOIN district AS T4 ON T1.district_id = T4.district_id")   # T4 = the CLIENT's district (client and account districts differ in 494 cases)

def f_chain_lookup(db, rng):  # tier 3: 3–4 joins, single fact or short list
    kind = rng.choice(["loan_to_client_gender", "card_to_district", "loan_to_district_region", "client_to_loan_status", "order_to_client_birth", "account_owner_district"])
    if kind == "loan_to_client_gender":
        lid = rng.choice(db.col_values("loan", "loan_id"))
        return (f"SELECT T3.gender, T3.birth_date FROM loan AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id INNER JOIN client AS T3 ON T2.client_id = T3.client_id WHERE T1.loan_id = {lid} AND T2.type = 'OWNER'",
                f"What are the gender code and birth date of the owner of the account that holds loan id {lid}?", ["chain", "join3", "lookup"])
    if kind == "card_to_district":
        cid = rng.choice(db.col_values("card", "card_id"))
        return (f"SELECT T4.A2, T4.A3 FROM card AS T1 INNER JOIN disp AS T2 ON T1.disp_id = T2.disp_id INNER JOIN account AS T3 ON T2.account_id = T3.account_id INNER JOIN district AS T4 ON T3.district_id = T4.district_id WHERE T1.card_id = {cid}",
                f"In which district and region is the account that card id {cid} was issued on? Give the district name and the region.", ["chain", "join3", "lookup", "coded"])
    if kind == "loan_to_district_region":
        st = rng.choice(STATUS); y = rng.choice(range(1996, 1999))
        return (f"SELECT DISTINCT T3.A3 FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T1.status = '{st}' AND STRFTIME('%Y', T1.date) = '{y}'",
                f"Which regions had loans with status {_meaning('loan','status',st)} granted in {y}? Give the distinct region names.", ["chain", "join3", "distinct", "date"])
    if kind == "client_to_loan_status":
        cid = rng.choice([r[0] for r in db.con.execute("SELECT DISTINCT T2.client_id FROM loan AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id ORDER BY RANDOM() LIMIT 30")])
        return (f"SELECT T1.loan_id, T1.status FROM loan AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id WHERE T2.client_id = {cid}",
                f"Which loans are on accounts linked to client id {cid}, and what is each loan's status? Give the loan id and the status code.", ["chain", "join", "lookup", "coded"])
    if kind == "order_to_client_birth":
        oid = rng.choice(db.col_values("order", "order_id"))
        return (f"SELECT T3.birth_date FROM \"order\" AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id INNER JOIN client AS T3 ON T2.client_id = T3.client_id WHERE T1.order_id = {oid} AND T2.type = 'OWNER'",
                f"What is the birth date of the owner of the account that permanent order id {oid} belongs to?", ["chain", "join3", "lookup", "reserved_word"])
    aid = rng.choice(db.col_values("account", "account_id"))
    return (f"SELECT T1.client_id, T4.A2 {CHAIN} WHERE T3.account_id = {aid} AND T2.type = 'OWNER'",
            f"Who owns account id {aid} and in which district does that owner live? Give the client id and the district name.", ["chain", "join3", "lookup"])

def f_chain_count(db, rng):  # tier 3: counts/aggregates at the end of a chain with a district/region condition
    kind = rng.choice(["clients_gender_in_district_with_loans", "male_clients_in_top_crime_district", "avg_loan_of_clients_born_decade", "cards_of_clients_region_gender"])
    if kind == "clients_gender_in_district_with_loans":
        name = rng.choice(db.col_values("district", "A2")); g = rng.choice(["M", "F"])
        return (f"SELECT COUNT(DISTINCT T1.client_id) {CHAIN} INNER JOIN loan AS T5 ON T3.account_id = T5.account_id WHERE T4.A2 = '{name}' AND T1.gender = '{g}'",
                f"How many distinct {_meaning('client','gender',g)} clients in the district '{name}' are linked to an account that has a loan?", ["chain", "join3", "count", "distinct"])
    if kind == "male_clients_in_top_crime_district":
        c = rng.choice(["A15", "A16", "A11", "A13"]); n = rng.choice([1, 2, 3]); g = rng.choice(["M", "F"]); d = rng.choice(["DESC", "ASC"])
        key = f"SELECT A2, {c} FROM district WHERE {c} IS NOT NULL ORDER BY {c} {d}"
        if not tie_free(db, key, n): return f_chain_count(db, rng)
        nth = {1: "highest" if d == "DESC" else "lowest", 2: "second-highest" if d == "DESC" else "second-lowest", 3: "third-highest" if d == "DESC" else "third-lowest"}[n]
        return (f"SELECT COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T1.gender = '{g}' AND T2.district_id = (SELECT district_id FROM district WHERE {c} IS NOT NULL ORDER BY {c} {d} LIMIT 1 OFFSET {n-1})",
                f"How many {_meaning('client','gender',g)} clients live in the district with the {nth} {DISTRICT[c]}?", ["chain", "nth", "subquery", "coded"])
    if kind == "avg_loan_of_clients_born_decade":
        dec = rng.choice([1940, 1950, 1960, 1970])
        return (f"SELECT AVG(T5.amount) FROM client AS T1 INNER JOIN disp AS T2 ON T1.client_id = T2.client_id INNER JOIN loan AS T5 ON T2.account_id = T5.account_id WHERE T2.type = 'OWNER' AND STRFTIME('%Y', T1.birth_date) BETWEEN '{dec}' AND '{dec+9}'",
                f"What is the average loan amount on accounts owned by clients born in the {dec}s?", ["chain", "join3", "aggregate", "date"])
    region = rng.choice(db.col_values("district", "A3")); g = rng.choice(["M", "F"]); ct = rng.choice(CARD)
    return (f"SELECT COUNT(*) FROM card AS T5 INNER JOIN disp AS T2 ON T5.disp_id = T2.disp_id INNER JOIN client AS T1 ON T2.client_id = T1.client_id INNER JOIN district AS T4 ON T1.district_id = T4.district_id WHERE T4.A3 = '{region}' AND T1.gender = '{g}' AND T5.type = '{ct}'",
            f"How many {_meaning('card','type',ct)}s are held by {_meaning('client','gender',g)} clients living in the region '{region}'?", ["chain", "join3", "count"])

def f_percentage(db, rng):  # tier 3/4: "what percentage of X ... Y"
    kind = rng.choice(["pct_gender_freq", "pct_loans_status_region", "pct_accounts_with_card_district", "pct_clients_gender_region", "pct_orders_ks"])
    if kind == "pct_gender_freq":
        g = rng.choice(["M", "F"]); fq = rng.choice(FREQ)
        return (f"SELECT CAST(SUM(CASE WHEN T3.frequency = '{fq}' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM client AS T1 INNER JOIN disp AS T2 ON T1.client_id = T2.client_id INNER JOIN account AS T3 ON T2.account_id = T3.account_id WHERE T1.gender = '{g}' AND T2.type = 'OWNER'",
                f"What percentage of {_meaning('client','gender',g)} account owners have {_meaning('account','frequency',fq)}?", ["percentage", "conditional_agg", "join3"])
    if kind == "pct_loans_status_region":
        st = rng.choice(STATUS); region = rng.choice(db.col_values("district", "A3"))
        return (f"SELECT CAST(SUM(CASE WHEN T1.status = '{st}' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T3.A3 = '{region}'",
                f"What percentage of loans on accounts in the region '{region}' have status {_meaning('loan','status',st)}?", ["percentage", "conditional_agg", "join3", "coded"])
    if kind == "pct_accounts_with_card_district":
        name = rng.choice(db.col_values("district", "A2"))
        return (f"SELECT CAST(SUM(CASE WHEN EXISTS (SELECT 1 FROM disp AS T2 INNER JOIN card AS T3 ON T2.disp_id = T3.disp_id WHERE T2.account_id = T1.account_id) THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM account AS T1 INNER JOIN district AS T4 ON T1.district_id = T4.district_id WHERE T4.A2 = '{name}'",
                f"What percentage of accounts in the district '{name}' have at least one card?", ["percentage", "exists", "conditional_agg"])
    if kind == "pct_clients_gender_region":
        g = rng.choice(["M", "F"]); region = rng.choice(db.col_values("district", "A3")); y = rng.choice([1950, 1960, 1970])
        return (f"SELECT CAST(SUM(CASE WHEN STRFTIME('%Y', T1.birth_date) < '{y}' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T1.gender = '{g}' AND T2.A3 = '{region}'",
                f"What percentage of {_meaning('client','gender',g)} clients in the region '{region}' were born before {y}?", ["percentage", "conditional_agg", "join", "date"])
    ks = rng.choice(OKS); fq = rng.choice(FREQ)
    return (f"SELECT CAST(SUM(CASE WHEN T1.k_symbol = '{ks}' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM \"order\" AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE T2.frequency = '{fq}'",
            f"Among permanent orders on accounts with {_meaning('account','frequency',fq)}, what percentage are for {_meaning('order','k_symbol',ks)}?", ["percentage", "conditional_agg", "join", "reserved_word"])

def f_nth(db, rng):  # tier 4: second/third-highest with a follow-up fact
    kind = rng.choice(["nth_district_fact", "nth_loan_owner", "nth_region_by_loans"])
    if kind == "nth_district_fact":
        c = rng.choice(["A11", "A13", "A15", "A16", "A14", "A10"]); n = rng.choice([2, 3]); d = rng.choice(["DESC", "ASC"]); out = "A2"  # region-of-nth-district was a grain bug
        key = f"SELECT A2, {c} FROM district WHERE {c} IS NOT NULL ORDER BY {c} {d}"
        if not tie_free(db, key, n): return f_nth(db, rng)
        nth = ("second" if n == 2 else "third") + ("-highest" if d == "DESC" else "-lowest")
        return (f"SELECT {out} FROM district WHERE {c} IS NOT NULL ORDER BY {c} {d} LIMIT 1 OFFSET {n-1}",
                f"Which {'district' if out=='A2' else 'region'} has the {nth} {DISTRICT[c]}? Give the {'district name' if out=='A2' else 'region name'}.", ["nth", "order_limit", "coded"])
    if kind == "nth_loan_owner":
        n = rng.choice([2, 3])
        key = "SELECT loan_id, amount FROM loan ORDER BY amount DESC"
        if not tie_free(db, key, n): return f_nth(db, rng)
        return (f"SELECT T3.client_id FROM loan AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id INNER JOIN client AS T3 ON T2.client_id = T3.client_id WHERE T2.type = 'OWNER' AND T1.loan_id = (SELECT loan_id FROM loan ORDER BY amount DESC LIMIT 1 OFFSET {n-1})",
                f"Who owns the account with the {'second' if n==2 else 'third'}-largest loan? Give the client id.", ["nth", "chain", "subquery"])
    n = rng.choice([2, 3])
    key = "SELECT T3.A3, COUNT(*) AS c FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id GROUP BY T3.A3 ORDER BY c DESC"
    if not tie_free(db, key, n): return f_nth(db, rng)
    return (key + f" LIMIT 1 OFFSET {n-1}", f"Which region has the {'second' if n==2 else 'third'}-most loans? Give the region and the number of loans.", ["nth", "group", "order_limit", "join3"])

FAMILIES = [(3, "chain_lookup", f_chain_lookup, 120), (3, "chain_count", f_chain_count, 100), (3, "percentage", f_percentage, 120), (4, "nth", f_nth, 80)]
