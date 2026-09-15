import json
import os
import subprocess
import time

import pytest

PORT = 8790
ENV = {**os.environ, 'ORACLE_URL': f'http://127.0.0.1:{PORT}'}
TEST_SET = os.environ.get('POKEVAL_TEST_SET')
TEAMS = '"teams":{"p1":"Tauros||||bodyslam,hyperbeam|||||||","p2":"Snorlax||||bodyslam,rest|||||||"}'
BAD = {
    'malformed json': '{"seed": 1,2,3',
    'missing teams': '{"seed":"1,2,3,4","choices":[]}',
    'extra field': '{"seed":"1,2,3,4",' + TEAMS + ',"choices":[],"foo":1}',
    'unknown species': '{"seed":"1,2,3,4","teams":{"p1":"Chikorita||||tackle|||||||",'
                       '"p2":"Snorlax||||bodyslam|||||||"},"choices":[]}',
    'unknown move': '{"seed":"1,2,3,4","teams":{"p1":"Tauros||||crunch|||||||",'
                    '"p2":"Snorlax||||bodyslam|||||||"},"choices":[]}',
    'item filled': '{"seed":"1,2,3,4","teams":{"p1":"Tauros||leftovers||bodyslam|||||||",'
                   '"p2":"Snorlax||||bodyslam|||||||"},"choices":[]}',
    'bad seed': '{"seed":"banana",' + TEAMS + ',"choices":[]}',
    'bad choice string': '{"seed":"1,2,3,4",' + TEAMS + ',"choices":[{"p1":"move 9","p2":"move 1"}]}',
    'oversized': '{"seed":"1,2,3,4",' + TEAMS + ',"choices":['
                 + ','.join(['{"p1":"move 1","p2":"move 1"}'] * 1500) + ']}',
}


@pytest.fixture(scope='module')
def server():
    p = subprocess.Popen(['node', 'harness/oracle_server.js', '--port', str(PORT), '--bucket', '300',
                          '--refill', '60', '--max-turns', '100', '--log', '/dev/null'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    yield p
    p.terminate()


def ask(line):
    p = subprocess.run(['python3', 'task/oracle'], input=line + '\n', capture_output=True, text=True, env=ENV)
    return json.loads(p.stdout.splitlines()[0]), p.returncode


def long_battle(n):
    growl = '"teams":{"p1":"Snorlax||||growl,leer,withdraw,splash|||||||","p2":"Snorlax||||growl,leer,withdraw,splash|||||||"}'
    choices = ','.join('{"p1":"move %d","p2":"move %d"}' % (i % 4 + 1, i % 4 + 1) for i in range(n))
    return '{"seed":"1,2,3,4",' + growl + ',"choices":[' + choices + ']}'


def test_every_bad_request_costs_one(server):
    for name, line in BAD.items():
        r, rc = ask(line)
        assert 'error' in r and r['charged'] == 1 and rc == 0, name


@pytest.mark.skipif(not TEST_SET, reason='POKEVAL_TEST_SET is not set')
def test_corpus_case_reproduces_gold(server):
    c = json.loads(open(TEST_SET).readline())
    r, _ = ask(json.dumps({k: c[k] for k in ('id', 'seed', 'teams', 'choices')}))
    assert r['id'] == c['id'] and r['log'] == c['gold_log'] and r['charged'] == min(c['turns'], 100)


def test_per_query_cap(server):
    r, _ = ask(long_battle(150))
    assert r['charged'] == 100 and 'truncated' in r


def test_bucket_empties_then_refills(server):
    for _ in range(6):
        r, rc = ask(long_battle(150))
        if rc == 2:
            assert r['error'].startswith('ORACLE RATE LIMIT')
            break
    else:
        assert False, 'bucket never emptied'
    time.sleep(2)
    r, rc = ask('{"seed":"1,2,3,4",' + TEAMS + ',"choices":[{"p1":"move 1","p2":"move 1"}]}')
    assert rc == 0 and 'log' in r, 'refill did not make turns available again'


def test_help_and_budget(server):
    out = subprocess.run(['python3', 'task/oracle', 'help'], capture_output=True, text=True, env=ENV).stdout
    assert 'USAGE' in out and 'Right now:' in out
    status = json.loads(subprocess.run(['python3', 'task/oracle', '--budget'],
                                       capture_output=True, text=True, env=ENV).stdout)
    assert status['unit'] == 'turns' and status['max_turns_per_query'] == 100 and status['refill_per_minute'] == 60
