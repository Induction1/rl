MODELS = [
    ('opus_run3', 'Opus 5'),
    ('opus48_run1', 'Opus 4.8'),
    ('opus47_run1', 'Opus 4.7'),
    ('sonnet_run1', 'Sonnet 5'),
    ('opus46_run1', 'Opus 4.6'),
    ('sonnet46_run1', 'Sonnet 4.6'),
]

WORK_WINDOWS = {
    'Opus 5': [(0, 1385), (1748, 7201), (7230, 8700)],
    'Opus 4.6': [(0, 860), (4852, 8046), (19777, 22904)],
    'Sonnet 4.6': [(0, 4558), (4678, 7200)],
}


def slug(label):
    return label.lower().replace(' ', '_').replace('.', '_')


def work_seconds(label, wall):
    return sum(max(0, min(wall, b) - a) for a, b in WORK_WINDOWS.get(label, [(0, 10 ** 9)]))
