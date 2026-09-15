import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'harness'))
import grade

RANDOM = {'-crit', '-miss', '-hitcount'}
EFFECT = {'-supereffective', '-resisted', '-immune'}
RANDOM_CANT = ('par', 'slp', 'frz', 'flinch')


def engines(root):
    def checkpoint(run, index):
        return sorted((root / 'runs' / run / 'checkpoints').glob('*'))[index] / 'task'

    def candidate(run):
        return root / 'candidates' / f'{run}.py'

    return [('opus_run3', 'Opus 5', checkpoint('opus_run3', 23)),
            ('opus48_run1', 'Opus 4.8', candidate('opus48_run1')),
            ('opus47_run1', 'Opus 4.7', candidate('opus47_run1')),
            ('sonnet_run1', 'Sonnet 5', checkpoint('sonnet_run1', 22)),
            ('opus46_run1', 'Opus 4.6', root / 'runs' / 'opus46_run1' / 'work'),
            ('sonnet46_run1', 'Sonnet 4.6', candidate('sonnet46_run1')),
            ('opus_run2', 'Opus 5 (host, run 2)', candidate('opus_run2')),
            ('opus_run1', 'Opus 5 (host, run 1)', candidate('opus_run1'))]


def task_dir(source):
    if source.suffix != '.py':
        return source
    d = Path(tempfile.mkdtemp())
    shutil.copy(source, d / 'engine.py')
    shutil.copytree(ROOT / 'docs', d / 'docs')
    return d


def is_random_cant(fields):
    return fields[1] == 'cant' and len(fields) > 3 and fields[3] in RANDOM_CANT


def classify(gold, got):
    if got is None:
        return 'crash'
    i = grade.first_divergence(gold, got)
    if i == len(gold) == len(got):
        return 'exact'
    if i >= len(got) or i >= len(gold):
        return 'log length'
    g, e = gold[i].split('|'), got[i].split('|')
    gt, et = g[1], e[1]
    if gt in RANDOM or et in RANDOM or is_random_cant(g) or is_random_cant(e):
        return 'random outcome'
    if gt == et and len(g) > 2 and len(e) > 2 and g[2] != e[2]:
        return 'order of events'
    if gt == et == 'move':
        return 'wrong move' if g[3] != e[3] else 'wording or tags'
    if gt == et and gt in ('-damage', '-heal'):
        return 'damage or HP value' if g[3].split()[0] != e[3].split()[0] else 'wording or tags'
    if gt in EFFECT or et in EFFECT:
        return 'type effectiveness line'
    if gt == et:
        return 'wording or tags' if g[:4] == e[:4] else 'other detail'
    return 'missing or extra event'


def analyze(cases, run, label, source):
    answers = grade.run_engine(grade.sandboxed_engine(task_dir(source)), cases, timeout=1800)[0]
    s = grade.score(cases, answers)
    counts, examples, per_battle = Counter(), {}, []
    for c in cases:
        gold, got = c['gold_log'], answers.get(c['id'])
        category = classify(gold, got)
        counts[category] += 1
        rec = {'battle': c['id'], 'category': category}
        if category not in ('exact', 'crash'):
            i = grade.first_divergence(gold, got)
            rec.update({'turn': grade.turn_of(gold, min(i, len(gold) - 1)), 'index': i,
                        'gold': gold[i] if i < len(gold) else None, 'engine': got[i] if i < len(got) else None,
                        'context': gold[max(0, i - 2):i]})
            if category not in examples and category != 'log length':
                examples[category] = rec
        per_battle.append(rec)
    res = {'run': run, 'label': label, 'turn_share': round(s.turn_share, 2),
           'ci': [round(s.ts_ci_low, 2), round(s.ts_ci_high, 2)], 'exact': s.exact,
           'counts': dict(counts.most_common()), 'examples': examples, 'battles': per_battle}
    print(json.dumps({k: res[k] for k in ('run', 'turn_share', 'exact', 'counts')}), flush=True)
    return res


def main():
    ap = argparse.ArgumentParser(description="Classify where each battle first goes wrong for each model's engine "
                                             'at 120 minutes of work.')
    ap.add_argument('root', type=Path, help='folder holding runs/ and candidates/')
    ap.add_argument('out', help='output JSON; it quotes test set lines, so keep it private')
    args = ap.parse_args()
    cases = grade.load(grade.require_test_set())
    with ThreadPoolExecutor(4) as ex:
        out = list(ex.map(lambda spec: analyze(cases, *spec), engines(args.root.resolve())))
    json.dump(out, open(args.out, 'w'), indent=1)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
