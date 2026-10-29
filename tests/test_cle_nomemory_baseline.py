"""P3保留Agent步骤和原修复规则，但任何经验访问都应为零。"""
import json
from pathlib import Path
from unittest.mock import patch

from methods.cle_ablation import runner
from configs.cle_nomemory_baseline_20261024.run import FirstTwoGate


def test_p3_keeps_analysis_planning_generation_and_never_retrieves():
    seen=[]
    def request(prompt):
        seen.append(str(prompt))
        if 'Plan the implementation.' in prompt:
            content=json.dumps({'Preserved_Func':'addition','Patch_Scope':'implement add','Avoidance_List':[],
                'Security_Actions':[],'Verification_Plan':[]})
        elif 'Generate complete runnable Python code;' in prompt:
            content='def add(a, b):\n    return a + b'
        else:
            content=json.dumps({'vulnerability_hypothesis':['No unsafe operations'],
                               'functional_invariants':['Return the sum']})
        return {'choices':[{'message':{'content':content},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}}
    task={'index':1,'CWE_ID':'20','task_description':{'function_name':'add','description':'Add a and b'}}
    evidence={'functional':{'status':'pass'},'security':{'status':'pass'}}
    with patch('methods.sct_trajectory.retriever.HskTreeRetriever',side_effect=AssertionError('no cards')),patch(
            'methods.sct_trajectory.closed_loop.validate_and_state',return_value=(evidence,'A')):
        row=runner.run_one('PLT',task,'P3',request,{'none':[]})
    assert len(seen)==3 and len(row['attempts'])==1
    assert row['attempts'][0]['joint']
    assert not row['attempts'][0]['generation']['cards']


def test_p3_main_does_not_load_memory_or_construct_embeddings(tmp_path,monkeypatch):
    root=tmp_path
    names=['context_pipeline','agent_pipeline','retriever','semantic_retrieval','closed_loop',
           'run_closed_loop','run_plus_frozen_comparison']
    for name in names:
        p=root/f'methods/sct_trajectory/{name}.py';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('')
    entry=root/'methods/cle_ablation/runner.py';entry.parent.mkdir(parents=True);entry.write_text('')
    data=root/'data/external/secodeplt/secodeplt/data.json';data.parent.mkdir(parents=True);data.write_text('[]')
    pools=root/'pools.json';pools.write_text('{}')
    monkeypatch.setattr(runner,'ROOT',root);monkeypatch.setattr(runner,'POOLS',pools)
    monkeypatch.setattr(runner,'__file__',str(entry))
    monkeypatch.setattr(runner,'load_tasks',lambda *a:[('PLT',{'index':1,'CWE_ID':'20'})])
    monkeypatch.setattr(runner,'load_memory',lambda *a:(_ for _ in ()).throw(AssertionError('no memory read')))
    monkeypatch.setattr(runner,'run_one',lambda *a:{'task_id':'1','arm':'P3','subset':'PLT',
        'attempts':[{'measured':True,'joint':True,'functional':True,'security':True}],'usage':{'calls':0}})
    with patch('methods.sct_trajectory.run_closed_loop._requester',return_value=None),patch(
         'methods.sct_trajectory.semantic_retrieval.EmbeddingClient',side_effect=AssertionError('no embedding')):
        monkeypatch.setattr('sys.argv',['test','--dataset','PLT','--arms','P3','--out',str(root/'translation_work/out')])
        runner._main()
    metadata=json.loads((root/'translation_work/out/run_metadata.json').read_text())
    assert metadata['memory_sha256']=={} and metadata['status']=='completed'


def test_first_two_gate_passes_failed_joint_when_workflow_is_complete(tmp_path):
    gate=FirstTwoGate(['1','2'],tmp_path/'gate.json')
    def native(subset,task,*a,**k):
        return {'task_id':str(task['index']),'attempts':[{'code':'def f(): return 0',
            'validation':{'state':'D'},'joint':False,'retrieval_trace':None,
            'generation':{'workflow_completed':True,'cards':[],
                'stages':[{'stage':'generation','status':'completed'}]}}]}
    run=gate.wrap(native)
    run('PLT',{'index':1});assert not gate.ready.is_set()
    run('PLT',{'index':2});assert gate.ready.is_set()
    assert json.loads((tmp_path/'gate.json').read_text())['passed']
