import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'harness'))
import grade


def kind(line):
    return 'end of log' if line is None else line.split('|')[1]


def median(xs):
    return sorted(xs)[len(xs) // 2] if xs else None


def profile(result, gold):
    failed, lost, when, split = Counter(), Counter(), defaultdict(list), Counter()
    for b in result['battles']:
        category = b['category']
        if category == 'exact':
            continue
        log = gold[b['battle']]
        total = len(grade.turn_starts(log))
        matched = 0 if category == 'crash' else grade.turns_before(log, b['index'])
        failed[category] += 1
        lost[category] += total - matched
        if category != 'crash':
            when[category].append(b['turn'])
        if category == 'missing or extra event':
            g, e = kind(b['gold']), kind(b['engine'])
            if e == 'turn':
                split[f'engine skipped a {g} line'] += 1
            elif g == 'turn':
                split[f'engine added a {e} line'] += 1
            else:
                split[f'{g} expected, {e} printed'] += 1
    nf, nl = sum(failed.values()), sum(lost.values())
    return {'run': result['run'], 'label': result['label'], 'failed_battles': nf,
            'profile_pct': {k: round(100 * v / nf, 1) for k, v in failed.most_common()},
            'lost_turns_pct': {k: round(100 * v / nl, 1) for k, v in lost.most_common()},
            'median_turn_of_first_mistake': {k: median(v) for k, v in when.items()},
            'missing_or_extra_split': dict(split.most_common(8))}


def main():
    ap = argparse.ArgumentParser(description="Each model's mix of first mistakes among its failed battles.")
    ap.add_argument('divergence_causes', help='output of analysis/divergence_causes.py')
    ap.add_argument('--out', default=str(ROOT / 'results' / 'break_profiles.json'))
    args = ap.parse_args()
    gold = {c['id']: c['gold_log'] for c in grade.load(grade.require_test_set())}
    out = [profile(r, gold) for r in json.load(open(args.divergence_causes))
           if not (r['run'].startswith('opus_run') and r['run'] != 'opus_run3')]
    json.dump(out, open(args.out, 'w'), indent=1)
    for res in out:
        print(f"=== {res['label']} ({res['failed_battles']} failed battles)")
        print('  profile %:     ', res['profile_pct'])
        print('  lost turns %:  ', res['lost_turns_pct'])
        print('  median turn:   ', res['median_turn_of_first_mistake'])
        print('  missing/extra: ', res['missing_or_extra_split'])


if __name__ == '__main__':
    main()
