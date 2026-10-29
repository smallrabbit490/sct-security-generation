"""List saved FFS cells that might match V4.1 cross arms; do not credit them."""
import json
from collections import Counter
from pathlib import Path

from .prepare import RUN, read
from methods.sct_trajectory.replay_journal import ReplayStop, write_json


def collect():
    schedule = read(RUN / 'FX_GATE/inputs/schedule.json')
    targets = {x['cell_id']: x for x in schedule if x['model_arm'] == 'V41'}
    tasks = read(RUN / 'FQ_GATE/inputs_v3/tasks.json')
    found, unreadable = {}, []
    for segment in sorted((RUN / 'FFS').glob('segment_*')):
        for path in (segment / 'task_rows').glob('*.json'):
            try:
                row = read(path)
            except (OSError, ValueError):
                unreadable.append(str(path))
                continue
            condition = row.get('condition')
            if condition not in ('B0', 'BM'):
                continue
            bank = 'E0' if condition == 'B0' else 'C32'
            task, repeat = str(row.get('task_id')), row.get('repeat')
            cell = f'{task}_r{repeat}_V41_{bank}'
            if cell not in targets or task not in tasks:
                raise ReplayStop('FFS_reuse_candidate_outside_fixed_manifest:' + cell)
            if str(row.get('family_id')) != str(tasks[task]['family_id']):
                raise ReplayStop('FFS_reuse_family_mismatch:' + cell)
            if row.get('Q_updates') or row.get('Q_sorting'):
                raise ReplayStop('FFS_reuse_candidate_has_Q_enabled:' + cell)
            if cell in found and found[cell]['row'] != row:
                raise ReplayStop('FFS_reuse_conflicting_saved_rows:' + cell)
            entry = found.setdefault(cell, {'row': row, 'paths': []})
            entry['paths'].append(str(path))
    candidates = [{'target_cell': cell, 'source_condition': entry['row']['condition'],
                   'source_paths': entry['paths'], 'status': 'candidate_not_credited',
                   'remaining_checks': ['complete inputs and task version', 'model and full prompt',
                                        'memory and retrieval behavior', 'repair and validator', 'repeat identity']}
                  for cell, entry in sorted(found.items())]
    counts = dict(Counter(item['source_condition'] for item in candidates))
    return {'status': 'inventory_only', 'candidate_count': len(candidates), 'by_condition': counts,
            'credited_cells': 0, 'unreadable_paths': unreadable, 'candidates': candidates,
            'API_calls': 0}


def main():
    result = collect()
    write_json(RUN / 'FX_GATE/reuse_candidates.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'candidates'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
