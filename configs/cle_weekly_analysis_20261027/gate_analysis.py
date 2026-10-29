"""全D_gate四臂零API分析；Q2对Q1/Q3为两项主要比较，Q0作原CLE参照。"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .analysis import RUN, read, write, metrics, cost_snapshot
from .retest_analysis import collect, compare, first_mechanism, review_queue

CONDITIONS = ('Q0', 'Q1', 'Q2', 'Q3')


def analyze(rows, planned_tasks=298):
    arms = {}
    for condition in CONDITIONS:
        items = [row for row in rows if row['condition'] == condition]
        by_task = defaultdict(dict)
        for row in items:
            by_task[str(row['task_id'])][row['repeat']] = row['final']
        measured_repeats = [value for value in by_task.values() if set(value) == {1, 2}
                            and all(a.get('measured') for a in value.values())]
        arms[condition] = {'first': metrics([r['attempts'][0] for r in items], planned_tasks*2),
            'final': metrics([r['final'] for r in items], planned_tasks*2),
            'repeat_variability': {'both_repeats_measured_tasks': len(measured_repeats),
                'joint_discordant_tasks': sum(v[1]['joint'] != v[2]['joint'] for v in measured_repeats)}}
    primary = [compare(rows, 'Q2', baseline, planned_tasks) for baseline in ('Q1', 'Q3')]
    observed = sorted([r for r in primary if r['p_family_swap'] is not None], key=lambda r: r['p_family_swap'])
    previous = 0.
    for index, item in enumerate(observed):
        previous = max(previous, min(1., item['p_family_swap']*(2-index)))
        item['p_holm_two_primary'] = previous
    secondary = compare(rows, 'Q2', 'Q0', planned_tasks)
    secondary['interpretation'] = 'original_CLE_system_reference; inspect presented candidate boundary before attribution'
    by = {(str(r['task_id']), r['repeat'], r['condition']): r for r in rows}
    mechanisms = []
    for task, repeat in sorted({(key[0], key[1]) for key in by}):
        for control in ('Q0', 'Q1', 'Q3'):
            a, b = by.get((task, repeat, 'Q2')), by.get((task, repeat, control))
            if a is not None and b is not None:
                item = first_mechanism(a, b)
                item['primary_controlled_comparison'] = control in ('Q1', 'Q3')
                ta = a['attempts'][0].get('retrieval_trace') or {}
                tb = b['attempts'][0].get('retrieval_trace') or {}
                item['same_presented_candidate_members'] = (set(ta.get('presented_candidate_ids', ta.get('candidate_ids', [])))
                    == set(tb.get('presented_candidate_ids', tb.get('candidate_ids', [])))) if item['both_retrieval_complete'] else None
                mechanisms.append(item)
    return {'arms': arms, 'primary_comparisons': primary, 'secondary_Q0_reference': secondary,
            'two_repeats_clustered_by_genuine_family': True,
            'statistical_direction_supported': all(c['difference'] is not None and c['difference'] > 0
                and c.get('p_holm_two_primary', 1.) <= .05 for c in primary),
            'verified_Q_code_path': 'pending_actual_case_review; statistical_direction_alone_is_not_final_Q_benefit'}, mechanisms


def run(root=RUN):
    package = root / 'FQ_GATE'
    inputs = package / 'inputs_v3'
    protocol = inputs / 'protocol.json'
    index = package / 'execution_index.json'
    segments = [Path(p) for p in read(index)['segments']] if index.exists() else []
    schedule = read(inputs / 'schedule.json') if (inputs / 'schedule.json').exists() else []
    rows, paths, duplicates = collect(segments, schedule) if segments else ([], {}, 0)
    out = package / 'analysis'
    if not rows:
        summary = {'status': 'not_started', 'planned': 2384, 'completed': 0, 'results': None,
                   'paid_calls_by_analysis': 0, 'observed_utc': datetime.now(timezone.utc).isoformat()}
        write(out / 'summary.json', summary)
        write(out / 'case_review_queue.json', [])
        (out / 'analysis.md').write_text('# 全D_gate四臂分析\n\n尚无真实四臂代码结果。298题参考预检通过属于数据校准，不计入2384格模型实验；先完成学习和冻结同题回测，再执行四臂。\n', encoding='utf-8')
        return summary
    result, mechanisms = analyze(rows)
    complete = (len(rows) == len(schedule) == 2384 and read(protocol)['task_count'] == 298
                and len({r['task_id'] for r in rows}) == 298
                and read(segments[-1] / 'state.json')['status'] == 'completed')
    summary = {**result, 'status': 'completed' if complete else 'partial', 'planned': 2384,
        'completed': len(rows), 'identical_duplicate_row_copies': duplicates,
        'costs': cost_snapshot(segments), 'paid_calls_by_analysis': 0,
        'observed_utc': datetime.now(timezone.utc).isoformat(),
        'not_significant_does_not_establish_equivalence_or_universal_failure': True}
    write(out / 'summary.json', summary)
    write(out / 'mechanisms.json', mechanisms)
    write(out / 'case_review_queue.json', review_queue(mechanisms, paths))
    lines = ['# 全D_gate四臂分析', '',
        f"当前{'完整' if complete else '部分'}保存{len(rows)}/2384格。任务和重复分别配对，统计重采样以真实family（关联题族）为单位。", '',
        '| 条件 | 完成 | 最终F/S/Joint | 完整可测 |', '|---|---:|---|---:|']
    for arm in CONDITIONS:
        f = result['arms'][arm]['final']
        lines.append(f"| {arm} | {f['completed']} | {f['functional']}/{f['security']}/{f['joint']} | {f['measured']} |")
    lines += ['', '主要比较是Q2−Q1和Q2−Q3，两项检验进行Holm校正。Q0保留原CLE候选路径，作为系统参照；若呈现候选边界不同，其差异不能全部归因为Q排序。', '',
        '| 主要比较 | 完整配对 | 救回/损失 | Joint差 | family 95%区间 | 校正p |', '|---|---:|---|---|---|---|']
    for c in result['primary_comparisons']:
        lines.append(f"| Q2−{c['control']} | {c['measured_pairs']} | {c['wins']}/{c['losses']} | {c['difference']} | {c['ci95_family_bootstrap']} | {c.get('p_holm_two_primary')} |")
    lines += ['', '选中编号、新成员声明采用、实际代码落实分别复核。已生成代表救回/损失队列，尚未据ID字段自动填写原因或签署Q收益。两项统计方向支持仍须完整测量、共同候选核验及实际代码证据；未显著不能写成等效或Q普遍无效。', '',
        '本分析不调用模型。用量读取最近恢复段的累计预算，未知用量单列；D_gate是本课题已历史接触的评价池，不能解释为整个CLE从未见过的独立测试。']
    (out / 'analysis.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, default=RUN)
    args = parser.parse_args()
    result = run(args.run_root)
    print(json.dumps({k: result[k] for k in ('status', 'completed', 'planned', 'paid_calls_by_analysis')}))


if __name__ == '__main__':
    main()
