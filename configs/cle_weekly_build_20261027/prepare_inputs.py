"""Prepare the fixed public task inputs for the new native CLE memory build."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
NATIVE = ROOT / 'translation_work/sct_runs/cle_full_v41flash1017_20261024/source_bundle/inputs'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    target = RUN / 'BUILD_C41/inputs'
    if target.exists():
        raise SystemExit('build_inputs_already_exist')
    original = read(NATIVE / 'plt_tasks.json')
    native_pools = read(NATIVE / 'pools.json')
    declared = read(RUN / 'manifest.json')['pools']
    sources = {
        'D_init': RUN / 'shared_inputs/tasks_D_init.json',
        'D_grow': RUN / 'FG_LABELS/inputs_contract_v2/tasks.json',
        'D_gate': RUN / 'FQ_GATE/inputs_v3/tasks.json',
    }
    merged = {}
    for pool, native in [('D_init', 'source_pool'), ('D_grow', 'replay_pool'), ('D_gate', 'audit_pool')]:
        rows = read(sources[pool])
        ids = set(map(str, declared[pool]))
        if set(rows) != ids or set(map(str, native_pools[native])) != ids or ids & set(merged):
            raise SystemExit('input_pool_mismatch:' + pool)
        if any(str(value['index']) != key for key, value in rows.items()):
            raise SystemExit('input_identity_mismatch:' + pool)
        merged.update(rows)
    ids = [str(row['index']) for row in original]
    if len(ids) != 874 or len(set(ids)) != 874 or set(ids) != set(merged):
        raise SystemExit('native_order_mismatch')
    target.mkdir(parents=True)
    (target / 'plt_tasks.json').write_text(json.dumps([merged[i] for i in ids], ensure_ascii=False, indent=2), encoding='utf-8')
    (target / 'pools.json').write_text(json.dumps(native_pools, ensure_ascii=False, indent=2), encoding='utf-8')
    (target / 'manifest.json').write_text(json.dumps({
        'sources': {name: str(path) for name, path in sources.items()},
        'original_order': str(NATIVE / 'plt_tasks.json'),
        'counts': {name: len(declared[name]) for name in sources},
        'starting_memory': 'empty', 'Q_enabled': False, 'API_calls': 0,
        'status': 'inputs_prepared_runner_not_ready',
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('prepared 874 native-order tasks; no API calls')


if __name__ == '__main__':
    main()
