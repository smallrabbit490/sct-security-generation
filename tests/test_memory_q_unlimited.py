"""新协议的数量上限、顺序干预与实际采用反馈；离线不调用 API。"""
import json

from methods.sct_trajectory.hsk_tree import HskTree, LanguageLeaf, SecurityInvariantNode
from methods.sct_trajectory.retriever import HskTreeRetriever
from methods.sct_trajectory.context_pipeline import adopt_experiences, experience_text
from methods.sct_trajectory.memory_q import rank_candidates, update_adopted


class Scores:
    model = 'offline'
    def cosine_scores(self, query, texts):
        return [0.95-i*0.01 for i in range(len(texts))]


def bank():
    return [SecurityInvariantNode(str(i), '22', 'Keep supplied path policy',
        q_value=-0.8 if i < 3 else 0.8, language_leaves={'python': LanguageLeaf('python')})
        for i in range(6)]


def test_unlimited_select_adopt_and_credit_all_six():
    nodes = bank()
    prompts = []
    def request(prompt):
        prompts.append(prompt)
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'selected': [1,2,3,4,5,6]})}}]}
    r = HskTreeRetriever(HskTree(), requester=request, retrieval_mode='semantic_llm',
                         embedding_client=Scores(), candidate_order='q', semantic_delta=-1)
    cards = r.search({'description': 'Handle paths', 'language': 'python'}, limit=None, pool_nodes=nodes)
    assert len(cards) == 6
    assert 'no fixed maximum' in prompts[0] and 'at most 3' not in prompts[0]
    assert 'q_value' not in prompts[0] and 'q_visits' not in prompts[0]
    adopted, audit = adopt_experiences(cards, {'applied_experience_ids': [c['invariant_id'] for c in cards]})
    assert len(adopted) == 6 and audit['error'] is None
    evidence = {'functional': {'status': 'pass'}, 'security': {'status': 'pass'}}
    events = update_adopted({n.invariant_id:n for n in nodes}, audit['applied_ids'], evidence,
                           code='def f(): return 1', pool='D_grow')
    assert len(events) == 6 and all(n.q_visits == 1 for n in nodes)
    assert 'q_value' not in experience_text(cards)


def test_same_candidates_q_changes_order_and_legacy_limit_stays_three():
    nodes = bank()
    scores = [{'id': n.invariant_id, 'cosine': .95-i*.01} for i,n in enumerate(nodes)]
    values = {n.invariant_id:n.q_value for n in nodes}
    sim = rank_candidates(scores, values, delta=-1, lambda_q=0, limit=None)
    q = rank_candidates(scores, values, delta=-1, lambda_q=.5, limit=None)
    assert {x['id'] for x in sim} == {x['id'] for x in q}
    assert [x['id'] for x in sim] != [x['id'] for x in q]
    assert len(rank_candidates(scores, values, delta=-1, limit=20)) == 3


def test_unadopted_and_unmeasured_do_not_get_q():
    nodes = bank(); before = [n.to_dict() for n in nodes]
    update_adopted({n.invariant_id:n for n in nodes}, ['0','1','2','3'],
                   {'error': 'environment_error'}, code='x', pool='D_grow')
    assert before == [n.to_dict() for n in nodes]


def test_real_pipeline_keeps_six_cards_to_generation():
    from methods.sct_trajectory.context_pipeline import run_context_pipeline
    cards=[{'invariant_id':str(i),'positive_principle':'Preserve supplied bindings',
            'high_level_invariant':'Preserve supplied bindings','applicability':'supplied context'} for i in range(6)]
    initial={'vulnerability_hypothesis':['Untrusted path'],'functional_invariants':['Preserve return value']}
    responses=[{**initial,'applied_experience_ids':[str(i) for i in range(6)],'rejected_experiences':[]},
               {'Preserved_Func':'Return value','Patch_Scope':'Implement function'}, 'def f(): return 1']
    prompts=[]
    def request(prompt):
        prompts.append(prompt); value=responses.pop(0)
        return {'choices':[{'finish_reason':'stop','message':{'content':value if isinstance(value,str) else json.dumps(value)}}]}
    result=run_context_pipeline({'description':'Return one'},[],requester=request,
                                cards_provider=lambda query:cards,initial_analysis=initial)
    assert result['workflow_completed'] and len(result['cards'])==6
    assert all(str(i) in prompts[-1] for i in range(6))


def test_failed_probe_does_not_start_full_paid_stages(tmp_path,monkeypatch):
    import sys
    from methods.cle_ablation import run_memory_q_unlimited as study
    monkeypatch.setattr(study,'ROOT',tmp_path)
    out=tmp_path/'translation_work/diagnostics/test';out.mkdir(parents=True)
    (out/'run_metadata.json').write_text('{}',encoding='utf-8')
    (out/'probe_gate.json').write_text('{"passed":false}',encoding='utf-8')
    monkeypatch.setattr(study,'execute',lambda *a,**k: (_ for _ in ()).throw(AssertionError('paid stage opened')))
    reports=[];monkeypatch.setattr(study,'report',lambda path:reports.append(path))
    monkeypatch.setattr(sys,'argv',['study','--stage','all','--out',str(out)])
    study.main()
    assert reports


def test_gate_screen_excludes_known_bad_task_and_its_family(tmp_path,monkeypatch):
    from configs.cle_memory_q_unlimited_20261018 import revise_gate_preflight as revision
    monkeypatch.setattr(revision,'ROOT',tmp_path)
    config=tmp_path/'new_config';config.mkdir();monkeypatch.setattr(revision,'CONFIG',config)
    old=tmp_path/'configs/cle_retrieval_q_public_contract_20261017';old.mkdir(parents=True)
    (old/'contract_review.json').write_text(json.dumps({'0':{'qualified':False,'reason':'public contract conflict'}}),encoding='utf-8')
    other=tmp_path/'configs/cle_memory_q_shared_initial8_20261016';other.mkdir()
    (other/'prepare.py').write_text("DECISIONS = {'4':'exclude: missing public API'}",encoding='utf-8')
    out=tmp_path/'run';out.mkdir()
    checks=[{'task_id':str(i),'qualified':True,'family_id':'0' if i==1 else str(i)} for i in range(60)]
    (out/'gate_preflight.json').write_text(json.dumps({'tasks':checks}),encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps({'development':list(range(48))}),encoding='utf-8')
    revision.main(out)
    ids=json.loads((out/'manifest.json').read_text(encoding='utf-8'))['development']
    assert len(ids)==48 and not {0,1,4}&set(ids)
    assert (out/'manifest.initial_reference_preflight.json').exists()


def test_explicit_user_override_runs_all_stages_despite_probe_failure(tmp_path,monkeypatch):
    import sys
    from methods.cle_ablation import run_memory_q_unlimited as study
    monkeypatch.setattr(study,'ROOT',tmp_path)
    out=tmp_path/'translation_work/diagnostics/test';out.mkdir(parents=True)
    (out/'run_metadata.json').write_text('{"probe_gate_override":true}',encoding='utf-8')
    (out/'probe_gate.json').write_text('{"passed":false}',encoding='utf-8')
    stages=[];monkeypatch.setattr(study,'execute',lambda path,stage,*a,**k:stages.append(stage))
    monkeypatch.setattr(study,'report',lambda path:None)
    monkeypatch.setattr(sys,'argv',['study','--stage','all','--out',str(out),'--continue-despite-probe'])
    study.main()
    assert stages==['observe','retest','gate']
