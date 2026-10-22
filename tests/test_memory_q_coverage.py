"""覆盖学习的必要离线检查：不造奖励、不截断、原策略不变。"""
from methods.sct_trajectory.memory_q import rank_coverage_candidates, rank_candidates, update_adopted
from methods.sct_trajectory.hsk_tree import SecurityInvariantNode
import copy
import json


def test_unlearned_first_preserves_candidates_and_ties():
    scores=[{'id':'old','cosine':.95},{'id':'new-b','cosine':.8},{'id':'new-a','cosine':.8},{'id':'low','cosine':.6}]
    before=copy.deepcopy(scores)
    ranked=rank_coverage_candidates(scores,{'old':3,'new-b':0,'new-a':0,'low':1})
    assert [r['id'] for r in ranked]==['new-a','new-b','old','low']
    assert scores==before and len(ranked)==4
    assert [s['id'] for s in rank_candidates(scores,{s['id']:0 for s in scores},delta=-1,lambda_q=0,limit=None)]==['old','new-a','new-b','low']


def test_coverage_respects_existing_semantic_threshold():
    assert rank_coverage_candidates([{'id':'new','cosine':.5}],{'new':0},delta=.5)==[]


def test_no_reward_without_measured_actual_adoption():
    node=SecurityInvariantNode.from_dict({'invariant_id':'a','cwe':'74','q_value':0,'q_visits':0})
    nodes={'a':node}
    update_adopted(nodes,[],{},code='x=1',pool='D_grow')
    update_adopted(nodes,['a'],{'error':'incomplete'},code='x=1',pool='D_grow')
    assert node.q_visits==0 and node.q_value==0
    good={'functional':{'status':'pass','measured':True},'security':{'status':'pass','measured':True}}
    update_adopted(nodes,['a','a'],good,code='x=1',pool='D_grow')
    assert node.q_visits==1 and node.q_value==.3


def test_native_selector_coverage_branch_keeps_limit_and_hides_Q():
    from methods.sct_trajectory.semantic_retrieval import semantic_select
    nodes=[SecurityInvariantNode.from_dict({'invariant_id':name,'cwe':'74','status':'active',
        'positive_principle':'Validate input '+name,'language_leaves':{'python':{'language':'python'}},
        'q_visits':visits,'q_value':.9 if visits else 0}) for name,visits in [('old',3),('new',0)]]
    class Embedding:
        model='offline'
        def cosine_scores(self,query,texts):return [.7,.9]
    prompts=[]
    def request(prompt):
        prompts.append(prompt)
        return {'choices':[{'message':{'content':json.dumps({'selected':[1]})},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}
    chosen,trace=semantic_select({'language':'python','description':'Validate input'},nodes,request,Embedding(),
                                limit=3,candidate_order='coverage',delta=-1)
    assert trace['status']=='completed' and trace['presented_candidate_ids']==['new','old']
    assert chosen[0].invariant_id=='new' and trace['selection_limit']==3
    assert 'q_visits' not in prompts[0] and 'q_value' not in prompts[0]
    assert [n.q_visits for n in nodes]==[3,0]


def test_L0_L1_normalization_preserves_native_records():
    from methods.cle_ablation.run_memory_q_coverage_v2 import normalize_result
    task={'index':1,'family_id':'family','CWE_ID':'74'}
    for arm in ['L0','L1']:
        row={'task_id':'1','arm':'P7','attempts':[{'attempt':0,'code':'x=1','generation':{}}]}
        normalize_result(row,task,arm,1)
        assert row['arm']==arm and row['final']['code']=='x=1'
        assert row['final'] is row['attempts'][0] and row['pool']=='D_grow'


def test_batch_credit_inherits_old_Q_and_counts_only_adopted(monkeypatch,tmp_path):
    from methods.cle_ablation import run_memory_q_coverage_v2 as study
    monkeypatch.setattr(study,'OUT',tmp_path)
    (tmp_path/'fixed_grow_anchor_ids.json').write_text('["used","unused"]')
    used=SecurityInvariantNode.from_dict({'invariant_id':'used','cwe':'74','q_value':.3,'q_visits':1})
    unused=SecurityInvariantNode.from_dict({'invariant_id':'unused','cwe':'74','q_value':0,'q_visits':0})
    attempt={'attempt':0,'code':'x=1','measured':True,'functional':True,'security':True,'joint':True,
        'generation':{'workflow_completed':True,'retrieved_cards':[{'invariant_id':'used'},{'invariant_id':'unused'}],
                      'cards':[{'invariant_id':'used'}]},
        'validation':{'evidence':{'functional':{'status':'pass','measured':True},'security':{'status':'pass','measured':True}}},
        'retrieval_trace':{'status':'completed'}}
    row={'task_id':'t','pool':'D_grow','family_id':'new-family','attempts':[attempt],'final':attempt,
         'accounting':{'total':{k:0 for k in study.FIELDS}}}
    folder=tmp_path/'batch';folder.mkdir()
    learned,families,summary=study.credit([row],[used,unused],{'used':['old-family']},['t'],folder)
    assert learned[0].q_value==.51 and learned[0].q_visits==2
    assert learned[1].q_visits==0 and used.q_value==.3 and used.q_visits==1
    assert families['used']=={'old-family','new-family'} and summary['valid_updates']==1
