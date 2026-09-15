#!/usr/bin/env python3
import argparse
import json
import os
import random
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass

GROWTH = 1.05
KEYS = ('id', 'seed', 'teams', 'choices')
TEST_SET_ENV = 'POKEVAL_TEST_SET'
SANDBOX_IMAGE = 'sandbox-task'

ISOLATE = r'''
import json, subprocess, sys
engine = sys.argv[1:]
cases = [l for l in sys.stdin if l.strip()]
ids = [json.loads(l)['id'] for l in cases]
def run(batch):
    p = subprocess.run(engine, input=''.join(batch), capture_output=True, text=True)
    got = {}
    for line in p.stdout.splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if isinstance(o, dict) and 'id' in o and isinstance(o.get('log'), list):
            got[o['id']] = line
    return got, p.returncode, p.stderr
answers, err, remaining = {}, '', list(range(len(cases)))
while remaining:
    got, rc, err = run([cases[i] for i in remaining])
    answers.update(got)
    pending = [i for i in remaining if ids[i] not in answers]
    if rc == 0 or not pending:
        break
    answers.update(run([cases[pending[0]]])[0])
    remaining = pending[1:]
sys.stdout.write(''.join(l + '\n' for l in answers.values()))
sys.stderr.write(err[-1500:])
'''


def load(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def require_test_set():
    path = os.environ.get(TEST_SET_ENV)
    if not path:
        sys.exit(f'{TEST_SET_ENV} is not set. The test set is private; point {TEST_SET_ENV} at ps_test.jsonl.')
    if not os.path.isfile(path):
        sys.exit(f'{TEST_SET_ENV}={path} does not exist.')
    return path


def sandboxed_engine(task_dir):
    return ['docker', 'run', '--rm', '-i', '--network', 'none', '-v', f'{os.path.abspath(task_dir)}:/task:ro',
            '-w', '/task', SANDBOX_IMAGE, 'python3', '/task/engine.py']


def run_engine(cmd, cases, timeout=1800):
    payload = ''.join(json.dumps({k: c[k] for k in KEYS}) + '\n' for c in cases)
    wrapped = cmd[:-2] + [cmd[-2], '-c', ISOLATE] + cmd[-2:]
    try:
        p = subprocess.run(wrapped, input=payload, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {}, 'TIMEOUT'
    if p.returncode != 0:
        raise RuntimeError(f'engine did not start (rc {p.returncode}): {p.stderr[-500:]}')
    answers = {}
    for line in p.stdout.splitlines():
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict) and 'id' in o and isinstance(o.get('log'), list):
            answers[o['id']] = o['log']
    return answers, p.stderr[-1500:]


def turn_starts(log):
    return [i for i, l in enumerate(log) if l.startswith('|turn|')]


def turns_before(log, index):
    starts = turn_starts(log)
    ends = starts[1:] + [len(log)]
    return sum(1 for end in ends if end <= index)


def first_divergence(gold, got):
    i = 0
    while i < len(gold) and i < len(got) and gold[i] == got[i]:
        i += 1
    return i


def matched_turns(gold, got):
    i = first_divergence(gold, got)
    if i == len(gold) == len(got):
        return len(turn_starts(gold)), i, True
    return turns_before(gold, i), i, False


def points(t):
    return sum(GROWTH ** k for k in range(1, t + 1))


def turn_of(log, idx):
    return sum(1 for l in log[:idx + 1] if l.startswith('|turn|'))


def bootstrap_ratio_ci(matched, totals, reps=1000, seed=0):
    rnd = random.Random(seed)
    n = len(matched)
    shares = []
    for _ in range(reps):
        idx = [rnd.randrange(n) for _ in range(n)]
        shares.append(sum(matched[i] for i in idx) / sum(totals[i] for i in idx))
    shares.sort()
    return shares[int(0.025 * reps)], shares[int(0.975 * reps)]


def bootstrap_ci(values, reps=1000, seed=0):
    rnd = random.Random(seed)
    n = len(values)
    means = sorted(sum(rnd.choice(values) for _ in range(n)) / n for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps)]


