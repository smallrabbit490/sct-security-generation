"""零API资格屏蔽敏感性分析：复现旧M1，去除已知不合格奖励，重放固定查询的呈现排序。

新Q与排序是派生诊断，不把旧代码的Joint移植成新策略成绩，不覆盖原库或继续学习。
"""
from collections import Counter, defaultdict
import copy
import csv
import json
from pathlib import Path

from methods.cle_ablation.runner import load_memory
from methods.cle_ablation.run_memory_q import shuffled_memory
from configs.cle_memory_q_full_gate_cap3_20261019.analyze import trace_of
from methods.sct_trajectory.memory_q import rank_candidates, reward_from_evidence, update_q
from methods.sct_trajectory.run_memory_q_study import _write_memory

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / 'translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2'
OUT = ROOT / 'translation_work/diagnostics/20261019/cle_memory_q/pro_closeout/qualification_replay'
CURATED = ROOT / 'results/curated/cle_q_pro_closeout_20261019'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def replay(nodes, events, eligible=None):
    """只对已有非空奖励按原记录顺序做相同EMA；不为此前缺测推造新奖励。"""
    target = copy.deepcopy(nodes)
    by_id = {n.invariant_id: n for n in target}
    for node in target:
        node.q_value = 0.0
        node.q_visits = 0
    used, removed = [], []
    for event in events:
        identifier = event.get('invariant_id')
        if identifier is None or event.get('reward') is None:
            continue
        if eligible is not None and str(event['task_id']) not in eligible:
            removed.append(event)
            continue
        node = by_id[identifier]
        node.q_value = update_q(node.q_value, event['reward'], .3)
        node.q_visits += 1
        used.append(event)
    return target, used, removed


