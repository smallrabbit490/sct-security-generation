"""两题冷启动的保存响应回放；封网，不补造缺失响应。"""
import json
import builtins
from pathlib import Path
from unittest.mock import patch

from configs.cle_weekly_build_20261027.native_adapter import run_native
from configs.cle_weekly_build_20261027.physical_guard import physical_guard
from configs.cle_weekly_build_20261027.prepare_inputs import read
from methods.sct_trajectory.closed_loop import CleRunner
from methods.sct_trajectory import closed_loop
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from .run import OUT, IDS, PrefixComplete


def main():
    source = OUT / 'segment_001'
    target = OUT / 'zero_API_replay_recorded_identity'
    if target.exists():
        raise ReplayStop('replay_output_exists_preserve_it')
    protocol = read(OUT / 'protocol.json')
    actual = read(source / 'native_phase1_result.json')
    pool = read(source / 'experience_pool_snapshot.json')
    hash_catalog = {}
    for row in actual['results']:
        for group in ('positive', 'negative', 'error_ledger'):
            for item in (row.get('distilled') or {}).get(group, []):
                for prefix, key in [('cand', 'high_level_invariant'), ('hint', 'minimal_patch_hint')]:
                    text = str(item.get(key) or '').strip()
                    candidates = [n for n in pool if n['invariant_id'].startswith(prefix+'-')
                                  and n['high_level_invariant'] == (text[:300] if prefix == 'hint' else text)]
                    if len(candidates) == 1 and text:
                        hash_catalog[text] = int(candidates[0]['invariant_id'].rsplit('-', 1)[1])
    write_json(target.parent/'recorded_node_identity_values.json', {
        'source': str(source/'experience_pool_snapshot.json'), 'text_to_absolute_hash': hash_catalog,
        'purpose': 'restore recorded process-randomized identity values only during saved event replay'})
    def recorded_hash(value):
        return hash_catalog[value] if isinstance(value, str) and value in hash_catalog else builtins.hash(value)
    def forbidden(*args, **kwargs):
        raise ReplayStop('zero_API_replay_network_forbidden')
    io = physical_guard(target, protocol['budget'], forbidden, resume_sources=[source], live=False)
    io.replay_source = source
    original = CleRunner.phase1_seed
    result = {}
    recorded_order = [str(r['task_id']) for r in actual['results']]
    def recorded_map(runner, fn, items, *, on_done=None, workers=None):
        by_id = {str(item['index']): item for item in items}
        if set(by_id) != set(recorded_order):
            raise ReplayStop('unexpected_items_before_ordered_event_replay')
        values = []
        for identity in recorded_order:
            value = fn(by_id[identity])
            values.append(value)
            if on_done:
                on_done(value)
        return values
    def bounded(runner, tasks, *args, **kwargs):
        if [str(t['index']) for t in tasks[:2]] != IDS or runner.experience_pool:
            raise ReplayStop('native_prefix_or_initial_pool_changed')
        replay = original(runner, tasks[:2], *args, **kwargs)
        by_task = lambda value: {str(r['task_id']): r for r in value['results']}
        prior, current = by_task(actual), by_task(replay)
        fields = ['state_first', 'state_after_repair', 'outcome', 'generated_codes',
                  'patch_diffs', 'evidence_first', 'evidence_after_repair', 'distilled']
        differences = [{'task': t, 'field': k} for t in IDS for k in fields if prior[t].get(k) != current[t].get(k)]
        nodes = [n.to_dict() for n in runner.experience_pool]
        def body(n):
            return {k: v for k, v in n.items() if k != 'invariant_id'}
        bodies_equal = sorted(json.dumps(body(n), sort_keys=True) for n in nodes) == sorted(json.dumps(body(n), sort_keys=True) for n in pool)
        exact_ids = {n['invariant_id'] for n in nodes} == {n['invariant_id'] for n in pool}
        unconsumed = {k: sorted(j.prior-j.consumed) for k,j in io.journals.items() if j.prior-j.consumed}
        result.update(status='passed_recorded_event_replay' if not differences and bodies_equal and exact_ids and not unconsumed else 'different',
            completed_tasks=2, differences=differences, card_bodies_equal=bodies_equal,
            card_identifiers_equal=exact_ids, unconsumed_saved_requests=unconsumed,
            replay_merge_order=recorded_order, merge_order_source='saved native_phase1_result.results',
            identifier_note='Restore recorded native identity values by full distillation text during replay; original IDs and inputs not rewritten.',
            new_HTTP=0, source=str(source))
        io.save('native_replayed_result', replay)
        io.save('replayed_pool', nodes)
        raise PrefixComplete()
    arguments = list(protocol['arguments'])
    arguments[arguments.index('--out')+1] = str(target/'native')
    arguments[arguments.index('--embedding-cache')+1] = str(target/'embeddings.sqlite3')
    with patch('socket.socket.connect', side_effect=ReplayStop('offline_socket_forbidden')):
        try:
            with patch.object(CleRunner, 'phase1_seed', bounded), patch.object(CleRunner, '_map', recorded_map), patch.object(closed_loop, 'hash', recorded_hash, create=True):
                run_native(io, arguments)
        except PrefixComplete:
            pass
    if list((target/'wire').glob('*.request.json')):
        raise ReplayStop('replay_created_physical_request')
    write_json(target/'replay_result.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
