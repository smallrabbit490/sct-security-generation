"""复用303题配对表与两阶段原生记录，生成包A/D的诊断表；不重算旧评分。

旧侧成绩来自现有逐题配对表，新侧从原生rows核对；缺旧原生代码时明确限定。
Q影子统计只分析已保存反馈，不修改奖励或长期经验。
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict

from .prepare import ROOT, ONLINE, OUT, read, write, write_csv
from methods.sct_trajectory.public_contract_checks import compile_public_contract, check_public_contract


def jsonl(path):
    with path.open(encoding='utf-8') as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                yield line_number, json.loads(line)


def main():
    with (ROOT / 'results/curated/cle_q_dinit_selection_joint_20261021/per_task.csv').open(encoding='utf-8-sig') as handle:
        pairs = list(csv.DictReader(handle))
    source_tasks = read(ONLINE / 'tasks_D_init.json')
    nodes = {n['invariant_id']: n for _, n in jsonl(ONLINE / 'D_grow/frozen/m_star_q.jsonl')}
    row_index, attempts, attempt_rows = {}, {}, []
    for pool in ['D_init', 'D_grow']:
        path = ONLINE / pool / 'rows.jsonl'
        for line_number, row in jsonl(path):
            tid = str(row['task_id'])
            final = row['final']
            row_index[(pool, tid)] = {'final': {k: final[k] for k in ['functional', 'security', 'joint', 'measured', 'code']},
                'line_number': line_number, 'row_error': row.get('error_type'), 'row': row}
            for attempt in row['attempts']:
                key = (pool, tid, attempt['attempt'])
                adopted = attempt.get('generation', {}).get('adoption', {}).get('applied_ids', [])
                trace = attempt.get('retrieval_trace', {})
                compact = {'pool': pool, 'task_id': tid, 'family_id': row['family_id'],
                    'attempt': attempt['attempt'], 'F': attempt['functional'], 'S': attempt['security'],
                    'Joint': attempt['joint'], 'measured': attempt['measured'],
                    'selected_count': len(trace.get('selected_ids', [])), 'adopted_count': len(adopted),
                    'adopted_ids': json.dumps(adopted), 'row_line': line_number,
                    'source_rows': str(path.relative_to(ROOT))}
                attempts[key] = compact
                attempt_rows.append(compact)
    cases = []
    evidence_dir = OUT / 'paired_code_evidence'
    evidence_dir.mkdir(exist_ok=True)
    for pair in pairs:
        tid = pair['task_id']
        native = row_index[('D_init', tid)]
        old_path = ONLINE.parent / 'cle_dinit_full_learning_v4b/task_rows/L1' / f'{tid}.json'
        old_native = read(old_path)
        old_final = old_native['final']
        final = native['final']
        assert old_final['joint'] == (pair['old_joint'] == 'True')
        assert final['joint'] == (pair['new_joint'] == 'True')
        code = final['code']
        rules = compile_public_contract(source_tasks[tid]['task_description'])
        static = check_public_contract(code, rules)
        static_ids = [v['rule_id'] + (':' + v['binding'] if v.get('binding') else '')
                      for v in static['violations']]
        labels = []
        if pair['new_verified_global_defect'] == 'True':
            labels.append('historically_verified_binding_defect')
        if static_ids:
            labels.append('current_public_contract_static_flag')
        if native['row_error']:
            labels.append('recorded_pipeline_error_not_automatically_causal')
        if not final['measured']:
            labels.append('missing_formal_measurement')
        if tid in ['1037', '989']:
            labels.append('historical_missing_public_context_case')
        if tid in ['874', '907']:
            labels.append('historical_resource_case')
        old, new = pair['old_joint'] == 'True', final['joint']
        transition = 'rescue' if new and not old else 'loss' if old and not new else 'both_pass' if new else 'both_fail'
        if transition in ['rescue', 'loss']:
            def code_evidence(row):
                value = row['final']
                applied = value.get('generation', {}).get('adoption', {}).get('applied_ids', [])
                return {'attempt': value['attempt'], 'code': value['code'],
                    'F': value['functional'], 'S': value['security'], 'Joint': value['joint'],
                    'measured': value['measured'], 'adopted_ids': applied,
                    'adopted_card_bodies': [{k: nodes[i].get(k) for k in
                        ['invariant_id', 'high_level_invariant', 'applicability', 'positive_principle', 'negative_guardrail']}
                        for i in applied]}
            write(evidence_dir / f'{tid}.json', {'task_id': tid,
                'public_task': source_tasks[tid]['task_description'],
                'old_source': str(old_path.relative_to(ROOT)),
                'new_source': f'translation_work/diagnostics/20261020/cle_q_online_v1/D_init/rows.jsonl:{native["line_number"]}',
                'old': code_evidence(old_native), 'new': code_evidence(native['row']),
                'implementation_review': 'pending; historical outcome association is not isolated Q causality'})
        cases.append({'task_id': tid, 'family_id': source_tasks[tid]['family_id'], 'cwe': pair['cwe'],
            'transition': transition, 'old_joint_verified_native_and_pair_table': old,
            'old_F_from_native': old_final['functional'], 'old_S_from_native': old_final['security'],
            'old_measured': old_final['measured'],
            'new_F_from_native': final['functional'], 'new_S_from_native': final['security'],
            'new_joint_from_native': new, 'new_measured': final['measured'],
            'selection_group': pair['selection_group'], 'new_added_adopted_ids': pair['new_added_adopted_ids'],
            'historical_verified_binding_defect': pair['new_verified_global_defect'] == 'True',
            'current_public_static_violation_ids': json.dumps(static_ids),
            'diagnostic_tags': '|'.join(labels) or 'unassigned_requires_code_review',
            'mechanism_implementation_review': 'pending; adoption is not implementation',
            'new_rows_line': native['line_number'],
            'old_code_evidence': str(old_path.relative_to(ROOT))})
    write_csv(OUT / 'historical_all_303_cases.csv', cases)
    write_csv(OUT / 'historical_38_disagreements.csv', [r for r in cases if r['transition'] in ['loss', 'rescue']])
    write_csv(OUT / 'historical_265_same_score_controls.csv', [r for r in cases if r['transition'] in ['both_pass', 'both_fail']])
    write_csv(OUT / 'training_attempt_shadow_FS.csv', attempt_rows)

    feedback = defaultdict(lambda: {'events': 0, 'positive': 0, 'negative': 0, 'families': set(),
                                  'self_family_events': 0, 'other_family_events': 0})
    reward_states, co_adoption, event_count = Counter(), Counter(), Counter()
    credit_cases = []
    for pool in ['D_init', 'D_grow']:
        for line_number, event in jsonl(ONLINE / pool / 'memory_q_events.jsonl'):
            event_count['all_recorded_events'] += 1
            if not event['credited']:
                event_count['not_credited'] += 1
                continue
            event_count['credited'] += 1
            attempt = attempts[(pool, str(event['task_id']), event['attempt'])]
            state = 'F+S+' if attempt['F'] and attempt['S'] else 'F+S-' if attempt['F'] else 'F-S+' if attempt['S'] else 'F-S-'
            reward_states[state] += 1
            co_adoption['multiple_cards' if attempt['adopted_count'] > 1 else 'one_card'] += 1
            card = nodes[event['invariant_id']]
            source_tid = str(card['source']['task_id'])
            source_family = source_tasks[source_tid]['family_id']
            f = feedback[event['invariant_id']]
            f['events'] += 1
            f['positive' if event['reward'] > 0 else 'negative'] += 1
            f['families'].add(event['family_id'])
            same_family = source_family == event['family_id']
            f['self_family_events' if same_family else 'other_family_events'] += 1
            if str(event['task_id']) == '1003':
                credit_cases.append({'task_id': '1003', 'pool': pool, 'attempt': event['attempt'],
                    'card_id': event['invariant_id'], 'reward': event['reward'],
                    'q_before': event['q_before'], 'q_after': event['q_after'],
                    'state': state, 'co_adopted_cards': attempt['adopted_count'],
                    'card_negative_guardrail': card.get('negative_guardrail'),
                    'card_positive_principle': card.get('positive_principle'),
                    'code_implementation_review': 'pending_manual_code_read',
                    'event_line': line_number})
    card_rows = [{'card_id': card_id, 'source_task_id': str(node['source']['task_id']),
        'source_family_id': source_tasks[str(node['source']['task_id'])]['family_id'],
        'cwe': str(node['cwe']), 'latest_q_value': node['q_value'], 'latest_q_visits': node['q_visits'],
        'current_two_stage_events': feedback[card_id]['events'],
        'current_two_stage_positive': feedback[card_id]['positive'],
        'current_two_stage_negative': feedback[card_id]['negative'],
        'current_two_stage_distinct_feedback_families': len(feedback[card_id]['families']),
        'self_family_events': feedback[card_id]['self_family_events'],
        'other_family_events': feedback[card_id]['other_family_events']}
        for card_id, node in nodes.items()]
    write_csv(OUT / 'card_family_feedback.csv', card_rows)
    write(OUT / 'q_credit_1003_cases.json', credit_cases)
    transitions = Counter(r['transition'] for r in cases)
    assert transitions == {'both_pass': 120, 'both_fail': 145, 'rescue': 20, 'loss': 18}
    summary = {'scope': 'old L1 and new Q2 native D_init303 paired; Q feedback covers new D_init303/D_grow23',
        'paired_tasks': len(cases), 'transitions': dict(transitions),
        'old_joint': sum(r['old_joint_verified_native_and_pair_table'] for r in cases),
        'new_joint': sum(r['new_joint_from_native'] for r in cases),
        'old_native_code_not_located_by_this_analysis': False,
        'both_native_results_verified': True, 'discordant_code_pair_exports': 38,
        'same_score_control_tasks': 265, 'implementation_reviews_pending': 303,
        'current_two_stage_attempts': len(attempt_rows), 'current_two_stage_event_counts': dict(event_count),
        'credited_events_by_FS': dict(reward_states), 'credited_events_by_co_adoption': dict(co_adoption),
        'cards_receiving_current_two_stage_credit': sum(r['current_two_stage_events'] > 0 for r in card_rows),
        'cards_with_multiple_current_feedback_families': sum(r['current_two_stage_distinct_feedback_families'] > 1 for r in card_rows),
        'self_family_events': sum(r['self_family_events'] for r in card_rows),
        'other_family_events': sum(r['other_family_events'] for r in card_rows),
        'latest_visits_positive': sum(r['latest_q_visits'] > 0 for r in card_rows),
        'full_historical_Q_ledger_complete': False, 'API_calls': 0, 'Q_updates': 0,
        'causal_limit': 'historical states/timing and repair inputs differ; no isolated Q efficacy conclusion'}
    write(OUT / 'history_summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
