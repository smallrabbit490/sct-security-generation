"""固定候选四臂重复选卡的必要验证；无API、代码生成或Q更新。"""
from types import SimpleNamespace
import pytest

from methods.cle_ablation import run_selector_repeat as study


def test_jaccard_empty_and_overlap():
    assert study.distance([],[])==0
    assert study.distance(['a'],[])==1
    assert study.distance(['a','b'],['b','c'])==pytest.approx(2/3)


def test_noise_and_separation_effects():
    identical={'1':{'Q1':[['a']]*5,'Q2':[['a']]*5}}
    result,_=study.compare(identical,'Q2','Q1')
    assert result['excess_distance']==0 and result['p_block_permutation']==1
    separated={str(i):{'Q1':[['a']]*5,'Q2':[['b']]*5} for i in range(8)}
    result,_=study.compare(separated,'Q2','Q1')
    assert result['excess_distance']==1 and result['p_block_permutation']<.001


def test_invalid_selection_is_not_an_empty_set():
    spec={'task_id':'1','family_id':'family','cwe':'1','first_trace':{'candidate_ids':['a'],'query_hash':'x'},
          'orders':{'Q0':['a']},'prompts':{'Q0':'only fixed candidate'}}
    def invalid(prompt):
        return {'choices':[{'message':{'content':'not json'},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}
    row=study.one_selection(spec,'Q0',1,invalid)
    assert row['status']=='error' and row['selected_ids'] is None
    assert len(row['retrieval_trace']['selector_attempts'])==2
    assert row['code_generated'] is False and row['Q_updated'] is False


def test_cached_native_selector_maps_ids_and_allows_more_than_three():
    node=lambda i:SimpleNamespace(invariant_id=i,q_value=0.,status='active')
    eligible={i:(node(i),'{}') for i in ('a','b','c','d')}
    query={'description':'public contract'}
    original=study.native.recall_semantic_candidates
    spec={'query':query,'first_trace':{'query_hash':study.native._digest(study.native.query_embedding_text(query)),
          'candidate_ids':list(eligible),'scores':[{'id':i,'cosine':.9,'lexical':0} for i in eligible]}}
    seen=[]
    def request(prompt):
        seen.append(str(prompt))
        return {'choices':[{'message':{'content':'{"selected":[4,1,2,3]}'},'finish_reason':'stop'}]}
    cards,trace=study.select_cached(spec,eligible,'Q0',request)
    assert [n.invariant_id for n in cards]==['d','a','b','c']
    assert trace['selection_limit'] is None
    assert study.native.recall_semantic_candidates is original
    assert 'no fixed maximum' in seen[0] and 'q_value' not in seen[0]
