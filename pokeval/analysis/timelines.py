import argparse
import datetime
import json
import re
from pathlib import Path

import plots
from models import MODELS, work_seconds

BULK = 50
ENGINE_WRITE = re.compile(r"(>|tee)\s*\S*engine\.py|cat\s+<<.*engine\.py|engine\.py\s*<<")


def timestamp(s):
    return datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone().replace(tzinfo=None)


def first_engine_write(transcript, label, t0):
    first = None
    for line in open(transcript):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        content = (e.get('message') or {}).get('content') if isinstance(e.get('message'), dict) else None
        if not isinstance(content, list) or not e.get('timestamp'):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get('type') != 'tool_use':
                continue
            payload = json.dumps(block.get('input', {}))
            wrote = (block['name'] in ('Write', 'Edit', 'MultiEdit') and 'engine.py' in payload) or \
                    (block['name'] == 'Bash' and ENGINE_WRITE.search(payload))
            if wrote and first is None:
                first = work_seconds(label, (timestamp(e['timestamp']) - t0).total_seconds()) / 60
    return first


def main():
    ap = argparse.ArgumentParser(description='When each agent first wrote its engine, first compared against the '
                                             'oracle in bulk, and first scored above 10.')
    ap.add_argument('runs_dir', type=Path)
    ap.add_argument('--out', type=Path, default=plots.RESULTS / 'timelines.json')
    args = ap.parse_args()
    out = []
    for run, label in MODELS:
        d = args.runs_dir / run
        t0 = datetime.datetime.fromisoformat(json.load(open(d / 'manifest.json'))['started'])
        first_write = first_engine_write(d / 'transcript.jsonl', label, t0)
        queries = sorted(work_seconds(label, (timestamp(r['t']) - t0).total_seconds()) / 60
                         for r in map(json.loads, open(d / 'oracle_queries.jsonl')) if r.get('t'))
        bulk = next((queries[i] for i in range(len(queries))
                     if sum(1 for x in queries[i:i + BULK] if x - queries[i] <= 5) >= BULK), None)
        pts = plots.trajectory(label)
        out.append({'run': run, 'label': label,
                    'first_engine_write': first_write and round(first_write, 1),
                    'first_bulk_oracle': bulk and round(bulk, 1),
                    'queries_first_30': sum(1 for x in queries if x <= 30), 'queries_total': len(queries),
                    'first_above_10': next((p[0] for p in pts if p[1] > 10), None), 'score_120': pts[-1][1]})
    json.dump(out, open(args.out, 'w'), indent=1)
    for r in out:
        print(r)


if __name__ == '__main__':
    main()
