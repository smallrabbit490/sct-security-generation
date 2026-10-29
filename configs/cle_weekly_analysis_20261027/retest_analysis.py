"""冻结五条件回测的零API配对复算；重复按真实题族聚类，不补造未运行结果。"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import json

from configs.cle_memory_q_full_gate_cap3_20261019.analyze import paired as native_paired
from .analysis import RUN, read, write, metrics, cost_snapshot

CONDITIONS = ('Q1', 'Q2_K0', 'Q2_K1', 'Q2_K2', 'Q2_K3')
COMPARISONS = tuple((condition, 'Q1') for condition in CONDITIONS[1:]) + (('Q2_K3', 'Q2_K0'),)


def collect(segments, schedule):
    expected = {cell['cell_id']: cell for cell in schedule}
    saved, paths = {}, {}
    duplicates = 0
    for segment in segments:
        for path in (Path(segment)/'task_rows').glob('*.json'):
            row = read(path)
            key = row['cell_id']
            if key not in expected or any(row[k] != expected[key][k] for k in ('task_id', 'condition', 'repeat')):
                raise ValueError('saved_row_outside_frozen_schedule:' + key)
            if key in saved:
                if saved[key] != row:
                    raise ValueError('conflicting_completed_cell:' + key)
                duplicates += 1
            saved[key], paths[key] = row, str(path)
    return list(saved.values()), paths, duplicates


def selected(attempt, key):
    return [str(card['invariant_id']) for card in attempt.get('generation', {}).get(key, [])]


def compare(rows, treated, control, planned_tasks):
    """原配对函数使用task×repeat唯一键，保留真实family；其bootstrap和置换整体交换题族。"""
    wanted = [r for r in rows if r['condition'] in (treated, control)]
    transformed = [{**r, 'task_id': f"{r['task_id']}_r{r['repeat']}", 'arm': r['condition']} for r in wanted]
    native = native_paired(transformed, target=treated, control=control, seed=20261027)
    # 原函数附带McNemar把重复当独立单元；本分析不消费该补充p值。
    native.pop('p_mcnemar_supplement', None)
    if not native['measured_pairs']:
        native['p_family_swap'] = None
        native['ci95_family_bootstrap'] = None
    by = {condition: {(str(r['task_id']), r['repeat']): r for r in wanted if r['condition'] == condition}
          for condition in (treated, control)}
    keys = sorted(set(by[treated]) & set(by[control]))
    complete = [key for key in keys if by[treated][key]['final'].get('measured')
                and by[control][key]['final'].get('measured')]
    repeats = {}
    for repeat in (1, 2):
        matching = [key for key in complete if key[1] == repeat]
        deltas = [int(by[treated][key]['final']['joint'])-int(by[control][key]['final']['joint']) for key in matching]
        repeats[str(repeat)] = {'measured_pairs': len(matching), 'net_joint': sum(deltas),
            'difference': sum(deltas)/len(deltas) if deltas else None}
    valid_tasks = {key[0] for key in complete}
    native.update(planned_pairs=planned_tasks*2, missing_unexecuted_pairs=planned_tasks*2-len(keys),
        unique_tasks_in_measured_pairs=len(valid_tasks),
        tasks_with_both_repeats_measured=sum(all((task, repeat) in complete for repeat in (1, 2)) for task in valid_tasks),
        repeat_comparisons=repeats,
        inference='task-repeat matched observations; genuine family clusters retained across both repeats and related tasks; missing outcomes excluded from measured contrasts',
        scope='same D_grow learning tasks, not cross-family transfer')
    return native


def first_mechanism(a, b):
    left, right = a['attempts'][0], b['attempts'][0]
    selected_a, selected_b = selected(left, 'retrieved_cards'), selected(right, 'retrieved_cards')
    adopted_a = selected(left, 'cards')
    new = set(selected_a)-set(selected_b)
    trace_a, trace_b = left.get('retrieval_trace') or {}, right.get('retrieval_trace') or {}
    valid_trace = trace_a.get('status') == trace_b.get('status') == 'completed'
    def signature(trace):
        return {'query_hash': trace.get('query_hash'), 'candidate_ids': sorted(trace.get('candidate_ids', [])),
            'scores': sorted([{k: item.get(k) for k in ('id', 'cosine', 'content_hash')}
                              for item in trace.get('scores', [])], key=lambda s: str(s['id']))}
    same_candidates = signature(trace_a) == signature(trace_b) if valid_trace else None
    return {'task_id': str(a['task_id']), 'family_id': a['family_id'], 'repeat': a['repeat'],
        'treated': a['condition'], 'control': b['condition'], 'both_retrieval_complete': valid_trace,
        'same_first_candidates': same_candidates,
        'selected_order_changed': selected_a != selected_b,
        'selected_members_changed': set(selected_a) != set(selected_b),
        'newly_selected_ids': sorted(new), 'newly_selected_declared_adopted_ids': sorted(new & set(adopted_a)),
        'both_final_measured': bool(a['final'].get('measured') and b['final'].get('measured')),
        'treated_joint': bool(a['final'].get('joint')), 'control_joint': bool(b['final'].get('joint')),
        'code_implementation_status': 'pending_actual_code_review'}


def analyze(rows, planned_tasks):
    arms = {}
    for condition in CONDITIONS:
        items = [row for row in rows if row['condition'] == condition]
        by_task = defaultdict(dict)
        for row in items:
            by_task[str(row['task_id'])][row['repeat']] = row['final']
        paired_repeat_tasks = [value for value in by_task.values() if set(value) == {1, 2}
                               and all(a.get('measured') for a in value.values())]
        arms[condition] = {'first': metrics([r['attempts'][0] for r in items], planned_tasks*2),
            'final': metrics([r['final'] for r in items], planned_tasks*2),
            'repeat_variability': {'tasks_with_two_measured_repeats': len(paired_repeat_tasks),
                'Joint_discordant_tasks': sum(v[1]['joint'] != v[2]['joint'] for v in paired_repeat_tasks)},
            'declared_adopted_positions': sum(len(selected(a, 'cards')) for r in items for a in r['attempts']),
            'tasks_with_declared_adoption': len({str(r['task_id']) for r in items if any(selected(a, 'cards') for a in r['attempts'])})}
    comparisons = [compare(rows, a, b, planned_tasks) for a, b in COMPARISONS]
    observed = sorted([c for c in comparisons if c['p_family_swap'] is not None], key=lambda c: c['p_family_swap'])
    previous = 0.
    for index, item in enumerate(observed):
        previous = max(previous, min(1., item['p_family_swap']*(len(COMPARISONS)-index)))
        item['exploratory_Holm5_p'] = previous
    by = {(str(r['task_id']), r['repeat'], r['condition']): r for r in rows}
    mechanisms = []
    for treated, control in COMPARISONS:
        for task, repeat in sorted({(key[0], key[1]) for key in by}):
            a, b = by.get((task, repeat, treated)), by.get((task, repeat, control))
            if a is not None and b is not None:
                mechanisms.append(first_mechanism(a, b))
    counts = {}
    for a, b in COMPARISONS:
        items = [m for m in mechanisms if m['treated'] == a and m['control'] == b]
        counts[a+'_vs_'+b] = {'paired_completed_cells': len(items),
            'common_candidates_verified': sum(m['same_first_candidates'] is True for m in items),
            'common_candidates_mismatched': sum(m['same_first_candidates'] is False for m in items),
            'common_candidates_unmeasured': sum(m['same_first_candidates'] is None for m in items),
            'observed_selected_members_changed': sum(m['selected_members_changed'] for m in items),
            'selected_members_changed_with_common_candidates': sum(m['selected_members_changed'] and m['same_first_candidates'] is True for m in items),
            'new_members_declared_adopted_with_common_candidates': sum(bool(m['newly_selected_declared_adopted_ids']) and m['same_first_candidates'] is True for m in items),
            'code_implementation_not_inferred': True}
    return {'arms': arms, 'comparisons': comparisons, 'mechanism_counts': counts}, mechanisms


def review_queue(mechanisms, paths):
    chosen = {}
    for mechanism in mechanisms:
        if not mechanism['both_final_measured']:
            category = 'missing_measurement'
        elif mechanism['treated_joint'] and not mechanism['control_joint']:
            category = 'rescue'
        elif not mechanism['treated_joint'] and mechanism['control_joint']:
            category = 'loss'
        elif mechanism['newly_selected_declared_adopted_ids']:
            category = 'new_member_adopted_no_outcome_change'
        else:
            continue
        key = (mechanism['treated'], mechanism['control'], category)
        bucket = chosen.setdefault(key, [])
        if len(bucket) >= 2:
            continue
        task, repeat = mechanism['task_id'], mechanism['repeat']
        bucket.append({**mechanism, 'category': category,
            'treated_row_path': paths[f'{task}_r{repeat}_{mechanism["treated"]}'],
            'control_row_path': paths[f'{task}_r{repeat}_{mechanism["control"]}'],
            'cause': None, 'verified_Q_effect_path': None, 'review_status': 'pending_actual_code_review'})
    return [item for bucket in chosen.values() for item in bucket]


def run(root=RUN):
    package = root/'FQ_RETEST'
    protocol_path = package/'inputs/protocol.json'
    planned = read(protocol_path)['planned_P7'] if protocol_path.exists() else 2730
    index_path = package/'execution_index.json'
    segments = [Path(p) for p in read(index_path)['segments']] if index_path.exists() else []
    schedule_path = package/'inputs/schedule.json'
    schedule = read(schedule_path) if schedule_path.exists() else []
    rows, paths, duplicates = collect(segments, schedule) if segments else ([], {}, 0)
    out = package/'analysis'
    if not rows:
        summary = {'status': 'not_started', 'planned': planned, 'completed': 0,
            'observed_utc': datetime.now(timezone.utc).isoformat(), 'paid_calls_by_analysis': 0,
            'results': None, 'reason': 'no_saved_real_retest_rows; no experiment outcomes fabricated'}
        write(out/'summary.json', summary)
        write(out/'case_review_queue.json', [])
        (out/'analysis.md').write_text('# 冻结回测分析\n\n尚无真实冻结回测逐题结果；当前只完成分析入口，不生成成绩、区间或有效性结论。下一步等待学习、快照、回放及阶段分析完成后，按固定五条件两重复执行回测。\n', encoding='utf-8')
        return summary
    planned_tasks = read(protocol_path)['task_count']
    result, mechanisms = analyze(rows, planned_tasks)
    completed = (len(rows) == planned == len(schedule) == 2730 and planned_tasks == 273
                 and bool(segments) and read(segments[-1]/'state.json')['status'] == 'completed')
    summary = {**result, 'status': 'completed' if completed else 'partial', 'planned': planned,
        'completed': len(rows), 'identical_duplicate_row_copies': duplicates, 'source_segments': list(map(str, segments)),
        'observed_utc': datetime.now(timezone.utc).isoformat(), 'paid_calls_by_analysis': 0,
        'costs': cost_snapshot(segments), 'two_repeats_are_independent_generations_not_independent_tasks': True,
        'interpretation': 'matched frozen retest on learning tasks; transfer and verified code causality require separate evidence',
        'not_significant_does_not_mean_equivalence_or_universal_failure': True}
    write(out/'summary.json', summary)
    write(out/'mechanisms.json', mechanisms)
    write(out/'case_review_queue.json', review_queue(mechanisms, paths))
    lines = ['# 冻结五条件同题回测分析', '',
        f"当前为{'完整阶段' if completed else '进行中快照'}，保存{len(rows)}/{planned}次代码结果。两次重复是同一道题的两次独立生成，推断按真实family（关联题族）整体处理，不作为两倍独立题目。", '',
        '| 条件 | 完成 | 末次F/S/Joint | 完整可测 | 两重复Joint不同题数 |', '|---|---:|---|---:|---:|']
    for condition in CONDITIONS:
        arm = result['arms'][condition]
        f = arm['final']
        lines.append(f"| {condition} | {f['completed']} | {f['functional']}/{f['security']}/{f['joint']} | {f['measured']} | {arm['repeat_variability']['Joint_discordant_tasks']} |")
    lines += ['', '配对只纳入双方完整测量的task×repeat，缺测与尚未执行分列。差值区间采用原项目按family整簇重采样，置换检验同时交换同一题族的所有重复和关联题；五项同题探索比较另列Holm校正，不替代后续D_gate两项主要比较。', '',
        '| 比较 | 完整配对 | 救回/损失 | Joint差 | family 95%区间 |', '|---|---:|---|---|---|']
    for value in result['comparisons']:
        lines.append(f"| {value['target']}−{value['control']} | {value['measured_pairs']} | {value['wins']}/{value['losses']} | {value['difference']} | {value['ci95_family_bootstrap']} |")
    lines += ['', 'Q是否改变选中卡编号、新成员是否被声明采用，与最终代码是否正确实现分别记录。代表救回、损失和改选但未改变结果的案例已进入待复核队列，不能仅据ID字段签署Q作用原因。', '',
        f"最近累计预算记录已知{summary['costs'].get('known_reported_tokens', '未记录')} Token，物理HTTP {summary['costs'].get('physical_HTTP_including_prior', '未记录')}次，未知或在途用量{summary['costs'].get('unknown_or_inflight_HTTP', '未记录')}次。各恢复段预算已累计，不能相加重复计费；金额未核实，本分析新发API请求0次。", '',
        '同题冻结回测用于判断学习题上的变化，不代表跨题族迁移。完整矩阵与实际代码路径尚未齐全时只报告阶段现象；未显著不能解释为等效或Q普遍无效。下一步完成原定全部五条件和两重复、零API回放与代码复核，再接全D_gate迁移评价。']
    (out/'analysis.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, default=RUN)
    args = parser.parse_args()
    summary = run(args.run_root)
    print(json.dumps({k: summary[k] for k in ('status', 'completed', 'planned', 'paid_calls_by_analysis')}))


if __name__ == '__main__':
    main()
