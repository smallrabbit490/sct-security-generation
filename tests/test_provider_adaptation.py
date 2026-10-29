"""只验证已观测的JSON拆分、单次HTTP和跨协议预算；不联网。"""
import copy
import json

import pytest

from methods.cle_ablation.provider_adaptation import (
    normalize_structured_response, carried_budget, exact_saved_response)
from methods.cle_ablation.run_joint_contract import BudgetExceeded
from methods.sct_trajectory.agent_pipeline import _content


def response(text):
    return {'choices':[{'message':{'content':text},'finish_reason':'stop'}],
            'usage':{'total_tokens':7}}


def test_adjacent_disjoint_objects_preserve_every_value_and_original():
    text='```json\n{"functional_invariants":["Return input."]}\n{"applied_experience_ids":["card-1"]}\n```'
    original=response(text)
    before=copy.deepcopy(original)
    normalized,note=normalize_structured_response('Perform experience-conditioned reanalysis.',original)
    assert json.loads(_content(normalized))=={'functional_invariants':['Return input.'],
                                             'applied_experience_ids':['card-1']}
    assert original==before and normalized['usage']==original['usage']
    assert note['object_count']==2 and note['invented_fields']==0


@pytest.mark.parametrize('text',[
    '{"x":1}{"x":2}', '{"x":1} explanatory text {"y":2}',
    'prefix {"x":1}{"y":2}', '{"x":1}[2]', '{"x":1}{"y":',
])
def test_ambiguous_or_partial_text_is_not_repaired(text):
    original=response(text)
    assert normalize_structured_response('Perform analysis.',original)==(original,None)


def test_code_and_valid_single_json_are_not_rewritten():
    for prompt,text in [('Generate complete runnable Python code','{"x":1}{"y":2}'),
                        ('Plan the implementation.','{"x":1}')]:
        original=response(text)
        assert normalize_structured_response(prompt,original)==(original,None)


def test_budget_carries_failed_unknown_usage_and_single_attempt_reservation():
    execution={'max_http_attempts':4,'max_conservative_tokens':10000,'max_embedding_attempts':1}
    old={'records':[{'kind':'chat','status':'failed','usage':None}],
         'reserved_http_attempts':3,'reserved_token_bound':3000,'reserved_embedding_http_attempts':0}
    budget=carried_budget(execution,[old])
    request=budget.wrap(lambda _:response('OK'),32,max_attempts=1)
    request('small')
    assert budget.snapshot()['reserved_http_attempts']==4
    assert budget.snapshot()['unknown_usage_operations']==1
    with pytest.raises(BudgetExceeded):request('no budget')


def test_only_same_cell_exact_prompt_reuses_completed_response(tmp_path):
    request=tmp_path/'requests';request.mkdir()
    (request/'0001.prompt.txt').write_text('same',encoding='utf-8')
    status=request/'0001.status.json'
    status.write_text(json.dumps({'status':'returned','cell_id':'cell-1'}),encoding='utf-8')
    (request/'0001.response.json').write_text(json.dumps(response('saved')),encoding='utf-8')
    assert exact_saved_response('same',tmp_path,'cell-1')[0]==response('saved')
    assert exact_saved_response('changed',tmp_path,'cell-1')==(None,None)
    assert exact_saved_response('same',tmp_path,'cell-2')==(None,None)
    status.write_text(json.dumps({'status':'failed','cell_id':'cell-1'}),encoding='utf-8')
    assert exact_saved_response('same',tmp_path,'cell-1')==(None,None)
