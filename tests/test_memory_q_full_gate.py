"""全D_gate四臂复用父P7，三张限制和原始状态映射验证，不调用API。"""
from types import SimpleNamespace
from methods.cle_ablation import run_memory_q_full_gate as s


def test_four_arm_mapping_has_true_original_Q0():
    assert s.ORDER=={'Q0':None,'Q1':'similarity','Q2':'q','Q3':'q'}


def test_all_arms_use_native_complete_P7_and_cap_three(monkeypatch):
    seen=[]
    def fake(subset,task,arm,request,memory,embedding,**kwargs):
        seen.append((subset,arm,memory,kwargs))
        return {'attempts':[{'attempt':0,'code':'pass','functional':True,'security':True,'joint':True,'measured':True,
            'generation':{'cards':[],'retrieved_cards':[],'workflow_completed':True}}]}
    monkeypatch.setattr(s.parent,'frozen_runner',lambda:SimpleNamespace(run_one=fake))
    task={'index':1,'family_id':'family','CWE_ID':1}
    for arm in s.ORDER:
        row=s.run_job('1',arm,{'1':task},{'1':{'analysis':'shared'}},['learned'],['shuffled'],lambda p:None,object())
        assert row['workflow_arm']=='P7' and row['pool']=='D_gate'
    for subset,arm,memory,kw in seen:
        assert subset=='PLT' and arm=='P7'
        assert kw['max_experiences']==3 and kw['retrieval_mode']=='semantic_llm'
        assert kw['initial_analysis']=={'analysis':'shared'}
    assert [m['full'] for _,_,m,_ in seen]==[['learned'],['learned'],['learned'],['shuffled']]
