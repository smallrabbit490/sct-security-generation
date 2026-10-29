"""公开事前状态决定similarity/q呈现顺序；不读代码、隐藏成绩或采用结果，不学习Q。"""
import copy
import random
from statistics import mean
from methods.sct_trajectory.memory_q import rank_candidates
from methods.sct_trajectory.public_contract_checks import compile_public_contract

FEATURES = {'explicit_external_binding', 'signature_known', 'visited_fraction',
            'negative_q_fraction', 'max_visits', 'normalized_rank_displacement'}


def route_features(public_query, scores, nodes, *, delta=-1, lambda_q=.5):
    """检索后、选卡及代码生成前提取六项状态；统计只限共同合法候选。"""
    rules = compile_public_contract(public_query)
    q = {key: node.q_value for key, node in nodes.items()}
    sim = rank_candidates(scores, q, delta=delta, lambda_q=0, limit=None)
    ordered = rank_candidates(scores, q, delta=delta, lambda_q=lambda_q, limit=None)
    positions = {s['id']: i for i, s in enumerate(sim)}
    count = len(sim)
    return {'explicit_external_binding': bool(rules['protected_bindings']),
        'signature_known': bool(rules['signature']),
        'visited_fraction': sum(nodes[s['id']].q_visits > 0 for s in sim) / count if count else 0,
        'negative_q_fraction': sum(q[s['id']] < 0 for s in sim) / count if count else 0,
        'max_visits': max((nodes[s['id']].q_visits for s in sim), default=0),
        'normalized_rank_displacement': mean(abs(i - positions[s['id']]) for i, s in enumerate(ordered)) / (count - 1)
            if count > 1 else 0}


def make_router(policy, *, delta=-1, lambda_q=.5):
    """加载已冻结的简单合取规则；无验证依据时enabled=false，不能自动发明阈值。"""
    policy = copy.deepcopy(policy)
    operations = {'eq': lambda a, b: a == b, 'ge': lambda a, b: a >= b, 'le': lambda a, b: a <= b}
    if type(policy.get('enabled')) is not bool:
        raise ValueError('route_policy_requires_explicit_enabled')
    rules = policy.get('rules', [])
    if policy['enabled'] and not rules:
        raise ValueError('enabled_route_requires_frozen_rules')
    if any(r.get('feature') not in FEATURES or r.get('op') not in operations or 'value' not in r for r in rules):
        raise ValueError('route_rule_uses_forbidden_or_unknown_input')

    def route(query, scores, nodes):
        features = route_features(query, scores, nodes, delta=delta, lambda_q=lambda_q)
        use_q = policy['enabled'] and all(operations[r['op']](features[r['feature']], r['value']) for r in rules)
        return {'candidate_order': 'q' if use_q else 'similarity', 'features': features,
                'policy_version': policy['version'], 'enabled': policy['enabled'],
                'reason': 'frozen_rules_matched' if use_q else policy.get('reason', 'frozen_rules_not_matched')}
    return route


def paired_screen(rows, task_ids, repeats, *, conditional_enabled, bootstrap_samples=5000):
    """按题族重采样两次重复的配对Joint差；缺测不通过扩大门，不混作独立题。"""
    from .joint_contract import VARIANT, CONDITIONAL_VARIANT
    by_arm = {}
    for row in rows:
        key = (str(row['task_id']), row['repeat'])
        bucket = by_arm.setdefault(row['arm'], {})
        if key in bucket:
            raise ValueError('duplicate_task_repeat_arm')
        bucket[key] = row['final']
    keys = [(str(t), rep) for rep in range(repeats) for t in task_ids]
    result = {'unit': 'task_family_cluster_with_repeats', 'planned_rows_per_arm': len(keys),
              'conditional_enabled': conditional_enabled, 'comparisons': {}}
    for name, baseline, threshold in ((VARIANT, 'P7', .03), (CONDITIONAL_VARIANT, VARIANT, .05)):
        if name == CONDITIONAL_VARIANT and not conditional_enabled:
            result['comparisons'][name] = {'decision': 'Q_ROUTE_DISABLED_NOT_TESTED'}
            continue
        current, base = by_arm.get(name, {}), by_arm.get(baseline, {})
        complete = all(k in current and k in base and current[k].get('measured') and base[k].get('measured') for k in keys)
        if not complete:
            result['comparisons'][name] = {'decision': 'INCOMPLETE_NO_ADVANCEMENT'}
            continue
        differences = {k: int(bool(current[k].get('joint'))) - int(bool(base[k].get('joint'))) for k in keys}
        per_repeat = [mean(differences[(str(t), rep)] for t in task_ids) for rep in range(repeats)]
        family_deltas = [mean(differences[(str(t), rep)] for rep in range(repeats)) for t in task_ids]
        delta = mean(family_deltas)
        rng = random.Random(20261023)
        boot = sorted(mean(rng.choices(family_deltas, k=len(family_deltas))) for _ in range(bootstrap_samples))
        lower, upper = boot[int(.1 * bootstrap_samples)], boot[min(bootstrap_samples - 1, int(.9 * bootstrap_samples))]
        passed = delta >= threshold and all(d >= 0 for d in per_repeat)
        if name == CONDITIONAL_VARIANT:
            passed = passed and lower > 0 and all(d > 0 for d in per_repeat)
        decision = 'PASS_DEVELOPMENT_GATE_NOT_FINAL_PROOF' if passed else 'STOP' if delta <= 0 else 'INCONCLUSIVE_NO_EXPANSION'
        result['comparisons'][name] = {'baseline': baseline, 'delta_joint': delta,
            'repeat_delta_joint': per_repeat, 'family_bootstrap_80pct': [lower, upper],
            'rescues': sum(d == 1 for d in differences.values()), 'losses': sum(d == -1 for d in differences.values()),
            'decision': decision}
    return result


def check_common_first_retrieval(first, second):
    """真实新臂必须共享首次公开查询、召回成员和余弦；修复轮随各臂代码分开。"""
    left, right = first['retrieval_traces'][0], second['retrieval_traces'][0]
    same = (left.get('status') == right.get('status') == 'completed'
        and left['query_hash'] == right['query_hash']
        and set(left['candidate_ids']) == set(right['candidate_ids'])
        and {s['id']: s['cosine'] for s in left['scores']} == {s['id']: s['cosine'] for s in right['scores']})
    if not same:
        raise RuntimeError('new_arms_do_not_share_first_query_candidates_and_cosines')
    return {'same_first_query': True, 'same_first_candidate_set': True, 'same_first_cosines': True,
            'repair_queries_shared': False}
