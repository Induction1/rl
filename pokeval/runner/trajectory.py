#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'harness'))
import grade

USAGE_KEYS = ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')


def tokens_up_to(transcript, nbytes):
    used = 0
    with open(transcript, 'rb') as f:
        for line in f:
            if f.tell() > nbytes:
                break
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            usage = ev.get('message', {}).get('usage') if ev.get('type') == 'assistant' else None
            if usage:
                used += sum(usage.get(k, 0) for k in USAGE_KEYS)
    return used


def grade_snapshot(task_dir, cases):
    if not (task_dir / 'engine.py').exists():
        return None
    answers, _ = grade.run_engine(grade.sandboxed_engine(task_dir), cases, timeout=1800)
    return grade.score(cases, answers)


def main():
    if len(sys.argv) != 2:
        sys.exit('usage: python3 runner/trajectory.py runs/<name>')
    run = Path(sys.argv[1]).resolve()
    cases = grade.load(grade.require_test_set())
    rows = []
    for ck in sorted((run / 'checkpoints').glob('*')):
        seconds = int(ck.name)
        nbytes = int((ck / 'transcript_bytes').read_text() or 0)
        s = grade_snapshot(ck / 'task', cases)
        row = {'seconds': seconds, 'hours': round(seconds / 3600, 3),
               'tokens': tokens_up_to(run / 'transcript.jsonl', nbytes)}
        if s is None:
            row.update(turn_share=None, weighted=None, ci=None, exact=None, missing=None)
        else:
            row.update(turn_share=round(s.turn_share, 2), weighted=round(s.weighted, 2),
                       ci=[round(s.ci_low, 2), round(s.ci_high, 2)], exact=s.exact, missing=s.missing)
        rows.append(row)
        print(f"  {row['hours']:6.2f} h  {row['tokens']:>10,} tok  weighted {row['weighted']}  exact {row['exact']}")
    json.dump(rows, open(run / 'trajectory.json', 'w'), indent=1)
    print(f'{len(rows)} checkpoints -> {run}/trajectory.json')


if __name__ == '__main__':
    main()
