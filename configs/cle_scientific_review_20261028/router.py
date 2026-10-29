"""按实际做题结果选择分类器；只复用五档记录，不产生模型请求。"""
from collections import defaultdict

from configs.cle_weekly_reduced_20261028 import granularity_analysis as ga


def choose_candidate(candidates):
    """优先留出题族Joint，其次可比的输入Token，最后偏好更强正则。"""
    best = max(c['family_mean_joint'] for c in candidates)
    tied = [c for c in candidates if c['family_mean_joint'] == best]
    if all(c['family_mean_input_tokens'] is not None for c in tied):
        cost = min(c['family_mean_input_tokens'] for c in tied)
        tied = [c for c in tied if c['family_mean_input_tokens'] == cost]
    return min(tied, key=lambda c: c['C'])['C']


def opportunity(rows, tasks, train_ids):
    """分开报告正确性差异和纯成本差异；两次实测不是永久的最优档标签。"""
    by = {(str(r['task_id']), r['repeat'], r['condition']): r for r in rows}
    counts = defaultdict(int)
    families = defaultdict(set)
    for tid in train_ids:
        pairs = [[by.get((tid, repeat, level)) for repeat in (1, 2)] for level in ga.LEVELS]
        if any(r is None or not r['final'].get('measured') for pair in pairs for r in pair):
            category = 'incomplete_or_unmeasured'
        else:
            vectors = [tuple(bool(r['final']['joint']) for r in pair) for pair in pairs]
            if len(set(vectors)) == 1:
                category = 'no_observed_correctness_difference'
            elif any(all(v) for v in vectors) and any(not any(v) for v in vectors):
                category = 'same_direction_difference_in_both_repeats'
            else:
                category = 'difference_with_repeat_variation'
        counts[category] += 1
        families[category].add(str(tasks[tid]['family_id']))
    return {'training_only': True, 'task_counts': dict(counts),
            'family_counts': {k: len(v) for k, v in families.items()},
            'meaning': '诊断分档是否改变正确性；不能把成本选出的不同标签直接解释成正确性需求不同。'}


def fit_model(rows, tasks, split, labels):
    """三折均按family隔离，用所有完整留出题的真实路由Joint选择原三种正则。"""
    train = set(split['train_task_ids'])
    dev = set(split['development_task_ids'])
    if train & dev or train | dev != set(tasks):
        raise ValueError('task_training_development_split_differed')
    families = {str(tasks[t]['family_id']) for t in train}
    if families & {str(tasks[t]['family_id']) for t in dev}:
        raise ValueError('family_training_development_leakage')
    folds = split['family_cv_fold']
    if set(folds) != families:
        raise ValueError('training_family_folds_incomplete')
    fixed, scores = ga.best_fixed(rows, train)
    usable = [v for v in labels if v['task_id'] in train and v['preferred_level']]
    model = {'type': 'constant', 'fixed': fixed, 'features': list(ga.FEATURE_NAMES),
             'confidence_threshold': .5, 'fit_task_ids': [v['task_id'] for v in usable],
             'fit_families': sorted({v['family_id'] for v in usable}),
             'fixed_training_scores': scores, 'development_used_for_fitting': False,
             'Q_or_CWE_or_ID_features': False, 'task_only_router': True,
             'label_definition': 'unchanged: all ten measured; memory intervention; 2/2 Joint; min mean P7 input tokens',
             'selection_objective': 'family-held-out actual Joint, then known mean P7 input tokens, then smaller C',
             'method_revision': 'cle-goal-aligned-router-20261028-v1',
             'performance_gate_controls_dispatch': False,
             'training_opportunity': opportunity(rows, tasks, train)}
    if len({v['preferred_level'] for v in usable}) < 2:
        model['degenerate_reason'] = 'fewer_than_two_stable_preferred_classes'
        return model
    by = {(str(r['task_id']), r['repeat'], r['condition']): r for r in rows}
    # 全五档完整可测的共同留出集合，不能把缺测算错，也不能按各模型路线挑分母。
    measured = {tid for tid in train if all(
        (tid, r, level) in by and by[tid, r, level]['final'].get('measured')
        for r in (1, 2) for level in ga.LEVELS)}
    if not measured:
        raise ValueError('no_common_measured_training_tasks')
    candidates = []
    for c in (.1, 1., 10.):
        joint, tokens = defaultdict(list), defaultdict(list)
        unknown_cost = False
        for fold in range(3):
            fit_items = [v for v in usable if folds[v['family_id']] != fold]
            held_ids = sorted(t for t in measured if folds[str(tasks[t]['family_id'])] == fold)
            if not held_ids:
                continue
            fold_ids = [t for t in train if folds[str(tasks[t]['family_id'])] != fold]
            fold_fixed, _ = ga.best_fixed(rows, fold_ids)
            temporary = {**model, 'fixed': fold_fixed}
            if len({v['preferred_level'] for v in fit_items}) >= 2:
                temporary.update(type='multinomial_logistic', fit=ga.fit_logistic(
                    [ga.features(tasks[v['task_id']]) for v in fit_items],
                    [v['preferred_level'] for v in fit_items], c))
            for tid in held_ids:
                level = ga.predict(tasks[tid], temporary)[0]
                family = str(tasks[tid]['family_id'])
                for repeat in (1, 2):
                    row = by[tid, repeat, level]
                    joint[family].append(int(row['final']['joint']))
                    cost = row.get('usage', {}).get('prompt_tokens')
                    if type(cost) is not int:
                        unknown_cost = True
                    else:
                        tokens[family].append(cost)
        score = sum(sum(v)/len(v) for v in joint.values())/len(joint)
        cost = None if unknown_cost else sum(sum(v)/len(v) for v in tokens.values())/len(tokens)
        candidates.append({'C': c, 'family_mean_joint': score, 'family_mean_input_tokens': cost,
                           'held_families': len(joint), 'held_tasks': len(measured)})
    chosen = choose_candidate(candidates)
    model.update(type='multinomial_logistic', fit=ga.fit_logistic(
        [ga.features(tasks[v['task_id']]) for v in usable], [v['preferred_level'] for v in usable], chosen),
        CV_C_scores=candidates, CV_scope='training-family three-fold only; all candidates share measured held tasks')
    return model
