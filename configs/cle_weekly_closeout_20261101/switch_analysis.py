"""换模前后分层复算：同题配对只在相同模型来源内进行，混合前缀单独报告。"""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

from . import analysis as native
from .switch_flash import MODEL,OLD,RUN,READ,root_for,switch_dir,completed_rows
from methods.sct_trajectory.replay_journal import write_json

COHORTS=('1017_only','flash_only','mixed_saved_prefix')
NAMES={'1017_only':'1017模型完整结果','flash_only':'无1017模型完整生成结果','mixed_saved_prefix':'复用1017成功前缀后接续的结果'}


def stratum(rows,paths,kind):
    conditions=native.qa.CONDITIONS if kind=='q' else native.ga.LEVELS
    comparisons=native.qa.COMPARISONS if kind=='q' else [(level,'L1') for level in ('L0','L2','L3','L4')]
    if kind=='q':
        result,mechanisms,cases=native.q_results(rows,paths,540)
        result['mechanisms']=mechanisms;result['case_review_queue']=cases
    else:
        result={'comparisons':[native.compare(rows,a,b,len({(str(r['task_id']),r['repeat']) for r in rows})) for a,b in comparisons]}
        pvalues=sorted((c for c in result['comparisons'] if c['p_family_swap'] is not None),key=lambda c:c['p_family_swap'])
        previous=0.
        for rank,item in enumerate(pvalues):
            previous=max(previous,min(1.,item['p_family_swap']*(4-rank)));item['exploratory_Holm4_p']=previous
    # 每一来源实际观察数为描述统计分母；整个固定名单的完成数另列，不能冒充单模型全量。
    result['arms']={c:{'first':native.qa.metrics([r.get('first',r.get('attempts',[{}])[0]) for r in rows if r['condition']==c],sum(r['condition']==c for r in rows)),
                       'final':native.qa.metrics([r['final'] for r in rows if r['condition']==c],sum(r['condition']==c for r in rows))} for c in conditions}
    result.update(completed=len(rows),unique_tasks=len({r['task_id'] for r in rows}),
        scope='observed model-homogeneous subset of the original fixed schedule; not a completed full-set model comparison',
        unexecuted_cells_counted_as_failures=False,case_review_status='pending_actual_code_review')
    for comp in result['comparisons']:
        pairkeys={(str(r['task_id']),r['repeat']) for r in rows if r['condition'] in (comp['target'],comp['control'])}
        comp['planned_pairs']=len(pairkeys);comp['not_yet_paired']=len(pairkeys)-comp['pairs']
        comp['cross_model_pairs_included']=False
    if kind=='q':result['inference_plan']['scope']=result['scope']
    return result


