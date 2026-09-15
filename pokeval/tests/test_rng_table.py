import json

import rng_table


def test_replay_was_faithful():
    d = json.load(open('rng_sites.json'))
    assert d['faithful'] == d['battles'] >= 1000


def test_every_site_has_a_pinned_row():
    text, n = rng_table.render()
    assert n == len(rng_table.SITES) == 21
    assert text.count('| ') > 21
