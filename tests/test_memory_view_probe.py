"""真实编排的共享起点、修复召回及付费停止边界；模型均为离线替身。"""
import copy
import json

import pytest

from methods.cle_ablation import runner
from methods.cle_ablation.run_memory_view_probe import ViewProvider, schedule, technical_errors, summary, await_source_review
from methods.sct_trajectory.memory_views import draft_view


def fixture():
    task = {'index':'test','CWE_ID':'79','task_description':{
        'function_name':'f','arguments':'value: str','description':'Return value unchanged.'},
        'unittest':{'setup':'','testcases':"testcases = {'capability':[({'value':'x'},'x')], 'safety':[({'value':'<x>'},'<x>')]}"},
        'ground_truth':'PRIVATE_ANSWER','install_requires':[]}
    initial = {'vulnerability_hypothesis':['input processing risk'],
               'functional_invariants':['return the input unchanged']}
    contract = runner.plt_contract(task)
    query = {**contract,'threat_analysis':initial,'current_code':'','failure_evidence':{}}
    def card(identifier):
        return {'invariant_id':identifier,'kind':'candidate','status':'active','support_count':1,
                'regression_count':0,'positive_principle':'Keep valid output.',
                'negative_guardrail':'Avoid unsafe input use.'}
    old,new = card('initial-card'),card('repair-card')
    specs = {}
    for item in [old,new]:
        spec = draft_view(item)
        spec['review_status']='reviewed'
        for segment in spec['segments']:
            segment['role']='functional' if segment['path'][0]=='positive_principle' else 'security'
        specs[item['invariant_id']]=spec
    start={'query':query,'selected_cards':[old],'initial_analysis':initial,
           'retrieval_trace':{'status':'completed','candidate_ids':['initial-card'],'selected_ids':['initial-card']}}
    return task,start,new,specs


def test_shared_first_query_and_repair_query_are_not_interchanged():
    _,start,new,specs=fixture()
    seen=[]
    def retrieve(query):
        seen.append(copy.deepcopy(query))
        return [new],{'status':'completed','candidate_ids':['repair-card'],'selected_ids':['repair-card']}
    provider=ViewProvider(start,'BFS',retrieve,lambda cards:specs)
    cards,trace=provider(start['query'])
    assert cards[0]['invariant_id']=='initial-card' and trace['shared_first_selection']
    assert not seen
    repair={**start['query'],'current_code':'bad draft','failure_evidence':{'functional':{'status':'fail'}}}
    cards,trace=provider(repair)
    assert seen==[repair] and cards[0]['invariant_id']=='repair-card'
    assert trace['pre_view_selected_ids']==['repair-card']
    assert start['retrieval_trace']['selected_ids']==['initial-card']


def test_B0_never_injects_or_retrieves_repair_memory():
    _,start,_,_=fixture()
    def forbidden(*args):
        raise AssertionError('B0 must not retrieve or review')
    provider=ViewProvider(start,'B0',forbidden,forbidden)
    assert provider(start['query'])[0]==[]
    assert provider({**start['query'],'current_code':'draft'})[0]==[]


def test_first_query_change_stops_before_any_view_or_model():
    _,start,_,specs=fixture()
    provider=ViewProvider(start,'BM',lambda q:None,lambda cards:specs)
    with pytest.raises(ValueError,match='shared_start'):
        provider({**start['query'],'current_code':'unexpected'})


def test_schedule_has_exactly_twenty_cells_without_selecting_on_outcomes():
    cells=schedule(['1394','102'])
    assert len(cells)==len({c['cell_id'] for c in cells})==20
    assert cells==schedule(['1394','102'])
    assert all(sum(c['task_id']==tid and c['repeat']==r for c in cells)==5
               for tid in ['1394','102'] for r in [1,2])


