"""Identify a failed embedding transport request without dispatching another request."""
import json
from pathlib import Path
import uuid

from configs.cle_weekly_build_20261027.recovery_plan import classify_sources
from configs.cle_weekly_fs_20261027 import evaluate
from methods.sct_trajectory.replay_journal import ReplayStop
from methods.sct_trajectory.replay_journal import write_json

ROOT = Path('E:/ResearchRuns/CLE/20261027_full_requirements/FFS')


def inspect():
    sources = [Path(p) for p in evaluate.base.read(ROOT / 'execution_index.json')['segments']]
    pending = classify_sources(sources)
    if len(pending) != 1:
        raise ReplayStop('expected_one_transport_interrupted_embedding')
    (cell, identity), records = next(iter(pending.items()))
    if cell != 'embedding':
        raise ReplayStop('pending_is_not_embedding')
    # Preserve the exact request identity and public input; wire classification above
    # requires matching input, no HTTP status, no response, and a connection failure.
    return {'status': 'classified', 'pending_cell': cell, 'pending_identity': identity,
            'pending_public': records[0], 'segments': [str(p) for p in sources],
            'new_HTTP': 0, 'unknown_usage_retained': True}


def probe(focus=None):
    info = inspect()
    sources = [Path(p) for p in info['segments']]
    previous = evaluate.base.unresolved_requests
    evaluate.base.unresolved_requests = lambda _: []
    root = ROOT / ('embedding_prefix_probe_' + uuid.uuid4().hex)
    root.mkdir()
    try:
        saved = set()
        for source in sources:
            saved.update(p.stem for p in (source / 'task_rows').glob('*.json'))
        # Only cells whose original journals exist can have reached the failed call.
        names = set()
        for source in sources:
            names.update(p.name for p in (source / 'journals').iterdir() if p.is_dir())
        candidates = [c for c in evaluate.base.read(ROOT / 'inputs/schedule.json')
                      if c['cell_id'] in names and c['cell_id'] not in saved and
                      (focus is None or c['task_id'] == focus)]
        targets = []
        outcomes = []
        for index, cell in enumerate(candidates):
            dest = root / ('candidate_%03d' % index)
            worker = evaluate.FrozenFS(sources, offline=True, destination=dest)
            def replay_embedding(texts):
                journal = worker.io.journal('embedding')
                def forbidden(_):
                    raise ReplayStop('unexpected_network')
                return journal.wrap(lambda: forbidden, {'model': 'text-embedding-3-large',
                    'operation': 'embedding'})(json.dumps(texts, ensure_ascii=False))['vectors']
            worker.embedding._request = replay_embedding
            try:
                start = worker.start(worker.tasks[cell['task_id']], cell['repeat'])
                worker.one(cell, start)
                outcome = 'completed'
            except ReplayStop as exc:
                outcome = str(exc)
            finally:
                worker.embedding._db.close()
            outcomes.append({'cell': cell['cell_id'], 'outcome': outcome})
            if outcome == 'replay_missing_request:' + info['pending_identity']:
                targets.append(cell['cell_id'])
        latest_names = {p.name for p in (sources[-1] / 'journals').iterdir() if p.is_dir()}
        for name in sorted(n for n in latest_names if n.startswith('shared_initial_')):
            key = name.split('_', 2)[2]
            starts = [source / 'shared_starts' / (key + '.json') for source in sources]
            if any(p.exists() and all(k in evaluate.base.read(p) for k in
                   ('query', 'selected_cards', 'retrieval_trace')) for p in starts):
                continue
            task_id, repeat = key.rsplit('_r', 1)
            if focus is not None and task_id != focus:
                continue
            worker = evaluate.FrozenFS(sources, offline=True, destination=root / ('shared_' + key))
            def replay_embedding(texts):
                journal = worker.io.journal('embedding')
                def forbidden(_):
                    raise ReplayStop('unexpected_network')
                return journal.wrap(lambda: forbidden, {'model': 'text-embedding-3-large',
                    'operation': 'embedding'})(json.dumps(texts, ensure_ascii=False))['vectors']
            worker.embedding._request = replay_embedding
            try:
                worker.start(worker.tasks[task_id], int(repeat))
                outcome = 'completed'
            except ReplayStop as exc:
                outcome = str(exc)
            finally:
                worker.embedding._db.close()
            outcomes.append({'cell': name, 'outcome': outcome})
            if outcome == 'replay_missing_request:' + info['pending_identity']:
                targets.append(name)
        result = {'status': 'passed' if len(targets) == 1 else 'different',
                'targets': targets, 'candidates': len(candidates), 'outcomes': outcomes, 'new_HTTP': 0,
                'pending_identity': info['pending_identity']}
        write_json(root / 'probe_result.json', result)
        return result
    finally:
        evaluate.base.unresolved_requests = previous


if __name__ == '__main__':
    import sys
    print(json.dumps(probe(sys.argv[1] if len(sys.argv) > 1 else None), ensure_ascii=False))
