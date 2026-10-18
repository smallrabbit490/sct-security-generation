"""候选评价池四指标与推进门；只消费标签和记录，不调用模型或更新经验。"""
from __future__ import annotations

from collections import Counter
import random

LABELS = {'direct', 'conditional', 'irrelevant', 'conflict', 'insufficient'}


def metrics(universes, predictions, labels, candidates=None):
    """同题共享完整评价池；未审定标签不作负例，零分母保留原因。"""
    counts = Counter()
    per_task, missing = [], []
    for task, universe in universes.items():
        if len(universe) != len(set(universe)):
            raise ValueError('duplicate_pair_in_universe')
        selected = set(predictions.get(task, []))
        if not selected <= set(universe):
            raise ValueError('prediction_outside_evaluation_pool')
        unknown = [p for p in universe if labels.get(p) not in LABELS - {'insufficient'}]
        missing.extend(unknown)
        if unknown:
            continue
        positives = {p for p in universe if labels[p] == 'direct'}
        conflicts = {p for p in universe if labels[p] == 'conflict'}
        recalled = set(candidates.get(task, [])) if candidates is not None else set()
        row = {'task_id': task, 'TP': len(selected & positives),
               'FP': len(selected - positives), 'FN': len(positives - selected),
               'TN': len(set(universe) - selected - positives),
               'positive': len(positives), 'negative': len(universe) - len(positives),
               'selected': len(selected), 'conflicts': len(selected & conflicts),
               'candidate_TP': len(recalled & positives), 'hit': int(bool(selected & positives))}
        counts.update({k: v for k, v in row.items() if k != 'task_id'})
        row.update(_ratios(row))
        per_task.append(row)
    result = {'scope': 'candidate_pool_only', 'full_library_recall': None,
              'full_library_recall_reason': 'full_library_not_labeled',
              'complete': not missing, 'missing_pairs': sorted(set(missing)),
              'tasks': len(universes), 'evaluated_tasks': len(per_task),
              'counts': dict(counts), 'per_task': per_task}
    if missing:
        result.update({k: None for k in ('accuracy', 'precision', 'recall', 'f1',
                                        'conflict_rate', 'candidate_recall', 'hit_rate')})
        result['reason'] = 'labels_missing_or_insufficient'
    else:
        result.update(_ratios(counts))
        result['hit_rate'] = counts['hit'] / len(universes) if universes else None
    return result


def _ratios(c):
    """定义四指标及冲突/召回；缺分母不填0，原始计数始终保留。"""
    tp, fp, fn, tn = (c.get(k, 0) for k in ('TP', 'FP', 'FN', 'TN'))
    pairs = {'accuracy': (tp + tn, tp + fp + fn + tn),
             'precision': (tp, tp + fp), 'recall': (tp, tp + fn),
             'f1': (2 * tp, 2 * tp + fp + fn),
             'conflict_rate': (c.get('conflicts', 0), tp + fp),
             'candidate_recall': (c.get('candidate_TP', 0), tp + fn)}
    result = {}
    for key, (numerator, denominator) in pairs.items():
        result[key] = numerator / denominator if denominator else None
        if not denominator:
            result[key + '_reason'] = 'zero_denominator'
    return result


def not_worse(a, b, key):
    """未定义冲突率只在两臂均零返回时可比较；其余缺失不通过门槛。"""
    if key == 'conflict_rate':
        return a['counts'].get('conflicts', 0) == 0 if b[key] is None else (
            a[key] is None or a[key] <= b[key])
    return a[key] is not None and b[key] is not None and a[key] >= b[key]


def retrieval_gate(candidate, baseline, margin=0.05):
    """工程推进门，不代替确认检验；空/未审定结果不通过。"""
    return (candidate['complete'] and baseline['complete'] and
            candidate['f1'] is not None and baseline['f1'] is not None and
            candidate['f1'] - baseline['f1'] >= margin - 1e-12 and
            not_worse(candidate, baseline, 'hit_rate') and
            not_worse(candidate, baseline, 'conflict_rate'))


def paired_f1_interval(universes, left, right, labels, *, seed=20261017, repeats=10000):
    """按题配对重采样汇总F1差；不能把同题卡片当作独立任务。"""
    rng = random.Random(seed)
    ids = sorted(universes)
    samples = []
    for _ in range(repeats):
        picked = rng.choices(ids, k=len(ids))
        us = {str(i): universes[t] for i, t in enumerate(picked)}
        a = metrics(us, {str(i): left.get(t, []) for i, t in enumerate(picked)}, labels)['f1']
        b = metrics(us, {str(i): right.get(t, []) for i, t in enumerate(picked)}, labels)['f1']
        if a is not None and b is not None:
            samples.append(b - a)
    samples.sort()
    return {'repeats': repeats, 'valid_repeats': len(samples),
            'ci95': [samples[int(.025 * (len(samples)-1))], samples[int(.975 * (len(samples)-1))]]
            if samples else None}