@pytest.mark.parametrize('mode',['B0','BF','BFS'])
def test_native_P7_uses_actual_repair_card_last_delivery_and_public_only_prompts(mode):
    task,start,new,specs=fixture()
    repairs=[]
    def retrieve(q):
        repairs.append(q)
        return [new],{'status':'completed','candidate_ids':['repair-card'],'selected_ids':['repair-card']}
    provider=ViewProvider(start,mode,retrieve,lambda cards:specs)
    codes=iter(['def f(value): return None','def f(value): return value'])
    prompts=[]
    def request(prompt):
        prompts.append(prompt)
        if prompt.startswith('Generate complete'):
            content=next(codes)
        elif prompt.startswith('Plan'):
            content=json.dumps({'Preserved_Func':'return input','Patch_Scope':'return unchanged'})
        else:
            chosen=[] if mode=='B0' else ['initial-card' if provider.calls==1 else 'repair-card']
            content=json.dumps({**start['initial_analysis'],'applied_experience_ids':chosen})
        return {'choices':[{'message':{'content':content}}],
                'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}
    row=runner.run_one('PLT',task,'P7',request,{'full':[]},
        retrieval_provider=provider,initial_analysis=start['initial_analysis'])
    assert len(row['attempts'])==2 and not row['attempts'][0]['joint']
    assert row['attempts'][-1]['joint'] and not technical_errors(row)
    assert all('PRIVATE_ANSWER' not in p for p in prompts)
    if mode=='B0':
        assert repairs==[] and all(not a['generation']['retrieved_cards'] for a in row['attempts'])
    else:
        assert repairs[0]['current_code']=='def f(value): return None'
        assert row['attempts'][1]['generation']['retrieved_cards'][0]['invariant_id']=='repair-card'
    row['view_arm']=mode
    report=summary([row],20)
    assert report['arms'][mode]['final']['joint']==1
    assert not report['effectiveness_gate_evaluated']


def test_wrong_generated_code_is_an_observation_but_technical_failure_stops():
    wrong={'attempts':[{'measured':True,'joint':False,'generation':{'workflow_completed':True,'error_type':None}}]}
    assert technical_errors(wrong)==[]
    broken={'attempts':[{'measured':False,'error_type':'TimeoutError'}]}
    assert technical_errors(broken)==['TimeoutError']


def test_last_empty_delivery_remains_unmeasured_in_summary():
    row={'view_arm':'BFS','attempts':[
        {'measured':True,'functional':False,'security':False,'joint':False},
        {'measured':False,'error_type':'TimeoutError'}]}
    item=summary([row],20)['arms']['BFS']
    assert item['first']['measured']==1
    assert item['final']['measured']==0 and item['unmeasured']==1


def test_missing_source_view_waits_for_review_before_returning(monkeypatch,tmp_path):
    from methods.cle_ablation import run_memory_view_probe as probe
    _,start,_,specs=fixture()
    registry=tmp_path/'reviewed_views.json'
    registry.write_text('{}',encoding='utf-8')
    def finish_review(_):
        state=json.loads((tmp_path/'runtime_status.json').read_text(encoding='utf-8'))
        assert state['status']=='waiting_source_content_review'
        assert (tmp_path/'pending_views/cell/initial-card.json').exists()
        temporary=tmp_path/'reviewed_views.tmp'
        temporary.write_text(json.dumps(specs),encoding='utf-8')
        temporary.replace(registry)
    monkeypatch.setattr(probe.time,'sleep',finish_review)
    result=await_source_review(start['selected_cards'],registry,tmp_path,'cell')
    assert result['initial-card']['review_status']=='reviewed'
    assert json.loads((tmp_path/'runtime_status.json').read_text(encoding='utf-8'))['status']=='running'


def test_native_repair_retrieval_error_does_not_borrow_first_success_trace():
    task,start,_,_=fixture()
    counter=0
    codes=iter(['def f(value): return None','def f(value): return value'])
    def provider(query):
        nonlocal counter
        counter+=1
        if counter==1:return [],{'status':'completed','selected_ids':['first-only']}
        exc=RuntimeError('observed selector transport failure')
        exc.retrieval_trace={'status':'error','selected_ids':[],'errors':['selector_transport_TimeoutError']}
        raise exc
    def request(prompt):
        if prompt.startswith('Generate complete'):content=next(codes)
        elif prompt.startswith('Plan'):content=json.dumps({'Preserved_Func':'return input','Patch_Scope':'return unchanged'})
        else:content=json.dumps({**start['initial_analysis'],'applied_experience_ids':[]})
        return {'choices':[{'message':{'content':content}}],
                'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}
    row=runner.run_one('PLT',task,'P7',request,{'full':[]},
        retrieval_provider=provider,initial_analysis=start['initial_analysis'])
    assert row['attempts'][0]['retrieval_trace']['status']=='completed'
    assert row['attempts'][1]['retrieval_trace']['status']=='error'
    assert row['attempts'][1]['retrieval_trace']['selected_ids']==[]
    assert row['attempts'][1]['joint'] is True  # 本补丁不改变原生降级后仍可生成的行为。
