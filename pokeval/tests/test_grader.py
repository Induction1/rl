import json
import os
import sys

import pytest

import grade

TEST_SET = os.environ.get('POKEVAL_TEST_SET')
if not TEST_SET:
    pytest.skip('POKEVAL_TEST_SET is not set', allow_module_level=True)

CASES = grade.load(TEST_SET)[:200]


def cut_after_turn(log, t):
    out = []
    for l in log:
        if l.startswith('|turn|') and int(l.split('|')[2]) == t + 1:
            return out + ['|turn|999']
        out.append(l)
    return out


def test_gold_is_100():
    s = grade.score(CASES, {c['id']: c['gold_log'] for c in CASES})
    assert s.weighted == 100.0 and s.exact == len(CASES)


def test_nothing_is_0():
    s = grade.score(CASES, {})
    assert s.weighted == 0.0 and s.missing == len(CASES)


def test_prefix_is_monotone():
    scores = [grade.score(CASES, {c['id']: cut_after_turn(c['gold_log'], t) for c in CASES}).weighted
              for t in (3, 10, 20)]
    assert 0 < scores[0] < scores[1] < scores[2] < 100


def test_crash_costs_only_that_battle(tmp_path):
    gold = tmp_path / 'gold.json'
    gold.write_text(json.dumps({c['id']: c['gold_log'] for c in CASES}))
    bad = {CASES[9]['id'], CASES[150]['id']}
    engine = tmp_path / 'engine.py'
    engine.write_text(f"""import json, sys
gold = json.load(open({str(gold)!r}))
for line in sys.stdin:
    case = json.loads(line)
    if case['id'] in {bad!r}:
        raise KeyError(case['id'])
    print(json.dumps({{'id': case['id'], 'log': gold[case['id']]}}))
""")
    answers, _ = grade.run_engine([sys.executable, str(engine)], CASES, timeout=120)
    s = grade.score(CASES, answers)
    assert s.missing == 2 and s.exact == len(CASES) - 2


def test_formula():
    assert abs(grade.points(10) / grade.points(20) - (1.05 ** 10 - 1) / (1.05 ** 20 - 1)) < 1e-12


def test_turn_share_bounds_and_monotone():
    gold = grade.score(CASES, {c['id']: c['gold_log'] for c in CASES})
    empty = grade.score(CASES, {})
    assert gold.turn_share == 100.0 and empty.turn_share == 0.0
    shares = [grade.score(CASES, {c['id']: cut_after_turn(c['gold_log'], t) for c in CASES}).turn_share
              for t in (3, 10, 20)]
    assert 0 < shares[0] < shares[1] < shares[2] < 100
