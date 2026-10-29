"""五档呈现、公开绑定和原P7修复；使用离线替身，不计模型实验成绩。"""
import copy
import json

import pytest

from methods.cle_ablation import runner
from methods.cle_ablation.memory_granularity_study import run_one_level,GranularityProvider
from methods.sct_trajectory.memory_granularity import (
    LEVELS,apply_memory_level,public_task,GranularityPreparationRequired)
from methods.sct_trajectory.context_pipeline import experience_text


def fixture():
    task={'index':'target','family_id':'target-family','CWE_ID':'20',
        'task_description':{'function_name':'f','arguments':'value: str','description':'Return value unchanged.',
                            'return':'The original string.','context':'','raise':''},
        'unittest':{'setup':'','testcases':"testcases = {'capability':[({'value':'x'},'x')], 'safety':[({'value':'<x>'},'<x>')]}"},
        'ground_truth':'PRIVATE_TARGET_ANSWER'}
    contract=runner.plt_contract(task)
    initial={'vulnerability_hypothesis':['Preserve valid input.'],'functional_invariants':['Return the input.']}
    cards=[];specs={};bindings={};examples={}
    for identifier in ('initial-card','repair-card'):
        card={'invariant_id':identifier,'kind':'direct_A','status':'active','support_count':1,'regression_count':0,
            'source_task_id':'source-'+identifier,'high_level_invariant':'Preserve the supplied input; avoid data loss.',
            'positive_principle':'Use the input unchanged.','negative_guardrail':'Do not discard valid input.',
            'applicability':'Identity task.','q_value':'PRIVATE_Q_VALUE'}
        cards.append(card)
        specs[identifier]={'card_id':identifier,'review_status':'reviewed',
            'reminder':{'path':['high_level_invariant'],'quote':'Preserve the supplied input'}}
        bindings[identifier]={'card_id':identifier,'review_status':'reviewed','public_task':public_task(contract),
            'operations':[{'action':'Preserve value and return the original string.',
                'card_evidence':[{'path':['positive_principle'],'quote':'Use the input unchanged.'}],
                'public_evidence':[{'field':'description','quote':'Return value unchanged.'}]}],
            'bound_elements':[{'role':'input','name':'value','public_field':'arguments'}],
            'unbound_source_details':[{'detail':'other source limits','status':'unknown'}]}
        examples[identifier]={'source_task_id':card['source_task_id'],'source_family_id':'source-family',
            'example_kind':'training_generated_episode','public_task':{'function_name':'source_func','description':'Historical source.'},
            'hidden_test':'PRIVATE_SOURCE_TEST','attempts':[{'attempt':0,'generated_code':'def source_func(): return None',
                'reported_state':'B','reported_validation':{'functional':'pass','security':'fail','details':'PRIVATE_SOURCE_TEST'}}]}
    start={'query':{**contract,'threat_analysis':initial,'current_code':'','failure_evidence':{}},
           'public_contract':contract,'task_id':'target','repeat':1,'initial_analysis':initial,
           'selected_cards':[cards[0]],'retrieval_trace':{'status':'completed','candidate_ids':['initial-card'],
                                                       'selected_ids':['initial-card']}}
    return task,start,cards,specs,bindings,examples


def material_callback(specs,bindings,examples):
    return lambda cards,task,level:{'card_specs':specs,'bindings':bindings,'examples':examples}


def test_five_levels_keep_source_cards_immutable_and_model_payload_whitelisted():
    task,start,cards,specs,bindings,examples=fixture()
    before=copy.deepcopy(cards)
    for level in LEVELS:
        rendered=apply_memory_level(cards,level,start['public_contract'],card_specs=specs,bindings=bindings,
                                     examples=examples,target_family=task['family_id'])
        text=experience_text(rendered)
        assert 'PRIVATE_' not in text
        assert [c['invariant_id'] for c in rendered]==([] if level=='L0' else ['initial-card','repair-card'])
        if level=='L1':assert 'risk_reminder' in text and 'positive_principle' not in text
        if level=='L2':assert 'Identity task.' in text and 'generated_code' not in text
        if level=='L3':assert 'target_operation_template' in text and 'generated_code' not in text
        if level=='L4':assert 'generated_code' in text and '"security": "fail"' in text
    assert cards==before


