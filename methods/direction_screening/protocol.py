"""联合初筛的数据隔离、脱敏和统计协议；不请求模型、不修改长期经验库。"""
from __future__ import annotations

import hashlib
import math
from collections import defaultdict


def sample_families(rows, count, excluded=()):
    """划分阶段按 CWE 轮转选择 family 代表；同一输入得到同一清单，容量不足拒绝。"""
    families = defaultdict(list)
    for row in rows:
        family = str(row.get('family_id') or '')
        if not family:
            raise ValueError('missing_family')
        if family not in excluded:
            families[family].append(row)
    buckets = defaultdict(list)
    for family, members in families.items():
        representative = min(members, key=lambda r: str(r['index']))
        buckets[str(representative['CWE_ID'])].append(representative)
    for bucket in buckets.values():
        bucket.sort(key=lambda r: hashlib.sha256(('20261009:' + str(r['family_id'])).encode()).hexdigest())
    result = []
    while len(result) < count:
        progress = False
        for cwe in sorted(buckets):
            if buckets[cwe]:
                result.append(buckets[cwe].pop(0))
                progress = True
                if len(result) == count:
                    break
        if not progress:
            raise ValueError('insufficient_distinct_families')
    return result


def public_task(row):
    """生成阶段只允许公开契约字段；答案、夹具和兄弟样本不得进入提示，不写经验。"""
    allowed = ('function_name', 'description', 'security_policy', 'context', 'arguments', 'return', 'raise')
    source = row.get('task_description') or {}
    return {**{k: source[k] for k in allowed if k in source},
            'task_id': str(row['index']), 'CWE_ID': str(row.get('CWE_ID', '')), 'language': 'python'}


def safe_evidence(evidence):
    """训练修复回流只保留八类状态和错误类别；不传夹具输入、答案、异常原文。"""
    result = {}
    for key in ('syntax_or_compile', 'functional', 'security', 'static_analysis', 'type_check',
                'resource', 'timeout', 'exception_behavior'):
        item = evidence.get(key) or {}
        result[key] = {field: item[field] for field in ('status', 'error_type') if field in item}
        result[key].setdefault('status', 'unmeasured')
    return result


def outcome(evidence):
    """评分阶段区分测量覆盖与分数；环境/夹具事故归缺测，不成为卡片有害证据。"""
    evidence = safe_evidence(evidence)
    infrastructure = {'environment_error', 'plt_validator_exception', 'validator_exception', 'local_worker_error'}
    for key in ('functional', 'security'):
        if evidence[key].get('error_type') in infrastructure:
            evidence[key]['status'] = 'unmeasured'
    functional = evidence['functional']['status'] == 'pass'
    security = evidence['security']['status'] == 'pass'
    measured = all(evidence[k]['status'] in ('pass', 'fail') for k in ('functional', 'security'))
    return {'functional': functional, 'security': security,
            'joint': functional and security and evidence['syntax_or_compile']['status'] == 'pass',
            'measured': measured, 'evidence': evidence}


def select_public(candidates):
    """冻结选择阶段只能使用预先形成的公开证据评分；绝不消费官方 Joint/答案。"""
    if not candidates:
        raise ValueError('empty_candidates')
    return max(range(len(candidates)), key=lambda i: candidates[i].get('public_score', -1000))


def summarize(rows, baseline='direct'):
    """开发汇总总分母/完整测量配对/成本，精确 McNemar 仅探索并提供 Holm 校正。"""
    groups = defaultdict(list)
    for row in rows:
        groups[row['arm']].append(row)
    report = {'arms': {}, 'paired': {}, 'role': 'training_development_only'}
    for arm, items in groups.items():
        report['arms'][arm] = {'n': len(items), **{k: sum(r['final'][k] for r in items)
                              for k in ('functional', 'security', 'joint', 'measured')},
                              'first_joint': sum(r['attempts'][0]['joint'] for r in items),
                              'errors': sum(bool(r.get('error_type')) for r in items),
                              'calls': sum(r['usage']['calls'] for r in items),
                              'total_tokens': sum(r['usage']['total_tokens'] for r in items),
                              'seconds': sum(r.get('elapsed_seconds', 0) for r in items)}
    base = {str(r['task_id']): r for r in groups.get(baseline, [])}
    for arm, items in groups.items():
        if arm == baseline:
            continue
        pairs = [(base[str(r['task_id'])]['final'], r['final']) for r in items if str(r['task_id']) in base]
        measured = [(a,b) for a,b in pairs if a['measured'] and b['measured']]
        wins = sum(not a['joint'] and b['joint'] for a,b in measured)
        losses = sum(a['joint'] and not b['joint'] for a,b in measured)
        n = wins + losses
        p = min(1, 2 * sum(math.comb(n, k) for k in range(min(wins, losses)+1)) / 2**n) if n else 1
        report['paired'][arm] = {'pairs':len(pairs), 'measured_pairs':len(measured), 'wins':wins, 'losses':losses,
                                'p_exact':p, 'functional_harms':sum(a['functional'] and not b['functional'] for a,b in measured)}
    ordered = sorted(report['paired'], key=lambda a: report['paired'][a]['p_exact'])
    previous = 0
    for i, arm in enumerate(ordered):
        previous = max(previous, min(1, report['paired'][arm]['p_exact'] * (len(ordered)-i)))
        report['paired'][arm]['p_holm'] = previous
    return report
