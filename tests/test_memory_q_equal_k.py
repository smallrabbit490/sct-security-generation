"""等量选卡、共用契约和重复统计的离线检验；不调用API。"""
import copy
import json
from types import SimpleNamespace

import pytest

from methods.cle_ablation.run_memory_q_equal_k import choose, cluster_pair, IMPLEMENTATION_CONSTRAINTS


def test_equal_k_above_three_and_common_presentation():
    nodes = [SimpleNamespace(invariant_id=str(i),q_value=-1 if i<5 else 1) for i in range(10)]
    scores = [{'id':str(i),'cosine':.9-i*.01} for i in range(10)]
    _,sim = choose(scores,nodes,7,'Q1')
    ranking,q = choose(scores,nodes,7,'Q2')
    assert len(sim)==len(q)==7 and set(sim)!=set(q)
    assert q==sorted(q,key=lambda i:int(i))
    assert q != [v['id'] for v in ranking[:7]]
    assert choose(scores,nodes,0,'Q2')[1] == []


def test_p7_callback_preserves_query_and_six_cards_to_generation(monkeypatch):
    from methods.cle_ablation.runner import run_one
    from methods.sct_trajectory import closed_loop
    from methods.sct_trajectory.semantic_retrieval import query_embedding_text
    initial={'vulnerability_hypothesis':['Untrusted value'],'functional_invariants':['Use caller configuration']}
    cards=[{'invariant_id':str(i),'positive_principle':'Preserve caller configuration'} for i in range(6)]
    prompts=[];queries=[]
    responses=[{**initial,'applied_experience_ids':[str(i) for i in range(6)],'rejected_experiences':[]},
               {'Preserved_Func':'Use supplied settings','Patch_Scope':'Return requested value'},'def f(): return SETTINGS']
    def request(prompt):
        prompts.append(prompt);v=responses.pop(0)
        return {'choices':[{'message':{'content':v if isinstance(v,str) else json.dumps(v)}}]}
    def provider(query):
        queries.append(query)
        return cards,{'status':'completed','selected_ids':[str(i) for i in range(6)]}
    monkeypatch.setattr(closed_loop,'validate_and_state',lambda *a,**k: (
        {'functional':{'status':'pass'},'security':{'status':'pass'}},'A'))
    row=run_one('PLT',{'index':1,'task_description':{'description':'Return SETTINGS'},'CWE_ID':'20'},
        'P7',request,{'full':[]},initial_analysis=copy.deepcopy(initial),
        retrieval_provider=provider,implementation_constraints=IMPLEMENTATION_CONSTRAINTS)
    assert len(row['attempts'])==1 and row['attempts'][0]['joint']
    assert len(row['attempts'][0]['generation']['cards'])==6 and len(prompts)==3
    assert all(IMPLEMENTATION_CONSTRAINTS in p for p in prompts)
    assert 'implementation_constraints' not in query_embedding_text(queries[0])
    assert initial=={'vulnerability_hypothesis':['Untrusted value'],'functional_invariants':['Use caller configuration']}


def test_repeated_pairs_use_eight_families_not_sixteen_samples():
    rows=[{'family_id':str(i),'arm':arm,'repeat':b,'final':{'joint':arm=='Q2'}}
          for i in range(8) for b in (1,2) for arm in ('Q1','Q2')]
    value=cluster_pair(rows,'Q1','Q2')
    assert value['families']==8 and value['mean_joint_difference']==1
    assert value['p_exact_sign_flip']==2/256
    assert value['ci95']==[1,1]
    assert cluster_pair(rows[:-1],'Q1','Q2')['complete'] is False


def test_human_review_requires_real_confirmation_fields(tmp_path):
    import csv
    from methods.cle_ablation.run_memory_q_equal_k import import_review
    (tmp_path/'blind_pairs.jsonl').write_text('{"pair_id":"p"}\n',encoding='utf-8')
    row={'pair_id':'p','human_label':'direct','task_evidence':'public task','card_evidence':'card text',
         'reason':'applicable','reviewer':'','confirmed_at':''}
    path=tmp_path/'review.csv'
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader();writer.writerow(row)
    with pytest.raises(ValueError,match='review_not_adjudicated'):
        import_review(tmp_path,path)
    assert not (tmp_path/'human_labels.json').exists()
