import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'harness'))
import grade
from models import MODELS


def per_battle(task_dir, cases):
    if not (task_dir / 'engine.py').exists():
        return None
    answers = grade.run_engine(grade.sandboxed_engine(task_dir), cases, timeout=1800)[0]
    rows = []
    for c in cases:
        got = answers.get(c['id'])
        matched = 0 if got is None else grade.matched_turns(c['gold_log'], got)[0]
        rows.append([matched, len(grade.turn_starts(c['gold_log']))])
    return rows


def summarize(rows):
    if rows is None:
        return {'turn_share': 0.0, 'ci': [0.0, 0.0]}
    matched = [m for m, _ in rows]
    totals = [t for _, t in rows]
    lo, hi = grade.bootstrap_ratio_ci(matched, totals)
    return {'turn_share': round(100 * sum(matched) / sum(totals), 2), 'ci': [round(100 * lo, 2), round(100 * hi, 2)]}


def main():
    ap = argparse.ArgumentParser(description='Regrade every checkpoint of the posted runs under the share of test '
                                             'turns matched.')
    ap.add_argument('finals', help='JSON list of {run, engine, rows} for the engine at 120 minutes of work')
    ap.add_argument('runs_dir', type=Path)
    args = ap.parse_args()
    cases = grade.load(grade.require_test_set())
    finals = {r['run']: r for r in json.load(open(args.finals))}

    def regrade(job):
        run, ck = job
        rows = per_battle(ck / 'task', cases)
        rec = {'run': run, 'seconds': int(ck.name), **summarize(rows), 'rows': rows}
        with open(args.runs_dir / run / 'checkpoints_turnshare.jsonl', 'a') as f:
            f.write(json.dumps(rec) + '\n')
        print(f"{run} {ck.name}: {rec['turn_share']} {rec['ci']}", flush=True)

    jobs = []
    for run, _ in MODELS:
        out = args.runs_dir / run / 'checkpoints_turnshare.jsonl'
        done = {json.loads(l)['seconds'] for l in open(out)} if out.exists() else set()
        checkpoints = sorted((args.runs_dir / run / 'checkpoints').glob('*'))
        jobs += [(run, ck) for ck in checkpoints if int(ck.name) not in done]
        final = finals[run]
        with open(args.runs_dir / run / 'final_turnshare.json', 'w') as f:
            json.dump({'run': run, 'engine': final['engine'], **summarize(final['rows']), 'rows': final['rows']}, f)
    print(f'{len(jobs)} checkpoints to grade', flush=True)
    with ThreadPoolExecutor(int(os.environ.get('WORKERS', '4'))) as ex:
        list(ex.map(regrade, jobs))
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
