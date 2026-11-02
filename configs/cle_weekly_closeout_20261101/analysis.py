"""零API复算本次有界批次；保留计划分母、重复、题族与尚未阅读的案例。"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone

from configs.cle_memory_q_full_gate_cap3_20261019.analyze import paired
from configs.cle_weekly_reduced_20261028 import retest_analysis as qa
from configs.cle_weekly_reduced_20261028 import granularity_analysis as ga
from configs.cle_scientific_review_20261028.router import opportunity, fit_model
from .resume import KINDS, RUN, READ


def compare(rows, target, control, planned_pairs):
    data = [{**r, 'task_id': f"{r['task_id']}_r{r['repeat']}",
             'arm': r['condition']} for r in rows if r['condition'] in (target, control)]
    result = paired(data, target=target, control=control, seed=20261101)
    result.pop('p_mcnemar_supplement', None)
    result['planned_pairs'] = planned_pairs
    result['not_yet_paired'] = planned_pairs-result['pairs']
    if not result['measured_pairs']:
        result['p_family_swap'] = None
        result['ci95_family_bootstrap'] = None
    by = {(str(r['task_id']), r['repeat'], r['condition']): r for r in rows}
    result['repeat_comparisons'] = {}
    for repeat in (1, 2):
        changes = []
        for tid in sorted({str(r['task_id']) for r in rows}):
            a, b = by.get((tid, repeat, target)), by.get((tid, repeat, control))
            if a and b and a['final']['measured'] and b['final']['measured']:
                changes.append(int(a['final']['joint'])-int(b['final']['joint']))
        result['repeat_comparisons'][str(repeat)] = {
            'measured_pairs': len(changes), 'net_joint': sum(changes),
            'difference': sum(changes)/len(changes) if changes else None}
    return result


def arms(rows, conditions, planned_per_arm):
    result = {}
    for c in conditions:
        group = [r for r in rows if r['condition'] == c]
        by = defaultdict(dict)
        for r in group:
            by[str(r['task_id'])][r['repeat']] = r['final']
        twice = [v for v in by.values() if set(v) == {1,2} and all(x['measured'] for x in v.values())]
        result[c] = {'first': qa.metrics([r.get('first', r.get('attempts', [{}])[0]) for r in group], planned_per_arm),
            'final': qa.metrics([r['final'] for r in group], planned_per_arm),
            'repeat_variability': {'tasks_with_two_measured_repeats': len(twice),
                'Joint_discordant_tasks': sum(v[1]['joint'] != v[2]['joint'] for v in twice)}}
    return result


def training_opportunity(rows, tasks, train_ids):
    """只用训练题估算按题选档的观察上限；不把事后最优当分类器成绩。"""
    by = {(str(r['task_id']), r['repeat'], r['condition']): r for r in rows}
    complete = [tid for tid in train_ids if all(
        (tid, repeat, level) in by and by[tid, repeat, level]['final']['measured']
        for repeat in (1, 2) for level in ga.LEVELS)]
    scores = {level: sum(int(by[tid, repeat, level]['final']['joint'])
              for tid in complete for repeat in (1, 2)) for level in ga.LEVELS}
    best = max(scores.values()) if complete else None
    oracle = sum(max(sum(int(by[tid, repeat, level]['final']['joint'])
                     for repeat in (1, 2)) for level in ga.LEVELS) for tid in complete) if complete else None
    return {**opportunity(rows, tasks, train_ids), 'complete_training_tasks':len(complete),
        'observed_fixed_level_joint_counts':scores, 'best_observed_fixed_joint':best,
        'hindsight_per_task_joint':oracle, 'potential_net_joint':oracle-best if complete else None,
        'paired_observations':2*len(complete),
        'not_classifier_performance':True,
        'interpretation':'optimistic selection using the same two observed repeats; development results unused'}


def label_readiness(rows, tasks, split, labels, out):
    """完整回放后评估原训练门；只存开发候选，不发布分类器或派发评价。"""
    from configs.cle_weekly_reduced_20261028.adaptive import readiness
    model = fit_model(rows, tasks, split, labels)
    development = ga.development_results(rows, tasks, split, model)
    by = {(str(r['task_id']),r['repeat'],r['condition']):r for r in rows}
    development['fixed_L1'] = [{'task_id':tid,'family_id':tasks[tid]['family_id'],
        'repeat':repeat,'selected_level':'L1','final':by[tid,repeat,'L1']['final']}
        for tid in split['development_task_ids'] for repeat in (1,2)]
    check = readiness(labels, model, development)
    qa.write(out/'candidate_model.json', model)
    qa.write(out/'development_routes.json', development)
    result = {'status':'analyzed','readiness':check,'paid_API_calls':0,
        'selection_objective':model['selection_objective'],
        'development_comparisons':[compare(
            [{**r,'condition':policy} for policy,items in development.items() for r in items],
            'classifier',control,len(split['development_task_ids'])*2)
            for control in ('fixed_L1','fixed','rule')],
        'candidate_only':True,'formal_classifier_frozen':False,
        'automatic_expansion':False,'paid_gate_dispatched':False}
    qa.write(out/'training_readiness.json',result)
    return result


def q_results(rows, paths, planned=540):
    conditions = qa.CONDITIONS
    per_arm = planned//len(conditions)
    comparisons = [compare(rows, a, b, per_arm) for a,b in qa.COMPARISONS]
    previous = 0.0
    for rank, item in enumerate(sorted((c for c in comparisons if c['p_family_swap'] is not None), key=lambda c:c['p_family_swap'])):
        previous = max(previous, min(1., item['p_family_swap']*(5-rank)))
        item['exploratory_Holm5_p'] = previous
    by = {(str(r['task_id']), r['repeat'], r['condition']):r for r in rows}
    mechanisms = []
    for target, control in qa.COMPARISONS:
        for tid, repeat in sorted({(str(r['task_id']),r['repeat']) for r in rows}):
            a,b = by.get((tid,repeat,target)), by.get((tid,repeat,control))
            if a and b:
                mechanisms.append(qa.first_mechanism(a,b))
    counts = {}
    for a,b in qa.COMPARISONS:
        items = [m for m in mechanisms if m['treated']==a and m['control']==b]
        counts[a+'_vs_'+b] = {
            'paired_cells':len(items),
            'common_candidates_verified':sum(m['same_first_candidates'] is True for m in items),
            'common_candidates_mismatched':sum(m['same_first_candidates'] is False for m in items),
            'selected_members_changed_with_common_candidates':sum(m['selected_members_changed'] and m['same_first_candidates'] is True for m in items),
            'new_members_declared_adopted_with_common_candidates':sum(bool(m['newly_selected_declared_adopted_ids']) and m['same_first_candidates'] is True for m in items)}
    return {'arms': arms(rows,conditions,per_arm), 'comparisons':comparisons,
        'primary_comparison':'Q2_K3 vs Q1',
        'inference_plan':{'primary_count':1,'primary_test':'two-sided family sign swap',
            'alpha':0.05,'primary_p_field':'p_family_swap','diagnostic_p_field':'exploratory_Holm5_p',
            'positive_evidence':'complete registered batch, positive difference, CI lower bound > 0, primary p < 0.05',
            'negative_evidence':'complete registered batch, negative difference, CI upper bound < 0, primary p < 0.05',
            'otherwise':'report observed contrast; no stable direction established',
            'scope':'fixed 54 learning tasks; no cross-family conclusion'},
        'mechanism_counts':counts}, mechanisms, qa.review_queue(mechanisms,paths)


def write_report(summary, out, title, scope):
    lines = [f'# {title}', '', scope, '',
        f"已保存{summary['completed']}/{summary['planned']}次；统计状态：{summary['status']}。", '',
        '| 条件 | 已保存 | 可测 | 功能通过 | 安全通过 | Joint通过 |', '|---|---:|---:|---:|---:|---:|']
    for name,value in summary['arms'].items():
        f=value['final']
        lines.append(f"| {name} | {f['completed']} | {f['measured']} | {f['functional']} | {f['security']} | {f['joint']} |")
    if summary.get('comparisons'):
        lines += ['', '| 比较 | 可测配对 | 救回/损失 | Joint差 | 题族95%区间 |', '|---|---:|---|---|---|']
        for c in summary['comparisons']:
            lines.append(f"| {c['target']}−{c['control']} | {c['measured_pairs']} | {c['wins']}/{c['losses']} | {c['difference']} | {c['ci95_family_bootstrap']} |")
    lines += ['', '同题两次运行分别配对，区间按关联题族整体重采样。尚未执行与测量失败分别登记，不写成已经测试失败。', '',
        '选中编号、模型声明采用和代码正确落实分别检查。案例清单列出需要实际阅读的题面、卡、计划、代码和测试；生成清单不代表原因已经核定。', '',
        '下一步：完成主要配对差异题复盘并回答来源要求；不自动扩大题数或启动排队全量。']
    (out/'analysis.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def analyze(kind):
    from pathlib import Path
    root, planned, _ = KINDS[kind]
    sources = [Path(s) for s in READ(root/'execution_index.json')['segments']]
    schedule = READ(root/'inputs/schedule.json')
    rows, paths, copies = qa.collect(sources, schedule)
    out = root/'analysis_20261101'
    if kind == 'gr':
        summary = ga.run(RUN, train=False)
        summary['comparisons'] = [compare(rows,level,'L1',len(schedule)//5) for level in ('L0','L2','L3','L4')]
        previous=0.
        for rank,item in enumerate(sorted((c for c in summary['comparisons'] if c['p_family_swap'] is not None),key=lambda c:c['p_family_swap'])):
            previous=max(previous,min(1.,item['p_family_swap']*(4-rank)))
            item['exploratory_Holm4_p']=previous
        summary['arms']=arms(rows,ga.LEVELS,len(schedule)//5)
        tasks=READ(root/'inputs/tasks.json')
        split=READ(root/'inputs/family_split.json')
        summary['training_opportunity']=training_opportunity(rows,tasks,split['train_task_ids'])
        replay=root/'zero_API_replay/replay_result.json'
        if summary['status']=='completed' and replay.exists() and READ(replay).get('status')=='passed':
            summary['training_readiness']=label_readiness(rows,tasks,split,READ(root/'analysis/labels.json'),out)
        summary['case_review_status']='pending_actual_code_review'
        title='82题五档记忆结果'
        scope='82道固定题、五档、每档两次；全量820次完成后再评价真实标签是否支持训练。'
    else:
        summary, mechanisms, cases = q_results(rows,paths,planned)
        summary.update(status='completed' if len(rows)==len(schedule)==planned and READ(sources[-1]/'state.json')['status']=='completed' else 'partial',
            completed=len(rows),planned=planned,costs=qa.cost_snapshot(sources),
            case_review_status='pending_actual_code_review')
        qa.write(out/'mechanisms.json',mechanisms)
        qa.write(out/'case_review_queue.json',cases)
        title='54题新Q冻结回测'
        scope='五条件各108次，均来自相同54道增长集题。主要问题是K3学习Q相对相似度排序的同题收益；跨题族迁移另有任务。'
    summary.update(observed_utc=datetime.now(timezone.utc).isoformat(),paid_API_calls_by_analysis=0,
        identical_duplicate_row_copies=copies,source_segments=list(map(str,sources)))
    qa.write(out/'summary.json',summary)
    write_report(summary,out,title,scope)
    return summary


def fs_snapshot():
    rows=READ(RUN/'FFS/analysis/paused_prefix_20261029/per_cell.json')
    summary={'status':'fixed_saved_prefix','completed':len(rows),'planned':2980,
        'unique_tasks':len({r['task_id'] for r in rows}),
        'arms':arms(rows,('B0','BM','BF','BS','BFS'),596),
        'comparisons':[compare(rows,a,b,596) for a,b in (('BFS','BM'),('BM','B0'),('BF','BM'),('BS','BM'))],
        'paid_API_calls_by_analysis':0,'observed_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'2433 saved observations only; no imputation for the unexecuted 547'}
    summary['repeat_arms']={str(repeat):arms([r for r in rows if r['repeat']==repeat],
        ('B0','BM','BF','BS','BFS'),298) for repeat in (1,2)}
    # 原卡对无卡属于已观察结果上的补充分析，不能回写为预先登记的主要比较。
    summary['primary_comparison']='BFS vs BM'
    summary['secondary_observed_comparison']='BM vs B0'
    out=RUN/'FFS/analysis/paired_20261101'
    qa.write(out/'summary.json',summary)
    write_report(summary,out,'功能安全对照的现有配对结果','固定复用2433次结果，按两次重复和真实题族复算；本次新增模型调用为0。')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('kind',choices=('q','gr','fs'))
    args=p.parse_args()
    result=fs_snapshot() if args.kind=='fs' else analyze(args.kind)
    print({k:result[k] for k in ('status','completed','planned')})
