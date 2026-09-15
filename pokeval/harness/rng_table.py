#!/usr/bin/env python3
import json
import sys
from pathlib import Path

SITES = {s['site']: s for s in json.load(open('rng_sites.json'))['sites']}

ROWS = [
    ('turn start', [
        ('battle.js:285 (Battle.eachEvent:296)', 'active speed tie', 'shuffle of the 2 active Pokémon',
         'whenever the engine visits both actives in speed order, which is at the start of every turn and after every action (the end-of-turn step counts as an action), and the two have equal speed. The list before the shuffle is [player 1\'s active, player 2\'s active]. No draw when speeds differ.',
         'this.prng.shuffle(list, sorted, sorted + nextIndexes.length);'),
        ('battle.js:285 (BattleQueue.sort:299)', 'action order tie', 'shuffle of the 2 queued actions',
         'when the two sides\' chosen actions tie on priority and speed when the turn\'s queue is sorted. The list before the shuffle is [player 1\'s action, player 2\'s action].',
         'this.prng.shuffle(list, sorted, sorted + nextIndexes.length);'),
        ('battle-queue.js:283', 'switch insertion tie', '`random(first, last + 1)`',
         'when a switch (including the lead switch-ins at battle start) is inserted into the queue and other actions tie with it; the index among the tied actions is drawn.',
         'const index = firstIndex === lastIndex ? firstIndex : this.battle.random(firstIndex, lastIndex + 1);'),
    ]),
    ('before a Pokémon moves', [
        ('../data/mods/gen1/conditions.js:51', 'full paralysis', '`randomChance(63, 256)`',
         'before every move attempt by a paralyzed Pokémon.',
         'if (this.randomChance(63, 256)) {'),
        ('../data/mods/gen1/conditions.js:162', 'confusion self-hit', '`randomChance(128, 256)`',
         'before every move attempt by a confused Pokémon, after its confusion counter is decremented and only if the confusion did not just end.',
         'if (!this.randomChance(128, 256)) {'),
    ]),
    ('when a move executes', [
        ('../data/mods/gen1/scripts.js:414', 'accuracy check', '`randomChance(accuracy, 256)`',
         'for every move with an accuracy value, except: no draw for a sleep-inducing move against a target that must recharge (it always hits); no draw when a one-hit-KO move is used on a faster target or when the target is immune to the move\'s type (`|-immune|` instead). `accuracy` = ⌊acc × 255 / 100⌋; then ⌊accuracy × T[s]/100⌋ for the user\'s accuracy stage s; then ⌊accuracy × T[−e]/100⌋ for the target\'s evasion stage e (note the sign); where T indexes stages −6..+6 into `[25, 28, 33, 40, 50, 66, 100, 150, 200, 250, 300, 350, 400]`; then clamped to 1..255; then +1 if the move targets the user. A Pokémon locked into Thrash/Petal Dance or Rage starts from the accuracy stored on its previous turn instead of ⌊acc × 255 / 100⌋, and the stage steps apply again on top of it.',
         'if (accuracy !== true && !this.battle.randomChance(accuracy, 256)) {'),
        ('../data/mods/gen1/scripts.js:426', 'multi-hit count', '`sample([2, 2, 2, 3, 3, 3, 4, 5])`',
         'after the accuracy check passes, for a move that hits 2–5 times.',
         'hits = this.battle.sample([2, 2, 2, 3, 3, 3, 4, 5]);'),
        ('../data/mods/gen1/scripts.js:694', 'critical hit', '`randomChance(critChance, 256)`',
         'for every move whose damage goes through the damage formula, that is every move with `basePower` > 0 and neither a `damage` nor a `damageCallback` field in `docs/moves.json`. `critChance` = ⌊baseSpeed / 2⌋, with baseSpeed the base Speed of the user\'s own species (Transform does not change it); then ⌊÷2⌋ if the user has Focus Energy, else ×2 clamped to 1..255; then ⌊÷2⌋ for a normal move (`critRatio` 1) or ×4 clamped to 1..255 for a high-crit move (`critRatio` 2).',
         'isCrit = this.battle.randomChance(critChance, 256);'),
        ('../data/mods/gen1/scripts.js:779', 'damage roll', '`random(217, 256)`',
         'for the same moves as the critical hit row, after type effectiveness is applied, only when the damage so far is greater than 1; the result multiplies the damage (⌊÷255⌋ afterwards).',
         'damage *= this.battle.random(217, 256);'),
        ('../data/mods/gen1/moves.js:574', 'Psywave damage', '`random(1, ⌊1.5 × level⌋)`',
         'when Psywave hits (`random(1, 150)` at level 100).',
         'const psywaveDamage = this.random(1, this.trunc(1.5 * pokemon.level));'),
        ('../data/mods/gen1/scripts.js:622', 'secondary effect', '`randomChance(⌈chance × 256 / 100⌉, 256)`',
         'for each secondary effect of a move that hit a target still standing (for multi-hit moves, on the last hit only); one less than the ceiling for confusion; skipped entirely when the secondary is paralysis, burn or freeze and the target shares the move\'s type.',
         'if (this.battle.randomChance(secondaryChance, 256)) {'),
        ('../data/mods/gen1/moves.js:467', 'Metronome', '`sample` of 163 moves',
         'when Metronome executes: every Generation 1 move except Metronome and Struggle, in numeric order.',
         'randomMove = this.sample(moves).id;'),
        ('../data/mods/gen1/moves.js:481', 'Mimic', '`sample` of the target\'s moves',
         'when Mimic hits.',
         'const moveid = this.sample(moves);'),
        ('../data/mods/gen1/moves.js:244', 'Disable: slot', '`sample` of the target\'s move slots with PP left',
         'when Disable hits.',
         'const [slotIndex, moveSlot] = this.sample(Array.from(pokemon.moveSlots.entries()).filter(([i, ms]) => ms.pp > 0));'),
        ('../data/mods/gen1/moves.js:249', 'Disable: duration', '`random(1, 9)`',
         'immediately after the slot draw.',
         'this.effectState.time = this.random(1, 9);'),
    ]),
    ('when an effect starts', [
        ('../data/mods/gen1/conditions.js:74', 'sleep duration', '`random(1, 8)`',
         'when sleep is inflicted.',
         'this.effectState.startTime = this.random(1, 8);'),
        ('../data/mods/gen1/conditions.js:149', 'confusion duration', '`random(2, 6)`',
         'when confusion starts.',
         'this.effectState.time = this.random(2, 6);'),
        ('../data/mods/gen1/conditions.js:304', 'Thrash / Petal Dance duration', '`random(2, 4)`',
         'when the lock starts.',
         'this.effectState.time = this.random(2, 4);'),
        ('../data/mods/gen1/moves.js:57', 'Bide duration', '`random(2, 4)`',
         'when Bide starts.',
         'this.effectState.time = this.random(2, 4);'),
        ('../data/mods/gen1/conditions.js:241', 'partial-trap duration', '`sample([2, 2, 2, 3, 3, 3, 4, 5])`',
         'when Bind, Clamp, Fire Spin or Wrap locks its user.',
         'return this.sample([2, 2, 2, 3, 3, 3, 4, 5]);'),
    ]),
    ('end of turn', [
        ('battle.js:285 (Battle.fieldEvent:333)', 'end-of-turn effect tie', 'shuffle of the tied effects (2–4)',
         'when end-of-turn effects (poison, burn, Leech Seed, and the like) tie on order. The list before the shuffle holds player 1\'s active\'s effects before player 2\'s.',
         'this.prng.shuffle(list, sorted, sorted + nextIndexes.length);'),
    ]),
]