def test_public_binding_change_and_wrong_source_do_not_silently_downgrade():
    task,start,cards,specs,bindings,examples=fixture()
    with pytest.raises(GranularityPreparationRequired):
        apply_memory_level(cards,'L3',{**start['public_contract'],'return':'Different result'},
            card_specs=specs,bindings=bindings,target_family=task['family_id'])
    examples['initial-card']['source_family_id']=task['family_id']
    with pytest.raises(ValueError,match='family_overlap'):
        apply_memory_level(cards[:1],'L4',start['public_contract'],card_specs=specs,examples=examples,
                           target_family=task['family_id'])


def test_reference_seed_is_not_replaced_by_generated_success_and_missing_stays_missing():
    task,start,cards,specs,_,examples=fixture()
    examples['initial-card']['attempts'][0]['reported_validation']=None
    rendered=apply_memory_level(cards[:1],'L4',start['public_contract'],card_specs=specs,examples=examples,
                               target_family=task['family_id'])
    assert rendered[0]['_cle_memory_view']['source_example']['attempts'][0]['reported_validation'] is None
    cards[0]['kind']='seed_from_diff'
    with pytest.raises(ValueError,match='interchanged'):
        apply_memory_level(cards[:1],'L4',start['public_contract'],card_specs=specs,examples=examples,
                           target_family=task['family_id'])


def test_valid_seed_uses_reference_code_without_invented_pass_status():
    task,start,cards,specs,_,examples=fixture()
    cards[0]['kind']='seed_from_diff'
    examples['initial-card'].update(example_kind='training_reference_seed',
        reference_seed_code='def source_func(): return 1')
    rendered=apply_memory_level(cards[:1],'L4',start['public_contract'],card_specs=specs,examples=examples,
                               target_family=task['family_id'])
    payload=rendered[0]['_cle_memory_view']['source_example']
    assert payload['reference_seed_code']=='def source_func(): return 1'
    assert payload['validation_status']=='reference seed not reexecuted in this study'
    assert 'attempts' not in payload


def test_source_with_only_empty_code_cannot_be_called_complete_L4():
    task,start,cards,specs,_,examples=fixture()
    examples['initial-card']['attempts'][0]['generated_code']=''
    with pytest.raises(GranularityPreparationRequired,match='no_generated_code'):
        apply_memory_level(cards[:1],'L4',start['public_contract'],card_specs=specs,examples=examples,
                           target_family=task['family_id'])


@pytest.mark.parametrize('level',LEVELS)
def test_native_P7_preserves_level_for_new_repair_card_and_delivers_last_code(level):
    task,start,cards,specs,bindings,examples=fixture()
    prompts=[];repairs=[];generation_count=0
    def retrieve(query):
        repairs.append(copy.deepcopy(query))
        return [cards[1]],{'status':'completed','selected_ids':['repair-card']}
    def request(prompt):
        nonlocal generation_count
        prompts.append(prompt)
        if prompt.startswith('Generate complete'):
            content='def f(value): return None' if generation_count==0 else 'def f(value): return value'
            generation_count+=1
        elif prompt.startswith('Plan '):
            content=json.dumps({'Preserved_Func':'Identity','Patch_Scope':'Return input'})
        else:
            adopted=[] if level=='L0' else ['initial-card' if generation_count==0 else 'repair-card']
            content=json.dumps({**start['initial_analysis'],'applied_experience_ids':adopted})
        return {'choices':[{'message':{'content':content}}]}
    row=run_one_level(task,start,level,request,retrieve,material_callback(specs,bindings,examples))
    assert row['repeat']==1 and row['cell_id']==f'target_r1_{level}'
    assert len(row['attempts'])==2 and row['attempts'][-1]['joint']
    assert all('PRIVATE_' not in prompt for prompt in prompts)
    if level=='L0':
        assert repairs==[]
        assert all(not a['generation']['retrieved_cards'] for a in row['attempts'])
    else:
        assert repairs[0]['current_code']=='def f(value): return None'
        repair=row['attempts'][1]['generation']['retrieved_cards'][0]
        assert repair['invariant_id']=='repair-card'
        assert repair['_cle_memory_view']['memory_level']==level


