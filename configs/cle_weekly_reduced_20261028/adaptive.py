"""阶段结束后的零API扩大决策与训练；不以小样本Joint正负代替最终验证。"""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import random

from .scope import RUN, CONTROL, read, write, frozen_selection, subset_split
from . import granularity_analysis as ga
from configs.cle_weekly_analysis_20261027.retest_analysis import collect


def label_data(include_extra=False):
    packages=['FG_LABELS']+(['FG_LABELS_EXTRA'] if include_extra else [])
    tasks, rows, labels={},[],[]
    for package in packages:
        root=RUN/package
        protocol=read(root/'inputs/protocol.json')
        schedule=read(root/'inputs/schedule.json')
        segments=[Path(p) for p in read(root/'execution_index.json')['segments']]
        if (not segments or read(segments[-1]/'summary.json').get('status')!='completed'
                or read(root/'zero_API_replay/replay_result.json').get('status')!='passed'
                or read(root/'analysis/summary.json').get('status')!='completed'):
            raise ValueError('adaptive_requires_complete_replayed_analyzed_batch:'+package)
        current=read(root/'inputs/tasks.json')
        batch,_,_=collect(segments,schedule)
        if len(batch)!=len(schedule) or any(r['protocol']!=protocol['protocol'] for r in batch):
            raise ValueError('adaptive_batch_incomplete_or_protocol_changed')
        if set(tasks)&set(current):
            raise ValueError('expanded_labels_must_not_repeat_paid_tasks')
        tasks.update(current); rows.extend(batch); labels.extend(ga.make_labels(batch,current))
    split=subset_split(frozen_selection()['original_family_split'],tasks)
    return tasks,rows,labels,split


def readiness(labels, model, development):
    """30族、两类各5族和开发路由两档为预登记工程门，不是收益检验。"""
    usable=[v for v in labels if v['task_id'] in set(model['fit_task_ids'])]
    groups=defaultdict(set)
    for item in usable:
        groups[item['preferred_level']].add(item['family_id'])
    families={v['family_id'] for v in usable}
    routes={r['selected_level'] for r in development['classifier']}
    reasons=[]
    if len(families)<30: reasons.append('training_label_families_below30')
    if sum(len(f)>=5 for f in groups.values())<2: reasons.append('fewer_than_two_classes_with5_training_families')
    if model['type']=='constant': reasons.append('classifier_is_constant')
    if len(routes)<2: reasons.append('development_routes_fewer_than2_levels')
    return {'ready':not reasons,'reasons':reasons,'training_label_families':len(families),
        'class_training_families':{k:len(v) for k,v in groups.items()},'development_routed_levels':sorted(routes)}


def decide_gr(extra=False):
    tasks,rows,labels,split=label_data(extra)
    model=ga.fit_model(rows,tasks,split,labels)
    development=ga.development_results(rows,tasks,split,model)
    check=readiness(labels,model,development)
    levels={v['preferred_level'] for v in labels if v['preferred_level']}
    intervention=any(v['any_memory_intervention'] for v in labels)
    action=('freeze_and_gate' if check['ready'] else 'expand' if not extra and intervention and len(levels)>=2 else 'close_classifier_exploration')
    result={'status':'decided','action':action,'completed_tasks':len(tasks),'completed_cells':len(rows),
        'readiness':check,'preferred_level_counts':dict(Counter(v['preferred_level'] for v in labels if v['preferred_level'])),
        'meaning':'training readiness only; Joint efficacy decided by frozen full298 comparison',
        'no_adaptive_RNG_or_hyperparameter_sweep':True,'new_API_calls':0,'max_tasks':164}
    write(CONTROL/('GR_decision_164.json' if extra else 'GR_decision_82.json'),result)
    write(CONTROL/'GR_decision.json',result)
    return result


def train():
    decision=read(CONTROL/'GR_decision.json')
    if decision['action']!='freeze_and_gate':
        raise ValueError('classifier_training_requires_registered_readiness')
    tasks,rows,labels,split=label_data(decision['completed_tasks']==164)
    model=ga.fit_model(rows,tasks,split,labels)
    model.update(protocol='cle-reduced-granularity-family-router-20261028-v1',
        source_protocol=read(RUN/'FG_LABELS/inputs/protocol.json')['protocol'],
        source_batches=['FG_LABELS']+(['FG_LABELS_EXTRA'] if len(tasks)==164 else []),
        completed_label_tasks=len(tasks))
    destination=RUN/'FG_TRAIN'
    if (destination/'model.json').exists() and read(destination/'model.json')!=model:
        raise ValueError('existing_frozen_classifier_cannot_be_overwritten')
    write(destination/'model.json',model); write(destination/'labels.json',labels)
    write(destination/'development.json',ga.development_results(rows,tasks,split,model))
    write(destination/'summary.json',{'status':'completed','paid_API_calls':0,
        'training_tasks':len(split['train_task_ids']),'development_tasks':len(split['development_task_ids']),
        'usable_label_tasks':len(model['fit_task_ids']),'classifier_type':model['type'],
        'source_batches':model['source_batches'],'development_not_used_for_fit':True})
    return read(destination/'summary.json')


