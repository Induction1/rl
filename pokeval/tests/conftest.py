import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if os.environ.get('POKEVAL_TEST_SET'):
    os.environ['POKEVAL_TEST_SET'] = str(Path(os.environ['POKEVAL_TEST_SET']).resolve())
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / 'harness'))
