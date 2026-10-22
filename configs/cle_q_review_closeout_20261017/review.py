"""零 API 复审既有 Q 原生记录；只写本轮派生产物，不运行生成或验证。"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from methods.cle_ablation.audit_memory_q import check_run, read_rows
from methods.cle_ablation.report_memory_q import paired_effect
from methods.cle_ablation.report_memory_q_probe import attempt_readout
from methods.cle_ablation.runner import load_memory
from methods.direction_screening.protocol import summarize
from methods.sct_trajectory.run_branch_gate_study import holm

OUT = ROOT / 'translation_work/diagnostics/20261017/cle_q_review_closeout'
CURATED = ROOT / 'results/curated/cle_q_review_closeout_20261017'
RUNS = {
    'autonomous24': 'translation_work/diagnostics/20261015/cle_memory_q/autonomous_v2/compare',
    'probe8': 'translation_work/diagnostics/20261016/cle_memory_q/probe8_cwe_shuffle/compare',
    'shared8': 'translation_work/diagnostics/20261016/cle_memory_q/shared_initial8/compare',
}
PACKAGES = {
    'autonomous24': 'cle_memory_q_autonomous_20261015',
    'probe8': 'cle_memory_q_probe8_20261016',
    'shared8': 'cle_memory_q_shared_initial8_20261016',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def funnel(records):
    tasks = lambda key: len({r['task_id'] for r in records if r[key]})
    return {
        'attempts': len(records),
        'empty_gate_attempts': sum(r['retrieval_status'] == 'completed' and not r['eligible_count'] for r in records),
        'retrieval_failed_attempts': sum(r['retrieval_status'] == 'error' for r in records),
        'set_changed_tasks': tasks('set_changed_vs_sim'),
        'order_changed_tasks': tasks('order_changed_vs_sim'),
        'new_card_adopted_tasks': tasks('new_cards_adopted'),
        'first_query_set_changed_tasks': len({r['task_id'] for r in records if r['attempt'] == 0 and r['set_changed_vs_sim']}),
        'first_query_order_changed_tasks': len({r['task_id'] for r in records if r['attempt'] == 0 and r['order_changed_vs_sim']}),
        'trained_eligible_tasks': tasks('trained_eligible'),
    }


def review_comparison(name, relative):
    run = ROOT / relative
    check = check_run(run)
    rows = read_rows(run / 'rows.jsonl')
    metadata = read(run / 'run_metadata.json')
    stored = read(ROOT / 'results/curated' / PACKAGES[name] / 'summary.json')
    computed = summarize(rows, 'Q1')
    assert computed['arms'] == stored['arms']
    original, shuffled = load_memory(run / 'input_memory.jsonl'), load_memory(run / 'input_shuffled_memory.jsonl')
    strip = lambda n: {k: v for k, v in n.to_dict().items() if k not in ('q_value', 'q_visits')}
    assert [strip(n) for n in original] == [strip(n) for n in shuffled]
    scope = metadata['args'].get('shuffle_scope', 'global')
    groups = {n.cwe for n in original} if scope == 'cwe' else {None}
    for cwe in groups:
        pairs = lambda bank: Counter((n.q_value, n.q_visits) for n in bank if cwe is None or n.cwe == cwe)
        assert pairs(original) == pairs(shuffled)
    banks = {a: {n.invariant_id: n for n in bank} for a, bank in [('Q1', original), ('Q2', original), ('Q3', shuffled)]}
    records = [item for row in rows if row['arm'] == 'Q2'
               for item in attempt_readout(row, banks, metadata['delta'], metadata['args']['lambda_q'])]
    by_task = {(r['task_id'], r['arm']): r for r in rows}
    shared = metadata['args'].get('shared_initial', False)
    if shared:
        for identity in metadata['task_ids']:
            traces = [by_task[(str(identity), a)]['attempts'][0]['retrieval_trace'] for a in ('Q1', 'Q2', 'Q3')]
            assert len({t['query_hash'] for t in traces}) == 1
            scores = [[(s['id'], s['cosine']) for s in t['scores']] for t in traces]
            assert scores[0] == scores[1] == scores[2]
    paired = {base: paired_effect(rows, base, 'Q2') for base in ('Q1', 'Q3')}
    for result, p in zip(paired.values(), holm([p['p_exact_two_sided'] for p in paired.values()])):
        result['p_holm_two_planned'] = p
    tasks, rescues = [], []
    for identity in metadata['task_ids']:
        key = str(identity)
        task_records = [r for r in records if r['task_id'] == key]
        outcomes = {a: by_task[(key, a)]['final'] for a in computed['arms']}
        rescue = not outcomes['Q1']['joint'] and outcomes['Q2']['joint']
        selected = sum(len(a.get('generation', {}).get('retrieved_cards', []))
                       for row in rows if row['task_id'] == key for a in row['attempts'])
        adopted = sum(len(a.get('generation', {}).get('cards', []))
                      for row in rows if row['task_id'] == key for a in row['attempts'])
        task = {'run': name, 'task_id': key, 'family_id': by_task[(key, 'Q2')]['family_id'],
                'Q2_set_changed': any(r['set_changed_vs_sim'] for r in task_records),
                'Q2_order_changed': any(r['order_changed_vs_sim'] for r in task_records),
                'new_card_ids_adopted': sorted({i for r in task_records for i in r['new_cards_adopted']}),
                'Q2_rescue_vs_Q1': rescue, 'Q2_harm_vs_Q1': outcomes['Q1']['joint'] and not outcomes['Q2']['joint'],
                'all_arms_selected_card_exposures': selected, 'all_arms_adopted_card_exposures': adopted,
                'outcomes': {a: {k: f[k] for k in ('functional', 'security', 'joint', 'measured')} for a, f in outcomes.items()}}
        tasks.append(task)
        if rescue:
            rescues.append(task)
    f = funnel(records)
    assert f['set_changed_tasks'] == (stored['mechanism_changed_tasks'] if name == 'autonomous24' else stored['funnel']['Q2']['set_changed_tasks'])
    assert f['new_card_adopted_tasks'] == (stored['q_added_adopted_tasks'] if name == 'autonomous24' else stored['funnel']['Q2']['new_card_adopted_tasks'])
    if name == 'autonomous24':
        arms = computed['arms']
        old_gate = (arms['Q2']['joint'] > arms['Q1']['joint'] and arms['Q2']['functional'] >= arms['Q1']['functional']
                    and arms['Q2']['measured'] >= 23 and arms['Q2']['errors'] <= arms['Q1']['errors'])
        assert old_gate == stored['confirmation_gate_passed']
        gate = {'Q2_joint_greater_than_Q1': arms['Q2']['joint'] > arms['Q1']['joint'],
                'Q2_functional_at_least_Q1': arms['Q2']['functional'] >= arms['Q1']['functional'],
                'Q2_measured_at_least_23': arms['Q2']['measured'] >= 23,
                'Q2_errors_not_above_Q1': arms['Q2']['errors'] <= arms['Q1']['errors']}
    else:
        gate = {'measured_each_arm': all(v['measured'] == 8 for v in computed['arms'].values()),
                'min_changed_tasks_Q2': f['set_changed_tasks'] >= 3,
                'min_changed_new_card_adopted_tasks_Q2': f['new_card_adopted_tasks'] >= 2,
                'workflow_errors_each_arm_max': all(v['errors'] == 0 for v in computed['arms'].values()),
                'Q2_joint_greater_than_Q1': computed['arms']['Q2']['joint'] > computed['arms']['Q1']['joint'],
                'Q2_joint_greater_than_Q3': computed['arms']['Q2']['joint'] > computed['arms']['Q3']['joint'],
                'Q2_functional_at_least_Q1': computed['arms']['Q2']['functional'] >= computed['arms']['Q1']['functional']}
        assert gate == stored['predeclared_development_gate']
        old_gate = all(gate.values())
        assert old_gate == stored['development_gate_passed']
    cost = read(run / 'cost.json')
    result = {'protocol': stored['protocol'], 'source': relative, 'format_check': check,
              'arms': computed['arms'], 'paired': paired, 'Q2_funnel': f, 'rescues': rescues,
              'original_gate_checks': gate, 'original_gate_passed': old_gate,
              'shared_initial_candidates_verified': shared, 'shuffle_scope': scope,
              'metadata_Q_frozen': metadata['q_unchanged'], 'Q_bank_count': len(original),
              'delta': metadata['delta'], 'parameters': {k: metadata['args'][k] for k in ('max_tokens', 'thinking', 'lambda_q', 'embedding_model')},
              'cost': {'llm': cost['llm']['total'], 'embedding': cost['embedding'], 'wall_seconds': metadata['wall_seconds']}}
    return result, tasks, records, rows


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    results, task_records, mechanisms, native = {}, [], [], {}
    for name, relative in RUNS.items():
        results[name], tasks, records, native[name] = review_comparison(name, relative)
        task_records.extend(tasks)
        mechanisms.extend(dict(run=name, **r) for r in records)
    learning = {}
    for name, relative in [('learn8', 'translation_work/diagnostics/20261015/cle_memory_q/autonomous_v2/learn'),
                           ('full_dgrow', 'translation_work/diagnostics/20261016/cle_memory_q/full_dgrow')]:
        run = ROOT / relative
        check = check_run(run)
        cost, meta = read(run / 'cost.json'), read(run / 'run_metadata.json')
        learning[name] = {'source': relative, 'format_check': check,
                          'cost': {'llm': cost['llm']['total'], 'embedding': cost['embedding'], 'wall_seconds': meta['wall_seconds']}}
    full = ROOT / learning['full_dgrow']['source']
    nodes = read_rows(full / 'frozen/m_star_q.jsonl')
    for name in ('probe8', 'shared8'):
        assert read_rows(ROOT / RUNS[name] / 'input_memory.jsonl') == nodes, 'latest frozen Q bank differs'
    support = read(full / 'q_family_support.json')
    events = [e for e in read_rows(full / 'memory_q_events.jsonl') if e.get('reward') is not None and e.get('invariant_id')]
    assert len(events) == sum(n['q_visits'] for n in nodes)
    coverage = {'cards': len(nodes), 'visited': sum(n['q_visits'] > 0 for n in nodes),
                'at_least_two_families': sum(n['q_visits'] > 0 and len(support[n['invariant_id']]) >= 2 for n in nodes),
                'at_least_three_families': sum(n['q_visits'] > 0 and len(support[n['invariant_id']]) >= 3 for n in nodes),
                'positive_updates': sum(e['reward'] == 1 for e in events),
                'negative_updates': sum(e['reward'] == -1 for e in events)}
    learned_values = Counter('positive' if n['q_value'] > 0 else 'negative' if n['q_value'] < 0 else 'zero'
                             for n in nodes if n['q_visits'] > 0)
    coverage.update(learned_signs=dict(learned_values), visited_once=sum(n['q_visits'] == 1 for n in nodes))
    study = ROOT / 'translation_work/diagnostics/20261017/cle_retrieval_q/public_contract_v2'
    study_summary = read(study / 'summary.json')
    current = {'protocol': study_summary['protocol'], 'gate_B': read(study / 'gate_B.json'),
               'AI_labels': study_summary['model_labeled'], 'human_confirmed': study_summary['human_confirmed'],
               'development_run': study_summary['P7_development_run'], 'confirmation_run': study_summary['confirmation_run'],
               'execution_state': 'WAIT_HUMAN', 'performance_failure': False}
    assert current['human_confirmed'] == 0 and not current['development_run'] and not current['confirmation_run']
    # 已执行旧协议各自失败；当前待人工的新协议不反造为失败实验。
    assert all(not r['original_gate_passed'] for r in results.values())
    assert all(not t['Q2_order_changed'] and not t['new_card_ids_adopted'] for r in results.values() for t in r['rescues'])
    decision = {'protocol': 'cle-q-retrospective-closeout-v1', 'decision_protocol': 'cle-q-full-test-decision-v1',
                'status': 'STOP_INCONCLUSIVE', 'reason': 'historical_gates_failed_and_no_Q_attributable_rescue',
                'claim': '当前冻结Q方案收益未建立，不值得继续全量投入；未证明Q普遍无效。',
                'full_test_recommended': False, 'full_test_started': False, 'confirmation_started': False,
                'Q_updates': False, 'new_model_calls': 0, 'new_embedding_calls': 0,
                'new_dynamic_validations': 0, 'current_study': current, 'comparisons': results,
                'learning_checks': learning, 'Q_coverage': coverage,
                'retrospective_only': True, 'different_protocol_scores_pooled': False,
                'reviewed_native_rows': sum(r['format_check']['rows'] for r in results.values()) + sum(r['format_check']['rows'] for r in learning.values())}
    metadata = {'protocol': decision['protocol'], 'observed_at': datetime.now().astimezone().isoformat(),
                'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
                'HEAD': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'runner': 'configs/cle_q_review_closeout_20261017/review.py',
                'native_functions': ['audit_memory_q.check_run', 'direction_screening.protocol.summarize',
                                     'report_memory_q.paired_effect', 'report_memory_q_probe.attempt_readout'],
                'input_manifest': {**RUNS, **{k:v['source'] for k,v in learning.items()}},
                'tracked_and_untracked_source_changes_preexisting': True,
                'operation': 'read_only_reanalysis_no_API_no_validator', 'new_model_calls': 0, 'new_embedding_calls': 0}
    for directory in (OUT, CURATED):
        write(directory / 'summary.json', decision)
        write(directory / 'run_metadata.json', metadata)
        write(directory / 'paired_tasks.json', task_records)
    write(OUT / 'Q2_attempt_mechanisms.json', mechanisms)
    errors = [{'run': name, 'task_id': r['task_id'], 'arm': r['arm'], 'error_type': r['error_type'],
               'failed_calls': r['usage']['failed_calls']} for name, rows in native.items() for r in rows if r['error_type']]
    write(CURATED / 'workflow_errors.json', errors)
    # 仅将人工阅读需要的真实代码展开在忽略的运行区；不更改原始rows。
    cases = {'autonomous24': {'498', '606', '87'}, 'probe8': {'370', '612', '603', '96'},
             'shared8': {'1013', '777', '1015', '1000', '1055'}}
    case_index = []
    for name, ids in cases.items():
        for row in native[name]:
            if row['task_id'] not in ids or row['arm'] != 'Q2':
                continue
            for a in row['attempts']:
                target = OUT / 'code_examples' / f"{name}_{row['task_id']}_Q2_attempt{a['attempt']}.py"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(a['code'] + '\n', encoding='utf-8')
                case_index.append({'run': name, 'task_id': row['task_id'], 'arm': 'Q2', 'attempt': a['attempt'],
                                   'source_rows': RUNS[name] + '/rows.jsonl', 'code': str(target.relative_to(ROOT)).replace('\\', '/'),
                                   'adopted_ids': [c['invariant_id'] for c in a['generation'].get('cards', [])],
                                   **{k: a[k] for k in ('functional', 'security', 'joint')}})
    write(CURATED / 'code_example_index.json', case_index)
    with (CURATED / 'scores.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['run', 'arm', 'n', 'functional', 'security', 'joint', 'measured', 'errors', 'calls', 'total_tokens'])
        writer.writeheader()
        for name, result in results.items():
            for arm, counts in result['arms'].items():
                writer.writerow({'run': name, 'arm': arm, **{k: counts[k] for k in writer.fieldnames[2:]}})
    print(json.dumps({'status': decision['status'], 'reviewed_native_rows': decision['reviewed_native_rows'],
                      'old_gates': {k:v['original_gate_passed'] for k,v in results.items()},
                      'current_study': current['execution_state'], 'Q_coverage': coverage,
                      'new_model_calls': 0, 'curated': str(CURATED)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
