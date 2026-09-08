# Verifier strictness rule — DRAFT for his sign-off (playbook B1; written before run 1)

The reward is computed by executing the model's query and comparing its result to the gold
result. Every line below is a place where "compare" can be loose or strict, and each loose
choice is a hole RL will find. Default = BIRD's official EX (set equality of rows), tightened
where a hole is known. ★ = his decision needed; the rest is standard.

| # | Case | Loose (hackable) | Strict (default here) | ★ / standard |
|---|---|---|---|---|
| 1 | Row order | ignore order always | ignore order UNLESS the question asks for a ranking / top-k / "ordered by", then compare as lists | standard (BIRD ignores; we tighten for ranking questions) |
| 2 | Duplicate rows | collapse to a set | collapse to a set (BIRD) — a query returning each row twice still passes | standard; multiset compare would punish harmless DISTINCT omissions |
| 3 | Column count / extra columns | subset match | exact column count; extra columns fail | standard (the tier-4 "ids vs id+name" case) |
| 4 | Column order | any order | position-sensitive (BIRD compares tuples) | standard |
| 5 | **Float values** | round both to 2 dp | exact equality (BIRD) — "percentage" rounded to 2 dp FAILS | ★ exact, or tolerance 1e-6 relative, or round both to 2 dp? Tolerance only lets through answers that agree to ~6 digits; rounding to 2 dp lets a rounded answer pass. |
| 6 | Empty result | empty == empty passes | empty result NEVER scores, even if gold is empty (and gold is never empty: generator drops them) | standard; blocks the "WHERE 1=0" family |
| 7 | Errors / timeouts | partial credit for "it ran" | reward 0; timeout 30 s = 0 | standard; blocks SELECT 1 hacks |
| 8 | Result size | any | queries returning > 1,000 rows fail (gold never does) | standard; blocks "SELECT *" dumps that happen to contain the answer |
| 9 | NULL handling | NULL == NULL | NULL == NULL (SQLite tuples) but an all-NULL result never scores | standard |
| 10 | Type coercion | 1 == 1.0 == "1" | numeric 1 == 1.0 passes; string "1" ≠ 1 | standard (Python tuple equality after casting ints to floats) |
| 11 | Format | any text | reward 0 unless exactly one ```sql block; small format term (+0.1) for a well-formed block even if wrong ★ | ★ whether to include the +0.1 format term at all (tic-tac-toe needed it for group variance) |
| 12 | Read-only | — | database opened read-only; any write / PRAGMA / ATTACH = 0 | standard |

## Data facts the verifier inherits (found by the 9/5 agent audit)
- `district.A4–A7` are declared TEXT: `A4 > 100000` compares strings in SQLite. Gold casts. A model
  that doesn't cast gets a wrong result and reward 0 — fair, it's a property of this database and
  part of what "knowing the schema" means. Worth a line in the writeup.
- Ties at LIMIT boundaries make top-k gold arbitrary. Generator now rejects tied boundaries; the
  106 BIRD test questions are NOT filtered this way, so a few test items are inherently noisy.
- NULLs in `A12`/`A15` (district Jesenik) sort first under ASC. Gold excludes NULLs explicitly.

## Hacks we expect, and the monitor for each
- Coincidence hacks: a semantically wrong query that returns the gold rows on THIS data ("either
  year" vs "both years"). Monitor: re-score a sample of "correct" answers on a perturbed copy of
  the database (shifted years, shuffled district ids); the pass-rate drop is the hack rate.
- Ranking without ORDER BY: passes under set equality when k = 1 by luck. Covered by rule 1.
- Precision games: CAST/ROUND to make floats match. Covered by rule 5 (his call).
- Over-wide SELECT: covered by 3 and 8.
- Format farming: many ```sql blocks, one of which is right. Rule 11 takes the LAST block only
  and requires exactly one.

## Open (his)
- Rule 5 float policy. My read: exact, plus the question generator never asks for rounding.
- Rule 11 format term: include +0.1 or pure binary.
- Whether to add a "would a person ask this" judge filter on Haiku-written questions (cheap, ~$2).
