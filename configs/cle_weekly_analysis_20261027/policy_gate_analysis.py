"""记忆档位三策略迁移分析：同题配对、真实题族区间和复用后的实际费用。"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .analysis import RUN, read, write, metrics, cost_snapshot
from .retest_analysis import collect, compare

POLICIES = ('fixed', 'rule', 'classifier')


def analyze(rows, planned_tasks=298):
    """策略格保留全部成绩；同题同档复用只减少实际调用，不增加独立样本。"""
    arms = {}
    for policy in POLICIES:
        items = [row for row in rows if row['condition'] == policy]
        repeats = defaultdict(dict)
        for row in items:
            repeats[str(row['task_id'])][row['repeat']] = row['final']
        complete_repeats = [value for value in repeats.values() if set(value) == {1, 2}
                            and all(a.get('measured') for a in value.values())]
        arms[policy] = {'first': metrics([r['attempts'][0] for r in items], planned_tasks * 2),
            'final': metrics([r['final'] for r in items], planned_tasks * 2),
            'selected_levels': dict(Counter(r['selected_level'] for r in items)),
            'repeat_variability': {'both_measured_tasks': len(complete_repeats),
                'Joint_discordant_tasks': sum(v[1]['joint'] != v[2]['joint'] for v in complete_repeats)}}
    comparisons = [compare(rows, 'classifier', control, planned_tasks) for control in ('fixed', 'rule')]
    observed = sorted([c for c in comparisons if c['p_family_swap'] is not None], key=lambda c: c['p_family_swap'])
    previous = 0.
    for index, item in enumerate(observed):
        previous = max(previous, min(1., item['p_family_swap'] * (2 - index)))
        item['p_holm_two_primary'] = previous
    by = {(str(r['task_id']), r['repeat'], r['condition']): r for r in rows}
    cases, level_pairs = [], {}
    for control, value in zip(('fixed', 'rule'), comparisons):
        value['scope'] = 'frozen training-family model on D_gate; matched task-repeat with true family clustering'
        same = different = 0
        for task, repeat in sorted({(key[0], key[1]) for key in by}):
            left, right = by.get((task, repeat, 'classifier')), by.get((task, repeat, control))
            if left is None or right is None:
                continue
            equal = left['selected_level'] == right['selected_level']
            same += equal
            different += not equal
            if not left['final'].get('measured') or not right['final'].get('measured'):
                category = 'missing_measurement'
            elif left['final']['joint'] and not right['final']['joint']:
                category = 'joint_rescue'
            elif not left['final']['joint'] and right['final']['joint']:
                category = 'joint_loss'
            elif not equal:
                category = 'changed_level_same_joint'
            else:
                continue
            if sum(c['control'] == control and c['category'] == category for c in cases) < 2:
                cases.append({'task_id': task, 'family_id': left['family_id'], 'repeat': repeat,
                    'treated': 'classifier', 'control': control, 'category': category,
                    'treated_level': left['selected_level'], 'control_level': right['selected_level'],
                    'cause': None, 'code_implementation': None,
                    'review_status': 'pending_actual_public_card_plan_code_validation_review'})
        level_pairs[control] = {'same_level_pairs': same, 'different_level_pairs': different}
    starts = defaultdict(list)
    for row in rows:
        starts[str(row['task_id']), row['repeat']].append(row)
    complete_starts = mismatched_starts = incomplete_starts = 0
    for group in starts.values():
        if {r['condition'] for r in group} != set(POLICIES):
            incomplete_starts += 1
        elif any(not r.get('first_start_identity') for r in group) or len({r.get('first_start_identity') for r in group}) != 1:
            mismatched_starts += 1
        else:
            complete_starts += 1
    unique_levels = {(str(r['task_id']), r['repeat'], r['selected_level']) for r in rows}
    canonical = {r.get('canonical_generation_cell', r['cell_id']) for r in rows}
    result = {'arms': arms, 'primary_comparisons': comparisons,
        'routing_level_comparisons': level_pairs,
        'common_first_start': {'verified_groups': complete_starts, 'mismatched_groups': mismatched_starts,
            'incomplete_groups': incomplete_starts},
        'logical_policy_cells': len(rows), 'unique_task_repeat_level_runs': len(unique_levels),
        'canonical_generation_cells': len(canonical),
        'reused_logical_cells': sum(bool(r.get('result_reused')) for r in rows),
        'billing_uses_physical_cumulative_ledger_not_sum_of_reused_row_usage': True,
        'two_repeats_clustered_by_true_family': True,
        'statistical_direction_supported': all(c['difference'] is not None and c['difference'] > 0
            and c.get('p_holm_two_primary', 1.) <= .05 for c in comparisons),
        'interpretation': 'routing performance, not proof of a uniquely correct memory degree; two observed outcomes form noisy labels'}
    return result, cases


def run(root=RUN):
    package = root / 'FG_GATE'
    inputs = package / 'inputs'
    index = package / 'execution_index.json'
    segments = [Path(p) for p in read(index)['segments']] if index.exists() else []
    schedule = read(inputs / 'schedule.json') if (inputs / 'schedule.json').exists() else []
    rows, paths, duplicates = collect(segments, schedule) if segments else ([], {}, 0)
    out = package / 'analysis'
    if not rows:
        result = {'status': 'not_started', 'planned': 1788, 'completed': 0,
            'results': None, 'paid_calls_by_analysis': 0}
        write(out / 'summary.json', result)
        write(out / 'case_review_queue.json', [])
        (out / 'analysis.md').write_text('# 全D_gate记忆档位三策略分析\n\n当前无真实三策略记录。先完成273题五档两重复、回放及按题族训练，再消费新冻结模型；准备1788格不能记作已完成或分类器有效。\n', encoding='utf-8')
        return result
    result, cases = analyze(rows)
    complete = (len(rows) == len(schedule) == 1788 and len({r['task_id'] for r in rows}) == 298
                and read(segments[-1] / 'state.json')['status'] == 'completed')
    for case in cases:
        case['treated_row_path'] = paths[f'{case["task_id"]}_r{case["repeat"]}_classifier']
        case['control_row_path'] = paths[f'{case["task_id"]}_r{case["repeat"]}_{case["control"]}']
    result.update(status='completed' if complete else 'partial', planned=1788, completed=len(rows),
        identical_duplicate_row_copies=duplicates, costs=cost_snapshot(segments),
        observed_utc=datetime.now(timezone.utc).isoformat(), paid_calls_by_analysis=0)
    write(out / 'summary.json', result)
    write(out / 'case_review_queue.json', cases)
    lines = ['# 全D_gate记忆档位三策略分析', '',
        f"当前{'完整' if complete else '部分'}保存{len(rows)}/1788个策略格，同题同重复同档的代码只生成一次。", '',
        '| 策略 | 完成 | 最终F/S/Joint | 完整可测 | 选择档位分布 |', '|---|---:|---|---:|---|']
    for policy in POLICIES:
        arm = result['arms'][policy]
        final = arm['final']
        lines.append(f"| {policy} | {final['completed']} | {final['functional']}/{final['security']}/{final['joint']} | {final['measured']} | {arm['selected_levels']} |")
    lines += ['', '| 主要比较 | 完整配对 | 救回/损失 | Joint差 | family 95%区间 | Holm校正p |',
        '|---|---:|---|---|---|---|']
    for value in result['primary_comparisons']:
        lines.append(f"| classifier−{value['control']} | {value['measured_pairs']} | {value['wins']}/{value['losses']} | {value['difference']} | {value['ci95_family_bootstrap']} | {value.get('p_holm_two_primary')} |")
    lines += ['', '分类器与训练集选择的固定档位、原公开规则分别比较，两项主要检验作Holm校正。两重复按真实family整体重采样和置换，不视作两倍独立题目。不同策略路由到同档时精确复用整条轨迹，因此同档结果相同来自实验设计；不用于宣称生成模型没有波动。', '',
        f"当前{result['logical_policy_cells']}个逻辑策略格对应{result['unique_task_repeat_level_runs']}次不同题/重复/档位运行，{result['reused_logical_cells']}格复用了相同档位结果。实际费用只取累计物理请求记录，不重复相加策略行内usage；共享初析、选卡和模板材料同样纳入实际累计成本。", '',
        '五档两重复只提供有限观测的训练标签，不能称作题目的唯一正确记忆程度。分类器改变档位是否帮助功能与安全，需要结合实际卡片、计划、代码和验证判断；待审队列保留原因空白。本分析不发API，未显著不代表策略等效。']
    (out / 'analysis.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, default=RUN)
    result = run(parser.parse_args().run_root)
    print(json.dumps({key: result[key] for key in ('status', 'completed', 'planned', 'paid_calls_by_analysis')}))


if __name__ == '__main__':
    main()
