"""全D_grow五档真实结果复算与离线路由训练；只消费保存行，不调用API。"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path

from configs.cle_v41_completion_20261026.policies import (
    FEATURE_NAMES, LEVELS, features, fit_logistic, predict, rule_level)
from .analysis import RUN, read, write, metrics, cost_snapshot
from .retest_analysis import collect


def make_labels(rows, tasks):
    """两重复成功且代价可测才定义首选档；无干预、全失败或缺测保持未知。"""
    by = {(str(r['task_id']), r['repeat'], r['condition']): r for r in rows}
    labels = []
    for tid, task in tasks.items():
        accepted, costs = [], {}
        complete = all((tid, repeat, level) in by for level in LEVELS for repeat in (1, 2))
        items = [by[tid, repeat, level] for level in LEVELS for repeat in (1, 2)
                 if (tid, repeat, level) in by]
        measured = complete and all(r['final'].get('measured') for r in items)
        intervention = any(a.get('generation', {}).get('retrieved_cards') for r in items for a in r['attempts'])
        for level in LEVELS:
            pair = [by[tid, repeat, level] for repeat in (1, 2) if (tid, repeat, level) in by]
            token_counts = [r.get('usage', {}).get('prompt_tokens') for r in pair]
            costs[level] = sum(token_counts)/2 if len(pair) == 2 and all(type(t) is int for t in token_counts) else None
            if len(pair) == 2 and all(r['final'].get('measured') and r['final'].get('joint') for r in pair):
                accepted.append(level)
        candidates = [level for level in accepted if costs[level] is not None]
        costs_complete = all(costs[level] is not None for level in accepted)
        preferred = min(candidates, key=lambda level: (costs[level], LEVELS.index(level))) if measured and intervention and candidates and costs_complete else None
        status = ('incomplete_grid' if not complete else 'unmeasured_outcome' if not measured else
                  'no_memory_intervention' if not intervention else 'no_stable_success' if not accepted else
                  'unknown_input_cost' if not candidates or not costs_complete else 'stable_success')
        labels.append({'task_id': tid, 'family_id': str(task['family_id']), 'accepted_levels': accepted,
            'preferred_level': preferred, 'input_tokens_P7_mean': costs, 'label_status': status,
            'all_ten_cells_measured': measured, 'any_memory_intervention': intervention,
            'interpretation': '2/2 observed success is a finite-repeat label, not a ground-truth optimum'})
    return labels


def best_fixed(rows, task_ids):
    """固定档只由指定训练题的真实成绩决定；并列选较低编号。"""
    task_ids = set(task_ids)
    scores = {level: sum(bool(r['final'].get('measured')) and bool(r['final'].get('joint'))
                        for r in rows if str(r['task_id']) in task_ids and r['condition'] == level) for level in LEVELS}
    return max(LEVELS, key=lambda level: (scores[level], -LEVELS.index(level))), scores


def fit_model(rows, tasks, split, labels):
    """固定旧8特征、旧逻辑回归与三参数范围；按真实family做训练侧三折。"""
    train_ids = set(split['train_task_ids'])
    development_ids = set(split['development_task_ids'])
    if train_ids & development_ids or train_ids | development_ids != set(tasks):
        raise ValueError('task_training_development_split_differed')
    train_families = {str(tasks[tid]['family_id']) for tid in train_ids}
    development_families = {str(tasks[tid]['family_id']) for tid in development_ids}
    if train_families & development_families:
        raise ValueError('family_training_development_leakage')
    folds = split['family_cv_fold']
    if set(folds) != train_families:
        raise ValueError('training_family_folds_incomplete')
    fixed, scores = best_fixed(rows, train_ids)
    usable = [label for label in labels if label['task_id'] in train_ids and label['preferred_level']]
    model = {'type': 'constant', 'fixed': fixed, 'features': list(FEATURE_NAMES),
        'confidence_threshold': .5, 'fit_task_ids': [item['task_id'] for item in usable],
        'fit_families': sorted({item['family_id'] for item in usable}),
        'fixed_training_scores': scores, 'development_used_for_fitting': False,
        'Q_or_CWE_or_ID_features': False, 'task_only_router': True,
        'label_definition': 'all ten outcomes measured, memory intervention exists, 2/2 Joint, min mean P7 input tokens',
        'shared_and_material_costs': 'separate reported costs; not part of preferred-level P7 input-token criterion',
        'performance_gate_controls_dispatch': False}
    if len({item['preferred_level'] for item in usable}) < 2:
        model['degenerate_reason'] = 'fewer_than_two_stable_preferred_classes; constant baseline, not learned superiority'
        return model
    candidates = []
    for regularization in (.1, 1., 10.):
        family_correct = defaultdict(list)
        for fold in range(3):
            fit_items = [item for item in usable if folds[item['family_id']] != fold]
            held = [item for item in usable if folds[item['family_id']] == fold]
            if not held:
                continue
            fold_train_ids = [tid for tid in train_ids if folds[str(tasks[tid]['family_id'])] != fold]
            fold_fixed, _ = best_fixed(rows, fold_train_ids)
            temporary = {**model, 'fixed': fold_fixed}
            if len({item['preferred_level'] for item in fit_items}) >= 2:
                temporary.update(type='multinomial_logistic', fit=fit_logistic(
                    [features(tasks[item['task_id']]) for item in fit_items],
                    [item['preferred_level'] for item in fit_items], regularization))
            for item in held:
                family_correct[item['family_id']].append(predict(tasks[item['task_id']], temporary)[0] == item['preferred_level'])
        score = sum(sum(items)/len(items) for items in family_correct.values())/len(family_correct) if family_correct else 0.
        candidates.append({'C': regularization, 'family_mean_label_accuracy': score,
            'held_families': len(family_correct)})
    chosen = max(candidates, key=lambda value: (value['family_mean_label_accuracy'], -value['C']))['C']
    model.update(type='multinomial_logistic', fit=fit_logistic(
        [features(tasks[item['task_id']]) for item in usable], [item['preferred_level'] for item in usable], chosen),
        CV_C_scores=candidates, CV_scope='training families only; scaling and fallback fixed level fit without held family')
    return model


def development_results(rows, tasks, split, model):
    """开发侧只复用其五档成绩验证策略，不用于挑特征、阈值或固定档。"""
    by = {(str(r['task_id']), r['repeat'], r['condition']): r for r in rows}
    results = {policy: [] for policy in ('fixed', 'rule', 'classifier')}
    for tid in split['development_task_ids']:
        for repeat in (1, 2):
            first_trace = by[tid, repeat, 'L2']['attempts'][0].get('retrieval_trace') or {}
            has_cards = bool(first_trace.get('pre_level_selected_ids'))
            levels = {'fixed': model['fixed'], 'rule': rule_level(tasks[tid], has_cards),
                      'classifier': predict(tasks[tid], model)[0]}
            for policy, level in levels.items():
                results[policy].append({'task_id': tid, 'family_id': tasks[tid]['family_id'], 'repeat': repeat,
                    'selected_level': level, 'first_has_cards': has_cards,
                    'final': copy.deepcopy(by[tid, repeat, level]['final'])})
    return results


def run(root=RUN, *, train=False):
    package = root/'FG_LABELS'
    inputs = package/'inputs'
    index = package/'execution_index.json'
    segments = [Path(p) for p in read(index)['segments']] if index.exists() else []
    schedule = read(inputs/'schedule.json') if (inputs/'schedule.json').exists() else []
    rows, paths, copies = collect(segments, schedule) if segments else ([], {}, 0)
    out = package/'analysis'
    if not rows:
        result = {'status': 'not_started', 'completed': 0, 'planned': 2730, 'paid_API_calls': 0, 'classifier_trained': False}
        write(out/'summary.json', result)
        return result
    tasks = read(inputs/'tasks.json')
    protocol = read(inputs/'protocol.json')
    if any(row.get('protocol') != protocol['protocol'] for row in rows):
        raise ValueError('granularity_rows_do_not_match_frozen_protocol')
    labels = make_labels(rows, tasks)
    arms = {level: {'first': metrics([r['attempts'][0] for r in rows if r['condition'] == level], 546),
                    'final': metrics([r['final'] for r in rows if r['condition'] == level], 546)} for level in LEVELS}
    complete = len(rows) == len(schedule) == 2730 and read(segments[-1]/'state.json')['status'] == 'completed'
    result = {'status': 'completed' if complete else 'partial', 'completed': len(rows), 'planned': 2730,
        'arms': arms, 'label_status_counts': dict(Counter(label['label_status'] for label in labels)),
        'preferred_level_counts': dict(Counter(label['preferred_level'] for label in labels if label['preferred_level'])),
        'costs': cost_snapshot(segments), 'identical_duplicate_row_copies': copies,
        'paid_API_calls': 0, 'classifier_trained': False,
        'level_interpretation': 'L3 adds target template; L4 adds source example to L2, not to L3; not a pure length experiment'}
    write(out/'labels.json', labels)
    write(out/'summary.json', result)
    cases, seen = [], set()
    for label in labels:
        key = (label['label_status'], label['preferred_level'])
        if key in seen or label['label_status'] in ('incomplete_grid', 'no_memory_intervention'):
            continue
        seen.add(key)
        tid = label['task_id']
        cases.append({'task_id': tid, 'family_id': label['family_id'],
            'preferred_level': label['preferred_level'], 'label_status': label['label_status'],
            'rows': {f'r{repeat}_{level}': paths[f'{tid}_r{repeat}_{level}'] for level in LEVELS for repeat in (1, 2)
                     if f'{tid}_r{repeat}_{level}' in paths},
            'cause': None, 'code_implementation': None, 'review_status': 'pending_actual_case_review'})
    write(out/'case_review_queue.json', cases)
    lines = ['# 全D_grow记忆档位分析', '',
        f"当前保存{len(rows)}/2730格，结果为{'完整' if complete else '部分'}；固定五档和两重复不按收益缩减。", '',
        '| 档位 | 完成 | 最终F/S/Joint | 完整可测 |', '|---|---:|---|---:|']
    for level in LEVELS:
        final = arms[level]['final']
        lines.append(f"| {level} | {final['completed']} | {final['functional']}/{final['security']}/{final['joint']} | {final['measured']} |")
    lines += ['', '首选标签只由完整测量、实际记忆干预和两重复成功构成，在成功档中按P7平均输入Token比较。共享初析、首次选卡和材料准备成本另计；全失败、无干预、缺测或成功档成本未知不硬标L0。两次观测不是已知真实最优档。', '',
        'L3添加目标操作模板，L4在L2上添加来源示例，两者不是单纯的长短递增关系。训练与开发按family隔离，开发成绩不参与拟合；标签差异还需阅读卡、计划、代码和验证，不能直接归因为记忆程度。']
    (out/'analysis.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    if train:
        replay = package/'zero_API_replay/replay_result.json'
        if not complete or not replay.exists() or read(replay).get('status') != 'passed':
            raise ValueError('classifier_requires_complete_full_grid_and_native_zero_API_replay')
        split = read(inputs/'family_split.json')
        model = fit_model(rows, tasks, split, labels)
        model.update(protocol='cle-weekly-granularity-family-router-20261027-v1', source_protocol=read(inputs/'protocol.json')['protocol'])
        target = root/'FG_TRAIN'
        if (target/'model.json').exists():
            if read(target/'model.json') != model:
                raise ValueError('existing_frozen_classifier_differs_no_overwrite')
        else:
            write(target/'model.json', model)
            write(target/'labels.json', labels)
            write(target/'development.json', development_results(rows, tasks, split, model))
            write(target/'summary.json', {'status': 'completed', 'paid_API_calls': 0,
                'training_tasks': len(split['train_task_ids']), 'development_tasks': len(split['development_task_ids']),
                'usable_label_tasks': len(model['fit_task_ids']), 'classifier_type': model['type'],
                'benefit_gate_controls_dispatch': False})
        result['classifier_trained'] = True
        write(out/'summary.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['analysis', 'train'])
    parser.add_argument('--run-root', type=Path, default=RUN)
    args = parser.parse_args()
    result = run(args.run_root, train=args.action == 'train')
    print(json.dumps({k: result[k] for k in ('status', 'completed', 'planned', 'paid_API_calls', 'classifier_trained')}))


if __name__ == '__main__':
    main()
