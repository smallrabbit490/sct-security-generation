import importlib.util
from pathlib import Path

path=Path(__file__).resolve().parents[1]/'configs/cle_memory_q_full_gate_cap3_20261019/analyze.py'
spec=importlib.util.spec_from_file_location('full_gate_analysis_tests',path)
analysis=importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def test_empty_code_attempt_recovers_saved_card_audit_without_editing_native_trace():
    trace={'status':'completed','selected_ids':['a']}
    attempt={'retrieval_trace':None,'generation':{'retrieved_cards':[
        {'invariant_id':'a','retrieval_audit':trace}],'stages':[{'stage':'retrieval','status':'completed'}]}}
    assert analysis.trace_of(attempt) is trace
    assert attempt['retrieval_trace'] is None


def test_failed_current_retrieval_keeps_priority_over_saved_old_audit():
    old={'status':'completed','selected_ids':['a']}
    failed={'status':'error','errors':['embedding_request_URLError']}
    attempt={'retrieval_trace':old,'generation':{'retrieved_cards':[],
        'stages':[{'stage':'retrieval','status':'degraded','retrieval_trace':failed}]}}
    assert analysis.trace_of(attempt) is failed


def test_missing_outcome_is_not_a_paired_failure():
    def row(task,arm,joint,measured=True):
        return {'task_id':task,'family_id':task,'arm':arm,
            'final':{'joint':joint,'functional':joint,'measured':measured}}
    rows=[row('a','Q2',True),row('a','Q0',False),
          row('b','Q2',True),row('b','Q0',True),
          row('c','Q2',False,False),row('c','Q0',True)]
    paired=analysis.paired(rows)
    assert paired['pairs']==3 and paired['measured_pairs']==2
    assert paired['wins']==1 and paired['losses']==0 and paired['net']==1
    assert sum(r['final']['joint'] for r in rows if r['arm']=='Q2')==sum(r['final']['joint'] for r in rows if r['arm']=='Q0')
