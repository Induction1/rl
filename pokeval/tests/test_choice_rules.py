import json
import os
from collections import Counter
from functools import lru_cache

import pytest

TEST_SET = os.environ.get('POKEVAL_TEST_SET')
if not TEST_SET:
    pytest.skip('POKEVAL_TEST_SET is not set', allow_module_level=True)

TRAP = {'Bind', 'Clamp', 'Fire Spin', 'Wrap'}
CALLERS = {'Metronome', 'Mirror Move'}
CASES = [json.loads(l) for l in open(TEST_SET) if l.strip()]


def ident(name):
    return ''.join(ch for ch in name.lower() if ch.isalnum())


def check(c):
    r = Counter()
    teams = {s: [m.split('|') for m in c['teams'][s].split(']')] for s in ('p1', 'p2')}
    original = {s: {f[0]: f[4].split(',') for f in teams[s]} for s in ('p1', 'p2')}
    movesets = {s: {k: list(v) for k, v in original[s].items()} for s in ('p1', 'p2')}
    choice = {}
    for ch in c['choices']:
        for s in ('p1', 'p2'):
            if ch[s]:
                choice.setdefault((ch['turn'], s), ch[s])
    for s in ('p1', 'p2'):
        order = [f[0] for f in teams[s]]
        expected = [order[0]]
        for ch in c['choices']:
            if ch[s] and ch[s].startswith('switch'):
                n = int(ch[s].split()[1])
                order[0], order[n - 1] = order[n - 1], order[0]
                expected.append(order[0])
        actual = [l.split('|')[3] for l in c['gold_log'] if l.startswith(f'|switch|{s}a:')]
        r['S ok' if actual == expected else 'S BAD'] += 1
    active, trapping, recharge, turn = {}, {}, {}, 0
    for l in c['gold_log']:
        f = l.split('|')
        tag = f[1]
        if tag == 'turn':
            turn = int(f[2])
            continue
        if tag == 'switch':
            s = f[2][:2]
            if active.get(s):
                movesets[s][active[s]] = list(original[s][active[s]])
            active[s], trapping[s], recharge[s] = f[2][5:], False, None
            continue
        if tag == '-mustrecharge':
            recharge[f[2][:2]] = turn
            continue
        if tag == '-start' and len(f) > 4 and f[3] == 'Mimic':
            s = f[2][:2]
            ms = movesets[s][active[s]]
            if 'mimic' in ms:
                ms[ms.index('mimic')] = ident(f[4])
                r['M mimic'] += 1
            continue
        if tag == '-transform':
            s, t = f[2][:2], f[3][:2]
            movesets[s][active[s]] = list(movesets[t][active[t]])
            r['M transform'] += 1
            continue
        if tag != 'move':
            continue
        s, move = f[2][:2], f[3]
        frm = f[5][7:] if len(f) > 5 and f[5].startswith('[from] ') else None
        chz = choice.get((turn, s))
        if not chz or not chz.startswith('move'):
            continue
        n = int(chz.split()[1])
        ms = movesets[s].get(active.get(s), [])
        if frm in CALLERS:
            r['callers (not locks)'] += 1
            continue
        if frm in TRAP:
            trapping[s] = True
            if move != frm:
                r['T BAD'] += 1
            else:
                r['T ok'] += 1
                if n <= len(ms) and ident(move) != ms[n - 1]:
                    r['T choice named another slot'] += 1
            continue
        if frm or (recharge.get(s) == turn - 1 and chz == 'move 1'):
            r['L ok' if chz == 'move 1' and (not frm or move == frm) else 'L BAD'] += 1
            continue
        if n <= len(ms) and ident(move) == ms[n - 1]:
            r['M ok'] += 1
            trapping[s] = move in TRAP
        elif move in TRAP and trapping.get(s):
            r['T ok (untagged continuation)'] += 1
        else:
            r['M BAD'] += 1
    return r


@lru_cache(maxsize=None)
def totals():
    r = Counter()
    for c in CASES:
        r.update(check(c))
    return r


def test_switch_rule():
    assert totals()['S BAD'] == 0


def test_move_slot_rule():
    r = totals()
    assert r['M BAD'] == 0 and r['M ok'] > 40000 and r['M mimic'] and r['M transform']


def test_lock_rule():
    r = totals()
    assert r['L BAD'] == 0 and r['L ok'] > 3000


def test_trap_rule_is_falsifiable():
    r = totals()
    assert r['T BAD'] == 0 and r['T ok'] > 1000 and r['T choice named another slot'] > 0
