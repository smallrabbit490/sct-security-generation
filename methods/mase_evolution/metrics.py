"""事后统计：固定总分母、缺测、配对退步及选择/记忆指标，不把分数回送解题。"""
from __future__ import annotations
from collections import Counter


def ratio(a, b):
    """分母不存在时返回None用于网页未测量，不将未知记成0%。"""
    return a / b if b else None


def summarize(rows, expected=None):
    """输入已落盘逐题记录→总览/机制指标；缺少步骤评分不虚构修复成功率。

    首次→最终仅是任务级变化。候选上界、选错率来自事后评分，不能部署选择。
    不执行模型/验证器、不修改经验；缺测与待运行分别计数。
    """
    n = len(rows) if expected is None else expected
    if n < len(rows):
        raise ValueError('expected_less_than_recorded')
    ids = [str(r['task_id']) for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate_task_result')
    for row in rows:
        final = row.get('final', {})
        if final.get('joint') is True and not all(final.get(k) is True for k in ('functional', 'security', 'measured')):
            raise ValueError('inconsistent_joint_evidence')
    totals = {k: sum(r.get('final', {}).get(k) is True for r in rows)
              for k in ('functional', 'security', 'joint', 'measured')}
    totals.update(n=n, recorded=len(rows), pending=n-len(rows),
                  missing=n-totals['measured'], joint_rate=ratio(totals['joint'], n),
                  measured_joint_rate=ratio(totals['joint'], totals['measured']))
    attempts = [(r['attempts'][0], r['final']) for r in rows
                if r.get('attempts') and r.get('final') and r['attempts'][0].get('measured') and r['final'].get('measured')]
    rescue = sum(not a.get('joint') and b.get('joint') for a, b in attempts)
    harm = sum(a.get('joint') and not b.get('joint') for a, b in attempts)
    step_pairs = []
    for r in rows:
        for step in r.get('repair_scores', []):
            a, b = step.get('before', {}), step.get('after', {})
            if a.get('measured') and b.get('measured'):
                step_pairs.append((a, b))
    before_pass = sum(bool(a.get('joint')) for a, _ in step_pairs)
    before_fail = len(step_pairs) - before_pass
    totals['repairs'] = {'first_final_measured': len(attempts), 'first_final_rescues': rescue,
                         'first_final_harms': harm, 'step_pairs': len(step_pairs),
                         'step_rescue_rate': ratio(sum(not a.get('joint') and bool(b.get('joint')) for a,b in step_pairs), before_fail),
                         'step_harm_rate': ratio(sum(bool(a.get('joint')) and not b.get('joint') for a,b in step_pairs), before_pass)}
    complete = [r for r in rows if r.get('candidate_scores') and
                all(c.get('measured') for c in r['candidate_scores']) and r.get('final', {}).get('measured')]
    oracle = [r for r in complete if any(c.get('joint') for c in r['candidate_scores'])]
    misses = [str(r['task_id']) for r in oracle if not r['final'].get('joint')]
    totals['selection'] = {'complete_tasks': len(complete), 'oracle_tasks': len(oracle),
                           'misses': len(misses), 'miss_ids': misses, 'miss_rate': ratio(len(misses), len(oracle))}
    decisions = Counter(r.get('memory', {}).get('decision', 'not_recorded') for r in rows)
    totals['memory'] = {'retrieved_tasks': sum(bool(r.get('memory', {}).get('retrieved_id')) for r in rows),
                        'injected_tasks': sum(bool(r.get('memory', {}).get('injected_ids')) for r in rows),
                        'decisions': dict(decisions), 'paired_effect': None}
    audits = [a for r in rows for a in r.get('public_attempts', []) if 'issues' in a]
    totals['interface'] = {'audited': len(audits), 'violating': sum(bool(a['issues']) for a in audits)}
    stages = Counter(e.get('stage', e.get('node_id', 'unknown')) for r in rows for e in r.get('trace', []))
    totals['usage'] = {k: sum(r.get('usage', {}).get(k, 0) for r in rows)
                       for k in ('calls', 'failed_calls', 'total_tokens')}
    totals['usage']['seconds'] = sum(r.get('elapsed_seconds', 0) for r in rows)
    totals['stages'] = dict(stages)
    totals['errors'] = dict(Counter(r.get('error_type') for r in rows if r.get('error_type')))
    events=[]
    def collect(items):
        for event in items:
            events.append(event)
            for nested in event.get('output', {}).get('repeat_rounds', []):
                collect(nested.get('events', []))
    for row in rows:
        collect(row.get('events', []))
    totals['execution']={'recorded_nodes':len(events),'completed_nodes':sum(e.get('status')=='completed' for e in events),
                         'failed_nodes':sum(e.get('status')=='failed' for e in events),
                         'skipped_nodes':sum(e.get('status')=='skipped' for e in events),
                         'missing_input_nodes':sum(e.get('error_type')=='missing_inputs' for e in events),
                         'nodes':dict(Counter(e.get('node_id') for e in events)),
                         'stop_reasons':dict(Counter(e.get('output',{}).get('stop_reason') for e in events if e.get('output',{}).get('stop_reason')))}
    aligned=[]
    for row in rows:
        scores={c.get('code'):c for c in row.get('candidate_scores', []) if c.get('code') and c.get('measured')}
        for public in row.get('public_attempts', []):
            cases=public.get('checks',{}).get('cases',[])
            official=scores.get(public.get('code'))
            if official and cases and all(c.get('measured') and c.get('status') in ('pass','fail') for c in cases):
                aligned.append((not public.get('issues') and all(c['status']=='pass' for c in cases),official['joint']))
    totals['public_alignment']={'compared':len(aligned),
                               'public_pass_official_fail':sum(a and not b for a,b in aligned),
                               'public_fail_official_pass':sum(not a and b for a,b in aligned)}
    totals['cwe'] = {c: {'n': len(group), 'joint': sum(r.get('final', {}).get('joint') is True for r in group)}
                     for c in sorted({str(r.get('cwe', 'unknown')) for r in rows})
                     for group in [[r for r in rows if str(r.get('cwe', 'unknown')) == c]]}
    return totals


def compare(before, after):
    """同题且同family完整测量才配对；返回新增/丢失及功能/安全退步，不声称显著。"""
    a = {str(r['task_id']): r for r in before}
    b = {str(r['task_id']): r for r in after}
    keys = sorted(a.keys() & b.keys())
    valid = [k for k in keys if a[k].get('final', {}).get('measured') and b[k].get('final', {}).get('measured')
             and a[k].get('family_id') == b[k].get('family_id')]
    def changed(field, old, new):
        return [k for k in valid if bool(a[k]['final'].get(field)) == old and bool(b[k]['final'].get(field)) == new]
    wins, losses = changed('joint', False, True), changed('joint', True, False)
    return {'pairs': len(keys), 'measured_pairs': len(valid), 'wins': wins, 'losses': losses,
            'net_joint': len(wins)-len(losses), 'functional_harms': changed('functional', True, False),
            'security_harms': changed('security', True, False), 'unmeasured_pairs': len(keys)-len(valid)}
