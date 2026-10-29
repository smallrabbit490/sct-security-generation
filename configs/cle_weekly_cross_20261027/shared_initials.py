"""Collect exact shared V4.1 initial analyses for matched memory comparisons."""
from pathlib import Path

from methods.sct_trajectory.replay_journal import ReplayStop
from .prepare import read


def collect(sources, task_ids):
    expected = {f'{task}_r{repeat}' for task in map(str, task_ids) for repeat in (1, 2)}
    result = {}
    for source in map(Path, sources):
        for path in (source / 'shared_starts').glob('*.json'):
            if path.stem not in expected:
                raise ReplayStop('FFS_shared_initial_outside_cross_manifest:' + path.stem)
            row = read(path)
            task, repeat = path.stem.rsplit('_r', 1)
            if str(row.get('task_id')) != task or row.get('repeat', int(repeat)) != int(repeat):
                raise ReplayStop('FFS_shared_initial_identity_mismatch:' + path.stem)
            if 'initial_analysis' not in row or 'error_type' not in row:
                raise ReplayStop('FFS_shared_initial_missing_fields:' + path.stem)
            value = {'task_id': task, 'repeat': int(repeat),
                     'initial_analysis': row['initial_analysis'], 'error_type': row['error_type']}
            if path.stem in result and result[path.stem] != value:
                raise ReplayStop('FFS_shared_initial_conflict:' + path.stem)
            result[path.stem] = value
    missing = expected - set(result)
    if missing:
        raise ReplayStop('FFS_shared_initial_incomplete:' + str(len(missing)))
    return result