def retrieval_statistics(records, labels):
    """以题目为重采样单位估计三查询候选召回的区间；未裁决标签不当负类。"""
    values=defaultdict(list)
    pending=0
    for record in records:
        pairs=set(record['pair_ids'])
        if any(labels.get(p) not in ('direct','conditional','irrelevant','conflict') for p in pairs):
            pending+=1
            continue
        direct={p for p in pairs if labels[p]=='direct'}
        if not direct:
            continue
        for mode,trace in record['traces'].items():
            candidates={record['card_to_pair'][i] for i in trace['candidate_ids']}
            values[mode].append(len(direct&candidates)/len(direct))
    output={}
    for mode,items in values.items():
        rng=random.Random('20261028-FR-'+mode)
        draws=sorted(sum(rng.choices(items,k=len(items)))/len(items) for _ in range(2000))
        output[mode]={'tasks_with_direct':len(items),'mean':sum(items)/len(items),
            'ci95':[draws[49],draws[1949]],'half_width':(draws[1949]-draws[49])/2}
    return output,pending


def decide_fr(extra=False):
    from . import retrieval_execute as executor
    packages=['FR']+(['FR_EXTRA'] if extra else [])
    records,labels,selected=[],{},set()
    for package in packages:
        root=RUN/package
        if read(root/'zero_API_replay.json').get('status')!='passed':
            raise ValueError('retrieval_decision_requires_zero_API_replay')
        sources=[Path(p) for p in read(root/'execution_index.json')['segments']]
        if not sources or read(sources[-1]/'summary.json').get('status')!='awaiting_human_confirmation':
            raise ValueError('retrieval_decision_requires_completed_AI_stage')
        public=read(root/'inputs/public_tasks.json')
        current=[read(p) for p in (root/'records').glob('*.json')]
        if len(current)!=len(public): raise ValueError('retrieval_pools_incomplete')
        if selected&set(public): raise ValueError('retrieval_expansion_repeats_tasks')
        selected.update(public);records.extend(current)
        cached=read(root/'reused_AI_labels.json') if (root/'reused_AI_labels.json').exists() else []
        for item in list(executor.saved_labels(sources).values())+cached:
            labels[item['pair_id']]=item.get('label')
    selection=frozen_selection(); missing=[]
    for pool,path in [('D_grow',RUN/'FG_LABELS/inputs_contract_v2/tasks.json'),('D_gate',RUN/'FQ_GATE/inputs_v3/tasks.json')]:
        all_tasks=read(path); counts=Counter(str(t['CWE_ID']) for t in all_tasks.values())
        observed={str(t['CWE_ID']) for i,t in all_tasks.items() if i in selected}
        missing.extend(pool+':'+c for c,n in counts.items() if n/len(all_tasks)>=.05 and c not in observed)
    statistics,pending=retrieval_statistics(records,labels)
    # 无正类、待裁决或有效题太少时不能把区间宽度伪设为零。
    imprecise=(len(statistics)<3 or any(v['tasks_with_direct']<20 or v['half_width']>.10 for v in statistics.values()))
    result={'status':'decided','action':'expand' if not extra and (missing or imprecise) else 'finish_sampled_retrieval',
        'completed_tasks':len(selected),'missing_major_CWE_strata':missing,'candidate_recall_intervals':statistics,
        'pending_label_task_pools':pending,'max_tasks':114,'new_API_calls':0,
        'label_basis':'AI_assisted_estimate; human confirmation separate','full_library_recall':'unmeasured',
        'no_relabel_or_regenerate_previous_pairs':True}
    write(CONTROL/('FR_decision_114.json' if extra else 'FR_decision_57.json'),result)
    write(CONTROL/'FR_decision.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['gr-first','gr-extra','fr-first','fr-extra','train'])
    args=parser.parse_args()
    action={'gr-first':lambda:decide_gr(False),'gr-extra':lambda:decide_gr(True),
        'fr-first':lambda:decide_fr(False),'fr-extra':lambda:decide_fr(True),'train':train}[args.action]
    import json
    print(json.dumps(action(),ensure_ascii=False))


if __name__=='__main__':
    main()
