"""候选池指标、人工门和P7查询扩展的针对性回归。"""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from methods.cle_ablation import retrieval_q_study as study
from methods.cle_ablation.retrieval_q_metrics import metrics, retrieval_gate, paired_f1_interval


def test_confusion_counts_and_four_metrics():
    m=metrics({'t':['a','b','c','d','e']},{'t':['a','c']},
              {'a':'direct','b':'direct','c':'conflict','d':'irrelevant','e':'conditional'}, {'t':['a','c']})
    assert {k:m['counts'][k] for k in ('TP','FP','FN','TN')}=={'TP':1,'FP':1,'FN':1,'TN':2}
    assert m['accuracy']==.6
    assert m['precision']==m['recall']==m['f1']==.5
    assert m['candidate_recall']==.5
    assert m['full_library_recall'] is None


@pytest.mark.parametrize('label', [None,'insufficient'])
def test_unknown_is_not_negative(label):
    m=metrics({'t':['p']},{'t':[]},{'p':label})
    assert not m['complete']
    assert m['accuracy'] is None
    assert m['missing_pairs']==['p']


def test_empty_prediction_still_has_false_negative():
    m=metrics({'t':['p','n']},{'t':[]},{'p':'direct','n':'irrelevant'})
    assert m['counts']['FN']==1
    assert m['precision'] is None
    assert m['recall']==m['f1']==0


def test_no_positive_or_prediction_is_undefined_not_perfect_f1():
    m=metrics({'t':['n']},{'t':[]},{'n':'irrelevant'})
    assert m['accuracy']==1
    assert m['f1'] is None
    assert m['f1_reason']=='zero_denominator'


def test_duplicate_pairs_and_outside_prediction_rejected():
    with pytest.raises(ValueError,match='duplicate_pair'):
        metrics({'t':['p','p']},{'t':[]},{'p':'direct'})
    with pytest.raises(ValueError,match='outside'):
        metrics({'t':['p']},{'t':['x']},{'p':'direct'})


def test_common_universe_changes_fn_not_denominator():
    labels={'a':'direct','b':'direct','c':'irrelevant'}
    left=metrics({'t':list(labels)},{'t':['a']},labels)
    right=metrics({'t':list(labels)},{'t':['a','b']},labels)
    assert sum(left['counts'][k] for k in ('TP','FP','FN','TN'))==3
    assert sum(right['counts'][k] for k in ('TP','FP','FN','TN'))==3
    assert retrieval_gate(right,left)


def test_high_accuracy_alone_does_not_pass_gate():
    labels={'p':'direct',**{str(i):'irrelevant' for i in range(99)}}
    empty=metrics({'t':list(labels)},{'t':[]},labels)
    selected=metrics({'t':list(labels)},{'t':['p']},labels)
    assert empty['accuracy']==.99
    assert not retrieval_gate(empty,selected)


def test_bootstrap_is_paired_by_task():
    interval=paired_f1_interval({'t':['p']},{'t':['p']},{'t':['p']},{'p':'direct'},repeats=20)
    assert interval['ci95']==[0,0]


def test_original_query_does_not_expose_answers_or_task_id():
    row={'index':1,'CWE_ID':'79','task_description':{'description':'escape','context':'template'},
         'ground_truth':{'patched_code':'ANSWER'},'unittest':{'setup':'HIDDEN'}}
    from methods.sct_trajectory.semantic_retrieval import query_embedding_text
    text=query_embedding_text(study.query_for(row,{'functional_invariants':['ok']},'original'))
    assert all(s not in text for s in ('ANSWER','HIDDEN','task_id','threat_analysis'))


def test_combined_query_preserves_full_public_contract():
    row={'index':1,'CWE_ID':'79','task_description':{'function_name':'f','arguments':'x: str','return':'str'}}
    q=study.query_for(row,{'functional_invariants':['ok']},'combined')
    assert q['return']=='str' and q['arguments']=='x: str'
    assert q['current_code']=='' and q['failure_evidence']=={}


def test_arm_dedup_and_fixed_shuffle():
    specs=study.arm_specs({'setting':'R0','query_mode':'combined','delta':.7},{'delta':.7})
    assert set(specs)=={'B','C','D'}
    assert specs['B']['lambda_q']==0 and specs['C']['lambda_q']==.5 and specs['D']['shuffle']


def test_human_gate_prevents_client_creation(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'verify',lambda _: {'parameters':{}})
    def forbidden(*args,**kwargs):raise AssertionError('paid client must not be created')
    monkeypatch.setattr(study,'clients',forbidden)
    with pytest.raises(ValueError,match='human_gate'):
        study.run_phase(tmp_path,'development')


def test_false_prepare_gate_prevents_paid_retrieval(tmp_path,monkeypatch):
    study.write(tmp_path/'run_metadata.json',{'source_files':{}})
    study.write(tmp_path/'manifest.json',{'prepared':False})
    with pytest.raises(ValueError,match='qualification_failed'):
        study.retrieve(tmp_path,'all')


