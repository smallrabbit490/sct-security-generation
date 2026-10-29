"""跨条件的选卡、冻结Q覆盖、模型波动及逻辑成本复算，无API调用。"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from pathlib import Path

from .policies import ROOT,RUN,read,rows_for
from .report import ids
from methods.sct_trajectory.replay_journal import write_json


def jaccard(a,b):return len(set(a)&set(b))/len(set(a)|set(b)) if set(a)|set(b) else 1.


def q_statistics(stage,rows,visits):
    arms=defaultdict(list)
    for row in rows:arms[row['condition']].append(row)
    result={}
    for arm,items in arms.items():
        candidates=[];selected=[];adopted=[];sets=defaultdict(list)
        for row in items:
            if stage=='D03a' and row.get('status')!='completed':continue
            attempt=(row.get('attempts') or [{}])[0]
            trace=row.get('retrieval_trace') or attempt.get('retrieval_trace') or {}
            candidates.extend(trace.get('presented_candidate_ids',trace.get('candidate_ids',[])))
            picked=row.get('selected_ids') or trace.get('selected_ids',[]) or []
            selected.extend(picked);sets[str(row['task_id'])].append(picked)
            adopted.extend(ids(attempt.get('generation',{}).get('cards',[])))
        def coverage(values):
            return {'occurrences':len(values),'with_feedback_visits_gt_zero':sum(visits.get(str(i),0)>0 for i in values),
                'unique':len(set(values)),'fraction':sum(visits.get(str(i),0)>0 for i in values)/len(values) if values else None}
        within=[1-jaccard(a,b) for values in sets.values() for a,b in combinations(values,2)]
        result[arm]={'candidates':coverage(candidates),'selected':coverage(selected),'adopted_c0':coverage(adopted),
            'unmeasured_selection_trials':sum(r.get('status')!='completed' for r in items) if stage=='D03a' else None,
            'within_arm_mean_set_distance':sum(within)/len(within) if within else None,
            'definition':'visits>0 includes learned zero Q; not q_value!=0; repeats are not new independent tasks'}
    if 'Q0' in arms:
        base={(str(r['task_id']),r['repeat']):r for r in arms['Q0']}
        for arm,items in arms.items():
            changed=adopted_new=mismatched=paired_count=0;distance=[];details=[]
            for row in items:
                key=str(row['task_id']),row['repeat']
                if key not in base:continue
                if stage=='D03a' and (row.get('status')!='completed' or base[key].get('status')!='completed'):continue
                def extract(r):
                    a=(r.get('attempts') or [{}])[0];t=r.get('retrieval_trace') or a.get('retrieval_trace') or {}
                    return r.get('selected_ids',t.get('selected_ids',[])),t,ids(a.get('generation',{}).get('cards',[]))
                selected_a,trace_a,used=extract(row);selected_b,trace_b,_=extract(base[key])
                new=sorted(set(selected_a)-set(selected_b));same=set(trace_a.get('candidate_ids',[]))==set(trace_b.get('candidate_ids',[]))
                changed+=set(selected_a)!=set(selected_b);adopted_new+=bool(set(new)&set(used));mismatched+=not same;paired_count+=1
                distance.append(1-jaccard(selected_a,selected_b))
                details.append({'task_id':key[0],'repeat':key[1],'new_member_ids':new,
                    'new_members_declared_adopted':sorted(set(new)&set(used)),'same_candidate_set':same,
                    'same_public_query':trace_a.get('query_hash')==trace_b.get('query_hash')})
            result[arm].update(against_Q0={'paired_runs':paired_count,'set_changed_runs':changed,
                'new_members_adopted_c0_runs':adopted_new,'candidate_set_mismatches':mismatched,
                'mean_set_distance':sum(distance)/len(distance) if distance else None},details=details)
    return result


def selector_noise(rows):
    from methods.cle_ablation.run_selector_repeat import compare,holm
    groups=defaultdict(lambda:{a:[] for a in ('Q0','Q1','Q2','Q3')})
    for row in sorted(rows,key=lambda r:r['repeat']):
        if row.get('status')=='completed':groups[row['task_id']][row['condition']].append(row['selected_ids'])
    comparisons=[];details=[]
    for test,control in (('Q2','Q0'),('Q2','Q1'),('Q2','Q3')):
        value,cases=compare(dict(sorted(groups.items())),test,control);comparisons.append(value);details.extend(cases)
    holm([c for c in comparisons if 'p_block_permutation' in c])
    complete=len(rows)==160 and all(r.get('status')=='completed' for r in rows)
    for value in comparisons:
        value['detectable_order_effect']=bool(complete and value.get('excess_distance',0)>0 and value.get('ci95_families',[0])[0]>0 and value.get('p_holm',1)<=.05)
    return {'native_statistics':'methods.cle_ablation.run_selector_repeat.compare/holm',
        'complete_valid':complete,'comparisons':comparisons,'details':details,'effect_gate_controls_dispatch':False}


def common_inputs(rows,selector_only):
    groups=defaultdict(list)
    for row in rows:
        attempt=(row.get('attempts') or [{}])[0]
        trace=row.get('retrieval_trace') or attempt.get('retrieval_trace')
        if not trace or trace.get('status')!='completed':continue
        groups[(str(row['task_id']),1 if selector_only else row['repeat'])].append((row['cell_id'],trace))
    results=[];expected_cells=20 if selector_only else 4
    for key,items in sorted(groups.items()):
        reference=items[0][1]
        def values(trace):return {s['id']:s['cosine'] for s in trace.get('scores',[])}
        expected=values(reference)
        results.append({'task_id':key[0],'repeat':key[1],'cells':len(items),
            'expected_cells':expected_cells,'complete':len(items)==expected_cells,
            'same_query':all(t.get('query_hash')==reference.get('query_hash') for _,t in items),
            'same_candidates':all(set(t.get('candidate_ids',[]))==set(reference.get('candidate_ids',[])) for _,t in items),
            'same_cosines_exact':all(values(t)==expected for _,t in items)})
    expected_groups=8 if selector_only else 48
    complete=len(results)==expected_groups and all(r['complete'] for r in results)
    return {'groups':results,'expected_groups':expected_groups,'complete':complete,
        'observed_common_inputs_match':bool(results) and all(r['same_query'] and r['same_candidates'] and r['same_cosines_exact'] for r in results),
        'all_common_inputs_match':complete and all(r['same_query'] and r['same_candidates'] and r['same_cosines_exact'] for r in results)}


def operation_costs(roots):
    records={}
    for root in roots:
        for path in (Path(root)/'journals').glob('*/requests/*.json'):
            value=read(path);namespace=path.parent.parent.name
            records[namespace,value['identity']]=value
    result={}
    for (namespace,_),value in records.items():
        item=result.setdefault(namespace,{'logical_requests':0,'known_prompt_tokens':0,'known_completion_tokens':0,
            'known_total_tokens':0,'unknown_logical_usage':0})
        item['logical_requests']+=1;usage=(value.get('response') or {}).get('usage')
        if not isinstance(usage,dict):item['unknown_logical_usage']+=1;continue
        for source,target in (('prompt_tokens','known_prompt_tokens'),('completion_tokens','known_completion_tokens'),('total_tokens','known_total_tokens')):
            if type(usage.get(source)) is int:item[target]+=usage[source]
    return {'by_operation_namespace':result,
        'allocation_rule':'cell namespaces are direct costs; shared_initial/shared_selection and material_* remain separate common/preparation costs, not charged twice to arms',
        'physical_unknown_cost':'reported separately in cumulative budget.json; logical final response usage never proves failed HTTP was free'}


def run():
    memory=ROOT/'translation_work/diagnostics/20261020/cle_q_online_v1/D_grow/frozen/m_star_q.jsonl'
    from methods.cle_ablation.runner import load_memory
    nodes=load_memory(memory);visits={str(n.invariant_id):n.q_visits for n in nodes}
    index=read(RUN/'execution_index.json');out=RUN/'CLOSEOUT';out.mkdir(exist_ok=True)
    write_json(out/'frozen_Q_coverage.json',{'cards':len(nodes),'feedback_cards':sum(v>0 for v in visits.values()),
        'fraction':sum(v>0 for v in visits.values())/len(nodes),'Q_updates_in_current_study':0})
    material=RUN/'shared_materials'
    partitions=defaultdict(int);bindings=defaultdict(int)
    for p in (material/'views').glob('*.json'):partitions[read(p).get('annotation_method','unspecified')]+=1
    for p in (material/'bindings').glob('*.json'):bindings[read(p).get('annotation_method','AI_public_source_mapping_not_human_gold')]+=1
    write_json(out/'material_methods.json',{'source_views':dict(partitions),'L3_bindings':dict(bindings),
        'limitation':'exact coverage and source quotation checks establish source fidelity, not semantic correctness or human agreement'})
    for stage,roots in index.items():
        write_json(out/(stage+'_operation_costs.json'),operation_costs(roots))
        if stage in ('D03a','D03b'):
            rows=rows_for(stage)
            write_json(out/(stage+'_Q_selection.json'),q_statistics(stage,rows,visits))
            write_json(out/(stage+'_common_inputs.json'),common_inputs(rows,stage=='D03a'))
        if stage=='D03a':write_json(out/'D03a_selector_noise.json',selector_noise(rows_for(stage)))
    return {'status':'completed','API_calls':0}


if __name__=='__main__':print(run())
