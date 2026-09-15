#!/usr/bin/env python3
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import grade

SPECIES = {v['name'] for v in json.load(open('docs/species.json')).values()}
MOVES = {v['name'] for v in json.load(open('docs/moves.json')).values()}
TYPES = list(json.load(open('docs/typechart.json')))
STATUS = 'par|slp|frz|brn|psn|tox'
STAT = 'atk|def|spa|spd|spe|accuracy|evasion'


def alternation(names):
    return '|'.join(sorted(map(re.escape, names), key=len, reverse=True))


SP, MV, TY = alternation(SPECIES), alternation(MOVES), alternation(TYPES)

RULES = [
    ('mon', r'(p[12]a: [^|]+)'),
    ('player', r'\|(P[12])(?=\||$)'),
    ('hp', r'(?<=[| ])(\d+/\d+)(?= |\||$)'),
    ('species', rf'(?<=\|)({SP})(?=\||$)'),
    ('species', rf'(?<=The foe )({SP})(?= can)'),
    ('move', rf'(?<=\|Mimic\|)({MV})(?=\||$)'),
    ('move', rf'(?<=\|Disable\|)({MV})(?=\||$)'),
    ('move', rf'(?<=\|)({MV})(?=\||$)(?!\|<move>)'),
    ('move', rf'(?<=\[from\] move: )({MV})(?=\||$)'),
    ('move', rf'(?<=\|move: )({MV})(?=\||$)'),
    ('move', rf'(?<=\[from\] )({MV})(?=\||$)'),
    ('status', rf'(?<= )({STATUS})(?=\||$)'),
    ('status', rf'(?<=\|)({STATUS})(?=\||$)'),
    ('status', r'(?<=\[from\] )(psn|brn)(?=\||$)'),
    ('stat', rf'(?<=\|)({STAT})(?=\||$)'),
    ('type', rf'(?<=\|typechange\|)((?:{TY})(?:/(?:{TY}))?)(?=\||$)'),
    ('n', r'(?<=\|)(\d+)(?=\||$)'),
]
LITERALS = {
    '0 fnt', '[from] Recoil', '[from] confusion', '[from] Leech Seed', '[of]', '[silent]', '[msg]', '[weak]',
    '[damage]', '[ohko]', '[miss]', '[still]', '[from] Substitute', 'recharge', 'flinch', 'confusion', 'Substitute',
    'Bide', 'Mimic', 'Disable', 'Rage', 'Leech Seed', 'Focus Energy', 'Light Screen', 'Reflect', 'Mist', 'Pay Day',
    "can't be hit while invulnerable!", 'The foe', 'move:', 'partiallytrapped', 'Clamp', 'Wrap', 'Bind', 'Fire Spin',
    'move: Haze', 'Haze', 'Transform', '[from]', '[from] move:', '[from] drain', 'typechange',
    "The foe  can't be hit while invulnerable!",
}
HIDDEN = {'mon', 'hp', 'n', 'player', 'species'}
SLOT_RE = re.compile(r'<[a-z]+>')


def mask(line):
    values = defaultdict(list)
    for slot, pattern in RULES:
        def sub(m, slot=slot):
            values[slot].append(m.group(1))
            return m.group(0).replace(m.group(1), f'<{slot}>')
        line = re.sub(pattern, sub, line)
    return line, values


def unclassified(shape):
    for field in shape.split('|')[2:]:
        rest = SLOT_RE.sub('', field).strip()
        if rest and rest not in LITERALS and not all(p in LITERALS for p in re.split(r'\s+(?=\[)', rest)):
            yield rest


def build(cases):
    shapes = {}
    bad = Counter()
    for c in cases:
        for line in c['gold_log']:
            tag = line.split('|')[1]
            shape, values = mask(line)
            entry = shapes.setdefault(tag, {}).setdefault(shape, {'n': 0, 'slots': defaultdict(Counter)})
            entry['n'] += 1
            for slot, vs in values.items():
                for i, v in enumerate(vs):
                    entry['slots'][(slot, i)][v] += 1
            for token in unclassified(shape):
                bad[(tag, token)] += 1
    return shapes, bad


def render(shapes):
    out = ['Every graded line has one of the shapes below. Slots: `<mon>` is `p1a: Name` or `p2a: Name`, the active',
           'Pokémon of player 1 or 2; `<species>` is a species name from `docs/species.json`; `<move>` is a move name',
           'from `docs/moves.json`; `<hp>` is `current/max`; `<status>` is one of `par slp frz brn psn tox`; `<stat>` is a',
           'stat id; `<n>` is an integer; `<player>` is `P1` or `P2`; `<type>` is a type, or two joined by `/`. Where a',
           'slot takes only a few values in that shape, they are listed under it. Everything not in angle brackets is',
           'literal text.', '']
    by_frequency = sorted(shapes.items(), key=lambda kv: -sum(d['n'] for d in kv[1].values()))
    for tag, tshapes in by_frequency:
        out += [f'**`|{tag}|`**', '', '```']
        for shape, d in sorted(tshapes.items(), key=lambda kv: -kv[1]['n']):
            out.append(shape)
            repeats = Counter(slot for slot, _ in d['slots'])
            for (slot, i), counts in d['slots'].items():
                if slot in HIDDEN or (slot == 'move' and len(counts) > 12):
                    continue
                label = f'<{slot}>' if repeats[slot] == 1 else f'<{slot}> #{i + 1}'
                out.append(f'    {label}: ' + '  '.join(v for v, _ in counts.most_common()))
        out += ['```', '']
    out.append('Any line type or shape not listed here does not occur in a graded log.')
    return '\n'.join(out) + '\n'


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else grade.require_test_set()
    shapes, bad = build(grade.load(src))
    if bad:
        print('UNCLASSIFIED tokens (add to LITERALS only after deciding they are truly fixed text):')
        for (tag, token), n in bad.most_common():
            print(f'  {tag:14s} {n:6d}  {token!r}')
        sys.exit(1)
    lines = render(shapes)
    Path('task/_lines.md').write_text(lines)
    head, tail = (Path(f'task/{f}').read_text() for f in ('_spec_head.md', '_spec_tail.md'))
    Path('task/SPEC.md').write_text(head.replace('@@LINES@@', lines) + tail)
    print(f'{len(shapes)} line types, {sum(map(len, shapes.values()))} shapes -> task/SPEC.md')


if __name__ == '__main__':
    main()
