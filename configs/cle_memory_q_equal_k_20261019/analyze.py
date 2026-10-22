"""本轮零API复算；两次重复按同8题分析，保留原生失败和人工待审状态。"""
import argparse
import ast
from collections import Counter
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.cle_ablation import run_memory_q_equal_k as study
from methods.cle_ablation.run_memory_q_unlimited import inspect_rows, technical_errors
from methods.sct_trajectory.retrieval_hit_study import read_rows

BINDINGS={'1341':{'xml_template'},'1000':{'BLOG_FORMAT'},
          '1013':{'USER_PROFILES','USERS'},'1055':{'PERMITTED_FIELDS'}}
SIGNATURES={'1256':('extract_email_domain',['email']),'1306':('parse_json_request',['request']),
    '1317':('convert_to_object',['serialized_data','format_type']),'1341':('generate_xml_response',['user_content']),
    '1000':('format_blog_entry',['headline','content']),'1013':('see_user_profile',['current_id','target_id']),
    '1055':('update_item_details',['inventory','update_data']),'1259':('validate_password',['password'])}


def write_csv(path,rows):
    if not rows:return
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def analyze(probe=False):
    out=study.OUT;study.verify(out)
    rows=read_rows(out/'rows.jsonl')
    specs={s['task_id']:s for s in study.read(out/'reused_inputs.json')}
    expected={(i,a,b) for i in specs for a in study.ARMS for b in (1,2)}
    actual={(r['task_id'],r['arm'],r['repeat']) for r in rows}
    assert len(actual)==len(rows) and actual<=expected
    if not probe:assert actual==expected
    inspect_rows(rows)
    nodes=study.load_memory(study.OLD/'observe/frozen/m_star_q.jsonl')
    shuffled=study.shuffled_memory(nodes,20261015,'cwe')
    assert Counter((n.cwe,n.q_value,n.q_visits) for n in nodes)==Counter((n.cwe,n.q_value,n.q_visits) for n in shuffled)
    assert not read_rows(out/'memory_q_events.jsonl')
    before={a:{n.invariant_id:n.q_value for n in (shuffled if a=='Q3' else nodes)} for a in study.ARMS}
    attempts=[];skipped=[]
    for row in rows:
        spec=specs[row['task_id']]
        for t in row['attempts']:
            trace=t.get('retrieval_trace') or {};g=t.get('generation',{})
            if t['attempt']==0:
                assert g.get('initial_analysis')==spec['initial_analysis']
                for key in ('query_hash','candidate_ids','scores'):
                    assert trace.get(key)==spec['first_trace'][key],(row['task_id'],key)
            retrieval_error=any(s.get('stage')=='retrieval' and s.get('status')=='degraded' for s in g.get('stages',[]))
            if retrieval_error:
                skipped.append({'task_id':row['task_id'],'arm':row['arm'],'repeat':row['repeat'],'attempt':t['attempt'],
                                'reason':'failed_retrieval_may_leave_last_native_trace'})
            else:
                ranked,chosen=study.choose(trace['scores'],shuffled if row['arm']=='Q3' else nodes,spec['K'],row['arm'])
                assert chosen==trace['selected_ids']
                assert trace['presented_candidate_ids']==chosen
                assert len(chosen)==spec['K'] and trace['selector_calls']==0
                assert trace['value_ranking']==ranked
                assert {v['id']:v['q_value'] for v in ranked}=={v['id']:before[row['arm']][v['id']] for v in ranked}
                assert [c['invariant_id'] for c in g.get('retrieved_cards',[])]==chosen
            try:
                tree=ast.parse(t.get('code',''))
                stores=sorted({n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)} & BINDINGS.get(row['task_id'],set()))
                entry,expected_args=SIGNATURES[row['task_id']]
                functions=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==entry]
                parameters=[v.arg for v in functions[0].args.posonlyargs+functions[0].args.args] if functions else []
                signature_diff=parameters!=expected_args
            except SyntaxError:
                stores=['syntax_error_unreviewed']
                parameters=[];signature_diff=True
            attempts.append({'task_id':row['task_id'],'arm':row['arm'],'repeat':row['repeat'],'attempt':t['attempt'],
                'K':spec['K'],'selected':len(g.get('retrieved_cards',[])),'adopted':len(g.get('cards',[])),
                'F':t['functional'],'S':t['security'],'Joint':t['joint'],'workflow_complete':g.get('workflow_completed',False),
                'binding_stores':';'.join(stores),'entry_positional_args':parameters,
                'public_signature_diff':signature_diff,'error':g.get('error_type') or t.get('error_type')})
    verification={'rows':len(rows),'expected':48,'all_completed':actual==expected,'unique_tasks':len({r['task_id'] for r in rows}),
        'native_P7_delivery_verified':True,'first_shared_queries_candidates_and_scores_verified':True,
        'direct_K_and_common_presentation_verified_for_successful_retrieval':True,
        'frozen_Q_and_CWE_shuffle_verified':True,'Q_events_empty':True,
        'unverified_failed_retrieval_attempts':skipped,'engineering_error_attempts':technical_errors(rows)}
    study.write(out/('probe_verification.json' if probe else 'verification.json'),verification)
    if probe:
        print(json.dumps({'rows':len(rows),'verified':True,'workflow_errors':technical_errors(rows)},ensure_ascii=False))
        return
    result=study.report(out)
    # 本轮仅标注已召回池；原指标函数未传candidates时的0不代表测出了召回阶段的0。
    for authority in result['label_metrics'].values():
        for item in authority.values():
            item['counts']['candidate_TP']=None
            for task in item['per_task']:
                task['candidate_TP']=None
                task['candidate_recall']=None
                task['candidate_recall_reason']='outside_candidate_pool_not_labeled'
    study.write(out/'summary.json',result)
    study.write(study.CURATED/'summary.json',result)
    by_key={(r['task_id'],r['arm'],r['repeat']):r for r in rows}
    task_rows=[];mechanism=[]
    for key,s in specs.items():
        first={a:by_key[key,a,1]['attempts'][0] for a in study.ARMS}
        base=set(first['Q1']['retrieval_trace']['selected_ids'])
        q=set(first['Q2']['retrieval_trace']['selected_ids'])
        task_rows.append({'task_id':key,'family_id':s['family_id'],'K':s['K'],
            **{a+'_repeat'+str(b):by_key[key,a,b]['final']['joint'] for a in study.ARMS for b in (1,2)},
            'Q2_members_changed':base!=q,'Q2_added_ids':sorted(q-base)})
        for a in ('Q2','Q3'):
            for b in (1,2):
                x=by_key[key,'Q1',b];y=by_key[key,a,b]
                g=y['attempts'][0].get('generation',{})
                added=set(y['attempts'][0]['retrieval_trace']['selected_ids'])-base
                adopted={c['invariant_id'] for c in g.get('cards',[])}
                mechanism.append({'task_id':key,'arm':a,'repeat':b,'first_members_changed':bool(added or
                                  set(y['attempts'][0]['retrieval_trace']['selected_ids'])!=base),
                    'new_first_adopted_ids':sorted(added & adopted),'base_final_joint':x['final']['joint'],
                    'test_final_joint':y['final']['joint'],'rescue':not x['final']['joint'] and y['final']['joint'],
                    'loss':x['final']['joint'] and not y['final']['joint']})
    repeat_disagreement={a:sum(by_key[i,a,1]['final']['joint']!=by_key[i,a,2]['final']['joint'] for i in specs) for a in study.ARMS}
    aggregate={a:{k:sum(r['final'][k] for r in rows if r['arm']==a) for k in ('functional','security','joint','measured')} for a in study.ARMS}
    aggregate={a:{**v,'P7_runs':16,'unique_tasks':8,'joint_rate':v['joint']/16,
        'workflow_error_runs':sum(bool(technical_errors([r])) for r in rows if r['arm']==a),
        'final_public_signature_diffs':sum(t['public_signature_diff'] for t in attempts if t['arm']==a and
                           t['attempt']==by_key[t['task_id'],a,t['repeat']]['final']['attempt']),
        'final_binding_redeclarations':sum(bool(t['binding_stores']) for t in attempts if t['arm']==a and
                           t['attempt']==by_key[t['task_id'],a,t['repeat']]['final']['attempt'])} for a,v in aggregate.items()}
    adoption={a:{'attempts':len(ts),'selected':sum(t['selected'] for t in ts),'declared_adopted':sum(t['adopted'] for t in ts),
                'above_three_selected':sum(t['selected']>3 for t in ts),'above_three_adopted':sum(t['adopted']>3 for t in ts)}
                for a in study.ARMS for ts in [[t for t in attempts if t['arm']==a]]}
    study.CURATED.mkdir(parents=True,exist_ok=True)
    study.write(study.CURATED/'verification.json',verification)
    study.write(study.CURATED/'analysis.json',{'aggregate':aggregate,'repeat_disagreement':repeat_disagreement,
        'primary':result['clustered_primary_comparisons'],'adoption':adoption,'human_confirmed':result['human_confirmed'],
        'technical_errors_retained':True,'model_estimate_is_not_human_gold':True})
    write_csv(study.CURATED/'task_pairs.csv',task_rows)
    write_csv(study.CURATED/'attempts.csv',attempts)
    write_csv(study.CURATED/'mechanisms.csv',mechanism)
    print(json.dumps({'verified':verification,'aggregate':aggregate,'repeat_disagreement':repeat_disagreement,
                      'primary':result['clustered_primary_comparisons']},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--probe',action='store_true')
    analyze(parser.parse_args().probe)
