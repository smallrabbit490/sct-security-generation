"""复现原P7修复检索失败后残留旧轨迹的记录情形，不调用API。"""
from methods.cle_ablation import run_memory_q_full_gate_v2 as s


def row(attempt):
    return {'task_id':'x','arm':'Q2','workflow_arm':'P7','pool':'D_gate',
        'attempts':[attempt],'final':attempt}


def test_failed_current_retrieval_does_not_claim_prior_selected_cards():
    old={'status':'completed','selection_limit':3,'selected_ids':['old']}
    actual={'status':'error','errors':['invalid_selection_count']}
    a={'attempt':0,'joint':False,'functional':False,'security':False,'measured':True,
        'retrieval_trace':old,'generation':{'cards':[],'retrieved_cards':[],
        'stages':[{'stage':'retrieval','status':'degraded','retrieval_trace':actual}]}}
    issues,resolved=s.inspect([row(a)])
    assert issues==[] and len(resolved)==1
    assert s.effective_trace(a) is actual
    assert a['retrieval_trace'] is old


def test_successful_retrieval_card_mismatch_still_stops():
    a={'attempt':0,'joint':False,'functional':False,'security':False,'measured':True,
        'retrieval_trace':{'status':'completed','selection_limit':3,'selected_ids':['old']},
        'generation':{'cards':[],'retrieved_cards':[],'stages':[{'stage':'retrieval','status':'completed'}]}}
    issues,_=s.inspect([row(a)])
    assert issues[0]['error']=='successful_trace_card_mismatch'
