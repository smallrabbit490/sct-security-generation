"""Q实验规格报告：重算全分母配对、保守区间、曝光与门槛，完全不请求模型。"""
from __future__ import annotations
import argparse
import json
from math import comb
from pathlib import Path
from methods.cle_ablation.audit_memory_q import check_run, read_rows
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_branch_gate_study import paired_binary, holm


def cp_bounds(x, n, alpha=0.025):
    """二项计数的97.5%精确边界；两个区间联合用于95%保守配对差界。"""
    if not n:
        return 0.0, 1.0
    def solve(tail, increasing):
        left, right = 0.0, 1.0
        for _ in range(60):
            mid = (left+right)/2
            value = sum(comb(n,k)*mid**k*(1-mid)**(n-k) for k in tail)
            if (value < alpha/2) == increasing:
                left = mid
            else:
                right = mid
        return (left+right)/2
    return (0.0 if x == 0 else solve(range(x,n+1), True),
            1.0 if x == n else solve(range(x+1), False))


def paired_effect(rows, old, new):
    by_arm = {a: {str(r['task_id']):r for r in rows if r['arm']==a} for a in (old,new)}
    assert by_arm[old].keys() == by_arm[new].keys(), 'incomplete pairing'
    result = paired_binary({k:r['final']['joint'] for k,r in by_arm[old].items()},
                           {k:r['final']['joint'] for k,r in by_arm[new].items()})
    n = result['pairs']
    win, loss = cp_bounds(result['new_only'],n), cp_bounds(result['old_only'],n)
    result['conservative_95_ci_percentage_points'] = [100*(win[0]-loss[1]),100*(win[1]-loss[0])]
    result['functional_rescues'] = sum(not r['final']['functional'] and by_arm[new][k]['final']['functional'] for k,r in by_arm[old].items())
    result['functional_harms'] = sum(r['final']['functional'] and not by_arm[new][k]['final']['functional'] for k,r in by_arm[old].items())
    return result


