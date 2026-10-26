"""经验复析必须真正约束注入，不调用 API。"""
import json
from methods.sct_trajectory.context_pipeline import run_context_pipeline
from methods.sct_trajectory.hsk_tree import HskTree, SecurityInvariantNode, LanguageLeaf
from methods.sct_trajectory.retriever import HskTreeRetriever


def response(value):
    return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value) if isinstance(value, dict) else value}}]}


def test_rejected_card_removed_from_downstream_but_kept_for_audit():
    cards = [{'invariant_id': 'good', 'positive_principle': 'GOOD_SENTINEL'},
             {'invariant_id': 'bad', 'positive_principle': 'BAD_SENTINEL'}]
    initial = {'vulnerability_hypothesis': ['path escape'], 'functional_invariants': ['read files']}
    replies = [initial, {**initial, 'applied_experience_ids': ['good', 'bad'],
                         'safe_actions': ['BAD_SENTINEL'],
                         'rejected_experiences': [{'id': 'bad', 'reason': 'BAD_SENTINEL wrong API'}]},
               {'Preserved_Func': 'read', 'Patch_Scope': 'resolve'}, 'def f(): return True']
    seen = []
    def req(prompt):
        seen.append(prompt)
        return response(replies.pop(0))
    result = run_context_pipeline({'description': 'Read valid paths'}, cards, requester=req)
    assert 'BAD_SENTINEL' in seen[1]
    assert all('BAD_SENTINEL' not in prompt for prompt in seen[2:])
    assert [c['invariant_id'] for c in result['cards']] == ['good']
    assert result['retrieved_cards'] == cards
    assert result['adoption']['rejected_ids'] == ['bad']
    assert result['experience_analysis']['safe_actions'] == ['BAD_SENTINEL']
    assert not any('\u4e00' <= c <= '\u9fff' for prompt in seen for c in prompt)


def test_missing_adoption_list_does_not_silently_inject_all_cards():
    initial = {'vulnerability_hypothesis': ['risk'], 'functional_invariants': ['return result']}
    replies = [initial, initial, {'Preserved_Func': 'result', 'Patch_Scope': 'full'}, 'def f(): return 1']
    result = run_context_pipeline({'description': 'return result'}, [{'invariant_id':'n'}], requester=lambda p: response(replies.pop(0)))
    assert result['cards'] == []
    assert result['adoption']['error'] == 'missing_applied_experience_ids'


def test_same_task_card_cannot_override_llm_rejection(monkeypatch):
    from methods.sct_trajectory import hier_retrieval
    own = SecurityInvariantNode('own','22','bad history',source={'task_id': 7})
    chosen = SecurityInvariantNode('chosen','22','valid action')
    for n in [own,chosen]: n.language_leaves['python'] = LanguageLeaf('python')
    monkeypatch.setattr(hier_retrieval,'hierarchical_select',lambda **kw: ([chosen],{'levels':[]}))
    r=HskTreeRetriever(HskTree(),requester=lambda p:{},retrieval_mode='hier_llm')
    cards=r.search({'task_id':7,'CWE_ID':'22','language':'python'},limit=1,pool_nodes=[own,chosen])
    assert [c['invariant_id'] for c in cards] == ['chosen']


def test_semantic_error_cannot_be_silent_empty_memory(monkeypatch):
    from methods.sct_trajectory import semantic_retrieval
    import pytest
    node = SecurityInvariantNode('n','22','check path')
    node.language_leaves['python'] = LanguageLeaf('python')
    monkeypatch.setattr(semantic_retrieval, 'semantic_select', lambda *a, **k: ([], {'status':'error','errors':['http_timeout']}))
    r = HskTreeRetriever(HskTree(),requester=lambda p:{},retrieval_mode='semantic_llm',embedding_client=object())
    with pytest.raises(RuntimeError, match='semantic_retrieval_failed'):
        r.search({'language':'python'},pool_nodes=[node])
    assert r.last_hier_trace['errors'] == ['http_timeout']


def test_hybrid_mode_requires_embedding_and_preserves_trace(monkeypatch):
    node = SecurityInvariantNode('n', '22', 'check path', language_leaves={'python': LanguageLeaf('python')})
    r = HskTreeRetriever(HskTree(), requester=lambda p: {}, retrieval_mode='semantic_hybrid_v2')
    import pytest
    with pytest.raises(ValueError, match='semantic_hybrid_v2_requires_embedding_client'):
        r.search({'language': 'python'}, pool_nodes=[node])

    from methods.sct_trajectory import semantic_retrieval
    monkeypatch.setattr(semantic_retrieval, 'hybrid_select', lambda *a, **k: ([], {
        'status': 'error', 'errors': ['embedding_timeout'], 'retrieval_mode': 'semantic_hybrid_v2'}))
    r = HskTreeRetriever(HskTree(), requester=lambda p: {}, retrieval_mode='semantic_hybrid_v2', embedding_client=object())
    with pytest.raises(RuntimeError, match='semantic_hybrid_v2_failed'):
        r.search({'language': 'python'}, pool_nodes=[node])
    assert r.last_hier_trace['retrieval_mode'] == 'semantic_hybrid_v2'


def test_non_english_analysis_and_plan_fail_closed():
    initial = {'vulnerability_hypothesis':['risk'],'functional_invariants':['result']}
    replies=[initial,{**initial,'safe_actions':['拒绝所有输入'],'applied_experience_ids':['n']},
             {'Preserved_Func':'结果','Patch_Scope':'修改'},'def f(): return 1']
    seen=[]
    def req(prompt):
        seen.append(prompt)
        return response(replies.pop(0))
    result=run_context_pipeline({'description':'return result'},[{'invariant_id':'n'}],requester=req)
    assert not result['workflow_completed']
    assert not result['cards']
    assert all('拒绝所有输入' not in p and '修改' not in p for p in seen)


def test_invalid_adoption_schema_closes_all_injection():
    from methods.sct_trajectory.context_pipeline import adopt_experiences
    cards = [{'invariant_id':'good'}, {'invariant_id':'bad'}]
    for value in ({'applied_experience_ids':['good','bad'], 'rejected_experiences':['bad']},
                  {'applied_experience_ids':['good','unknown'], 'rejected_experiences':[]}):
        selected, audit = adopt_experiences(cards,value)
        assert selected == [] and audit['error']


def test_semantic_gate_pipeline_error_is_unmeasured(monkeypatch):
    import pytest
    from methods.sct_trajectory import closed_loop as cl
    from methods.sct_trajectory.error_ledger import ErrorLedger
    runner=cl.CleRunner(lambda p:{},HskTree(),ErrorLedger(),retrieval_mode='semantic_llm',context_pipeline=True)
    monkeypatch.setattr(cl,'run_pipeline',lambda *a,**k:{'code':'def f(): return 1','error_type':'retrieval:RuntimeError'})
    rows=[{'index':1,'task_description':{'description':'return one'}}]
    with pytest.raises(RuntimeError,match='unmeasured_gate_pipeline'):
        runner._joint_pass_rate(rows,lambda q:[])
    with pytest.raises(RuntimeError,match='unmeasured_regression_pipeline'):
        runner._regression_probe(rows,lambda q:[],samples=1)