def test_ai_labels_cannot_lock_setting(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'verify',lambda _: {'parameters':{'delta':.7}})
    monkeypatch.setattr(study,'inputs',lambda: ([SimpleNamespace(invariant_id='c',q_value=0)],{},{}))
    study.write(tmp_path/'manifest.json',{'calibration':['1'],'development':['2']})
    trace={'scores':[{'id':'c','cosine':.8}]}
    for task,phase in [('1','calibration'),('2','development')]:
        study.append(tmp_path/'retrieval.jsonl',{'task_id':task,'phase':phase,'pair_ids':[task],
            'card_to_pair':{'c':task},'traces':{'combined':trace,'original':trace}})
        study.append(tmp_path/'model_labels.jsonl',{'pair_id':task,'label':'direct'})
    study.summarize(tmp_path)
    assert not study.read(tmp_path/'gate_B.json')['passed']
    assert not (tmp_path/'selection.json').exists()


def test_identical_settings_remain_R0_after_human_calibration(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'verify',lambda _: {'parameters':{'delta':.7}})
    monkeypatch.setattr(study,'inputs',lambda: ([SimpleNamespace(invariant_id='c',q_value=0)],{},{}))
    study.write(tmp_path/'manifest.json',{'calibration':['1'],'development':['2']})
    trace={'scores':[{'id':'c','cosine':.8}]}
    for task,phase in [('1','calibration'),('2','development')]:
        study.append(tmp_path/'retrieval.jsonl',{'task_id':task,'phase':phase,'pair_ids':[task],
            'card_to_pair':{'c':task},'traces':{'combined':trace,'original':trace}})
    study.write(tmp_path/'human_labels.json',[{'pair_id':'1','label':'direct'},{'pair_id':'2','label':'direct'}])
    study.summarize(tmp_path)
    assert study.read(tmp_path/'gate_B.json')['passed']
    assert study.read(tmp_path/'selection.json')['setting']=='R0'


def test_exact_pair_pool_human_review_required(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'verify',lambda _: {})
    study.append(tmp_path/'pairs.jsonl',{'pair_id':'p'})
    source=tmp_path/'review.csv'
    study.csv_write(source,[{'pair_id':'p','human_label':'direct','task_evidence':'task',
        'card_evidence':'card','reason':'correct','reviewer':'','confirmed_at':''}])
    with pytest.raises(ValueError,match='incomplete'):
        study.import_review(tmp_path,source)
    assert not (tmp_path/'human_labels.json').exists()


def test_reference_pass_does_not_hide_unpublished_binding(monkeypatch):
    from methods.sct_trajectory import closed_loop
    monkeypatch.setattr(closed_loop,'validate_and_state',lambda *a,**k: (
        {'functional':{'status':'pass'},'security':{'status':'pass'}},'A'))
    task={'index':1015,'task_description':{'context':'USERS is available'},
          'ground_truth':{'code_before':'def f():\n','patched_code':' return USER_DETAILS\n','code_after':''},
          'unittest':{'setup':'USER_DETAILS = {}'}}
    result=study.reference_check(task)
    assert result['state']=='A' and not result['passed']
    assert result['undeclared_setup_bindings']==['USER_DETAILS']


def test_native_runner_original_mode_only_changes_retrieval(monkeypatch):
    from methods.cle_ablation import runner
    from methods.sct_trajectory import retriever,context_pipeline,closed_loop
    queries=[]
    monkeypatch.setattr(retriever.HskTreeRetriever,'search',lambda self,q,**k:queries.append(q) or [])
    def generate(contract,cards,**kwargs):
        kwargs['cards_provider']({**contract,'threat_analysis':{'x':1},'current_code':'draft','failure_evidence':{'state':'B'}})
        return {'code':'def f(): return 1','workflow_completed':True,'error_type':None}
    monkeypatch.setattr(context_pipeline,'run_context_pipeline',generate)
    monkeypatch.setattr(closed_loop,'validate_and_state',lambda *a,**k:(
        {'functional':{'status':'pass'},'security':{'status':'pass'}},'A'))
    task={'index':1,'CWE_ID':'79','task_description':{'function_name':'f','description':'public'}}
    row=runner.run_one('PLT',task,'P7',lambda p:{},{'full':[]},
                       initial_analysis={'functional_invariants':['ok']},retrieval_query_mode='original')
    assert 'threat_analysis' not in queries[0]
    assert queries[0]['current_code']=='draft'
    assert queries[0]['failure_evidence']=={'state':'B'}
    assert row['attempts'][0]['joint'] and len(row['attempts'])==1


