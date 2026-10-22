"""固定Q库小样本三臂诊断：重算原P7格式、同查询排序、实际采用和API成本。"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from methods.cle_ablation.audit_memory_q import check_run, read_rows
from methods.cle_ablation.report_memory_q import paired_effect
from methods.cle_ablation.runner import load_memory
from methods.sct_trajectory.memory_q import rank_candidates
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_branch_gate_study import file_digest, holm

ROOT = Path(__file__).resolve().parents[2]
ARMS = ('Q1', 'Q2', 'Q3')


def attempt_readout(row, banks, delta, lambda_q):
    """只读同一次真实召回分数，重算三种排序；采纳取生成器实际cards而非检索列表。"""
    values = {arm: {key: node.q_value for key, node in bank.items()} for arm, bank in banks.items()}
    records = []
    for attempt in row['attempts']:
        generation = attempt.get('generation', {})
        trace = attempt.get('retrieval_trace') or {}
        trace_source = 'attempt.retrieval_trace'
        # 原P7检索抛错时不会追加provider轨迹，attempt字段可能仍指向前次成功检索。
        # 本轮只读诊断优先使用本次stage所保存的异常轨迹，不改原始结果或生成流程。
        for stage in generation.get('stages', []):
            if stage.get('stage') == 'retrieval' and stage.get('status') == 'degraded':
                trace = stage.get('retrieval_trace') or {}
                trace_source = 'generation.stages.retrieval'
        scores = trace.get('scores', [])
        rankings = {arm: rank_candidates(scores, values[arm], delta=delta,
                                         lambda_q=0 if arm == 'Q1' else lambda_q) for arm in ARMS}
        ids = {arm: [s['id'] for s in ranking] for arm, ranking in rankings.items()}
        arm = row['arm']
        actual = ids[arm]
        if 'selected_ids' in trace:
            assert actual == trace['selected_ids'], (row['task_id'], arm, attempt['attempt'], 'ranking mismatch')
        retrieved = [c['invariant_id'] for c in generation.get('retrieved_cards', [])]
        adopted = [c['invariant_id'] for c in generation.get('cards', [])]
        assert set(adopted) <= set(retrieved), 'adopted card was not delivered'
        added = set(actual)-set(ids['Q1'])
        adoption = generation.get('adoption', {})
        if retrieved:
            assert retrieved == actual, 'delivered card order differs from actual ranking'
        bank = banks[arm]
        evidence = attempt.get('validation', {}).get('evidence', {})
        records.append({'task_id': str(row['task_id']), 'family_id': row['family_id'], 'cwe': row['cwe'],
            'arm': arm, 'attempt': attempt['attempt'], 'candidate_count': len(scores),
            'retrieval_status': trace.get('status', 'unavailable'), 'retrieval_errors': trace.get('errors', []),
            'trace_source': trace_source, 'query_hash': trace.get('query_hash'),
            'eligible_count': sum(s['cosine'] > delta for s in scores),
            'trained_candidates': sum(bank[s['id']].q_visits > 0 for s in scores),
            'trained_eligible': sum(bank[s['id']].q_visits > 0 and s['cosine'] > delta for s in scores),
            'rankings_same_query': ids, 'actual_ranked_ids': actual, 'delivered_ids': retrieved,
            'set_changed_vs_sim': set(actual) != set(ids['Q1']), 'order_changed_vs_sim': actual != ids['Q1'],
            'added_ids': sorted(added), 'removed_ids': sorted(set(ids['Q1'])-set(actual)),
            'adopted_ids': adopted, 'new_cards_adopted': sorted(added & set(adopted)),
            'nonzero_q_adopted': [i for i in adopted if bank[i].q_value != 0],
            'adoption_error': adoption.get('error'),
            'rejected_ids': adoption.get('rejected_ids', []),
            'workflow_completed': generation.get('workflow_completed', False),
            'error_type': attempt.get('error_type') or generation.get('error_type'),
            **{key: attempt[key] for key in ('functional', 'security', 'joint', 'measured')},
            'validation_status': {key: value.get('status') for key, value in evidence.items() if isinstance(value, dict)},
            'selected_scores': rankings[arm]})
    return records


def build(root, curated):
    run = root/'compare'
    checks = check_run(run)
    metadata = json.loads((run/'run_metadata.json').read_text(encoding='utf-8'))
    manifest = json.loads((run/'experiment_manifest.json').read_text(encoding='utf-8'))
    preflight = json.loads((root/'preflight.json').read_text(encoding='utf-8'))
    calibration = json.loads((run/'input_calibration.json').read_text(encoding='utf-8'))
    assert metadata['args']['shuffle_scope'] == 'cwe'
    original, placebo = load_memory(run/'input_memory.jsonl'), load_memory(run/'input_shuffled_memory.jsonl')
    strip = lambda n: {k: v for k, v in n.to_dict().items() if k not in ('q_value', 'q_visits')}
    assert [strip(n) for n in original] == [strip(n) for n in placebo]
    for cwe in {n.cwe for n in original}:
        pairs = lambda bank: Counter((n.q_value, n.q_visits) for n in bank if n.cwe == cwe)
        assert pairs(original) == pairs(placebo), 'CWE distribution changed'
    assert file_digest(ROOT/manifest['input_memory']) == calibration['memory_sha256']
    assert file_digest(ROOT/calibration['learning_calibration']) == calibration['learning_calibration_sha256']
    for path, digest in metadata['source_sha256'].items():
        assert file_digest(ROOT/path) == digest, 'comparison source changed'
    for key, path in (
        ('dataset_sha256', ROOT/'data/external/secodeplt/secodeplt/data.json'),
        ('family_manifest_sha256', ROOT/'data/external/secodeplt/derived_metadata/family_manifest.json'),
        ('pools_sha256', ROOT/manifest['input_pools'])):
        assert file_digest(path) == metadata[key], 'evaluation input changed: '+key
    checks.update(cwe_q_pair_distributions_preserved=True, card_content_unchanged=True,
                  source_memory_unchanged=True, learning_calibration_unchanged=True,
                  dataset_families_pools_unchanged=True)
    write(root/'format_check.json', checks)
    rows = read_rows(run/'rows.jsonl')
    by_task = {(str(row['task_id']), row['arm']): row for row in rows}
    if metadata['args'].get('shared_initial'):
        for identity in manifest['development']:
            first = [by_task[(str(identity), arm)]['attempts'][0] for arm in ARMS]
            traces = [a.get('retrieval_trace') or {} for a in first]
            assert all(t.get('status') == 'completed' for t in traces), 'shared retrieval incomplete'
            assert len({t['query_hash'] for t in traces}) == 1, 'shared query mismatch'
            projected = [[(s['id'], s['cosine']) for s in t['scores']] for t in traces]
            assert projected[0] == projected[1] == projected[2], 'shared candidates mismatch'
        checks.update(shared_initial_queries_candidates_equal=True)
        write(root/'format_check.json', checks)
    summary = json.loads((run/'summary.json').read_text(encoding='utf-8'))
    cost = json.loads((run/'cost.json').read_text(encoding='utf-8'))
    banks = {'Q1': {n.invariant_id: n for n in original}, 'Q2': {n.invariant_id: n for n in original},
             'Q3': {n.invariant_id: n for n in placebo}}
    attempts = [item for row in rows for item in attempt_readout(row, banks, calibration['delta'], calibration['lambda_q'])]
    write(root/'attempt_analysis.json', attempts)
    paired = {'Q2_vs_Q1': paired_effect(rows, 'Q1', 'Q2'), 'Q2_vs_Q3': paired_effect(rows, 'Q3', 'Q2')}
    for item, adjusted in zip(paired.values(), holm([item['p_exact_two_sided'] for item in paired.values()])):
        item['p_holm_two_planned'] = adjusted
    funnel, costs = {}, {}
    for arm in ARMS:
        items = [a for a in attempts if a['arm'] == arm]
        count_tasks = lambda key: len({a['task_id'] for a in items if a[key]})
        funnel[arm] = {'attempts': len(items),
            'empty_gate_attempts': sum(a['retrieval_status'] == 'completed' and not a['eligible_count'] for a in items),
            'retrieval_failed_attempts': sum(a['retrieval_status'] == 'error' for a in items),
            'retrieval_errors': dict(Counter(e for a in items for e in a['retrieval_errors'])),
            'candidate_cards': sum(a['candidate_count'] for a in items),
            'eligible_cards': sum(a['eligible_count'] for a in items),
            'selected_cards': sum(len(a['actual_ranked_ids']) for a in items),
            'adopted_cards': sum(len(a['adopted_ids']) for a in items),
            'nonzero_q_adopted_cards': sum(len(a['nonzero_q_adopted']) for a in items),
            'trained_candidate_tasks': count_tasks('trained_candidates'),
            'trained_eligible_tasks': count_tasks('trained_eligible'),
            'set_changed_tasks': count_tasks('set_changed_vs_sim'),
            'order_changed_tasks': count_tasks('order_changed_vs_sim'),
            'new_card_adopted_tasks': count_tasks('new_cards_adopted'),
            'ranking_changed_with_adoption_tasks': len({a['task_id'] for a in items if a['order_changed_vs_sim'] and a['adopted_ids']}),
            'workflow_incomplete_attempts': sum(not a['workflow_completed'] for a in items),
            'adoption_errors': dict(Counter(a['adoption_error'] for a in items if a['adoption_error']))}
        usage = cost['llm']['by_label'][arm+'.pipeline']
        arm_rows = [r for r in rows if r['arm'] == arm]
        assert usage['calls'] == sum(r['usage']['calls'] for r in arm_rows)
        assert usage['total_tokens'] == sum(r['usage']['total_tokens'] for r in arm_rows)
        costs[arm] = {**usage, 'summed_job_seconds': sum(r['elapsed_seconds'] for r in arm_rows),
                      'currency_actual': None}
    tasks = []
    for identity in manifest['development']:
        key = str(identity)
        current = [by_task[(key, arm)] for arm in ARMS]
        q2_mechanism = [a for a in attempts if a['task_id'] == key and a['arm'] == 'Q2']
        c0_queries = {a['arm']: a['query_hash'] for a in attempts if a['task_id'] == key and a['attempt'] == 0}
        tasks.append({'task_id': key, 'cwe': current[0]['cwe'], 'family_id': current[0]['family_id'],
            'outcomes': {r['arm']: {**{k: r['final'][k] for k in ('functional', 'security', 'joint', 'measured')},
                        'attempts': len(r['attempts']), 'error_type': r['error_type'], 'usage': r['usage']} for r in current},
            'Q2_set_changed': any(a['set_changed_vs_sim'] for a in q2_mechanism),
            'Q2_order_changed': any(a['order_changed_vs_sim'] for a in q2_mechanism),
            'Q2_new_cards_adopted': sorted({i for a in q2_mechanism for i in a['new_cards_adopted']}),
            'Q1_Q2_c0_query_equal': bool(c0_queries.get('Q1')) and c0_queries.get('Q1') == c0_queries.get('Q2'),
            'Q1_Q2_final_code_equal': current[0]['final']['code'] == current[1]['final']['code'],
            'Q2_vs_Q1': 'rescue' if current[1]['final']['joint'] and not current[0]['final']['joint'] else
                           'harm' if current[0]['final']['joint'] and not current[1]['final']['joint'] else 'tie'})
    q2 = summary['arms']['Q2']
    gate_spec = manifest['evaluation_progression_gate']
    gate = {'measured_each_arm': all(summary['arms'][a]['measured'] == len(tasks) for a in ARMS),
            'min_changed_tasks_Q2': funnel['Q2']['set_changed_tasks'] >= gate_spec['min_changed_tasks_Q2'],
            'min_changed_new_card_adopted_tasks_Q2': funnel['Q2']['new_card_adopted_tasks'] >= gate_spec['min_changed_new_card_adopted_tasks_Q2'],
            'workflow_errors_each_arm_max': all(summary['arms'][a]['errors'] <= gate_spec['workflow_errors_each_arm_max'] for a in ARMS),
            'Q2_joint_greater_than_Q1': q2['joint'] > summary['arms']['Q1']['joint'],
            'Q2_joint_greater_than_Q3': q2['joint'] > summary['arms']['Q3']['joint'],
            'Q2_functional_at_least_Q1': q2['functional'] >= summary['arms']['Q1']['functional']}
    result = {'protocol': manifest['protocol'], 'role': manifest['role'], 'branch': 'fjy/cle-memory-q-batch2',
        'git_commit': metadata['git_commit'], 'manifest': manifest, 'checks': checks,
        'arms': summary['arms'], 'paired_full_denominator': paired, 'paired_complete_measured': summary['paired'],
        'funnel': funnel, 'tasks': tasks, 'predeclared_development_gate': gate, 'development_gate_passed': all(gate.values()),
        'cost': {'by_arm': costs, 'llm_total': cost['llm']['total'], 'embedding_shared': cost['embedding'],
            'shared_initial': cost['llm']['by_label'].get('shared_initial.pipeline'),
            'wall_seconds': metadata['wall_seconds'], 'currency_actual': None,
            'legacy_pricing_source': cost['llm']['pricing_source'],
            'note': 'Logical LLM requests; usage from provider; legacy cost_ca is an old-rate estimate, not a bill. Embedding is shared and not assigned to arms.'},
        'post_run_actions': 'none; no additional learning, confirmation, full CLE or Base/Plus'}
    write(root/'analysis.json', result)
    curated.mkdir(parents=True, exist_ok=True)
    write(curated/'summary.json', result)
    fields = ['task_id', 'family_id', 'cwe', 'arm', 'functional', 'security', 'joint', 'measured', 'attempts',
              'error_type', 'calls', 'prompt_tokens', 'completion_tokens', 'total_tokens']
    with (curated/'task_scores.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for task in tasks:
            for arm, outcome in task['outcomes'].items():
                writer.writerow({**{k: task[k] for k in ('task_id', 'family_id', 'cwe')}, 'arm': arm,
                                 **{k: v for k, v in outcome.items() if k != 'usage'}, **{k: outcome['usage'][k] for k in
                                     ('calls', 'prompt_tokens', 'completion_tokens', 'total_tokens')}})
    public_attempts = [{k: v for k, v in a.items() if k != 'selected_scores'} for a in attempts]
    write(curated/'mechanism.json', public_attempts)
    lines = ['# 最新Q库8题三臂机制探针', '', '原生P7、同CWE打乱Q；仅D_gate开发诊断。', '',
             '| 臂 | n | F | S | Joint | 完整测量 | 流程错误 | 调用 | Token |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        item = summary['arms'][arm]
        lines.append('| '+arm+' | '+' | '.join(str(item[k]) for k in ('n','functional','security','joint','measured','errors','calls','total_tokens'))+' |')
    lines += ['', '逐题最终结果：F/S/J依次表示功能、安全及同时通过（1为通过）。', '',
              '| 题目 | CWE | Q1 F/S/J | Q2 F/S/J | Q3 F/S/J | Q2同查询集合变化 | 新卡实际采纳 |',
              '|---|---|---|---|---|---|---|']
    for task in tasks:
        states = ['/'.join(str(int(task['outcomes'][arm][k])) for k in ('functional','security','joint')) for arm in ARMS]
        lines.append('| '+task['task_id']+' | '+task['cwe']+' | '+' | '.join(states)+' | '+str(task['Q2_set_changed'])+' | '+str(len(task['Q2_new_cards_adopted']))+' |')
    lines += ['', '详细排序和采纳见mechanism.json；summary.json包含原生统计、全分母配对区间和成本。',
              'Q库和原学习配置未修改，未启动完整CLE、预留确认集或Base/Plus。',
              '货币费用未读取账单；cost_ca仅为仓库2026-09-18旧单价估算。']
    (curated/'README.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'checks': checks, 'arms': summary['arms'], 'funnel': funnel,
                      'paired': paired, 'development_gate': gate, 'cost': result['cost']}, ensure_ascii=False))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.root, args.out)