@dataclass
class Score:
    n: int
    turn_share: float
    ts_ci_low: float
    ts_ci_high: float
    weighted: float
    ci_low: float
    ci_high: float
    raw_share: float
    exact: int
    median_frac: float
    median_turn: float
    max_turn: int
    missing: int
    causes: dict


def score(cases, answers):
    per_battle, fracs, turns, causes = [], [], [], Counter()
    matched_list, total_list = [], []
    exact = missing = 0
    earned = available = 0.0
    for c in cases:
        gold, got = c['gold_log'], answers.get(c['id'])
        total = len(turn_starts(gold))
        available += points(total)
        total_list.append(total)
        if got is None:
            matched_list.append(0)
            missing += 1
            per_battle.append(0.0)
            fracs.append(0.0)
            turns.append(0)
            causes['NO OUTPUT'] += 1
            continue
        matched, i, is_exact = matched_turns(gold, got)
        matched_list.append(matched)
        earned += points(matched)
        per_battle.append(points(matched) / points(total) if total else 0.0)
        fracs.append(i / max(len(gold), 1))
        turns.append(turn_of(gold, min(i, len(gold) - 1)))
        if is_exact:
            exact += 1
        else:
            causes[gold[i].split('|')[1] if i < len(gold) else 'EARLY-END'] += 1
    n = len(cases)
    lo, hi = bootstrap_ci(per_battle)
    tlo, thi = bootstrap_ratio_ci(matched_list, total_list)
    return Score(
        n=n,
        turn_share=100 * sum(matched_list) / sum(total_list),
        ts_ci_low=100 * tlo,
        ts_ci_high=100 * thi,
        weighted=100 * sum(per_battle) / n,
        ci_low=100 * lo,
        ci_high=100 * hi,
        raw_share=100 * earned / available if available else 0.0,
        exact=exact,
        median_frac=100 * sorted(fracs)[n // 2],
        median_turn=sorted(turns)[n // 2],
        max_turn=max(turns),
        missing=missing,
        causes=dict(causes.most_common()),
    )


def report(name, s):
    lines = [
        f'=== {name} ===',
        f'  share of test turns matched      : {s.turn_share:.1f}   95% CI [{s.ts_ci_low:.1f}, {s.ts_ci_high:.1f}]',
        f'  old weighted score (1.05^t)      : {s.weighted:.1f}   95% CI [{s.ci_low:.1f}, {s.ci_high:.1f}]'
        f'   (raw-points share {s.raw_share:.1f})',
        f'  exact whole-battle matches       : {s.exact}/{s.n}  ({100 * s.exact / s.n:.1f}%)',
        f'  median % of log matched          : {s.median_frac:.1f}%',
        f'  median turn of divergence        : {s.median_turn}   (best {s.max_turn})',
    ]
    if s.missing:
        lines.append(f'  cases with no output             : {s.missing}')
    top = ', '.join(f'{k} {v}' for k, v in list(s.causes.items())[:6])
    lines.append(f'  first divergence caused by       : {top}')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description='Score engines on a test set.')
    ap.add_argument('test_set', help='path to the test set (ps_test.jsonl)')
    ap.add_argument('candidates', nargs='+', help='name=command to run')
    ap.add_argument('--json', help='write scores here')
    ap.add_argument('--timeout', type=int, default=1800)
    args = ap.parse_args()
    cases = load(args.test_set)
    print(f'corpus: {len(cases)} battles\n')
    results = {}
    for spec in args.candidates:
        name, cmd = spec.split('=', 1)
        answers, err = run_engine(cmd.split(), cases, args.timeout)
        s = score(cases, answers)
        results[name] = asdict(s)
        print(report(name, s))
        if err == 'TIMEOUT':
            print('  (engine timed out)')
        print()
    if args.json:
        json.dump(results, open(args.json, 'w'), indent=1)


if __name__ == '__main__':
    main()
