"""Tier-1 families (one table, no join): text matching · date ranges · multi-condition filters · distinct
counts · NULL/blank checks · per-row arithmetic. Contract as templates.py."""
from __future__ import annotations
from semantics import DISTRICT, NUMERIC_DISTRICT, VALUES
from templates import num, tie_free, _meaning, _yr, month_range

STATUS = list(VALUES[("loan", "status")]); FREQ = list(VALUES[("account", "frequency")]); CARD = list(VALUES[("card", "type")])
OKS = list(VALUES[("order", "k_symbol")]); TOPS = [k for k in VALUES[("trans", "operation")]]
def _s(v): return _meaning("loan", "status", v)

def f_text(db, rng):
    kind = rng.choice(["district_prefix", "district_contains", "region_like", "district_ends"])
    names = db.col_values("district", "A2", k=77)
    if kind == "district_prefix":
        p = rng.choice(names)[:rng.choice([1, 2])]
        if sum(n.startswith(p) for n in names) < 2: return f_text(db, rng)
        return (f"SELECT A2 FROM district WHERE A2 LIKE '{p}%'", f"List the names of districts that start with '{p}'.", ["like"])
    if kind == "district_contains":
        sub = rng.choice(["ov", "ice", "in", "nad", "Brod", "Hradec"]); c = rng.choice(["A11", "A4"])
        return (f"SELECT A2, {c} FROM district WHERE A2 LIKE '%{sub}%'", f"For districts whose name contains '{sub}', give the district name and its {DISTRICT[c]}.", ["like", "coded"])
    if kind == "region_like":
        sub = rng.choice(["Bohemia", "Moravia"])
        return (f"SELECT COUNT(*) FROM district WHERE A3 LIKE '%{sub}%'", f"How many districts are in regions whose name contains '{sub}'?", ["like", "count"])
    suf = rng.choice(["ov", "ice", "in"])
    return (f"SELECT COUNT(*) FROM district WHERE A2 LIKE '%{suf}'", f"How many district names end with '{suf}'?", ["like", "count"])

def f_dates(db, rng):
    kind = rng.choice(["loans_between", "accounts_quarter", "cards_year_type", "clients_decade", "orders_none"])
    if kind == "loans_between":
        y = rng.choice(range(1994, 1999)); m1, m2 = sorted(rng.sample(range(1, 13), 2)); f = rng.choice(["COUNT(*)", "SUM(amount)", "AVG(amount)"])
        w = {"COUNT(*)": "how many loans were granted", "SUM(amount)": "what was the total loan amount granted", "AVG(amount)": "what was the average loan amount granted"}[f]
        return (f"SELECT {f} FROM loan WHERE {month_range(y, m1, m2)}",
                f"Between the start of month {m1} and the end of month {m2} of {y}, {w}?", ["date_range", "aggregate"])
    if kind == "accounts_quarter":
        y = _yr(rng); q = rng.choice([1, 2, 3, 4]); m1 = 3 * q - 2; m2 = 3 * q
        return (f"SELECT COUNT(*) FROM account WHERE {month_range(y, m1, m2)}",
                f"How many accounts were opened in quarter {q} of {y}?", ["date_range", "count"])
    if kind == "cards_year_type":
        ct = rng.choice(CARD); y = rng.choice(range(1995, 1999))
        return (f"SELECT COUNT(*) FROM card WHERE type = '{ct}' AND STRFTIME('%Y', issued) = '{y}'",
                f"How many {_meaning('card','type',ct)}s were issued in {y}?", ["date", "count"])
    if kind == "clients_decade":
        dec = rng.choice([1930, 1940, 1950, 1960, 1970]); g = rng.choice(["M", "F"])
        return (f"SELECT COUNT(*) FROM client WHERE gender = '{g}' AND STRFTIME('%Y', birth_date) BETWEEN '{dec}' AND '{dec+9}'",
                f"How many {_meaning('client','gender',g)} clients were born in the {dec}s?", ["date_range", "count"])
    y = rng.choice(range(1994, 1999)); d = rng.choice(["ASC", "DESC"])
    key = f"SELECT loan_id, date FROM loan WHERE STRFTIME('%Y', date) = '{y}' ORDER BY date {d}"
    if not tie_free(db, key, 1): return f_dates(db, rng)
    return (f"SELECT loan_id FROM loan WHERE STRFTIME('%Y', date) = '{y}' ORDER BY date {d} LIMIT 1",
            f"What is the loan id of the {'first' if d=='ASC' else 'last'} loan granted in {y}?", ["date", "order_limit"])

