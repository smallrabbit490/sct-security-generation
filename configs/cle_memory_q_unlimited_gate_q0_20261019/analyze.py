"""零API核对新增Q0与原48题三臂；保留原成绩，输出配对差异及执行诊断。"""
from collections import Counter
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.cle_ablation import run_memory_q_gate_q0 as study


def main():
    study.verify(study.OUT)
    new=study.read_rows(study.OUT/'rows.jsonl')
    old=study.read_rows(study.PARENT/'gate/rows.jsonl')
    ids=study.read(study.OUT/'manifest.json')['tasks']
    assert len(new)==48 and {r['task_id'] for r in new}==set(ids)
    combined=old+new
    assert len(combined)==192 and len({(r['task_id'],r['arm']) for r in combined})==192
    assert len({r['family_id'] for r in combined})==48
    study.inspect_rows(combined)
    degraded=study.check_rows(new)
    assert (study.OUT/'memory_q_events.jsonl').stat().st_size==0
    result=study.report(study.OUT)
    by_task={i:{r['arm']:r for r in combined if r['task_id']==i} for i in ids}
    attempts=[];changes=[]
    for row in combined:
        for a in row['attempts']:
            g=a.get('generation',{});t=a.get('retrieval_trace') or {}
            attempts.append({'task_id':row['task_id'],'arm':row['arm'],'attempt':a['attempt'],
                'F':a['functional'],'S':a['security'],'Joint':a['joint'],'measured':a['measured'],
                'selected':len(g.get('retrieved_cards',[])),'declared_adopted':len(g.get('cards',[])),
                'workflow_completed':g.get('workflow_completed',False),'error':g.get('error_type') or a.get('error_type'),
                'selector_attempts':len(t.get('selector_attempts',[])),'retrieval_status':t.get('status'),
                'source':'new_Q0' if row['arm']=='Q0' else 'parent_gate'})
    for i,group in by_task.items():
        baseline=group['Q0']
        first=baseline['attempts'][0]
        base_cards={c['invariant_id'] for c in first.get('generation',{}).get('cards',[])}
        base_selected=set((first.get('retrieval_trace') or {}).get('selected_ids',[]))
        for arm in ('Q1','Q2','Q3'):
            test=group[arm];t=test['attempts'][0]
            cards={c['invariant_id'] for c in t.get('generation',{}).get('cards',[])}
            selected=set((t.get('retrieval_trace') or {}).get('selected_ids',[]))
            changes.append({'task_id':i,'family_id':baseline['family_id'],'baseline':'Q0','test':arm,
                'base_Joint':baseline['final']['joint'],'test_Joint':test['final']['joint'],
                'delta':int(test['final']['joint'])-int(baseline['final']['joint']),
                'first_selected_changed':selected!=base_selected,'first_adopted_changed':cards!=base_cards,
                'test_first_added_adopted_ids':sorted(cards-base_cards),
                'both_measured':baseline['final']['measured'] and test['final']['measured']})
    study.dump_csv(study.CURATED/'attempts.csv',attempts)
    study.dump_csv(study.CURATED/'paired_mechanisms.csv',changes)
    diagnostics={arm:{
        'workflow_error_runs':sum(bool(study.technical_errors([r])) for r in combined if r['arm']==arm),
        'error_attempts':sum(bool(t['error']) or not t['workflow_completed'] or not t['measured'] for t in attempts if t['arm']==arm),
        'error_types':dict(Counter(t['error'] or 'unmeasured_or_incomplete' for t in attempts if t['arm']==arm and
                           (t['error'] or not t['workflow_completed'] or not t['measured']))),
        'first_joint':sum(r['attempts'][0]['joint'] for r in combined if r['arm']==arm),
        'any_attempt_joint':sum(any(a['joint'] for a in r['attempts']) for r in combined if r['arm']==arm),
        'final_joint':sum(r['final']['joint'] for r in combined if r['arm']==arm),
        'first_selection_empty':sum(not r['attempts'][0].get('generation',{}).get('retrieved_cards') for r in combined if r['arm']==arm)}
        for arm in ('Q0','Q1','Q2','Q3')}
    mechanism_summary={arm:{
        'first_selected_changed':sum(v['first_selected_changed'] for v in changes if v['test']==arm),
        'first_adopted_changed':sum(v['first_adopted_changed'] for v in changes if v['test']==arm),
        'rescued_ids':[v['task_id'] for v in changes if v['test']==arm and v['delta']==1],
        'lost_ids':[v['task_id'] for v in changes if v['test']==arm and v['delta']==-1]}
        for arm in ('Q1','Q2','Q3')}
    study.write(study.CURATED/'diagnostics.json',{'arms':diagnostics,'mechanisms':mechanism_summary,
        'unverified_failed_retrieval_attempts':degraded,'new_API_calls':0,
        'raw_rows_preserved':True,'dates_differ_between_Q0_and_parent':True})
    coverage=sum(n.q_visits>0 for n in study.load_memory(study.PARENT/'observe/frozen/m_star_q.jsonl'))
    primary=result['paired']['Q2']
    supported=(result['arms']['Q2']['joint']>result['arms']['Q0']['joint'] and primary['p_holm']<=.05)
    decision={'execution':'COMPLETE_48_ADDED_144_REUSED','comparison':'Q2-Q0',
        'Q2_minus_Q0_Joint':result['arms']['Q2']['joint']-result['arms']['Q0']['joint'],
        'p_exact':primary['p_exact'],'p_holm_vs_Q0_family':primary['p_holm'],
        'statistical_positive_signal':supported,'automatic_full_test_started':False,
        'classification':'exploratory_addendum_no_automatic_full_test',
        'mechanism_causal_benefit':'requires_code_review_not_inferred_from_ID_changes',
        'frozen_Q_covered_cards':coverage,'total_cards':1939,
        'new_training':False,'new_Base_Plus':False}
    study.write(study.CURATED/'decision.json',decision)
    study.write(study.OUT/'decision.json',decision)
    study.write(study.OUT/'verification.json',{'passed':True,'new_rows':48,'reused_rows':144,
        'native_P7_checked':True,'shared_first_candidates_checked':True,
        'degraded_retrieval_attempts':degraded,'Q_frozen':True,'old_input_files_unchanged':True})
    print(json.dumps({'arms':result['arms'],'paired_against_Q0':result['paired'],
        'new_cost':result['new_cost'],'diagnostics':diagnostics,'mechanisms':mechanism_summary},ensure_ascii=False))


if __name__=='__main__':
    main()
