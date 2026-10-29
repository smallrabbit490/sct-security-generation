"""零API连接38例历史救损与PR5静态契约标记，预先固定开发题；不改旧成绩。"""
from pathlib import Path
from collections import Counter
import csv
import json
from math import comb

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).resolve().parent
OUT = ROOT / 'results/curated/cle_contract_q_20261023'


def fisher_exact(table):
    """固定边际的双侧Fisher精确检验；零格的无穷OR用null及文字解释保存。"""
    (a, b), (c, d) = table
    first, positives, total = a + b, a + c, a + b + c + d
    denominator = comb(total, first)
    probability = lambda x: comb(positives, x) * comb(total - positives, first - x) / denominator
    observed = probability(a)
    p = sum(probability(x) for x in range(max(0, first - total + positives), min(first, positives) + 1)
            if probability(x) <= observed + 1e-12)
    ratio = a * d / (b * c) if b * c else None
    infinite = bool(a * d and not b * c)
    return {'table_loss_rescue_by_flag': table, 'odds_ratio': ratio,
            'odds_ratio_infinite': infinite, 'two_sided_p': min(1.0, p),
            'proposal_gate_passed': (infinite or ratio is not None and ratio >= 3) and p <= .10}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    from methods.cle_ablation.run_joint_contract import load_explicit_tasks, select_tasks
    from methods.sct_trajectory.public_contract_checks import compile_public_contract
    pairs_path = ROOT / 'results/curated/cle_q_dinit_selection_joint_20261021/per_task.csv'
    audit_path = ROOT / 'results/curated/cle_joint_contract_20261022/public_contract_audit.json'
    with pairs_path.open(encoding='utf-8-sig', newline='') as f:
        original = list(csv.DictReader(f))
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    flags = {str(row['task_id']): row for row in audit['flagged_finals']}
    tasks = {str(t['index']): t for t in load_explicit_tasks(
        ROOT / 'translation_work/diagnostics/20261020/cle_q_online_v1/tasks_D_init.json', 'PLT')}
    cases = []
    for row in original:
        old, new = row['old_joint'] == 'True', row['new_joint'] == 'True'
        if old == new:
            continue
        tid = row['task_id']
        rules = compile_public_contract(tasks[tid]['task_description'])
        flag = flags.get(tid, {})
        cases.append({'task_id': tid, 'transition': 'rescue' if new else 'loss',
            'old_joint': old, 'new_joint': new, 'both_measured': row['both_measured'] == 'True',
            'new_static_flag': bool(flag), 'violation_ids': flag.get('violation_ids', []),
            'pre_generation_explicit_bindings': bool(rules['protected_bindings']),
            'pre_generation_signature_known': bool(rules['signature']),
            'verified_global_defect': row['new_verified_global_defect'] == 'True'})
    assert Counter(c['transition'] for c in cases) == {'rescue': 20, 'loss': 18}

    def compare(items, field):
        return fisher_exact([[sum(c['transition'] == outcome and bool(c[field]) == flag for c in items)
                              for flag in (True, False)] for outcome in ('loss', 'rescue')])

    result = {'operation': 'historical_post_outcome_association_not_new_policy_scores',
        'source_pairs': str(pairs_path.relative_to(ROOT)), 'source_static_audit': str(audit_path.relative_to(ROOT)),
        'primary_38': compare(cases, 'new_static_flag'),
        'complete_measurement_sensitivity': compare([c for c in cases if c['both_measured']], 'new_static_flag'),
        'pre_generation_binding_signal': compare(cases, 'pre_generation_explicit_bindings'),
        'pre_generation_signature_signal': compare(cases, 'pre_generation_signature_known'),
        'cases': cases, 'new_API_calls': 0, 'new_Joint_scores': 0,
        'limits': ['Static flags depend on generated code and cannot be used as pre-generation route inputs.',
                   'The 38 outcomes are selected historical disagreements, not an independent validation set.',
                   'No threshold search, card learning or reinterpretation of old scores as new-policy scores.']}
    # 单个历史分组即使偶然相关，也没有独立验证；不据此发明候选Q阈值。
    policy = {'version': 'conditional-q-public-v1', 'enabled': False, 'rules': [],
        'reason': 'No independently validated pre-generation routing signal; keep Q route disabled.',
        'historical_contract_enrichment_gate': result['primary_38']['proposal_gate_passed'],
        'allowed_features': ['explicit_external_binding', 'signature_known', 'visited_fraction',
                             'negative_q_fraction', 'max_visits', 'normalized_rank_displacement'],
        'forbidden_inputs': ['F', 'S', 'Joint', 'generated_code', 'adoption', 'hidden_tests', 'reference']}
    gate_source = ROOT / 'translation_work/diagnostics/20261020/cle_q_online_v1/tasks_D_gate.json'
    gate_tasks = sorted(load_explicit_tasks(gate_source, 'PLT'), key=lambda t: str(t['index']))
    selected = select_tasks(gate_tasks, 'PLT', 48)
    assert len(selected) == len({t['family_id'] for t in selected}) == 48
    selected_path = ROOT / 'translation_work/diagnostics/20261023/cle_contract_q/tasks_D_gate_48.json'
    dump(selected_path, selected)
    manifest = {'dataset': 'PLT', 'pool': 'D_gate', 'historical_exposure': True,
        'selection': 'CWE round robin after string task ID sorting; at most one task per family',
        'source': str(gate_source.relative_to(ROOT)), 'tasks': [
            {'task_id': str(t['index']), 'family_id': t['family_id'], 'cwe': str(t['CWE_ID'])} for t in selected],
        'repeats': 2, 'requested_arms': ['P7', 'P7_public_contract_v1', 'P7_public_contract_q_conditional_v1'],
        'conditional_route_disabled': True, 'effective_arms': ['P7', 'P7_public_contract_v1'],
        'screening_only': True, 'paid_execution_authorized_by_attached_roadmap': False}
    manifest['selected_tasks_path'] = str(selected_path.relative_to(ROOT))
    dump(OUT / 'loss_contract_cross_table.json', result)
    dump(CONFIG / 'route_policy.json', policy)
    dump(CONFIG / 'manifest.json', manifest)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'historical_38_cases.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(cases[0]))
        writer.writeheader()
        writer.writerows({**c, 'violation_ids': json.dumps(c['violation_ids'])} for c in cases)
    print(json.dumps({k: result[k] for k in ('primary_38', 'complete_measurement_sensitivity',
        'pre_generation_binding_signal', 'pre_generation_signature_signal')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
