"""完整执行后的零API复核与配对分析；只读原生记录，产出精简机器结果。"""
from collections import Counter
import copy
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.cle_ablation.run_memory_q_unlimited import inspect_rows, technical_errors
from methods.cle_ablation.audit_memory_q import read_rows
from methods.cle_ablation.run_memory_q import shuffled_memory
from methods.cle_ablation.runner import load_memory
from methods.direction_screening.protocol import summarize
from methods.sct_trajectory.memory_q import rank_candidates

RUN=ROOT/'translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2'
OUT=ROOT/'results/curated/cle_memory_q_unlimited_complete_20261018'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def write(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def dump_csv(name,items):
    if not items:return
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(items[0]));writer.writeheader();writer.writerows(items)


def pair(items,base,test):
    subset=[r for r in items if r['arm'] in (base,test)]
    result=summarize(subset,base)['paired'][test]
    a={str(r['task_id']):r for r in subset if r['arm']==base}
    b={str(r['task_id']):r for r in subset if r['arm']==test}
    tasks=[]
    for key in a:
        x,y=a[key]['final'],b[key]['final']
        tasks.append({'task_id':key,'cwe':a[key]['cwe'],'family_id':a[key]['family_id'],
            'base':base,'test':test,'base_joint':x['joint'],'test_joint':y['joint'],
            'joint_delta':int(y['joint'])-int(x['joint']),'both_measured':x['measured'] and y['measured'],
            'base_functional':x['functional'],'test_functional':y['functional']})
    result.update(total_wins=sum(t['joint_delta']==1 for t in tasks),
                  total_losses=sum(t['joint_delta']==-1 for t in tasks),
                  delta_joint=sum(t['joint_delta'] for t in tasks)/len(tasks),
                  base=base,test=test,tasks=tasks)
    return result


