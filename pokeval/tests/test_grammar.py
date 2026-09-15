import json
import os
import re

import pytest

TEST_SET = os.environ.get('POKEVAL_TEST_SET')
if not TEST_SET:
    pytest.skip('POKEVAL_TEST_SET is not set', allow_module_level=True)

SPEC = open('task/SPEC.md').read()
SPECIES = {v['name'] for v in json.load(open('docs/species.json')).values()}
MOVES = {v['name'] for v in json.load(open('docs/moves.json')).values()}
TYPES = list(json.load(open('docs/typechart.json')))


def alternation(names):
    return '(?:' + '|'.join(sorted(map(re.escape, names), key=len, reverse=True)) + ')'


SLOT = {
    'mon': r'p[12]a: ' + alternation(SPECIES),
    'species': alternation(SPECIES),
    'move': alternation(MOVES),
    'hp': r'\d+/\d+',
    'status': '(?:par|slp|frz|brn|psn|tox)',
    'stat': '(?:atk|def|spa|spd|spe|accuracy|evasion)',
    'n': r'\d+',
    'player': 'P[12]',
    'type': alternation(TYPES) + '(?:/' + alternation(TYPES) + ')?',
}


def fenced_blocks(text):
    block, inside = [], False
    for line in text.splitlines():
        if line.startswith('```'):
            if inside:
                yield block
            block, inside = [], not inside
        elif inside:
            block.append(line)


def compile_shapes():
    shapes = []
    for block in fenced_blocks(SPEC):
        for line in block:
            if line.startswith('|'):
                pattern = ''.join(SLOT[m[1:-1]] if m.startswith('<') else re.escape(m)
                                  for m in re.split(r'(<[a-z]+>)', line))
                shapes.append((line, re.compile('^' + pattern + '$')))
    return shapes


def test_every_gold_line_fits_exactly_one_shape():
    shapes = compile_shapes()
    assert len(shapes) > 70
    unmatched, ambiguous, total = [], [], 0
    for c in (json.loads(l) for l in open(TEST_SET) if l.strip()):
        for line in c['gold_log']:
            total += 1
            hits = [s for s, rx in shapes if rx.match(line)]
            if not hits:
                unmatched.append(line)
            elif len(hits) > 1:
                ambiguous.append((line, hits))
    assert total > 150000
    assert not unmatched, unmatched[:5]
    assert not ambiguous, ambiguous[:3]
