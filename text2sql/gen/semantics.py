"""What the financial schema's coded columns and Czech values MEAN. This is the knowledge the
specialized model is supposed to internalize and a frontier model cannot know cold. Used by the
template generator (to phrase canonical questions) and by the round-trip check (as the schema
legend Haiku gets). Source: the PKDD'99 Czech bank dataset documentation, as used by BIRD."""

DISTRICT = {  # column -> plain meaning
    "A2": "district name", "A3": "region", "A4": "number of inhabitants",
    "A5": "number of municipalities with fewer than 500 inhabitants",
    "A6": "number of municipalities with 500 to 1999 inhabitants",
    "A7": "number of municipalities with 2000 to 9999 inhabitants",
    "A8": "number of municipalities with more than 10000 inhabitants",
    "A9": "number of cities", "A10": "ratio of urban inhabitants (percent)",
    "A11": "average salary", "A12": "unemployment rate in 1995", "A13": "unemployment rate in 1996",
    "A14": "number of entrepreneurs per 1000 inhabitants",
    "A15": "number of committed crimes in 1995", "A16": "number of committed crimes in 1996",
}
NUMERIC_DISTRICT = ["A4", "A9", "A10", "A11", "A12", "A13", "A14", "A15", "A16"]

VALUES = {  # (table, column) -> {stored value: plain meaning}
    ("account", "frequency"): {"POPLATEK MESICNE": "monthly statement issuance",
                               "POPLATEK TYDNE": "weekly statement issuance",
                               "POPLATEK PO OBRATU": "statement issuance after each transaction"},
    ("disp", "type"): {"OWNER": "account owner", "DISPONENT": "authorized user (disponent)"},
    ("card", "type"): {"gold": "gold card", "classic": "classic card", "junior": "junior card"},
    ("loan", "status"): {"A": "contract finished, no problems", "B": "contract finished, loan not paid",
                         "C": "running contract, OK so far", "D": "running contract, client in debt"},
    ("client", "gender"): {"M": "male", "F": "female"},
    ("trans", "type"): {"PRIJEM": "credit (money in)", "VYDAJ": "withdrawal (money out)", "VYBER": "withdrawal in cash (also money out)"},
    ("trans", "operation"): {"VKLAD": "credit in cash", "PREVOD Z UCTU": "collection from another bank",
                             "PREVOD NA UCET": "remittance to another bank", "VYBER": "withdrawal in cash",
                             "VYBER KARTOU": "credit card withdrawal"},
    ("trans", "k_symbol"): {"POJISTNE": "insurance payment", "SLUZBY": "payment for statement",
                            "UROK": "interest credited", "SANKC. UROK": "sanction interest for negative balance",
                            "SIPO": "household payment", "DUCHOD": "old-age pension", "UVER": "loan payment"},
    ("order", "k_symbol"): {"POJISTNE": "insurance payment", "SIPO": "household payment",
                            "LEASING": "leasing payment", "UVER": "loan payment"},
}

TABLES = {
    "account": "a bank account (one row per account); frequency = how often statements are issued",
    "client": "a person; district_id = where the client lives",
    "disp": "disposition: links a client to an account with a role (OWNER or DISPONENT = authorized user)",
    "card": "a credit card issued to a disposition (i.e. to a client on an account)",
    "loan": "a loan granted on an account; status codes below",
    "order": "a PERMANENT ORDER (standing order) set up on an account: recurring payments; k_symbol = purpose",
    "trans": "a transaction on an account (about 1 million rows); type/operation/k_symbol coded below",
    "district": "a district (region-level demographics); the A-columns are coded, see below",
}

def legend() -> str:
    """Plain-language legend of the coded columns and values, for prompts that are ALLOWED to know it
    (question writing, round-trip check). The RL training prompt does NOT include this."""
    out = ["tables:"] + [f"  {t}: {m}" for t, m in TABLES.items()] + ["district columns:"] + [f"  {c} = {m}" for c, m in DISTRICT.items()] + ["coded values:"]
    for (t, c), m in VALUES.items():
        out.append(f"  {t}.{c}: " + "; ".join(f"'{k}' = {v}" for k, v in m.items()))
    return "\n".join(out)
