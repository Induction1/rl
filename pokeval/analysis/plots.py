import argparse
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

from models import MODELS, WORK_WINDOWS, slug, work_seconds

RESULTS = Path(__file__).resolve().parents[1] / 'results'
MUSTARD = '#e0a63a'
MAUVE = '#a95c7a'
INDIGO = '#5b4fcf'
TERRA = '#c96a4a'
TEAL = '#3f8f8a'
COLORS = {
    'Opus 5': (TERRA, TERRA),
    'Opus 4.8': (MUSTARD, MUSTARD),
    'Opus 4.7': (MAUVE, '#c97a9a'),
    'Sonnet 5': (INDIGO, '#8f85e8'),
    'Opus 4.6': (TEAL, TEAL),
    'Sonnet 4.6': ('#9a9a9a', '#8a8a8a'),
}
PAUSED = {'Opus 4.6'}


@dataclass
class Theme:
    dark: bool
    ink: str
    sub: str
    grid: str
    spine: str
    mauve: str


def theme(dark):
    if dark:
        t = Theme(dark, ink='#e6e6e6', sub='#a8a8a8', grid='#3a3a3a', spine='#555', mauve='#c97a9a')
    else:
        t = Theme(dark, ink='#2b2b2b', sub='#6f6f6f', grid='#ececec', spine='#d9d9d9', mauve=MAUVE)
    plt.rcParams.update({'font.family': ['Helvetica Neue', 'Helvetica', 'Arial', 'DejaVu Sans'], 'font.size': 11,
                         'text.color': t.ink, 'axes.labelcolor': t.sub, 'xtick.color': t.sub, 'ytick.color': t.sub})
    return t


def card(fig, ax, t):
    fig.patch.set_alpha(0)
    ax.set_facecolor('none')
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(t.spine)
    ax.yaxis.grid(True, color=t.grid, lw=0.9)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def save(fig, out, name, t):
    fig.savefig(out / (name + ('_dark' if t.dark else '') + '.png'), transparent=True)
    plt.close(fig)


def checkpoints(label):
    rows = [json.loads(l) for l in open(RESULTS / f'{slug(label)}_checkpoints.jsonl')]
    return sorted(({'seconds': r['seconds'], 'score': r['turn_share'], 'ci': r['ci']} for r in rows),
                  key=lambda r: r['seconds'])


def at_120(label):
    d = json.load(open(RESULTS / f'{slug(label)}_final.json'))
    return d['turn_share'], d['ci']


def trajectory_by_work(label):
    pts, seen = [(0, 0.0, 0.0, 0.0)], set()
    for r in checkpoints(label):
        w = work_seconds(label, r['seconds'])
        inside = any(a <= r['seconds'] <= b + 300 for a, b in WORK_WINDOWS[label])
        if not inside or round(w) in seen or w > 7200:
            continue
        seen.add(round(w))
        pts.append((round(w / 60, 1), r['score'], *r['ci']))
    score, ci = at_120(label)
    return pts + [(120, score, *ci)]


def trajectory(label, n=23):
    if label in PAUSED:
        return trajectory_by_work(label)
    rows = checkpoints(label)[:n]
    score, ci = at_120(label)
    return [(0, 0.0, 0.0, 0.0)] + [(5 * (i + 1), r['score'], *r['ci']) for i, r in enumerate(rows)] + [(120, score, *ci)]


def spread(ys, gap):
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    for a, b in zip(order, order[1:]):
        if out[b] - out[a] < gap:
            out[b] = out[a] + gap
    return out


def fig_runs(out, dark):
    t = theme(dark)
    fig, ax = plt.subplots(figsize=(8.6, 4.6), dpi=170)
    card(fig, ax, t)
    ends = []
    for _, label in MODELS:
        color = COLORS[label][1 if dark else 0]
        pts = trajectory(label)
        x = [p[0] for p in pts]
        y = [p[1] for p in pts]
        ax.fill_between(x, [p[2] for p in pts], [p[3] for p in pts], color=color, alpha=0.32, linewidth=0)
        ax.plot(x, y, color=color, lw=2.4, marker='o', ms=3.6, mfc=color, mec='none')
        ends.append((y[-1], label, color))
    for (_, label, color), y in zip(ends, spread([e[0] for e in ends], 4.6)):
        ax.text(123, y, label, color=color, fontsize=10.5, ha='left', va='center')
    ax.set_xlim(0, 121)
    ax.set_ylim(0, 100)
    ax.set_xticks(range(0, 121, 15))
    ax.set_yticks(range(0, 101, 20))
    ax.set_xlabel('minutes of work')
    ax.set_ylabel('test set score')
    fig.subplots_adjust(left=0.08, right=0.84, top=0.96, bottom=0.13)
    save(fig, out, 'runs_trajectory', t)