def test_p7_technical_error_stops_before_next_arm_or_task(tmp_path,monkeypatch):
    config={'delta':.7}
    monkeypatch.setattr(study,'verify',lambda _: {'parameters':config})
    study.write(tmp_path/'gate_B.json',{'passed':True})
    study.write(tmp_path/'selection.json',{'setting':'R0','query_mode':'combined','delta':.7})
    study.write(tmp_path/'manifest.json',{'development':['1','2'],'parameters':config})
    for i in ('1','2'):
        study.append(tmp_path/'contexts.jsonl',{'task_id':i,'analysis':{'functional_invariants':['ok']}})
        study.append(tmp_path/'retrieval.jsonl',{'task_id':i,'traces':{'combined':{'query_hash':'q','scores':[]}}})
    class Node:
        invariant_id='card';q_value=0;q_visits=0;cwe='79'
        def to_dict(self):return {'id':'card','q':self.q_value,'visits':self.q_visits}
    node=Node()
    by_id={i:{'index':int(i),'family_id':i,'CWE_ID':'79'} for i in ('1','2')}
    monkeypatch.setattr(study,'inputs',lambda:([node],by_id,{}))
    class Request:
        def snapshot(self):return {k:0 for k in ('calls','failed_calls','prompt_tokens','completion_tokens','total_tokens')}
    monkeypatch.setattr(study,'clients',lambda c:(Request(),SimpleNamespace(usage={})))
    called=[]
    def broken(subset,task,*args,**kwargs):
        called.append(task['index'])
        return {'task_id':str(task['index']),'attempts':[{'attempt':0,'code':'x','measured':True,
            'functional':False,'security':False,'joint':False,'generation':{'error_type':'JSONDecodeError','workflow_completed':False},
            'retrieval_trace':{'query_hash':'q','scores':[]}}],
            'usage':{k:0 for k in ('calls','failed_calls','prompt_tokens','completion_tokens','total_tokens')}}
    monkeypatch.setattr(study,'run_one',broken)
    monkeypatch.setattr(study,'development_gate',lambda _: {})
    study.run_phase(tmp_path,'development')
    assert called==[1]
    check=study.read(tmp_path/'development/format_check.json')
    assert not check['complete'] and check['errors']
    assert not (tmp_path/'confirmation_lock.json').exists()


def test_no_development_gain_does_not_open_confirmation(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'verify',lambda _: {'parameters':{'delta':.7}})
    study.write(tmp_path/'gate_B.json',{'passed':True})
    study.write(tmp_path/'selection.json',{'setting':'R0','query_mode':'combined','delta':.7})
    study.write(tmp_path/'manifest.json',{'confirmation':['1'],'parameters':{'delta':.7}})
    monkeypatch.setattr(study,'development_gate',lambda _: {'q_passed':False,'retrieval_passed':False})
    with pytest.raises(ValueError,match='no_confirmation'):
        study.run_phase(tmp_path,'confirmation')
    assert not (tmp_path/'confirmation_lock.json').exists()


def test_public_override_copies_only_context_and_preserves_source():
    source={'102':{'task_description':{'context':'original','arguments':'x: str'},
                   'ground_truth':{'patched_code':'answer'},'unittest':{'setup':'hidden'}}}
    before=copy.deepcopy(source)
    changed=study.apply_public_overrides(source,[{'task_id':'102','original_context':'original',
                                                 'append_context':'supplied validator interface'}])
    assert source==before
    assert changed['102']['task_description']['context']=='original\nsupplied validator interface'
    assert changed['102']['ground_truth']==before['102']['ground_truth']
    assert changed['102']['unittest']==before['102']['unittest']
    assert changed['102']['task_description']['arguments']=='x: str'


def test_public_override_rejects_changed_original_context():
    with pytest.raises(ValueError,match='original_context_changed'):
        study.apply_public_overrides({'102':{'task_description':{'context':'different'}}},
            [{'task_id':'102','original_context':'expected','append_context':'extra'}])


def test_real_overlays_disclose_interfaces_without_patient_or_test_constants():
    root=Path(__file__).resolve().parents[1]
    raw={str(x['index']):x for x in json.loads((root/'data/external/secodeplt/secodeplt/data.json').read_text(encoding='utf-8'))}
    overlays=study.read(root/'configs/cle_retrieval_q_public_contract_20261017/public_contract_overrides.json')
    subset={i:raw[i] for i in ('102','136')}
    amended=study.apply_public_overrides(subset,overlays)
    visible=json.dumps({i:study.plt_contract(x) for i,x in amended.items()})
    assert 'valid_key_pattern' in visible and 'patients' in visible
    assert all(s not in visible for s in ('P001','John Doe','Hypertension','testcases','canonicalized_key','ProtectedPatient'))
    assert '^[a-zA-Z0-9_%]+$' not in visible
    assert subset['136']['task_description']['context']==raw['136']['task_description']['context']


def test_real_amended_reference_preflight_passes_both():
    root=Path(__file__).resolve().parents[1]
    raw={str(x['index']):x for x in json.loads((root/'data/external/secodeplt/secodeplt/data.json').read_text(encoding='utf-8'))}
    overlays=study.read(root/'configs/cle_retrieval_q_public_contract_20261017/public_contract_overrides.json')
    amended=study.apply_public_overrides({i:raw[i] for i in ('102','136')},overlays)
    for task in amended.values():
        result=study.reference_check(task)
        assert result['passed'] and result['undeclared_setup_bindings']==[]
