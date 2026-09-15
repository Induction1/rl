import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from models import MODELS, slug


def main(runs, out):
    out.mkdir(parents=True, exist_ok=True)
    for run, label in MODELS:
        rows = sorted((json.loads(line) for line in open(runs / run / 'checkpoints_turnshare.jsonl')), key=lambda r: r['seconds'])
        with open(out / f'{slug(label)}_checkpoints.jsonl', 'w') as f:
            for r in rows:
                f.write(json.dumps({'seconds': r['seconds'], 'turn_share': r['turn_share'], 'ci': r['ci']}) + '\n')
        final = json.load(open(runs / run / 'final_turnshare.json'))
        with open(out / f'{slug(label)}_final.json', 'w') as f:
            f.write(json.dumps({'turn_share': final['turn_share'], 'ci': final['ci']}))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: python3 analysis/export_results.py <runs dir> <out dir>')
    main(Path(sys.argv[1]), Path(sys.argv[2]))