def write_csv(path, values):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    CURATED.mkdir(parents=True, exist_ok=True)
    original = load_memory(PARENT / 'observe/frozen/m_star_q.jsonl')
    initial = load_memory(PARENT / 'input_memory.jsonl')
    if any(n.q_visits or n.q_value for n in initial):
        raise RuntimeError('prelearning_snapshot_is_not_zero_Q')
    def bodies(nodes):
        return {n.invariant_id: {k: v for k, v in n.to_dict().items() if k not in {'q_value', 'q_visits'}} for n in nodes}
    if bodies(initial) != bodies(original):
        raise RuntimeError('fixed_card_body_changed_from_prelearning')
    events = list(rows(PARENT / 'observe/memory_q_events.jsonl'))
    # 逐项对应原生尝试；事件数值可复现还不够，必须确实采用并拥有同次完整测量。
    native_rewards = {}
    for row in rows(PARENT / 'observe/rows.jsonl'):
        for attempt in row['attempts']:
            generation = attempt.get('generation', {})
            if not generation.get('workflow_completed'):
                continue
            reward = reward_from_evidence(attempt.get('validation', {}).get('evidence', {}), code=attempt.get('code', ''))
            for card in generation.get('cards', []):
                native_rewards[(str(row['task_id']), attempt['attempt'], card['invariant_id'])] = reward
    for event in events:
        if event.get('invariant_id') and event.get('reward') is not None:
            key = (str(event['task_id']), event['attempt'], event['invariant_id'])
            if native_rewards.get(key) != event['reward']:
                raise RuntimeError('credited_event_missing_native_adoption_or_reward:' + str(key))
    reproduced, used_old, _ = replay(initial, events)
    if any(a.q_visits != b.q_visits or a.q_value != b.q_value for a, b in zip(original, reproduced)):
        raise RuntimeError('original_M1_replay_mismatch')
    controls = read(ROOT / 'translation_work/diagnostics/20261019/cle_memory_q/coverage_learning_v2/qualification.after_dependencies.json')['tasks']
    eligible = {str(t['task_id']) for t in controls if t['reward_eligible']}
    screened, used, removed = replay(initial, events, eligible)
    family_support = defaultdict(set)
    old_family_support = defaultdict(set)
    for event in used_old:
        old_family_support[event['invariant_id']].add(event['family_id'])
    for event in used:
        family_support[event['invariant_id']].add(event['family_id'])
    historical_support = read(PARENT / 'observe/q_family_support.json')
    if {k: sorted(v) for k, v in old_family_support.items()} != historical_support:
        raise RuntimeError('original_family_support_replay_mismatch')
    (OUT / 'diagnostic_q_family_support.json').write_text(
        json.dumps({k: sorted(v) for k, v in family_support.items()}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    old = {n.invariant_id: n for n in original}
    new = {n.invariant_id: n for n in screened}
    changes = [{'invariant_id': a.invariant_id, 'cwe': str(a.cwe), 'Q_old': a.q_value,
                'visits_old': a.q_visits, 'Q_screened': b.q_value, 'visits_screened': b.q_visits,
                'lost_all_support': bool(a.q_visits and not b.q_visits),
                'sign_changed': (a.q_value > 0) - (a.q_value < 0) != (b.q_value > 0) - (b.q_value < 0)}
               for a, b in zip(original, screened) if a.q_visits != b.q_visits or a.q_value != b.q_value]
    write_csv(CURATED / 'qualification_Q_changes.csv', changes)
    _write_memory(OUT / 'diagnostic_qualification_screened_Q.jsonl', screened)
    (OUT / 'excluded_existing_events.jsonl').write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in removed), encoding='utf-8')
    results, skipped = [], []
    exposure = {arm: Counter() for arm in ['Q0', 'Q1', 'Q2', 'Q3']}
    stage_exposure = defaultdict(Counter)
    unique_exposure = defaultdict(set)
    gate_path = ROOT / 'translation_work/diagnostics/20261019/cle_memory_q/full_gate_cap3_v4/rows.jsonl'
    placebo = load_memory(gate_path.parent / 'shuffled_input_memory.jsonl')
    expected_placebo = shuffled_memory(original, 20261015, 'cwe')
    if [n.to_dict() for n in placebo] != [n.to_dict() for n in expected_placebo]:
        raise RuntimeError('saved_Q3_not_exact_CWE_shuffle')
    placebo_by_id = {n.invariant_id: n for n in placebo}
    assignment_entries = 0
    recovered_first_traces, error_selector_queries = [], []
    for row in rows(gate_path):
        active = placebo_by_id if row['arm'] == 'Q3' else old
        for a in row['attempts']:
            trace = trace_of(a)
            stages = {'candidate': trace.get('candidate_ids'), 'presented': trace.get('presented_candidate_ids'),
                      'selected': [c['invariant_id'] for c in a.get('generation', {}).get('retrieved_cards', [])],
                      'adopted': [c['invariant_id'] for c in a.get('generation', {}).get('cards', [])]}
            for scope in ['all_attempts'] + (['first_attempt'] if a['attempt'] == 0 else []):
                for stage, ids in stages.items():
                    key = (row['arm'], scope, stage)
                    bucket = stage_exposure[key]
                    if ids is None:
                        bucket['missing_stage_records'] += 1
                        continue
                    bucket['stage_records'] += 1
                    bucket['occurrences'] += len(ids)
                    for identifier in ids:
                        unique_exposure[key].add(identifier)
                        bucket['originally_learned_occurrences'] += old[identifier].q_visits > 0
                        bucket['assigned_visited_occurrences'] += active[identifier].q_visits > 0
                        bucket['qualification_screened_visited_occurrences'] += new[identifier].q_visits > 0
            for field, label in [('retrieved_cards', 'selected'), ('cards', 'adopted')]:
                for card in a.get('generation', {}).get(field, []):
                    identifier = card['invariant_id']
                    exposure[row['arm']][label] += 1
                    exposure[row['arm']][label + '_originally_learned'] += old[identifier].q_visits > 0
                    exposure[row['arm']][label + '_assigned_visits'] += active[identifier].q_visits > 0
            if row['arm'] == 'Q3':
                for score in trace.get('value_ranking', []):
                    if score['q_value'] != active[score['id']].q_value:
                        raise RuntimeError('Q3_trace_assignment_mismatch')
                    assignment_entries += 1
        if row['arm'] != 'Q2':
            continue
        attempt = row['attempts'][0]
        trace = trace_of(attempt)
        if not attempt.get('retrieval_trace') and trace:
            recovered_first_traces.append(row['task_id'])
        if trace.get('candidate_order') != 'q' or 'scores' not in trace or 'presented_candidate_ids' not in trace:
            skipped.append({'task_id': row['task_id'], 'reason': 'no_saved_first_Q_presentation'})
            continue
        if trace.get('status') != 'completed':
            error_selector_queries.append(row['task_id'])
        kwargs = {'delta': trace['delta'], 'lambda_q': trace['lambda_q'], 'limit': None}
        old_order = [v['id'] for v in rank_candidates(trace['scores'], {k: n.q_value for k, n in old.items()}, **kwargs)]
        if old_order != trace['presented_candidate_ids']:
            raise RuntimeError('saved_original_ranking_mismatch:' + row['task_id'])
        new_order = [v['id'] for v in rank_candidates(trace['scores'], {k: n.q_value for k, n in new.items()}, **kwargs)]
        selected = {c['invariant_id'] for c in attempt.get('generation', {}).get('retrieved_cards', [])}
        adopted = {c['invariant_id'] for c in attempt.get('generation', {}).get('cards', [])}
        changed = {v['invariant_id'] for v in changes}
        results.append({'task_id': row['task_id'], 'family_id': row['family_id'],
                        'candidate_count': len(old_order), 'presentation_order_changed': old_order != new_order,
                        'top3_set_changed': set(old_order[:3]) != set(new_order[:3]),
                        'original_selected_Q_changed': len(selected & changed),
                        'original_adopted_Q_changed': len(adopted & changed),
                        'old_rank_top3': '|'.join(old_order[:3]), 'screened_rank_top3': '|'.join(new_order[:3])})
    write_csv(CURATED / 'fixed_first_query_ranking_replay.csv', results)
    stage_rows = []
    for (arm, scope, stage), counts in stage_exposure.items():
        identifiers = unique_exposure[arm, scope, stage]
        assigned = placebo_by_id if arm == 'Q3' else old
        stage_rows.append({'arm': arm, 'scope': scope, 'stage': stage, **counts,
                           'unique_cards': len(identifiers),
                           'originally_learned_unique': sum(old[i].q_visits > 0 for i in identifiers),
                           'assigned_visited_unique': sum(assigned[i].q_visits > 0 for i in identifiers),
                           'qualification_screened_visited_unique': sum(new[i].q_visits > 0 for i in identifiers)})
    # 每个阶段缺失字段显式填0只是已计数的缺失次数，不是验证/人工标签的缺测得分。
    columns = set().union(*(r.keys() for r in stage_rows))
    stage_rows = [{k: r.get(k, 0) for k in sorted(columns)} for r in stage_rows]
    write_csv(CURATED / 'stage_coverage_occurrence_and_unique.csv', stage_rows)
    summary = {'operation': 'zero_API_qualification_screening_sensitivity',
               'original_M1_exactly_reproduced': True, 'starting_cards': len(original),
               'prelearning_snapshot_verified_zero_Q': True,
               'fixed_card_body_equal_prelearning': True,
               'credited_events_verified_against_native_attempts': len(used_old),
               'original_family_support_exactly_reproduced': True,
               'original_two_feedback_family_cards': sum(len(v) >= 2 for v in old_family_support.values()),
               'screened_two_feedback_family_cards': sum(len(v) >= 2 for v in family_support.values()),
               'original_valid_updates': len(used_old), 'retained_updates': len(used), 'removed_updates': len(removed),
               'removed_feedback_tasks': len({str(e['task_id']) for e in removed}),
               'affected_cards': len(changes), 'lost_all_support': sum(c['lost_all_support'] for c in changes),
               'Q_sign_changes_including_zero': sum(c['sign_changed'] for c in changes),
               'original_visited': sum(n.q_visits > 0 for n in original),
               'screened_visited': sum(n.q_visits > 0 for n in screened),
               'screened_Q_signs': dict(Counter('positive' if n.q_value > 0 else 'negative' if n.q_value < 0 else 'zero' for n in screened)),
               'fixed_query_replays': len(results), 'skipped_first_traces': skipped,
               'recovered_embedded_first_traces': recovered_first_traces,
               'included_first_queries_with_selector_errors': error_selector_queries,
               'presentation_order_changes': sum(r['presentation_order_changed'] for r in results),
               'top3_set_changes': sum(r['top3_set_changed'] for r in results),
               'tasks_original_selected_Q_changed': sum(r['original_selected_Q_changed'] > 0 for r in results),
               'tasks_original_adopted_Q_changed': sum(r['original_adopted_Q_changed'] > 0 for r in results),
               'Q3_saved_bank_exact_CWE_shuffle': True,
               'Q3_trace_assignment_entries_verified': assignment_entries,
               'actual_exposure': exposure,
               'new_API_calls': 0, 'new_outcome_measurements': 0, 'new_Joint': None,
               'limitations': ['Only already assigned rewards retained; no missing rewards reconstructed.',
                              'Qualification-screened does not mean human-validated clean.',
                              'Replayed top3 is ranked preview, not actual LLM selection under new ordering.',
                              'No new selection/adoption/code/outcome can be inferred from historical outcomes.']}
    for path in [OUT / 'summary.json', CURATED / 'qualification_replay.json']:
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