def build(root):
    checks = {'learn':check_run(root/'learn'), 'compare':check_run(root/'compare')}
    learn, rows = read_rows(root/'learn/rows.jsonl'), read_rows(root/'compare/rows.jsonl')
    events = read_rows(root/'learn/memory_q_events.jsonl')
    # 固定库没有经验进化外轮，策略由run_one实测记录确定；保留原始事件，另导出完整规格字段。
    with (root/'memory_q_events.export.jsonl').open('w',encoding='utf-8') as exported:
        for event in events:
            exported.write(json.dumps({'outer_round':0,'selection_policy':'semantic_llm',
                'q_before':None,'q_after':None,'q_visits':None, **event},ensure_ascii=False)+'\n')
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    summary = json.loads((root/'compare/summary.json').read_text(encoding='utf-8'))
    families = [{r['family_id'] for r in group} for group in (learn,rows)]
    assert not families[0] & families[1]
    assert len(families[0]) == len(learn) and len(families[1]) == len(manifest['development'])
    arms=summary['arms']
    source_memory = read_rows(root/'compare/input_memory.jsonl')
    shuffled = read_rows(root/'compare/input_shuffled_memory.jsonl')
    assert sorted((n['q_value'],n['q_visits']) for n in source_memory) == sorted((n['q_value'],n['q_visits']) for n in shuffled)
    strip_q = lambda bank: [{k:v for k,v in n.items() if k not in ('q_value','q_visits')} for n in bank]
    assert strip_q(source_memory) == strip_q(shuffled), 'placebo changed experience content'
    gate = (arms['Q2']['joint'] > arms['Q1']['joint'] and arms['Q2']['functional'] >= arms['Q1']['functional']
            and arms['Q2']['measured'] >= 23 and arms['Q2']['errors'] <= arms['Q1']['errors'])
    exposure={}
    for arm in arms:
        attempts=[a for r in rows if r['arm']==arm for a in r['attempts']]
        retrieved=sum(len(a.get('generation',{}).get('retrieved_cards',[])) for a in attempts)
        adopted=sum(len(a.get('generation',{}).get('cards',[])) for a in attempts)
        exposure[arm]={'attempts':len(attempts),'retrieved':retrieved,'adopted':adopted,
                       'adoption_fraction':adopted/retrieved if retrieved else None,
                       'workflow_incomplete':sum(not a.get('generation',{}).get('workflow_completed') for a in attempts)}
    result={'protocol':'cle-q-autonomous-v2','role':'PLT_development_only','manifest':manifest,
            'checks':checks, 'learning_rows':len(learn), 'comparison_rows':len(rows), 'arms':arms,
            'paired_complete_measured':summary['paired'],
            'primary_full_denominator_Q2_vs_Q1':paired_effect(rows,'Q1','Q2'),
            'placebo_full_denominator_Q2_vs_Q3':paired_effect(rows,'Q3','Q2'),
            'mechanism':summary['mechanism'], 'exposure':exposure,
            'rewards':{'positive':sum(e.get('reward')==1 and e.get('invariant_id') is not None for e in events),
                       'negative':sum(e.get('reward')==-1 and e.get('invariant_id') is not None for e in events),
                       'skipped':sum(bool(e.get('skip_reason')) for e in events),
                       'visited_cards':len({e['invariant_id'] for e in events if e.get('reward') is not None and e.get('invariant_id') is not None})},
            'confirmation_gate_passed':gate,
            'cost':{stage:json.loads((root/stage/'cost.json').read_text(encoding='utf-8')) for stage in ('learn','compare')}}
    result['by_cwe'] = {}
    for cwe in manifest['cwes']:
        result['by_cwe'][cwe] = {}
        for arm in arms:
            items = [r for r in rows if r['arm']==arm and r['cwe']==cwe]
            result['by_cwe'][cwe][arm] = {'n':len(items), **{
                key:sum(r['final'][key] for r in items) for key in ('functional','security','joint','measured')}}
    result['mechanism_changed_tasks'] = len({r['task_id'] for r in summary['mechanism'] if r['set_changed']})
    new_adopted=[]
    readouts={(str(m['task_id']),m['attempt']):m for m in summary['mechanism']}
    for row in rows:
        if row['arm']!='Q2':continue
        for attempt in row['attempts']:
            readout=readouts[(str(row['task_id']),attempt['attempt'])]
            added=set(readout['q_ids_same_query'])-set(readout['similarity_ids_same_query'])
            adopted={c['invariant_id'] for c in attempt.get('generation',{}).get('cards',[])}
            if added & adopted:
                new_adopted.append({'task_id':row['task_id'],'attempt':attempt['attempt'],'ids':sorted(added & adopted)})
    result['q_added_cards_actually_adopted'] = new_adopted
    result['q_added_adopted_tasks'] = len({r['task_id'] for r in new_adopted})
    planned=[result['primary_full_denominator_Q2_vs_Q1'],result['placebo_full_denominator_Q2_vs_Q3']]
    for comparison, adjusted in zip(planned,holm([c['p_exact_two_sided'] for c in planned])):
        comparison['p_holm_two_planned'] = adjusted
    write(root/'analysis.json',result)
    lines=['# CLE记忆Q v2开发结果','', '| 臂 | n | F | S | Joint | 完整测量 | 流程错误 | 调用 | Token |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for a,s in arms.items():
        lines.append('| '+a+' | '+' | '.join(str(s[k]) for k in ('n','functional','security','joint','measured','errors','calls','total_tokens'))+' |')
    lines+=['','主比较（全分母）：`'+json.dumps(result['primary_full_denominator_Q2_vs_Q1'],ensure_ascii=False)+'`',
             '', '安慰剂对照：`'+json.dumps(result['placebo_full_denominator_Q2_vs_Q3'],ensure_ascii=False)+'`',
             '', '条件确认门：'+str(gate),'', '开发评分不等于独立Base/Plus结果。零提升、缺测、流程错误和成本均保留。']
    (root/'analysis.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    print(json.dumps({'confirmation_gate_passed':build(parser.parse_args().root)['confirmation_gate_passed']}))
