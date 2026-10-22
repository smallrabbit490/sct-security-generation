"""补充Q0仅恢复原P7、取消数量限制且不读取Q；测试不调用API。"""
import inspect
import json
from types import SimpleNamespace

from methods.cle_ablation import run_memory_q_gate_q0 as study


def test_parent_runner_is_loaded_instead_of_changed_live_runner():
    runner=study.frozen_runner()
    assert 'unlimited_complete_v2/source_snapshot' in runner.__file__.replace('\\','/')
    parameters=inspect.signature(runner.run_one).parameters
    assert parameters['max_experiences'].default==3
    assert 'implementation_constraints' not in parameters
    assert runner.ROOT==study.ROOT


def test_job_passes_unlimited_native_order_and_reuses_initial(monkeypatch):
    seen={}
    initial={'functional_invariants':['preserve provided interface']}
    nodes=[SimpleNamespace(q_value=.9,q_visits=3)]
    task={'index':1256,'family_id':'family','CWE_ID':1333}
    def fake_run(subset,provided,arm,request,memory,embedding,**kwargs):
        seen.update(subset=subset,task=provided,arm=arm,memory=memory,kwargs=kwargs)
        assert kwargs['initial_analysis'] is not initial
        request('test-only prompt')
        return {'attempts':[{'code':'pass','functional':True,'security':True,'joint':True,'measured':True,
            'generation':{'cards':[],'workflow_completed':True}}],
            'usage':{'calls':1,'total_tokens':3}}
    monkeypatch.setattr(study,'frozen_runner',lambda:SimpleNamespace(run_one=fake_run))
    response=lambda prompt:{'usage':{'prompt_tokens':2,'completion_tokens':1,'total_tokens':3}}
    row=study.run_job('1256',{'1256':task},{'1256':initial},nodes,response,object())
    assert seen['arm']=='P7' and seen['subset']=='PLT'
    assert seen['kwargs']['retrieval_mode']=='semantic_llm'
    assert seen['kwargs']['candidate_order'] is None
    assert seen['kwargs']['max_experiences'] is None
    assert 'implementation_constraints' not in seen['kwargs']
    assert row['arm']=='Q0' and row['pool']=='D_gate'
    assert row['accounting']['total']['calls']==1
    assert nodes[0].q_value==.9 and nodes[0].q_visits==3


def test_resume_does_not_rerun_saved_failures(tmp_path,monkeypatch):
    (tmp_path/'manifest.json').write_text(json.dumps({'tasks':['1256','1306']}),encoding='utf-8')
    (tmp_path/'rows.jsonl').write_text(''.join(json.dumps({'task_id':i,'error_type':'saved_native_failure'})+'\n'
                                            for i in ('1256','1306')),encoding='utf-8')
    monkeypatch.setattr(study,'verify',lambda out:None)
    monkeypatch.setattr(study,'report',lambda out:{'saved_rows_kept':True})
    from methods.sct_trajectory import run_closed_loop
    def forbidden(*args,**kwargs):
        raise AssertionError('saved identities must not make API requester')
    monkeypatch.setattr(run_closed_loop,'_requester',forbidden)
    assert study.run(tmp_path,2,2)=={'saved_rows_kept':True}
