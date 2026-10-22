"""零API回放已有D_grow奖励；固定历史查询比较检查点排序，不模拟新的生成结果。"""
from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path

from methods.cle_ablation.audit_memory_q import read_rows
from methods.sct_trajectory.memory_q import rank_candidates, update_q
from methods.sct_trajectory.run_artifacts import write_json_atomic as write


def replay(learn, probe, out):
    manifest = json.loads((learn/'experiment_manifest.json').read_text(encoding='utf-8'))
    calibration = json.loads((learn/'calibration.json').read_text(encoding='utf-8'))
    final = {n['invariant_id']: n for n in read_rows(learn/'frozen/m_star_q.jsonl')}
    events = read_rows(learn/'memory_q_events.jsonl')
    by_task = defaultdict(list)
    for event in events:
        by_task[str(event['task_id'])].append(event)
    queries = []
    for row in read_rows(probe/'compare/rows.jsonl'):
        for attempt in row['attempts']:
            trace = attempt.get('retrieval_trace') or {}
            for stage in attempt.get('generation', {}).get('stages', []):
                if stage.get('stage') == 'retrieval' and stage.get('status') == 'degraded':
                    trace = stage.get('retrieval_trace') or {}
            if trace.get('status') == 'completed':
                queries.append({'task_id': row['task_id'], 'arm': row['arm'], 'attempt': attempt['attempt'],
                                'scores': trace.get('scores', []), 'query_hash': trace.get('query_hash')})
    checkpoints = (0, 68, 136, 204, 246, len(manifest['learning']))
    values = dict.fromkeys(final, 0.0)
    visits = Counter()
    families = defaultdict(set)
    snapshots = []

    def capture(n):
        snapshots.append({'tasks_processed': n, 'values': dict(values), 'visits': dict(visits),
                          'families': {key: len(v) for key, v in families.items()}})

    capture(0)
    for index, task_id in enumerate(manifest['learning'], 1):
        for event in by_task[str(task_id)]:
            key, reward = event.get('invariant_id'), event.get('reward')
            if key is None or reward is None:
                continue
            assert abs(values[key]-event['q_before']) < 1e-12
            values[key] = update_q(values[key], reward, calibration['alpha'])
            visits[key] += 1
            families[key].add(event['family_id'])
            assert abs(values[key]-event['q_after']) < 1e-12
        if index in checkpoints:
            capture(index)
    assert all(abs(values[k]-n.get('q_value', 0)) < 1e-12 and visits[k] == n.get('q_visits', 0)
               for k, n in final.items()), 'replay must reproduce frozen Q'

    def ranks(q):
        return [[s['id'] for s in rank_candidates(query['scores'], q, delta=calibration['delta'],
                 lambda_q=calibration['lambda_q'])] for query in queries]

    final_ranks = ranks(values)
    summaries, query_rows = [], []
    previous = snapshots[0]
    previous_ranks = ranks(previous['values'])
    for snap in snapshots:
        current = ranks(snap['values'])
        changed = [k for k in values if snap['values'][k] != previous['values'][k]]
        learned = list(snap['visits'])
        summaries.append({'tasks_processed': snap['tasks_processed'], 'reward_updates': sum(snap['visits'].values()),
            'learned_cards': len(learned), 'cards_ge2_families': sum(v >= 2 for v in snap['families'].values()),
            'cards_changed_since_previous': len(changed),
            'mean_abs_q_change_changed_cards': sum(abs(snap['values'][k]-previous['values'][k]) for k in changed)/len(changed) if changed else 0,
            'mean_abs_q_gap_to_final_learned_cards': sum(abs(snap['values'][k]-values[k]) for k in learned)/len(learned) if learned else None,
            'nonempty_queries': sum(bool(r) for r in current), 'queries': len(current),
            'set_changed_since_previous': sum(set(a) != set(b) for a,b in zip(current, previous_ranks)),
            'order_changed_since_previous': sum(a != b for a,b in zip(current, previous_ranks)),
            'set_diff_from_final': sum(set(a) != set(b) for a,b in zip(current, final_ranks)),
            'order_diff_from_final': sum(a != b for a,b in zip(current, final_ranks))})
        query_rows += [{**{k:v for k,v in query.items() if k != 'scores'},
                       'tasks_processed': snap['tasks_processed'], 'ranked_ids': ranking}
                      for query, ranking in zip(queries, current)]
        previous, previous_ranks = snap, current
    result = {'protocol': 'cle-q-fixed-exposure-replay-v1', 'model_calls': 0, 'embedding_calls': 0,
              'source_learning': str(learn), 'fixed_queries': str(probe), 'queries_are_independent_samples': False,
              'frozen_q_exactly_reproduced': True, 'alpha': calibration['alpha'], 'delta': calibration['delta'],
              'checkpoints': summaries, 'visits_histogram': dict(sorted(Counter(visits.values()).items())),
              'limits': 'Fixed historical exposure and queries. No new rewards, online-policy trajectory, accuracy or numerical convergence proof.'}
    write(out/'replay_summary.json', result)
    write(out/'replay_rankings.json', query_rows)
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('learn', 'probe', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    replay(args.learn, args.probe, args.out)