def analyze(kind):
    root=root_for(kind);out=switch_dir(kind)/'analysis';out.mkdir(exist_ok=True)
    sources=[Path(p) for p in READ(root/'execution_index.json')['segments']]
    schedule=READ(root/'inputs/schedule.json');rows,paths,copies=native.qa.collect(sources,schedule)
    all_complete=len(rows)==len(schedule) and READ(sources[-1]/'state.json')['status']=='completed'
    replay_file=switch_dir(kind)/'replay_result.json'
    replay=READ(replay_file) if replay_file.exists() else {}
    summaries={};cases=[]
    for cohort in COHORTS:
        items=[r for r in rows if r.get('model_cohort','1017_only')==cohort]
        result=stratum(items,paths,kind)
        if kind=='q':
            for case in result.pop('case_review_queue'):cases.append({**case,'model_cohort':cohort})
            write_json(out/(cohort+'_mechanisms.json'),result.pop('mechanisms'))
        summaries[cohort]=result
        write_json(out/(cohort+'.json'),result)
    budget=READ(sources[-1]/'budget.json');model_costs={}
    for entry in budget['entries']:
        m=entry['model'];c=model_costs.setdefault(m,dict(physical_HTTP=0,known_reported_tokens=0,unknown_or_inflight_HTTP=0))
        c['physical_HTTP']+=1
        usage=entry.get('usage')
        if isinstance(usage,dict) and type(usage.get('total_tokens')) is int:c['known_reported_tokens']+=usage['total_tokens']
        else:c['unknown_or_inflight_HTTP']+=1
    summary=dict(status='completed' if all_complete and replay.get('status')=='passed' else 'partial',
        completed=len(rows),planned=len(schedule),model=MODEL,old_model=OLD,model_strata=summaries,
        physical_cost_by_requested_model=model_costs,cumulative_costs=native.qa.cost_snapshot(sources),
        pooled_Joint_rate=None,model_transition_is_not_a_paired_model_effect=True,
        identical_duplicate_row_copies=copies,source_segments=list(map(str,sources)),
        replay_status=replay.get('status','not_started'),case_review_status='pending_actual_code_review',
        observed_utc=datetime.now(timezone.utc).isoformat(),paid_API_calls_by_analysis=0)
    if kind=='gr':
        tasks=READ(root/'inputs/tasks.json');split=READ(root/'inputs/family_split.json');label_sets={}
        for cohort in COHORTS:
            items=[r for r in rows if r.get('model_cohort','1017_only')==cohort]
            labels=native.ga.make_labels(items,tasks);label_sets[cohort]=labels
            write_json(out/(cohort+'_labels.json'),labels)
            for label in labels:
                if label['label_status']=='incomplete_grid':continue
                key=(cohort,label['label_status'],label['preferred_level'])
                if any(tuple(v.get('label_key',[]))==key for v in cases):continue
                cases.append(dict(model_cohort=cohort,label_key=list(key),task_id=label['task_id'],
                    rows=[paths[r['cell_id']] for r in items if str(r['task_id'])==label['task_id']],
                    review_status='pending_actual_case_review',cause=None))
        pure=[r for r in rows if r.get('model_cohort')=='flash_only']
        counts=Counter(str(r['task_id']) for r in pure)
        eligible={tid for tid,count in counts.items() if count==10}
        summary['pure_flash_complete_label_tasks']=len(eligible)
        summary['training_readiness']={'status':'waiting_complete_batch_and_replay','automatic_expansion':False}
        if summary['status']=='completed':
            selected={tid:tasks[tid] for tid in eligible};filtered=[r for r in pure if str(r['task_id']) in eligible]
            partition={**split,'train_task_ids':[tid for tid in split['train_task_ids'] if tid in eligible],
                'development_task_ids':[tid for tid in split['development_task_ids'] if tid in eligible]}
            families={str(tasks[tid]['family_id']) for tid in partition['train_task_ids']}
            partition['family_cv_fold']={f:v for f,v in split['family_cv_fold'].items() if f in families}
            if partition['train_task_ids'] and partition['development_task_ids']:
                labels=native.ga.make_labels(filtered,selected)
                summary['training_readiness']=native.label_readiness(filtered,selected,partition,labels,out)
            else:
                summary['training_readiness']={'status':'insufficient_homogeneous_training_or_development_tasks',
                    'automatic_expansion':False,'formal_classifier_frozen':False,'paid_gate_dispatched':False}
    write_json(out/'case_review_queue.json',cases)
    write_json(out/'summary.json',summary)
    lines=['# Q回测换模分层分析' if kind=='q' else '# 记忆标签换模分层分析','',
        f'固定名单已保存{len(rows)}/{len(schedule)}次。模型变化前后的结果分别统计，混合前缀独立列出。','',
        '| 来源 | 条件 | 保存 | 已测量 | 功能通过 | 安全通过 | Joint通过 |','|---|---|---:|---:|---:|---:|---:|']
    for cohort,s in summaries.items():
        for condition,arm in s['arms'].items():
            a=arm['final'];lines.append(f"| {NAMES[cohort]} | {condition} | {a['completed']} | {a['measured']} | {a['functional']} | {a['security']} | {a['joint']} |")
    lines+=['','配对分析只纳入模型来源一致的task×repeat，保留原题族区间和校正。不同模型覆盖不同未完成单元，换模前后总体差值不能解释为换模型本身的收益。',
        '复用旧响应不产生新HTTP，物理费用按实际请求模型分别记账；源卡库与固定历史材料继续沿用原协议。',
        '下一步：完成每一来源的主要差异题代码复盘，回答原研究要求；排队全量继续跳过。']
    (out/'analysis.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return summary
