"""为Pro网页版审阅汇总既有实验；流式复算末次成绩，不调用API、不更新Q。"""
from collections import Counter, defaultdict
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'translation_work/diagnostics/20261019/cle_memory_q/pro_closeout'
CURATED = ROOT / 'results/curated/cle_q_pro_closeout_20261019'


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def brief(value):
    """删除逐题长数组；数值不改变，原件位置保留供复核。"""
    if isinstance(value, list):
        return [brief(v) for v in value] if len(value) <= 8 else {'items': len(value)}
    if isinstance(value, dict):
        return {k: brief(v) for k, v in value.items()
                if k not in {'task_pairs', 'workflow_errors', 'technical_errors', 'rescue_tasks', 'loss_tasks'}}
    return value


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    CURATED.mkdir(parents=True, exist_ok=True)
    gate = 'translation_work/diagnostics/20261019/cle_memory_q/full_gate_cap3_v4/rows.jsonl'
    counts = defaultdict(Counter)
    paired = defaultdict(dict)
    with (ROOT / gate).open(encoding='utf-8') as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            final = row['attempts'][-1]
            counts[row['arm']]['n'] += 1
            for key in ('functional', 'security', 'joint', 'measured'):
                counts[row['arm']][key] += bool(final.get(key))
            paired[str(row['task_id'])][row['arm']] = {
                'joint': final.get('joint'), 'measured': final.get('measured'), 'family_id': row['family_id']}
    primary = read('results/curated/cle_memory_q_full_gate_cap3_20261019/final_analysis.json')
    source_summary = read('results/curated/cle_memory_q_full_gate_cap3_20261019/summary.json')
    for arm, count in counts.items():
        for key in ('n', 'functional', 'security', 'joint', 'measured'):
            assert count[key] == source_summary['arms'][arm][key], (arm, key)
    pair_counts = {}
    for control in ['Q0', 'Q1', 'Q3']:
        complete = [v for v in paired.values() if v['Q2']['measured'] and v[control]['measured']]
        wins = sum(v['Q2']['joint'] and not v[control]['joint'] for v in complete)
        losses = sum(v[control]['joint'] and not v['Q2']['joint'] for v in complete)
        expected = next(p for p in primary['primary'] if p['control'] == control)
        assert (len(complete), wins, losses) == (expected['measured_pairs'], expected['wins'], expected['losses'])
        pair_counts[control] = {'measured_pairs': len(complete), 'wins': wins, 'losses': losses,
                                'net': wins - losses, 'p_holm': expected['p_holm'],
                                'ci95_family_bootstrap': expected['ci95_family_bootstrap']}
    sources = {
        'unlimited': 'results/curated/cle_memory_q_unlimited_complete_20261018/analysis.json',
        'Q0_addendum': 'results/curated/cle_memory_q_unlimited_gate_q0_20261019/summary.json',
        'equal_K': 'results/curated/cle_memory_q_equal_k_20261019/analysis.json',
        'selection_repeat': 'results/curated/cle_selector_repeat_20261019/summary.json',
        'coverage': 'results/curated/cle_q_coverage_20261019/coverage_summary.json',
        'coverage_probe': 'results/curated/cle_q_coverage_learning_v2_20261019/summary.json',
        'Dinit': 'results/curated/cle_memory_q_dinit_20261019/summary.json'}
    extras = {}
    for name, path in sources.items():
        value = read(path)
        if name == 'unlimited':
            value = {'protocol': value['protocol'], 'total_P7_rows': value['total_P7_rows'],
                     'stage_arms': {k: v['native']['arms'] for k, v in value['stages'].items()},
                     'Q_coverage': value['Q_coverage']}
        extras[name] = {'source': path, 'data': brief(value)}
    evidence = {'operation': 'existing_result_review_no_API', 'raw_gate_source': gate,
                'native_gate_rows_verified': sum(c['n'] for c in counts.values()),
                'native_gate_counts': dict(counts), 'native_gate_pairs': pair_counts,
                'gate_primary_source': 'results/curated/cle_memory_q_full_gate_cap3_20261019/final_analysis.json',
                'gate_summary_source': 'results/curated/cle_memory_q_full_gate_cap3_20261019/summary.json',
                'gate_costs': source_summary['total_llm_cost'], 'known_cost_is_lower_bound': True,
                'other_evidence': extras, 'new_API_calls': 0, 'new_Q_updates': 0}
    text = json.dumps(evidence, ensure_ascii=False, indent=2) + '\n'
    (OUT / 'evidence.json').write_text(text, encoding='utf-8')
    (CURATED / 'evidence.json').write_text(text, encoding='utf-8')
    print(json.dumps({'verified_rows': evidence['native_gate_rows_verified'], 'arms': dict(counts),
                      'pairs': pair_counts, 'bytes': len(text.encode('utf-8')), 'new_API_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
