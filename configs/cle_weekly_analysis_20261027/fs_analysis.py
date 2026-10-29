"""功能安全五条件分析：同代码四象限、配对迁移和题族聚类，全部零API。"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .analysis import RUN, read, write, metrics, cost_snapshot
from .retest_analysis import collect, compare

CONDITIONS = ('B0', 'BM', 'BF', 'BS', 'BFS')
QUADRANTS = ('both_pass', 'functional_only', 'security_only', 'both_fail', 'unmeasured')


def logical_cost_breakdown(segments):
    """按实际请求命名空间拆已知用量；物理未知消耗仍以累计预算另报。"""
    records = {}
    for segment in segments:
        for path in (Path(segment) / 'journals').glob('*/requests/*.json'):
            record = read(path)
            key = (path.parent.parent.name, record['identity'])
            if key in records and records[key] != record:
                raise ValueError('conflicting_logical_cost_record')
            records[key] = record
    costs = defaultdict(lambda: {'logical_requests': 0, 'known_reported_tokens': 0, 'unknown_usage_operations': 0})
    for (namespace, _), record in records.items():
        suffix = namespace.rsplit('_', 1)[-1]
        group = ('embedding' if namespace == 'embedding' else 'source_partition' if namespace.startswith('material_')
                 else 'shared_initial' if namespace.startswith('shared_initial_')
                 else 'shared_selection' if namespace.startswith('shared_selection_')
                 else suffix if suffix in CONDITIONS else 'other_common')
        item = costs[group]
        item['logical_requests'] += 1
        usage = (record.get('response') or {}).get('usage')
        if isinstance(usage, dict) and type(usage.get('total_tokens')) is int:
            item['known_reported_tokens'] += usage['total_tokens']
        else:
            item['unknown_usage_operations'] += 1
    return {'namespaces': dict(costs), 'shared_not_charged_again_to_each_arm': True,
            'physical_retries_and_unknown_usage': 'separately preserved in cumulative cost_snapshot; not assumed zero',
            'old_reused_material_costs': 'not counted as new paid usage'}


def quadrant(final):
    if not final.get('measured'):
        return 'unmeasured'
    return ('both_pass' if final.get('security') else 'functional_only') if final.get('functional') else (
        'security_only' if final.get('security') else 'both_fail')


def analyze(rows, planned_tasks=298):
    by = {(str(r['task_id']), r['repeat'], r['condition']): r for r in rows}
    arms = {}
    for condition in CONDITIONS:
        items = [r for r in rows if r['condition'] == condition]
        counts = Counter(quadrant(r['final']) for r in items)
        arms[condition] = {'first': metrics([r['attempts'][0] for r in items], planned_tasks*2),
            'final': metrics([r['final'] for r in items], planned_tasks*2),
            'final_quadrants': {key: counts[key] for key in QUADRANTS},
            'declared_adopted_positions': sum(len(a.get('generation', {}).get('cards', [])) for r in items for a in r['attempts'])}
    comparisons = []
    cases = []
    for treated, control in [('BFS', 'BM'), ('BM', 'B0'), ('BF', 'BM'), ('BS', 'BM')]:
        value = compare(rows, treated, control, planned_tasks)
        value.update(primary=treated == 'BFS' and control == 'BM',
                     scope='same D_gate tasks and original P7; presentation intervention, not independently constructed dual libraries')
        transitions = {a: {b: 0 for b in QUADRANTS} for a in QUADRANTS}
        fs_tradeoff = 0
        for task, repeat in sorted({(k[0], k[1]) for k in by}):
            a, b = by.get((task, repeat, treated)), by.get((task, repeat, control))
            if a is None or b is None:
                continue
            qa, qb = quadrant(a['final']), quadrant(b['final'])
            transitions[qb][qa] += 1
            if qa == 'security_only' and qb == 'functional_only':
                fs_tradeoff += 1
            if qa == 'unmeasured' or qb == 'unmeasured':
                category = 'missing_measurement'
            elif a['final']['joint'] and not b['final']['joint']:
                category = 'joint_rescue'
            elif not a['final']['joint'] and b['final']['joint']:
                category = 'joint_loss'
            elif a['final']['functional'] != b['final']['functional'] or a['final']['security'] != b['final']['security']:
                category = 'functional_security_tradeoff'
            else:
                continue
            if sum(c['treated'] == treated and c['control'] == control and c['category'] == category for c in cases) < 2:
                cases.append({'task_id': task, 'family_id': a['family_id'], 'repeat': repeat,
                    'treated': treated, 'control': control, 'category': category,
                    'treated_quadrant': qa, 'control_quadrant': qb,
                    'cause': None, 'code_implementation': None, 'review_status': 'pending_actual_public_card_plan_code_validation_review'})
        value.update(quadrant_transitions_control_to_treated=transitions,
            security_gain_with_functional_loss_observations=fs_tradeoff,
            tradeoff_is_not_automatically_overdefense=True)
        comparisons.append(value)
    groups = defaultdict(list)
    for r in rows:
        if r['condition'] != 'B0':
            groups[str(r['task_id']), r['repeat']].append(r)
    same = mismatched = incomplete = 0
    for group in groups.values():
        sources = []
        for r in group:
            trace = r['attempts'][0].get('retrieval_trace') or {}
            if trace.get('status') == 'completed' and 'pre_view_selected_ids' in trace:
                sources.append(trace['pre_view_selected_ids'])
        if len(sources) != 4:
            incomplete += 1
        elif all(s == sources[0] for s in sources[1:]):
            same += 1
        else:
            mismatched += 1
    return {'arms': arms, 'comparisons': comparisons,
            'common_first_source_selection': {'verified_groups': same, 'mismatched_groups': mismatched,
                                             'incomplete_groups': incomplete},
            'attribution_boundary': 'actual case review required; quadrant fields do not establish missing contract, source migration or overdefense'}, cases


def run(root=RUN):
    package = root / 'FFS'
    inputs = package / 'inputs'
    index = package / 'execution_index.json'
    segments = [Path(p) for p in read(index)['segments']] if index.exists() else []
    schedule = read(inputs / 'schedule.json') if (inputs / 'schedule.json').exists() else []
    rows, paths, copies = collect(segments, schedule) if segments else ([], {}, 0)
    out = package / 'analysis'
    if not rows:
        result = {'status': 'not_started', 'planned': 2980, 'completed': 0, 'results': None, 'paid_calls_by_analysis': 0}
        write(out / 'summary.json', result)
        write(out / 'case_review_queue.json', [])
        (out / 'analysis.md').write_text('# 全D_gate功能安全五条件分析\n\n当前无真实五条件代码记录，尚不形成成绩或收益结论。来源材料复用和离线接线不计入2980格完成数。\n', encoding='utf-8')
        return result
    result, cases = analyze(rows)
    complete = (len(rows) == len(schedule) == 2980 and len({r['task_id'] for r in rows}) == 298
                and read(segments[-1] / 'state.json')['status'] == 'completed')
    for c in cases:
        c['treated_row_path'] = paths[f'{c["task_id"]}_r{c["repeat"]}_{c["treated"]}']
        c['control_row_path'] = paths[f'{c["task_id"]}_r{c["repeat"]}_{c["control"]}']
    result.update(status='completed' if complete else 'partial', planned=2980, completed=len(rows),
                  identical_duplicate_row_copies=copies, costs=cost_snapshot(segments),
                  logical_cost_by_stage_or_arm=logical_cost_breakdown(segments),
                  observed_utc=datetime.now(timezone.utc).isoformat(), paid_calls_by_analysis=0)
    write(out / 'summary.json', result)
    write(out / 'case_review_queue.json', cases)
    lines = ['# 全D_gate功能安全五条件分析', '',
        f"当前{'完整' if complete else '部分'}保存{len(rows)}/2980格。主要比较BFS分栏对BM原经验，其余为机制诊断。", '',
        '| 条件 | 完成 | 最终F/S/Joint | 完整可测 | F过S不过 | S过F不过 |', '|---|---:|---|---:|---:|---:|']
    for arm in CONDITIONS:
        f, q = result['arms'][arm]['final'], result['arms'][arm]['final_quadrants']
        lines.append(f"| {arm} | {f['completed']} | {f['functional']}/{f['security']}/{f['joint']} | {f['measured']} | {q['functional_only']} | {q['security_only']} |")
    lines += ['', '四象限（同一份代码功能和安全是否分别通过）及配对迁移表已保存。完整配对用于救回/损失和按真实family聚类的差值区间；缺测单列，两重复不作为两倍独立题目。', '',
        '安全通过但功能失败是待解释现象，不能仅据布尔值判断为过度防御。需要实际阅读公开题面、来源卡、计划、代码和验证，区分公开契约、来源假设和模型实现等原因。来源分区的AI或规则方法保留其不确定性，不等同于人工金标准或已实现独立功能/安全双库。', '',
        '本分析新发API请求0次，成本读取最近恢复段累计预算，不能叠加各段总数。下一步完成固定全部五条件、零API回放和代表案例复核；低Joint不取消固定实验。']
    (out / 'analysis.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, default=RUN)
    result = run(parser.parse_args().run_root)
    print(json.dumps({k: result[k] for k in ('status', 'completed', 'planned', 'paid_calls_by_analysis')}))


if __name__ == '__main__':
    main()