def f_multi(db, rng):
    kind = rng.choice(["loan_status_amount_duration", "client_gender_year", "order_ks_amount", "district_two_conditions", "trans_type_amount_year"])
    if kind == "loan_status_amount_duration":
        st = rng.choice(STATUS); thr = rng.choice([100000, 200000, 300000]); dur = rng.choice([12, 24, 36, 48, 60]); op = rng.choice([">", "<"])
        return (f"SELECT COUNT(*) FROM loan WHERE status = '{st}' AND amount {op} {thr} AND duration = {dur}",
                f"How many loans have status {_s(st)}, an amount {'above' if op=='>' else 'below'} {thr}, and a duration of {dur} months?", ["multi_filter", "count", "coded"])
    if kind == "client_gender_year":
        g = rng.choice(["M", "F"]); y = rng.choice(range(1940, 1990, 5)); op = rng.choice(["<", ">="])
        return (f"SELECT COUNT(*) FROM client WHERE gender = '{g}' AND STRFTIME('%Y', birth_date) {op} '{y}'",
                f"How many {_meaning('client','gender',g)} clients were born {'before' if op=='<' else 'in or after'} {y}?", ["multi_filter", "count", "date"])
    if kind == "order_ks_amount":
        ks = rng.choice(OKS); thr = rng.choice([500, 1000, 3000, 5000]); op = rng.choice([">", "<"])
        return (f"SELECT COUNT(*) FROM \"order\" WHERE k_symbol = '{ks}' AND amount {op} {thr}",
                f"How many permanent orders for {_meaning('order','k_symbol',ks)} have an amount {'above' if op=='>' else 'below'} {thr}?", ["multi_filter", "count", "reserved_word"])
    if kind == "district_two_conditions":
        c1, c2 = rng.sample(["A11", "A13", "A14", "A10", "A9"], 2); t1 = db.num_quantiles("district", c1)[rng.choice([1, 2])]; t2 = db.num_quantiles("district", c2)[rng.choice([1, 2])]
        o1, o2 = rng.choice([">", "<"]), rng.choice([">", "<"])
        return (f"SELECT A2 FROM district WHERE {c1} {o1} {t1} AND {c2} {o2} {t2}",
                f"List the names of districts whose {DISTRICT[c1]} is {'above' if o1=='>' else 'below'} {t1} and whose {DISTRICT[c2]} is {'above' if o2=='>' else 'below'} {t2}.", ["multi_filter", "coded"])
    tp = rng.choice(["PRIJEM", "VYDAJ"]); thr = rng.choice([10000, 20000, 50000]); y = rng.choice(range(1995, 1999))
    return (f"SELECT COUNT(*) FROM trans WHERE type = '{tp}' AND amount > {thr} AND STRFTIME('%Y', date) = '{y}'",
            f"How many {_meaning('trans','type',tp)} transactions above {thr} occurred in {y}?", ["multi_filter", "count", "trans", "date"])

def f_distinct(db, rng):
    kind = rng.choice(["regions", "districts_with_accounts", "ks_orders", "operations_trans", "durations"])
    if kind == "regions": return ("SELECT COUNT(DISTINCT A3) FROM district", "How many distinct regions are there?", ["distinct", "count"])
    if kind == "districts_with_accounts":
        fq = rng.choice(FREQ)
        return (f"SELECT COUNT(DISTINCT district_id) FROM account WHERE frequency = '{fq}'", f"How many distinct districts have at least one account with {_meaning('account','frequency',fq)}?", ["distinct", "count", "coded"])
    if kind == "ks_orders": return ("SELECT DISTINCT k_symbol FROM \"order\" WHERE k_symbol != ''", "List the distinct purposes recorded on permanent orders (ignoring blank ones).", ["distinct", "reserved_word"])
    if kind == "operations_trans":
        y = rng.choice(range(1995, 1999))
        return (f"SELECT COUNT(DISTINCT account_id) FROM trans WHERE STRFTIME('%Y', date) = '{y}' AND operation = 'VYBER KARTOU'",
                f"How many distinct accounts had at least one credit card withdrawal in {y}?", ["distinct", "count", "trans", "date"])
    st = rng.choice(STATUS)
    return (f"SELECT DISTINCT duration FROM loan WHERE status = '{st}' ORDER BY duration", f"Which distinct loan durations (in months) occur among loans with status {_s(st)}? List them in increasing order.", ["distinct", "order", "coded"])