def test_first_material_missing_stops_before_model_and_L0_needs_no_materials():
    task,start,cards,specs,bindings,examples=fixture()
    def forbidden(*args):raise AssertionError('must not call')
    with pytest.raises(GranularityPreparationRequired):
        run_one_level(task,start,'L3',forbidden,forbidden,
                      material_callback(specs,{},examples))
    provider=GranularityProvider(start,'L0',forbidden,forbidden,task['family_id'])
    assert provider(start['query'])[0]==[]
    assert provider({**start['query'],'current_code':'draft'})[0]==[]


def test_unknown_level_and_more_than_three_cards_stop_before_material_requests():
    task,start,cards,_,_,_=fixture()
    def forbidden(*args):raise AssertionError('must not call')
    with pytest.raises(ValueError,match='unknown_memory_level'):
        GranularityProvider(start,'unknown',forbidden,forbidden,task['family_id'])
    start['selected_cards']=cards*2
    with pytest.raises(ValueError,match='card_cap'):
        GranularityProvider(start,'L3',forbidden,forbidden,task['family_id'])


def test_changed_target_contract_stops_before_network_or_materials():
    task,start,_,_,_,_=fixture()
    task['task_description']['return']='Different result'
    def forbidden(*args):raise AssertionError('must not call')
    with pytest.raises(ValueError,match='public_contract_differs'):
        run_one_level(task,start,'L3',forbidden,forbidden,forbidden)


def test_missing_repair_binding_blocks_later_model_calls_and_retains_native_error():
    task,start,cards,specs,bindings,examples=fixture()
    del bindings['repair-card']
    prompts=[]
    def request(prompt):
        prompts.append(prompt)
        if prompt.startswith('Generate complete'):content='def f(value): return None'
        elif prompt.startswith('Plan '):content=json.dumps({'Preserved_Func':'Identity','Patch_Scope':'Return input'})
        else:content=json.dumps({**start['initial_analysis'],'applied_experience_ids':['initial-card']})
        return {'choices':[{'message':{'content':content}}]}
    row=run_one_level(task,start,'L3',request,lambda q:([cards[1]],{'status':'completed','selected_ids':['repair-card']}),
                      material_callback(specs,bindings,examples))
    assert row['preparation_blocked_reason'].startswith('GranularityPreparationRequired')
    assert row['pending_materials']['cards'][0]['invariant_id']=='repair-card'
    assert row['pending_materials']['query']['current_code']=='def f(value): return None'
    assert row['pending_materials']['trace_before_view']['selected_ids']==['repair-card']
    assert row['pending_materials']['trace_before_view']['status']=='completed'
    assert prompts[-1].startswith('Perform initial task threat analysis')
    assert not row['attempts'][-1]['measured']
    assert len([p for p in prompts if p.startswith('Generate complete')])==1


def test_native_first_joint_pass_skips_repair_entirely():
    task,start,cards,specs,bindings,examples=fixture()
    def forbidden(query):raise AssertionError('no repair retrieval')
    def request(prompt):
        if prompt.startswith('Generate complete'):text='def f(value): return value'
        elif prompt.startswith('Plan '):text=json.dumps({'Preserved_Func':'Identity','Patch_Scope':'Return input'})
        else:text=json.dumps({**start['initial_analysis'],'applied_experience_ids':['initial-card']})
        return {'choices':[{'message':{'content':text}}]}
    row=run_one_level(task,start,'L2',request,forbidden,material_callback(specs,bindings,examples))
    assert len(row['attempts'])==1 and row['attempts'][0]['joint']