def diagnostics(runs,stages,frozen):
    """区分曝光、选择、采用和有效反馈；用量仅汇总已落盘回执。"""
    funnel={k:set() for k in ('candidate','selected','declared_adopted','credited')}
    by_arm={}
    for stage,items in runs.items():
        for arm in sorted({r['arm'] for r in items}):
            group=[r for r in items if r['arm']==arm]
            attempts=[a for r in group for a in r['attempts']]
            traces=[a.get('retrieval_trace') or {} for a in attempts]
            selected=[len(a.get('generation',{}).get('retrieved_cards',[])) for a in attempts]
            adopted=[len(a.get('generation',{}).get('cards',[])) for a in attempts]
            by_arm[stage+'/'+arm]={
                'attempts':len(attempts),'selected_total':sum(selected),'declared_adopted_total':sum(adopted),
                'selected_mean':sum(selected)/len(attempts),'declared_adopted_mean':sum(adopted)/len(attempts),
                'selected_above_three':sum(n>3 for n in selected),'declared_adopted_above_three':sum(n>3 for n in adopted),
                'normal_empty_selection':sum(t.get('status')=='completed' and not t.get('selected_ids') for t in traces),
                'retrieval_status':dict(Counter(t.get('status','missing') for t in traces)),
                'final_outcomes':dict(Counter('unmeasured' if not r['final']['measured'] else
                    'joint' if r['final']['joint'] else 'functional_only' if r['final']['functional'] else
                    'security_only' if r['final']['security'] else 'neither' for r in group)),
                'error_categories':dict(Counter(part for r in group for a in r['attempts']
                    for part in str(a.get('error_type') or a.get('generation',{}).get('error_type') or '').split(';') if part)),
                'unmeasured_final_ids':[r['task_id'] for r in group if not r['final']['measured']]}
        if stage=='observe':
            for r in items:
                for a in r['attempts']:
                    t=a.get('retrieval_trace') or {};g=a.get('generation',{})
                    funnel['candidate'].update(t.get('candidate_ids',[]))
                    funnel['selected'].update(c['invariant_id'] for c in g.get('retrieved_cards',[]))
                    funnel['declared_adopted'].update(c['invariant_id'] for c in g.get('cards',[]))
    funnel['credited']={key for key,n in frozen.items() if n.get('q_visits',0)>0}
    events=read_rows(RUN/'observe/memory_q_events.jsonl')
    known_llm={k:sum(v['cost']['llm']['total'][k] for v in stages.values())
               for k in ('calls','prompt_tokens','completion_tokens','total_tokens','errors','usage_missing')}
    known_embedding={k:sum(v['cost']['embedding'].get(k,0) for v in stages.values())
               for k in ('calls','failures','total_tokens','usage_missing_calls')}
    health=read_rows(RUN/'infrastructure_health.jsonl') if (RUN/'infrastructure_health.jsonl').exists() else []
    recoveries=read_rows(RUN/'infrastructure_recoveries.jsonl') if (RUN/'infrastructure_recoveries.jsonl').exists() else []
    return {'observer_unique_card_funnel':{k:len(v) for k,v in funnel.items()},
        'observer_unexposed_cards':len(set(frozen)-funnel['candidate']),
        'observer_selected_never_adopted':len(funnel['selected']-funnel['declared_adopted']),
        'observer_adopted_never_credited':len(funnel['declared_adopted']-funnel['credited']),
        'observer_card_reward_updates':dict(Counter(str(e['reward']) for e in events
            if e.get('invariant_id') and e.get('reward') is not None)),
        'observer_skipped_rewards':dict(Counter(e['skip_reason'] for e in events if e.get('skip_reason'))),
        'by_arm':by_arm,'known_native_llm_usage':known_llm,'known_embedding_usage':known_embedding,
        'separate_infrastructure_health':health,'infrastructure_recoveries':recoveries,
        'interrupted_unsaved_usage_unknown':bool(recoveries),
        'cost_scope':'Recorded native receipts; inherited probes counted once; health separate; interrupted unsaved usage unknown; no invoice.'}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=read(RUN/'manifest.json')
    runs={s:read_rows(RUN/s/'rows.jsonl') for s in ('observe','retest','gate')}
    stages={};adoption=[];comparison=[]
    for stage,items in runs.items():
        inspect_rows(items)
        expected={str(i) for i in manifest['development' if stage=='gate' else 'learning']}
        arms=['Q0'] if stage=='observe' else ['Q2'] if stage=='retest' else ['Q1','Q2','Q3']
        assert {(str(r['task_id']),r['arm']) for r in items}=={(i,a) for i in expected for a in arms}
        assert len(items)==len(expected)*len(arms)
        native=read(RUN/stage/'summary.json');recomputed=summarize(items,arms[0])
        assert native['arms']==recomputed['arms']
        shared=read_rows(RUN/('observe' if stage=='retest' else stage)/'shared_initial.jsonl')
        initials={str(r['task_id']):r['initial_analysis'] for r in shared}
        for row in items:
            assert row['attempts'][0].get('generation',{}).get('initial_analysis')==initials[str(row['task_id'])]
        cost=read(RUN/stage/'cost.json')
        billed_shared=[] if stage=='retest' else shared
        for k in ('calls','prompt_tokens','completion_tokens','total_tokens','errors','usage_missing'):
            assert cost['llm']['total'][k]==sum(r['accounting']['total'][k] for r in items+billed_shared)
        stages[stage]={'native':native,'cost':cost,'workflow_error_tasks':len({e['task_id'] for e in technical_errors(items)}),
                       'workflow_errors':technical_errors(items)}
        for row in items:
            for a in row['attempts']:
                g=a.get('generation',{});trace=a.get('retrieval_trace') or {}
                adoption.append({'stage':stage,'task_id':row['task_id'],'arm':row['arm'],'attempt':a['attempt'],
                    'candidate_count':len(trace.get('candidate_ids',[])),
                    'selected_count':len(g.get('retrieved_cards',[])),'declared_adopted_count':len(g.get('cards',[])),
                    'joint':a['joint'],'workflow_complete':bool(g.get('workflow_completed'))})
    base={n['invariant_id']:n for n in read_rows(RUN/'input_memory.jsonl')}
    replay=copy.deepcopy(base)
    for event in read_rows(RUN/'observe/memory_q_events.jsonl'):
        key=event.get('invariant_id')
        if not key:continue
        n=replay[key];assert n.get('q_value',0)==event['q_before']
        if event['reward'] is not None:
            n['q_value']=event['q_before']+.3*(event['reward']-event['q_before'])
            n['q_visits']=n.get('q_visits',0)+1
        assert n.get('q_value',0)==event['q_after']
    frozen_path=RUN/'observe/frozen/m_star_q.jsonl'
    frozen={n['invariant_id']:n for n in read_rows(frozen_path)}
    assert replay==frozen
    for key in base:
        assert {k:v for k,v in base[key].items() if k not in ('q_value','q_visits')}=={
               k:v for k,v in frozen[key].items() if k not in ('q_value','q_visits')}
    node_list=load_memory(frozen_path)
    qvalues={n.invariant_id:n.q_value for n in node_list}
    shuffled=shuffled_memory(node_list,20261015,'cwe')
    shuffled_values={n.invariant_id:n.q_value for n in shuffled}
    assert Counter((n.cwe,n.q_value,n.q_visits) for n in node_list)==Counter((n.cwe,n.q_value,n.q_visits) for n in shuffled)
    for stage in ('retest','gate'):
        assert not read_rows(RUN/stage/'memory_q_events.jsonl')
        for row in runs[stage]:
            for attempt in row['attempts']:
                trace=attempt.get('retrieval_trace')
                if not trace or trace.get('status')!='completed':continue
                values=shuffled_values if row['arm']=='Q3' else qvalues
                for value in trace.get('value_ranking',[]):assert value['q_value']==values[value['id']]
    gate_by={arm:{str(r['task_id']):r for r in runs['gate'] if r['arm']==arm} for arm in ('Q1','Q2','Q3')}
    for key in gate_by['Q1']:
        first=[gate_by[arm][key]['attempts'][0] for arm in ('Q1','Q2','Q3')]
        traces=[a.get('retrieval_trace') for a in first]
        valid=all(t and t.get('status')=='completed' for t in traces)
        if valid:
            assert all((t['query_hash'],t['candidate_ids'],t['scores'])==
                       (traces[0]['query_hash'],traces[0]['candidate_ids'],traces[0]['scores']) for t in traces)
        selected=[set(t.get('selected_ids',[])) if t else set() for t in traces]
        adopted=[{c['invariant_id'] for c in a.get('generation',{}).get('cards',[])} for a in first]
        comparison.append({'task_id':key,'cwe':gate_by['Q1'][key]['cwe'],'valid_shared_query':valid,
            'q_order_changed':valid and traces[0]['presented_candidate_ids']!=traces[1]['presented_candidate_ids'],
            'selected_members_changed':valid and selected[0]!=selected[1],
            'adopted_members_changed':valid and adopted[0]!=adopted[1],
            'q_vs_shuffled_order_changed':valid and traces[1]['presented_candidate_ids']!=traces[2]['presented_candidate_ids'],
            'q_vs_shuffled_selected_changed':valid and selected[1]!=selected[2],
            'q_vs_shuffled_adopted_changed':valid and adopted[1]!=adopted[2],
            'new_q_adopted_ids':sorted(adopted[1]-adopted[0]),
            'new_q_adopted_unlearned':sum(frozen[k].get('q_visits',0)==0 for k in adopted[1]-adopted[0]),
            'new_q_adopted_positive':sum(frozen[k].get('q_visits',0)>0 and frozen[k]['q_value']>0 for k in adopted[1]-adopted[0]),
            'new_q_adopted_negative':sum(frozen[k].get('q_visits',0)>0 and frozen[k]['q_value']<0 for k in adopted[1]-adopted[0]),
            'Q1_joint':gate_by['Q1'][key]['final']['joint'],'Q2_joint':gate_by['Q2'][key]['final']['joint'],
            'Q3_joint':gate_by['Q3'][key]['final']['joint']})
    fit=pair([{**r,'arm':'Q1'} for r in runs['observe']]+runs['retest'],'Q1','Q2')
    main_pairs={'Q2_vs_Q1':pair(runs['gate'],'Q1','Q2'),'Q2_vs_Q3':pair(runs['gate'],'Q3','Q2')}
    previous=0
    for j,key in enumerate(sorted(main_pairs,key=lambda k:main_pairs[k]['p_exact'])):
        previous=max(previous,min(1,main_pairs[key]['p_exact']*(2-j)))
        main_pairs[key]['p_holm_primary']=previous
    families=read(RUN/'observe/q_family_support.json')
    learning_families={r['family_id'] for r in runs['observe']}
    assert not learning_families & {r['family_id'] for r in runs['gate']}
    inherited=read_rows(Path(read(RUN/'run_metadata.json')['inherited_probe_source'])/'observe/rows.jsonl')
    observer={str(r['task_id']):r for r in runs['observe']}
    assert all(observer[str(r['task_id'])]==r for r in inherited)
    coverage={'cards':len(frozen),'visited':sum(n.get('q_visits',0)>0 for n in frozen.values()),
        'positive_q':sum(n.get('q_visits',0)>0 and n['q_value']>0 for n in frozen.values()),
        'negative_q':sum(n.get('q_visits',0)>0 and n['q_value']<0 for n in frozen.values()),
        'one_visit':sum(n.get('q_visits',0)==1 for n in frozen.values()),
        'two_family':sum(len(v)>=2 for v in families.values()),'three_family':sum(len(v)>=3 for v in families.values())}
    coverage['fraction']=coverage['visited']/coverage['cards']
    data={'protocol':manifest['protocol'],'verification':'pass','total_P7_rows':sum(map(len,runs.values())),
          'stages':stages,'training_fit':fit,'D_gate_primary':main_pairs,'Q_coverage':coverage,
          'gate_mechanism_counts':{k:sum(bool(v[k]) for v in comparison) for k in
              ('valid_shared_query','q_order_changed','selected_members_changed','adopted_members_changed',
               'q_vs_shuffled_order_changed','q_vs_shuffled_selected_changed','q_vs_shuffled_adopted_changed')},
          'declaration_is_not_implementation':True,'inherited_probe_identical':True,'Q_event_replay_exact':True,
          'memory_body_unchanged':True,'frozen_Q_used_exactly':True,'learning_gate_families_disjoint':True}
    write('analysis.json',data)
    write('diagnostics.json',diagnostics(runs,stages,frozen))
    write('verification.json',{k:v for k,v in data.items() if k not in ('stages','training_fit','D_gate_primary')})
    dump_csv('adoption_by_attempt.csv',adoption);dump_csv('gate_mechanisms.csv',comparison)
    dump_csv('training_fit_pairs.csv',fit['tasks'])
    for key,item in main_pairs.items():dump_csv(key+'_pairs.csv',item['tasks'])
    dump_csv('card_q.csv',[{'id':key,'cwe':n['cwe'],'Q':n['q_value'],'visits':n['q_visits'],
             'independent_families':len(families.get(key,[]))} for key,n in frozen.items()])
    print(json.dumps({'verified_rows':data['total_P7_rows'],'Q_coverage':coverage,
          'mechanisms':data['gate_mechanism_counts'],'gate':{a:v['joint'] for a,v in stages['gate']['native']['arms'].items()}},ensure_ascii=False))


if __name__=='__main__':main()