def f_nulls(db, rng):
    kind = rng.choice(["orders_blank_ks", "trans_null_operation", "trans_null_bank_year", "district_null"])
    if kind == "orders_blank_ks":
        return ("SELECT COUNT(*) FROM \"order\" WHERE k_symbol = '' OR k_symbol IS NULL", "How many permanent orders have no recorded purpose (blank or missing)?", ["null", "count", "reserved_word"])
    if kind == "trans_null_operation":
        y = rng.choice(range(1995, 1999))
        return (f"SELECT COUNT(*) FROM trans WHERE operation IS NULL AND STRFTIME('%Y', date) = '{y}'", f"How many transactions in {y} have no recorded operation?", ["null", "count", "trans", "date"])
    if kind == "trans_null_bank_year":
        y = rng.choice(range(1995, 1999)); tp = rng.choice(["PRIJEM", "VYDAJ"])
        return (f"SELECT COUNT(*) FROM trans WHERE bank IS NULL AND type = '{tp}' AND STRFTIME('%Y', date) = '{y}'",
                f"How many {_meaning('trans','type',tp)} transactions in {y} have no partner bank recorded?", ["null", "count", "trans", "date"])
    c = rng.choice(["A12", "A15"])
    return (f"SELECT A2 FROM district WHERE {c} IS NULL", f"Which districts have no recorded {DISTRICT[c]}? Give the district names.", ["null", "coded"])

def f_arith(db, rng):
    kind = rng.choice(["repayment_loan", "top_repayment", "crime_rate_district", "monthly_amount"])
    if kind == "repayment_loan":
        thr = rng.choice([300000, 500000, 800000]); op = rng.choice([">", "<"])
        return (f"SELECT COUNT(*) FROM loan WHERE payments * duration {op} {thr}",
                f"How many loans have a total scheduled repayment (monthly payment times duration in months) {'above' if op=='>' else 'below'} {thr}?", ["arithmetic", "count"])
    if kind == "top_repayment":
        k = rng.choice([1, 3, 5]); d = rng.choice(["DESC", "ASC"])
        key = f"SELECT loan_id, payments * duration AS r FROM loan ORDER BY r {d}"
        if not tie_free(db, key, k): return f_arith(db, rng)
        return (key + f" LIMIT {k}", f"Which {k} loan{'s' if k>1 else ''} {'have' if k>1 else 'has'} the {'largest' if d=='DESC' else 'smallest'} total scheduled repayment (monthly payment times duration)? Give the loan id and the repayment.", ["arithmetic", "order_limit"])
    if kind == "crime_rate_district":
        k = rng.choice([1, 3, 5]); d = rng.choice(["DESC", "ASC"]); yc = rng.choice(["A15", "A16"]); yl = "1995" if yc == "A15" else "1996"
        key = f"SELECT A2, {yc} * 1000.0 / CAST(A4 AS INTEGER) AS r FROM district WHERE {yc} IS NOT NULL ORDER BY r {d}"
        if not tie_free(db, key, k): return f_arith(db, rng)
        return (key + f" LIMIT {k}", f"Which {k} district{'s' if k>1 else ''} {'have' if k>1 else 'has'} the {'highest' if d=='DESC' else 'lowest'} number of committed crimes in {yl} per 1000 inhabitants? Give the district name and the rate.", ["arithmetic", "order_limit", "coded"])
    thr = rng.choice([2000, 4000, 6000]); st = rng.choice(STATUS)
    return (f"SELECT COUNT(*) FROM loan WHERE status = '{st}' AND amount / duration > {thr}",
            f"How many loans with status {_s(st)} have an amount divided by duration in months (integer division) above {thr}?", ["arithmetic", "count", "coded"])

FAMILIES = [("text", f_text), ("dates", f_dates), ("multi", f_multi), ("distinct", f_distinct), ("nulls", f_nulls), ("arith", f_arith)]