def render():
    out = ['## Where the reference draws random numbers', '',
           'Every place the reference calls its random number generator, and when. `random`, `randomChance`, `sample`',
           'and shuffles are defined in `SPEC.md`. A sort shuffles each group of tied elements separately, one shuffle',
           'per group. Every draw advances the generator once.', '']
    covered = set()
    for group, rows in ROWS:
        out += [f'**{group}**', '']
        if group == 'when a move executes':
            out += ['None of the draws in this group fire on the continuation turns of Bind, Clamp, Fire Spin or Wrap.',
                    '']
        out += ['| draw | call | fires when |', '|---|---|---|']
        for site, name, call, when, code in rows:
            s = SITES.get(site)
            if s is None:
                sys.exit(f'FAIL: site {site} not in rng_sites.json (the reference moved?)')
            if s['code'] != code:
                sys.exit(f'FAIL: code at {site} changed:\n  wrote against: {code}\n  now: {s["code"]}\n'
                         'Re-read before shipping.')
            covered.add(site)
            out.append(f'| {name} | {call} | {when} |')
        out.append('')
    missing = set(SITES) - covered
    if missing:
        sys.exit(f'FAIL: draw sites in the replay with no row: {sorted(missing)}')
    return '\n'.join(out) + '\n', len(covered)


def main():
    text, n = render()
    Path('task/_rng.md').write_text(text)
    head, tail = (Path(f'task/{f}').read_text() for f in ('_docs_readme_head.md', '_docs_readme_tail.md'))
    Path('docs/README.md').write_text(head + text + tail)
    print(f'{n} draw sites documented -> docs/README.md')


if __name__ == '__main__':
    main()