def data_runs(out):
    series = []
    for run, label in MODELS:
        light, dark = COLORS[label]
        series.append({'id': run, 'label': label, 'light': light, 'dark': dark, 'faint': False,
                       'points': [[m, round(v, 1), round(lo, 1), round(hi, 1)] for m, v, lo, hi in trajectory(label)]})
    json.dump({'series': series}, open(out / 'runs_trajectory.json', 'w'))


def load_jsonl(path):
    return [json.loads(l) for l in open(path)]


def move_counts(cases):
    moves = {}
    for c in cases:
        for side in ('p1', 'p2'):
            for member in c['teams'][side].split(']'):
                for m in member.split('|')[4].split(','):
                    moves[m] = moves.get(m, 0) + 1
    return moves


def smooth_counts(values, grid, bandwidth):
    norm = 1 / (bandwidth * math.sqrt(2 * math.pi))
    return [sum(norm * math.exp(-0.5 * ((g - v) / bandwidth) ** 2) for v in values) for g in grid]


def fig_test_set(out, dark, original, final):
    t = theme(dark)
    fig, (left, right) = plt.subplots(1, 2, figsize=(8.6, 3.2), dpi=170)
    card(fig, left, t)
    card(fig, right, t)
    grid = [x / 2 for x in range(0, 301)]
    left.plot(grid, smooth_counts([c['turns'] for c in original], grid, 3.0), color=t.mauve, lw=2.2,
              label='original rules')
    left.plot(grid, smooth_counts([c['turns'] for c in final], grid, 2.0), color=TEAL, lw=2.2,
              label='final test set')
    left.set_xlim(0, 150)
    left.set_ylim(bottom=0)
    left.set_xticks(range(0, 151, 50))
    left.set_xlabel('battle length in turns')
    left.set_ylabel('battles per turn of length')
    before = sorted(move_counts(original).values(), reverse=True)
    after = sorted(move_counts(final).values(), reverse=True)
    right.plot(range(1, len(before) + 1), before, color=t.mauve, lw=2.2)
    right.plot(range(1, len(after) + 1), after, color=TEAL, lw=2.2)
    right.set_xlim(1, len(after))
    right.set_ylim(bottom=0)
    right.set_xticks([1, len(after)])
    right.set_xlabel('moves, most to least common')
    right.set_ylabel('team slots')
    left.legend(frameon=False, fontsize=10, labelcolor='linecolor', loc='upper right', handlelength=0,
                handletextpad=0)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.95, bottom=0.18, wspace=0.3)
    save(fig, out, 'test_set', t)


def fig_timeline(out, dark):
    t = theme(dark)
    rows = {r['label']: r for r in json.load(open(RESULTS / 'timelines.json'))}
    fig, ax = plt.subplots(figsize=(8.6, 3.6), dpi=170)
    card(fig, ax, t)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=t.grid, lw=0.9)
    marks = [('first_engine_write', 'first engine written', 'o', t.ink),
             ('first_bulk_oracle', 'first bulk oracle comparison', 'D', TEAL),
             ('first_above_10', 'score first above 10', 's', TERRA)]
    for i, (_, label) in enumerate(MODELS):
        r = rows[label]
        values = [r[key] for key, *_ in marks if r[key] is not None]
        if values:
            ax.plot([min(values), max(values)], [i, i], color=t.spine, lw=2, zorder=1)
        for key, name, marker, color in marks:
            if r[key] is not None:
                ax.scatter(r[key], i, marker=marker, s=46, color=color, zorder=3, label=name if i == 0 else None)
    ax.set_yticks(range(len(MODELS)))
    ax.set_yticklabels([label for _, label in MODELS])
    ax.invert_yaxis()
    ax.set_xlim(0, 120)
    ax.set_xticks(range(0, 121, 15))
    ax.set_xlabel('minutes of work')
    ax.legend(frameon=False, fontsize=9.5, ncol=3, loc='upper center', bbox_to_anchor=(0.45, -0.2), labelcolor=t.sub)
    fig.subplots_adjust(left=0.12, right=0.98, top=0.97, bottom=0.3)
    save(fig, out, 'timeline', t)


def main():
    ap = argparse.ArgumentParser(description='Draw the figures for the writeup from results/.')
    ap.add_argument('out_dir')
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    test_set = os.environ.get('POKEVAL_TEST_SET')
    original = load_jsonl(RESULTS / 'battles_original_rules.jsonl')
    final = load_jsonl(test_set) if test_set else None
    for dark in (False, True):
        fig_runs(out, dark)
        if final is not None:
            fig_test_set(out, dark, original, final)
        fig_timeline(out, dark)
    data_runs(out)
    if final is None:
        print('POKEVAL_TEST_SET is not set: skipped test_set.png, which needs the private test set')
    print(f'wrote figures to {out}')


if __name__ == '__main__':
    main()
